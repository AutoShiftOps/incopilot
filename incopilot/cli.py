"""Command-line interface for incopilot."""

from __future__ import annotations

import argparse
import json
import re
import sys

from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import __version__, ai, collectors, settings
from .analyzer import Analysis, analyze
from .html import render_html
from .patterns import PACKS, SEVERITY_RANK, resolve_packs
from .redact import Redactor
from .reporter import build_meta, build_report_json, build_report_md, safe_next_commands, write_outputs

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
    g.add_argument("--config", help="path to incopilot.toml (default: ./incopilot.toml if present)")
    g.add_argument("--max-bytes", type=int, default=collectors.DEFAULT_MAX_BYTES,
                   help="analyze only the last N bytes of input (default: 5000000)")
    g.add_argument("--timeout", type=int, default=collectors.DEFAULT_TIMEOUT,
                   help="seconds to wait for journalctl, docker or kubectl (default: 60)")
    g = common.add_argument_group("privacy")
    g.add_argument("--no-redact", action="store_true", help="do not mask secrets in reports")
    g.add_argument("--redact-ips", action="store_true", help="also mask IPv4 addresses")
    g = common.add_argument_group("AI (optional, bring your own key)")
    g.add_argument("--ai", action="store_true",
                   help="add a root-cause hypothesis from an LLM, built from the redacted summary only")
    g.add_argument("--ai-provider", choices=ai.PROVIDERS, help="default: detected from environment")
    g.add_argument("--ai-model", help="model name (required for openai and ollama)")

    ap = argparse.ArgumentParser(
        prog="incopilot",
        description="Read-only incident triage: collect logs, map them to the Four Golden Signals, "
                    "and write a report with safe next steps.",
    )
    ap.add_argument("--version", action="version", version=f"incopilot {__version__}")
    sub = ap.add_subparsers(dest="source", required=True, metavar="SOURCE")

    j = sub.add_parser("journal", parents=[common], help="systemd journal (journalctl)")
    j.add_argument("--unit", required=True, help="systemd unit, e.g. nginx")
    j.add_argument("--since", default="30 min ago", help="e.g. '30 min ago' or '2026-03-01 10:00:00'")

    d = sub.add_parser("docker", parents=[common], help="docker container logs")
    d.add_argument("--container", required=True, help="container name or ID")
    d.add_argument("--since", default="1h", help="e.g. 1h, 30m, 2026-03-01T10:00:00")

    k = sub.add_parser("k8s", parents=[common], help="Kubernetes pod logs (kubectl)")
    kt = k.add_mutually_exclusive_group(required=True)
    kt.add_argument("--pod", help="pod name, or a reference such as deploy/api")
    kt.add_argument("-l", "--selector", help="label selector, e.g. app=api")
    k.add_argument("-n", "--namespace")
    k.add_argument("-c", "--container", help="default: all containers")
    k.add_argument("--since", default="30m", help="e.g. 30m, 2h")
    k.add_argument("--previous", action="store_true", help="logs of the previous (crashed) container")
    k.add_argument("--context", help="kubeconfig context")
    k.add_argument("--tail", type=int, default=5000, help="max lines per container (default: 5000)")

    f = sub.add_parser("file", parents=[common], help="a log file, .gz file, or '-' for stdin")
    f.add_argument("--path", required=True)

    b = sub.add_parser("bundle", parents=[common], help="several sources analyzed as one timeline")
    b.add_argument("--unit", help="systemd unit")
    b.add_argument("--since-journal", default="30 min ago")
    b.add_argument("--container", help="docker container")
    b.add_argument("--since-docker", default="1h")
    b.add_argument("--pod", help="Kubernetes pod or deploy/name")
    b.add_argument("-n", "--namespace")
    b.add_argument("--since-k8s", default="30m")
    b.add_argument("--path", action="append", default=[], help="log file (repeatable)")
    return ap


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


def run(argv=None) -> int:
    """Run the CLI and return an exit code."""
    args = build_parser().parse_args(argv)
    err = Console(stderr=True)
    try:
        cfg = settings.load(args.config)
        pack_names = [p.strip() for p in args.packs.split(",")] if args.packs else cfg.packs
        patterns = resolve_packs(pack_names) + cfg.patterns
        text, target, since, ctx = collect(args)
    except (collectors.CollectorError, settings.SettingsError, ValueError) as exc:
        err.print(Text(f"incopilot: {exc}", style="red"))
        return EXIT_ERROR

    text, truncated = collectors.tail_bytes(text, args.max_bytes)
    redactor = Redactor(enabled=not args.no_redact, redact_ips=args.redact_ips, extra=cfg.redact_extra)
    analysis = analyze(text, patterns, noise=cfg.noise, redactor=redactor)
    analysis.stats["truncated"] = truncated

    meta = build_meta(args.source, target, since)
    ai_result = None
    if args.ai:
        if args.no_redact:
            err.print(Text("incopilot: --ai is ignored with --no-redact (unredacted logs are never sent)",
                           style="yellow"))
        else:
            ai_result = ai.hypothesize(analysis, meta, args.ai_provider or cfg.ai_provider,
                                       args.ai_model or cfg.ai_model, timeout=args.timeout)

    commands = safe_next_commands(ctx)
    report = build_report_json(meta, analysis, commands, ai_result)
    paths = None
    if not args.no_write:
        try:
            paths = write_outputs(args.out_dir, build_report_md(meta, analysis, commands, ai_result), report,
                                  render_html(report) if args.html else None)
        except OSError as exc:
            err.print(Text(f"incopilot: cannot write reports: {exc}", style="red"))
            return EXIT_ERROR

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif not args.quiet:
        render(Console(), analysis, ai_result, paths)

    if args.fail_on and SEVERITY_RANK[analysis.severity] >= SEVERITY_RANK[args.fail_on]:
        return EXIT_THRESHOLD
    return EXIT_OK


def main() -> None:
    """Console-script entry point."""
    sys.exit(run())


if __name__ == "__main__":
    main()
