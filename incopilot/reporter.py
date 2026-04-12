import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .analyzer import Finding
from .config import SAFE_NEXT_COMMANDS


def suggest_next_steps(findings: Dict[str, Finding]) -> List[str]:
    s = []
    if "oom_kill" in findings:
        s.append("Memory pressure (OOM). Check limits and memory growth; look for repeated restarts.")
    if "disk_full" in findings:
        s.append("Disk-full signals. Check df/du; find fastest-growing directory (logs, images, tmp).")
    if "timeout" in findings or "conn_refused" in findings:
        s.append("Timeout/refused connections. Validate upstream health, listeners, DNS, error rate trend.")
    if "http_5xx" in findings:
        s.append("5xx pattern. Correlate with recent deploy/config changes; inspect app + upstream logs.")
    if not s:
        s.append("No strong pattern. Start with baseline host signals (CPU/mem/disk/IO), then narrow by service logs.")
    s.append("Run the safe next-commands checklist below (non-destructive).")
    return s


def build_report_md(meta: dict, findings: Dict[str, Finding], signal_hits: Dict[str, List[str]], top_lines: List[str], suggestions: List[str]) -> str:
    out = [
        "# Incident Copilot Report", "",
        f"- Generated : {meta['generated_at']}",
        f"- Source    : {meta['source']}",
        f"- Target    : {meta['target']}",
        f"- Since     : {meta['since']}", "",
        "## Golden Signals (heuristic)",
    ]
    if signal_hits:
        for sig, keys in signal_hits.items():
            out.append(f"- **{sig}**: {', '.join(keys)}")
    else:
        out.append("- No clear golden-signal pattern detected.")

    out += ["", "## Findings (pattern counts)"]
    if findings:
        for k, f in sorted(findings.items(), key=lambda kv: -kv[1].count):
            out.append(f"- `{k}`: {f.count}")
    else:
        out.append("- No pattern matches.")

    out += ["", "## Top repeating lines (normalized)"]
    out += [f"- {ln}" for ln in top_lines[:10]]

    out += ["", "## Suggested next steps"]
    out += [f"- {s}" for s in suggestions]

    out += ["", "## Safe next-commands checklist (non-destructive)"]
    for title, cmd in SAFE_NEXT_COMMANDS:
        out.append(f"- **{title}**: `{cmd}`")

    out += ["", "## Examples (first 3 per pattern)"]
    for k, f in sorted(findings.items(), key=lambda kv: -kv[1].count):
        if not f.examples:
            continue
        out.append(f"### {k}")
        for ex in f.examples:
            out.append(f"- `{ex.strip()[:220]}`")
        out.append("")

    return "\n".join(out)


def write_outputs(out_dir: str, meta: dict, findings: Dict[str, Finding], signal_hits: Dict[str, List[str]], top_lines: List[str], suggestions: List[str]) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    md_path = out / "report.md"
    js_path = out / "report.json"

    md_path.write_text(build_report_md(meta, findings, signal_hits, top_lines, suggestions), encoding="utf-8")

    js_path.write_text(json.dumps({
        "meta": meta,
        "golden_signals": signal_hits,
        "findings": {k: {"count": v.count, "examples": v.examples} for k, v in findings.items()},
        "top_repeating_lines": top_lines[:10],
        "suggestions": suggestions,
        "safe_next_commands": [{"title": t, "cmd": c} for t, c in SAFE_NEXT_COMMANDS],
        "safety_note": "Suggestions only — no destructive actions",
    }, indent=2), encoding="utf-8")

    return {"report_md": str(md_path), "report_json": str(js_path)}


def build_meta(source: str, target: str, since: str) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source": source,
        "target": target,
        "since": since,
    }
