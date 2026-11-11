"""Report rendering: Markdown for people, JSON for pipelines."""

from __future__ import annotations

import json
import shlex
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .ai import AIResult
from .analyzer import Analysis

SCHEMA_VERSION = "2"
SAFETY_NOTE = "Read-only. incopilot collects and explains; it never changes the systems it reads."
_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "none": "🟢"}

_HOST_CHECKS = [
    ("Top CPU processes", "ps aux --sort=-%cpu | head -15"),
    ("Memory overview", "free -h"),
    ("Disk usage", "df -h"),
    ("Listening ports", "ss -tuln"),
]


def build_meta(source: str, target: str, since: str) -> dict:
    """Describe the run."""
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "tool_version": __version__,
        "source": source,
        "target": target,
        "since": since,
    }


def safe_next_commands(ctx: dict) -> list[tuple[str, str]]:
    """Read-only commands to run next, filled in with the targets that were analyzed."""
    cmds: list[tuple[str, str]] = []
    if "journal" in ctx:
        unit = shlex.quote(ctx["journal"]["unit"])
        cmds += [
            ("Service status", f"systemctl status {unit} --no-pager"),
            ("Follow service logs", f"journalctl -u {unit} -f"),
        ]
    if "docker" in ctx:
        name = shlex.quote(ctx["docker"]["container"])
        cmds += [
            ("Container state and restart count",
             f"docker inspect --format '{{{{.State.Status}}}} restarts={{{{.RestartCount}}}}' {name}"),
            ("Container resource snapshot", f"docker stats --no-stream {name}"),
        ]
    if "k8s" in ctx:
        k = ctx["k8s"]
        ns = f" -n {shlex.quote(k['namespace'])}" if k.get("namespace") else ""
        if k.get("selector"):
            target = f"-l {shlex.quote(k['selector'])}"
            cmds.append(("Pod status", f"kubectl get pods {target}{ns} -o wide"))
        else:
            target = shlex.quote(k["pod"])
            cmds.append(("Describe target", f"kubectl describe {target if '/' in target else 'pod ' + target}{ns}"))
        cmds += [
            ("Recent events", f"kubectl get events{ns} --sort-by=.lastTimestamp | tail -30"),
            ("Pod resource usage", f"kubectl top pods{ns}"),
        ]
    return cmds + _HOST_CHECKS


def suggest_next_steps(analysis: Analysis) -> list[str]:
    """Advice for each finding, most severe first, without repeats."""
    seen, steps = set(), []
    for f in analysis.findings.values():
        if f.advice and f.advice not in seen:
            seen.add(f.advice)
            steps.append(f.advice)
    if not steps:
        steps.append("No known failure pattern matched. Start with host basics (CPU, memory, disk), "
                     "then read the top repeating lines below.")
    return steps


def _code(text: str) -> str:
    return "`" + text.replace("`", "'").strip() + "`"


def build_report_md(meta: dict, analysis: Analysis, commands, ai: AIResult | None = None) -> str:
    """Render the Markdown report."""
    st = analysis.stats
    out = [
        "# Incident triage report", "",
        f"**Overall severity: {_ICON[analysis.severity]} {analysis.severity.upper()}**", "",
        f"- Generated: {meta['generated_at']} (incopilot {meta['tool_version']})",
        f"- Source: {meta['source']}",
        f"- Target: {meta['target']}",
        f"- Window: {meta['since']}",
        f"- Lines: {st['lines_analyzed']} analyzed, {st['lines_matched']} matched a pattern, "
        f"{st['lines_noise_filtered']} filtered as noise",
    ]
    if st["first_timestamp"]:
        out.append(f"- Log time range: {st['first_timestamp']} to {st['last_timestamp']}")

    out += ["", "## Four Golden Signals", ""]
    if analysis.signals:
        out += ["| Signal | Worst severity | Findings |", "|---|---|---|"]
        for sig, keys in analysis.signals.items():
            worst = analysis.findings[keys[0]].severity
            out.append(f"| {sig} | {_ICON[worst]} {worst} | {', '.join(_code(k) for k in keys)} |")
    else:
        out.append("No golden-signal pattern detected.")

    out += ["", "## Findings", ""]
    if analysis.findings:
        out += ["| Finding | Severity | Count | First seen | Last seen |", "|---|---|---:|---|---|"]
        for f in analysis.findings.values():
            out.append(f"| {f.title} ({_code(f.key)}) | {_ICON[f.severity]} {f.severity} | {f.count} "
                       f"| {f.first_seen or 'n/a'} | {f.last_seen or 'n/a'} |")
    else:
        out.append("No pattern matched.")

    if len(analysis.order) > 1:
        out += ["", "## Order of first appearance", "",
                "Earlier patterns are more likely causes; later ones are often knock-on effects.", ""]
        out += [f"{i}. {analysis.findings[k].title} ({_code(k)})" for i, k in enumerate(analysis.order, 1)]

    out += ["", "## Suggested next steps", ""]
    out += [f"- {s}" for s in suggest_next_steps(analysis)]

    if ai is not None:
        out += ["", "## AI hypothesis (unverified)", ""]
        if ai.text:
            out += [f"_Generated by {ai.provider} / {ai.model} from the redacted summary above. "
                    "Treat it as a lead to check, not a conclusion._", "", ai.text]
        else:
            out.append(f"_Not available: {ai.error}_")

    out += ["", "## Read-only checks to run next", ""]
    out += [f"- **{title}**: {_code(cmd)}" for title, cmd in commands]

    if analysis.top_lines:
        out += ["", "## Top repeating lines (normalized)", ""]
        out += [f"- {n}x {_code(line)}" for n, line in analysis.top_lines]

    if analysis.findings:
        out += ["", "## Examples", ""]
        for f in analysis.findings.values():
            out.append(f"**{f.title}**")
            out += [f"- {_code(ex[:220])}" for ex in f.examples]
            out.append("")

    out += ["---", f"_{SAFETY_NOTE}_", ""]
    return "\n".join(out)


def build_report_json(meta: dict, analysis: Analysis, commands, ai: AIResult | None = None) -> dict:
    """Build the machine-readable report. The shape is versioned by `schema_version`."""
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": meta,
        "severity": analysis.severity,
        "stats": analysis.stats,
        "golden_signals": analysis.signals,
        "order_of_first_appearance": analysis.order,
        "findings": {
            f.key: {
                "title": f.title, "signal": f.signal, "severity": f.severity, "count": f.count,
                "first_seen": f.first_seen, "last_seen": f.last_seen, "examples": f.examples,
            }
            for f in analysis.findings.values()
        },
        "top_repeating_lines": [{"count": n, "line": line} for n, line in analysis.top_lines],
        "suggestions": suggest_next_steps(analysis),
        "safe_next_commands": [{"title": t, "cmd": c} for t, c in commands],
        "ai": None if ai is None else {
            "provider": ai.provider, "model": ai.model, "hypothesis": ai.text, "error": ai.error,
        },
        "safety_note": SAFETY_NOTE,
    }


def write_outputs(out_dir: str, markdown: str, report: dict, html: str | None = None) -> dict[str, str]:
    """Write report.md and report.json (and report.html when given) into out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path, js_path = out / "report.md", out / "report.json"
    md_path.write_text(markdown, encoding="utf-8")
    js_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    paths = {"report_md": str(md_path), "report_json": str(js_path)}
    if html is not None:
        html_path = out / "report.html"
        html_path.write_text(html, encoding="utf-8")
        paths["report_html"] = str(html_path)
    return paths
