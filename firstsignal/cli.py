"""Command-line interface for firstsignal."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import __version__, ai, collectors, memory, settings
from .analyzer import Analysis, analyze
from .html import render_html
from .patterns import PACKS, SEVERITY_RANK, resolve_packs
from .redact import Redactor
from .reporter import build_meta, build_report_json, build_report_md, safe_next_commands, write_outputs
from .watch import MAX_FAILURES, FileFollower, Watcher

EXIT_OK, EXIT_ERROR, EXIT_THRESHOLD = 0, 1, 3
TIMELINE_ROWS = 10
_CLOCK = re.compile(r"\d{2}:\d{2}:\d{2}")


def _clock(ts: str | None) -> str:
    """Show the time of day from a timestamp, or the raw value if it has none."""
    if not ts:
        return "n/a"
    m = _CLOCK.search(ts)
    return m.group(0) if m else ts


_STYLE = {"critical": "bold red", "high": "red", "medium": "yellow", "low": "cyan", "none": "green"}


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser. Shared options are accepted after any subcommand."""
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group("output")
    g.add_argument("--out-dir", default="out", help="directory for report.md and report.json (default: out)")
    g.add_argument("--no-write", action="store_true", help="do not write report files")
    g.add_argument("--html", action="store_true",
                   help="also write report.html, a self-contained dashboard you can open in a browser")
    g.add_argument("--json", action="store_true", help="print the JSON report to stdout and nothing else")
    g.add_argument("-q", "--quiet", action="store_true", help="no console output")
    g.add_argument("--fail-on", choices=["low", "medium", "high", "critical"],
                   help=f"exit {EXIT_THRESHOLD} if overall severity is at or above this level")
    g = common.add_argument_group("analysis")
    g.add_argument("--packs", default=None,
                   help=f"comma-separated pattern packs: {', '.join(PACKS)}, all (default: core)")
    g.add_argument("--config", help="path to firstsignal.toml (default: ./firstsignal.toml if present)")
    g.add_argument("--max-bytes", type=int, default=collectors.DEFAULT_MAX_BYTES,
                   help="analyze only the last N bytes of input (default: 5000000)")
    g.add_argument("--timeout", type=int, default=collectors.DEFAULT_TIMEOUT,
                   help="seconds to wait for journalctl, docker or kubectl (default: 60)")
    g = common.add_argument_group("incident memory")
    g.add_argument("--no-history", action="store_true", help="do not record this run or look for past matches")
    g.add_argument("--history", metavar="FILE", help="history file (default: ~/.firstsignal/history.jsonl)")
    g = common.add_argument_group("privacy")
    g.add_argument("--no-redact", action="store_true", help="do not mask secrets in reports")
    g.add_argument("--redact-ips", action="store_true", help="also mask IPv4 addresses")
    g = common.add_argument_group("AI (optional, bring your own key)")
    g.add_argument("--ai", action="store_true",
                   help="add a root-cause hypothesis from an LLM, built from the redacted summary only")
    g.add_argument("--ai-provider", choices=ai.PROVIDERS, help="default: detected from environment")
    g.add_argument("--ai-model", help="model name (required for openai and ollama)")

    ap = argparse.ArgumentParser(
        prog="firstsignal",
        description="Read-only incident triage: collect logs, map them to the Four Golden Signals, "
                    "and write a report with safe next steps.",
    )
    ap.add_argument("--version", action="version", version=f"firstsignal {__version__}")
    sub = ap.add_subparsers(dest="source", required=True, metavar="SOURCE")

    _add_sources(sub, [common])

    w = sub.add_parser("watch", help="follow a source and report what changes, until you stop it")
    wopts = argparse.ArgumentParser(add_help=False)
    g = wopts.add_argument_group("watch")
    g.add_argument("--window", type=int, default=5, metavar="MINUTES",
                   help="how much recent log to analyze each time (default: 5)")
    g.add_argument("--interval", type=int, default=15, metavar="SECONDS",
                   help="how often to check (default: 15)")
    g.add_argument("--duration", type=int, default=0, metavar="SECONDS",
                   help="stop after this long (default: run until Ctrl+C)")
    ws = w.add_subparsers(dest="watch_source", required=True, metavar="SOURCE")
    _add_sources(ws, [common, wopts], watch=True)

    b = sub.add_parser("bundle", parents=[common], help="several sources analyzed as one timeline")
    b.add_argument("--unit", help="systemd unit")
    b.add_argument("--since-journal", default="30 min ago")
    b.add_argument("--container", help="docker container")
    b.add_argument("--since-docker", default="1h")
    b.add_argument("--pod", help="Kubernetes pod or deploy/name")
    b.add_argument("-n", "--namespace")
    b.add_argument("--since-k8s", default="30m")
    b.add_argument("--path", action="append", default=[], help="log file (repeatable)")

    h = sub.add_parser("history", help="list remembered incidents, add a note, or forget one")
    h.add_argument("--history", metavar="FILE", help="history file (default: ~/.firstsignal/history.jsonl)")
    hs = h.add_subparsers(dest="history_cmd", required=True, metavar="ACTION")
    hl = hs.add_parser("list", help="show remembered incidents, newest first")
    hl.add_argument("--limit", type=int, default=20)
    hn = hs.add_parser("note", help="record what fixed an incident")
    hn.add_argument("id")
    hn.add_argument("text")
    hf = hs.add_parser("forget", help="remove one incident from history")
    hf.add_argument("id")
    return ap


def _add_sources(sub, parents, watch: bool = False) -> None:
    """Define the single-source subcommands. In watch mode the time range comes from --window."""
    j = sub.add_parser("journal", parents=parents, help="systemd journal (journalctl)")
    j.add_argument("--unit", required=True, help="systemd unit, e.g. nginx")

    d = sub.add_parser("docker", parents=parents, help="docker container logs")
    d.add_argument("--container", required=True, help="container name or ID")

    k = sub.add_parser("k8s", parents=parents, help="Kubernetes pod logs (kubectl)")
    kt = k.add_mutually_exclusive_group(required=True)
    kt.add_argument("--pod", help="pod name, or a reference such as deploy/api")
    kt.add_argument("-l", "--selector", help="label selector, e.g. app=api")
    k.add_argument("-n", "--namespace")
    k.add_argument("-c", "--container", help="default: all containers")
    k.add_argument("--context", help="kubeconfig context")
    k.add_argument("--tail", type=int, default=5000, help="max lines per container (default: 5000)")

    f = sub.add_parser("file", parents=parents,
                       help="a log file" if watch else "a log file, .gz file, or '-' for stdin")
    f.add_argument("--path", required=True)
    if watch:
        f.add_argument("--from-start", action="store_true",
                       help="include what is already in the file (default: only new lines)")
        return
    j.add_argument("--since", default="30 min ago", help="e.g. '30 min ago' or '2026-03-01 10:00:00'")
    d.add_argument("--since", default="1h", help="e.g. 1h, 30m, 2026-03-01T10:00:00")
    k.add_argument("--since", default="30m", help="e.g. 30m, 2h")
    k.add_argument("--previous", action="store_true", help="logs of the previous (crashed) container")


def run_history(args) -> int:
    """Handle `firstsignal history ...`."""
    path = Path(args.history) if args.history else memory.default_path()
    console, err = Console(), Console(stderr=True)
    if args.history_cmd == "list":
        incidents = memory.load(path)[::-1][: max(0, args.limit)]
        if not incidents:
            console.print(Text(f"No incidents remembered yet ({path})."))
            return EXIT_OK
        table = Table(title="Remembered incidents", title_justify="left")
        for col in ("ID", "Last seen", "Target", "Severity", "First to appear", "Note"):
            table.add_column(col)
        for inc in incidents:
            table.add_row(inc.id, inc.last_seen_at[:16].replace("T", " "), Text(inc.target),
                          Text(inc.severity, style=_STYLE.get(inc.severity, "")), inc.first or "n/a", Text(inc.note))
        console.print(table)
        return EXIT_OK
    if args.history_cmd == "note":
        hit = memory.set_note(path, args.id, args.text)
        if hit is None:
            err.print(Text(f"firstsignal: no incident with id {args.id}", style="red"))
            return EXIT_ERROR
        console.print(Text(f"Noted on {hit.id}."))
        return EXIT_OK
    if not memory.forget(path, args.id):
        err.print(Text(f"firstsignal: no incident with id {args.id}", style="red"))
        return EXIT_ERROR
    console.print(Text(f"Forgot {args.id}."))
    return EXIT_OK


def collect(args) -> tuple[str, str, str, dict]:
    """Run the collector(s) for the chosen source. Returns (text, target, window, context)."""
    t = args.timeout
    if args.source == "journal":
        return (collectors.from_journal(args.unit, args.since, t), args.unit, args.since,
                {"journal": {"unit": args.unit}})
    if args.source == "docker":
        return (collectors.from_docker(args.container, args.since, t), args.container, args.since,
                {"docker": {"container": args.container}})
    if args.source == "k8s":
        text = collectors.from_k8s(args.pod, args.selector, args.namespace, args.container, args.since,
                                   args.previous, args.context, args.tail, t)
        target = args.pod or f"-l {args.selector}"
        if args.namespace:
            target = f"{args.namespace}/{target}"
        return text, target, args.since, {
            "k8s": {"pod": args.pod, "selector": args.selector, "namespace": args.namespace}}
    if args.source == "file":
        return collectors.from_file(args.path, args.max_bytes), args.path, "n/a", {}

    parts, targets, windows, ctx = [], [], [], {}
    if args.unit:
        parts.append((f"journalctl {args.unit}", collectors.from_journal(args.unit, args.since_journal, t)))
        targets.append(args.unit)
        windows.append(f"journal: {args.since_journal}")
        ctx["journal"] = {"unit": args.unit}
    if args.container:
        parts.append((f"docker {args.container}", collectors.from_docker(args.container, args.since_docker, t)))
        targets.append(args.container)
        windows.append(f"docker: {args.since_docker}")
        ctx["docker"] = {"container": args.container}
    if args.pod:
        parts.append((f"k8s {args.pod}", collectors.from_k8s(
            pod=args.pod, namespace=args.namespace, since=args.since_k8s, timeout=t)))
        targets.append(args.pod)
        windows.append(f"k8s: {args.since_k8s}")
        ctx["k8s"] = {"pod": args.pod, "selector": None, "namespace": args.namespace}
    for path in args.path:
        parts.append((f"file {path}", collectors.from_file(path, args.max_bytes)))
        targets.append(path)
    if not parts:
        raise collectors.CollectorError("bundle needs at least one of --unit, --container, --pod, --path")
    return collectors.join_sources(parts), " + ".join(targets), ", ".join(windows) or "n/a", ctx


def render_memory(console: Console, recorded, matches) -> None:
    """Print past incidents that look like this one."""
    if matches:
        console.print("\n[bold]Seen before[/bold]")
        for m in matches:
            inc = m.incident
            when = "today" if m.days_ago == 0 else f"{m.days_ago} day{'s' if m.days_ago != 1 else ''} ago"
            pct = round(m.similarity * 100)
            console.print(Text(f"  {inc.id}  {when} on {inc.target}  ({pct}% similar, {inc.severity})"))
            console.print(Text(f"      {'Fix noted: ' + inc.note if inc.note else 'No fix noted.'}"))
    if recorded is not None:
        console.print(Text(f"\nRemembered as {recorded.id}. When it is fixed: "
                           f'firstsignal history note {recorded.id} "what fixed it"'))


def render(console: Console, analysis: Analysis, ai_result, paths) -> None:
    """Print a short summary to the terminal. Log content is printed as plain text, never as markup."""
    sev = analysis.severity
    console.print(Text.assemble("\nOverall severity: ", (sev.upper(), _STYLE[sev])))
    st = analysis.stats
    console.print(f"{st['lines_analyzed']} lines analyzed, {st['lines_matched']} matched, "
                  f"{st['lines_noise_filtered']} filtered as noise", highlight=False)
    if analysis.findings:
        table = Table(title="Findings", title_justify="left")
        for col, kw in (("Finding", {}), ("Signal", {}), ("Severity", {}), ("Count", {"justify": "right"})):
            table.add_column(col, **kw)
        for f in analysis.findings.values():
            table.add_row(Text(f.title), f.signal, Text(f.severity, style=_STYLE[f.severity]), str(f.count))
        console.print(table)
        if analysis.signals:
            line = Text("Golden signals: ")
            for i, (sig, keys) in enumerate(analysis.signals.items()):
                worst = analysis.findings[keys[0]].severity
                line.append(", " if i else "")
                line.append(f"{sig} ")
                line.append(worst, style=_STYLE[worst])
            console.print(line)
        if len(analysis.order) > 1:
            first = analysis.findings[analysis.order[0]]
            timeline = Table(title="Order of first appearance", title_justify="left")
            for col in ("#", "First seen", "Finding", "Signal"):
                timeline.add_column(col)
            for i, key in enumerate(analysis.order[:TIMELINE_ROWS], 1):
                f = analysis.findings[key]
                timeline.add_row(str(i), Text(_clock(f.first_seen)), Text(f.title), f.signal)
            console.print(timeline)
            if len(analysis.order) > TIMELINE_ROWS:
                console.print(f"... and {len(analysis.order) - TIMELINE_ROWS} more in the report", highlight=False)
            console.print(Text(f"First to appear: {first.title}"))
    else:
        console.print("No known failure pattern matched.")
    if ai_result is not None:
        console.print("\n[bold]AI hypothesis (unverified)[/bold]")
        console.print(Text(ai_result.text or f"Not available: {ai_result.error}"))
    if paths:
        console.print(Text("\nSaved: " + ", ".join(paths.values())))


def _print_event(console: Console, ev: dict) -> None:
    """One line per change. Log-derived text is printed as plain text, never as markup."""
    line = Text(f"{ev['at']}  ")
    kind = ev["event"]
    if kind == "new":
        line.append("NEW          ", style="bold")
        line.append(f"{ev['severity']:<9}", style=_STYLE[ev["severity"]])
        line.append(f"{ev['title']} ({ev['signal']}) x{ev['count']}")
    elif kind == "cleared":
        line.append("CLEARED      ", style="green")
        line.append(f"{'':<9}{ev['title']}")
    elif kind == "severity":
        line.append("SEVERITY     ", style="bold")
        line.append(f"{ev['from']} -> ")
        line.append(ev["to"], style=_STYLE[ev["to"]])
    else:
        when = "today" if ev["days_ago"] == 0 else f"{ev['days_ago']} day{'s' if ev['days_ago'] != 1 else ''} ago"
        line.append("SEEN BEFORE  ", style="bold cyan")
        line.append(f"{ev['id']}, {when} on {ev['target']} ({round(ev['similarity'] * 100)}% similar). ")
        line.append(f"Fix noted: {ev['note']}" if ev["note"] else "No fix noted.")
    console.print(line)


def run_watch(args, sleep=time.sleep, clock=time.monotonic) -> int:
    """Handle `firstsignal watch <source> ...`."""
    err, console = Console(stderr=True), Console()
    source = args.watch_source
    window = max(1, args.window)
    interval = max(1, args.interval)
    state = {"target": None, "ctx": {}}
    try:
        cfg = settings.load(args.config)
        pack_names = [p.strip() for p in args.packs.split(",")] if args.packs else cfg.packs
        patterns = resolve_packs(pack_names) + cfg.patterns
        if source == "file":
            if args.path == "-" or args.path.endswith(".gz"):
                raise collectors.CollectorError("watch needs a regular file that is being written to")
            poll = FileFollower(args.path, window * 60, clock, args.from_start).poll
            state["target"] = args.path
        else:
            ns = copy.copy(args)
            ns.source, ns.previous = source, False
            ns.since = f"{window} min ago" if source == "journal" else f"{window}m"

            def collect_once() -> str:
                text, state["target"], _, state["ctx"] = collect(ns)
                return collectors.tail_bytes(text, args.max_bytes)[0]

            pending = [collect_once()]  # fail fast, and learn the target name

            def poll() -> str:
                return pending.pop() if pending else collect_once()
    except (collectors.CollectorError, settings.SettingsError, ValueError) as exc:
        err.print(Text(f"firstsignal: {exc}", style="red"))
        return EXIT_ERROR

    redactor = Redactor(enabled=not args.no_redact, redact_ips=args.redact_ips, extra=cfg.redact_extra)
    history_path = None if args.no_history else (Path(args.history) if args.history else memory.default_path())
    watcher = Watcher(poll, patterns, cfg.noise, redactor, state["target"], source, history_path)
    chatty = not args.json and not args.quiet
    if chatty:
        console.print(Text(f"Watching {state['target']}: last {window} min of logs, checked every {interval}s. "
                           "Ctrl+C to stop."))
    started, failures = clock(), 0
    try:
        while True:
            try:
                events = watcher.tick()
                failures = 0
            except collectors.CollectorError as exc:
                failures += 1
                err.print(Text(f"firstsignal: {exc} ({failures}/{MAX_FAILURES})", style="yellow"))
                if failures >= MAX_FAILURES:
                    err.print(Text("firstsignal: source unavailable, stopping", style="red"))
                    return EXIT_ERROR
                events = []
            for ev in events:
                if args.json:
                    print(json.dumps(ev, ensure_ascii=False), flush=True)
                elif chatty:
                    _print_event(console, ev)
            if args.duration and clock() - started >= args.duration:
                break
            sleep(interval)
    except KeyboardInterrupt:
        pass

    peak = watcher.peak
    if peak is None:
        return EXIT_ERROR
    peak.stats["truncated"] = False
    meta = build_meta(f"watch {source}", state["target"], f"last {window} min, peak of {watcher.ticks} checks")
    ai_result = None
    if args.ai and not args.no_redact and peak.findings:
        ai_result = ai.hypothesize(peak, meta, args.ai_provider or cfg.ai_provider,
                                   args.ai_model or cfg.ai_model, timeout=args.timeout)
    commands = safe_next_commands(state["ctx"])
    seen = []
    if history_path is not None and watcher.started_at:
        seen = memory.matches_as_dicts(memory.find_similar(history_path, watcher.session_id))
    report = build_report_json(meta, peak, commands, ai_result, seen)
    paths = None
    if not args.no_write:
        try:
            paths = write_outputs(args.out_dir, build_report_md(meta, peak, commands, ai_result, seen), report,
                                  render_html(report) if args.html else None)
        except OSError as exc:
            err.print(Text(f"firstsignal: cannot write reports: {exc}", style="red"))
            return EXIT_ERROR
    if chatty:
        console.print(Text(f"\nStopped after {watcher.ticks} checks. Peak severity: {peak.severity}."))
        if paths:
            console.print(Text("Saved: " + ", ".join(paths.values())))
        if watcher.started_at and history_path is not None:
            console.print(Text(f"Remembered as {watcher.session_id}. When it is fixed: "
                               f'firstsignal history note {watcher.session_id} "what fixed it"'))
    if args.fail_on and SEVERITY_RANK[peak.severity] >= SEVERITY_RANK[args.fail_on]:
        return EXIT_THRESHOLD
    return EXIT_OK


def run(argv=None) -> int:
    """Run the CLI and return an exit code."""
    args = build_parser().parse_args(argv)
    if args.source == "history":
        return run_history(args)
    if args.source == "watch":
        return run_watch(args)
    err = Console(stderr=True)
    try:
        cfg = settings.load(args.config)
        pack_names = [p.strip() for p in args.packs.split(",")] if args.packs else cfg.packs
        patterns = resolve_packs(pack_names) + cfg.patterns
        text, target, since, ctx = collect(args)
    except (collectors.CollectorError, settings.SettingsError, ValueError) as exc:
        err.print(Text(f"firstsignal: {exc}", style="red"))
        return EXIT_ERROR

    text, truncated = collectors.tail_bytes(text, args.max_bytes)
    redactor = Redactor(enabled=not args.no_redact, redact_ips=args.redact_ips, extra=cfg.redact_extra)
    analysis = analyze(text, patterns, noise=cfg.noise, redactor=redactor)
    analysis.stats["truncated"] = truncated

    meta = build_meta(args.source, target, since)
    ai_result = None
    if args.ai:
        if args.no_redact:
            err.print(Text("firstsignal: --ai is ignored with --no-redact (unredacted logs are never sent)",
                           style="yellow"))
        else:
            ai_result = ai.hypothesize(analysis, meta, args.ai_provider or cfg.ai_provider,
                                       args.ai_model or cfg.ai_model, timeout=args.timeout)

    recorded, matches = None, []
    if not args.no_history and analysis.findings:
        try:
            recorded, matches = memory.remember(
                Path(args.history) if args.history else memory.default_path(),
                memory.from_analysis(analysis, target, args.source))
        except OSError as exc:
            err.print(Text(f"firstsignal: history not updated: {exc}", style="yellow"))
    seen = memory.matches_as_dicts(matches)

    commands = safe_next_commands(ctx)
    report = build_report_json(meta, analysis, commands, ai_result, seen)
    paths = None
    if not args.no_write:
        try:
            paths = write_outputs(args.out_dir, build_report_md(meta, analysis, commands, ai_result, seen), report,
                                  render_html(report) if args.html else None)
        except OSError as exc:
            err.print(Text(f"firstsignal: cannot write reports: {exc}", style="red"))
            return EXIT_ERROR

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif not args.quiet:
        render(Console(), analysis, ai_result, paths)
        render_memory(Console(), recorded, matches)

    if args.fail_on and SEVERITY_RANK[analysis.severity] >= SEVERITY_RANK[args.fail_on]:
        return EXIT_THRESHOLD
    return EXIT_OK


def main() -> None:
    """Console-script entry point."""
    if os.path.basename(sys.argv[0]).startswith("incopilot"):
        print("note: incopilot is now firstsignal. The incopilot command still works but will be "
              "removed in a future release.", file=sys.stderr)
    sys.exit(run())


if __name__ == "__main__":
    main()
