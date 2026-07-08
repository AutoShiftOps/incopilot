"""CLI entry point for incopilot incident triage agent."""
import argparse

from rich.console import Console
from rich.table import Table

from . import collectors
from .analyzer import analyze, map_to_golden_signals
from .reporter import suggest_next_steps, write_outputs, build_meta

console = Console()


def _render(findings, signal_hits, top_lines):
    """Render findings and signals to console."""
    if signal_hits:
        console.print("\n[bold green]Golden Signals hit[/bold green] (heuristic):")
        for sig, keys in signal_hits.items():
            console.print(f"  {sig}: {', '.join(keys)}")
    else:
        console.print("\n[dim]Golden Signals: none detected[/dim]")

    if findings:
        t = Table(title="Findings")
        t.add_column("Pattern")
        t.add_column("Count", justify="right")
        for k, f in sorted(findings.items(), key=lambda kv: -kv[1].count):
            t.add_row(k, str(f.count))
        console.print(t)

    console.print("\nTop repeating lines (normalized):")
    for ln in top_lines[:10]:
        console.print(f"  {ln}")


def main():
    """Parse arguments and run incident triage analysis."""
    ap = argparse.ArgumentParser(
        prog="incopilot",
        description=(
            "AI Incident Copilot CLI — collect logs, detect patterns, "
            "suggest safe next steps."
        )
    )
    sub = ap.add_subparsers(dest="source", required=True)

    j = sub.add_parser("journal", help="Collect from systemd journal (journalctl)")
    j.add_argument("--unit", required=True, help="systemd unit name, e.g. nginx")
    j.add_argument(
        "--since",
        default="30 min ago",
        help="e.g. '30 min ago' or '2026-03-01 10:00:00'"
    )

    d = sub.add_parser("docker", help="Collect from docker logs")
    d.add_argument("--container", required=True, help="container name or ID")
    d.add_argument(
        "--since",
        default="1h",
        help="e.g. 1h, 30m, 2026-03-01T10:00:00"
    )

    b = sub.add_parser("bundle", help="Collect from BOTH journalctl and docker logs")
    b.add_argument("--unit", required=True)
    b.add_argument("--since-journal", default="30 min ago")
    b.add_argument("--container", required=True)
    b.add_argument("--since-docker", default="1h")

    f = sub.add_parser("file", help="Analyze a plain log file")
    f.add_argument("--path", required=True)

    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--max-bytes", type=int, default=2_000_000)

    args = ap.parse_args()

    if args.source == "journal":
        text = collectors.from_journal(args.unit, args.since)
        target = args.unit
        since = args.since
    elif args.source == "docker":
        text = collectors.from_docker(args.container, args.since)
        target = args.container
        since = args.since
    elif args.source == "bundle":
        text = collectors.bundle(
            args.unit, args.since_journal, args.container, args.since_docker
        )
        target = f"{args.unit} + {args.container}"
        since = f"journal:{args.since_journal}  docker:{args.since_docker}"
    else:
        text = collectors.from_file(args.path)
        target = args.path
        since = "n/a"

    if len(text.encode("utf-8", errors="ignore")) > args.max_bytes:
        text = text[-args.max_bytes:]

    findings, top_lines = analyze(text)
    signal_hits = map_to_golden_signals(findings)
    suggestions = suggest_next_steps(findings)
    meta = build_meta(args.source, target, since)
    paths = write_outputs(args.out_dir, meta, findings, signal_hits,
                          top_lines, suggestions)

    console.print(
        f"\n[bold]Saved[/bold]: {paths['report_md']}  &  {paths['report_json']}"
    )
    _render(findings, signal_hits, top_lines)


if __name__ == "__main__":
    main()
