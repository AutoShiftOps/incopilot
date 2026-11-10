"""Pattern matching, Four Golden Signal mapping and severity scoring."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .parsing import LEVEL_RANK, TS_RE, parse_line
from .patterns import DEFAULT_NOISE, SEVERITY_RANK, SIGNALS, Pattern
from .redact import Redactor

_SOURCE_MARK = re.compile(r"^=== SOURCE: (.+) ===$")
_NORMALIZERS = [
    (TS_RE, "<TS>"),
    (re.compile(r"\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b"), "<TS>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE), "<UUID>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<IP>"),
    (re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{8,}\b", re.IGNORECASE), "<ID>"),
    (re.compile(r"\b\d+(?:\.\d+)?(ms|s|m|h|kb|mb|gb|%)\b", re.IGNORECASE), r"<N>\1"),
    (re.compile(r"\b\d{4,}\b"), "<N>"),
]


@dataclass
class Finding:
    """All matches of one pattern."""

    key: str
    title: str
    signal: str
    severity: str
    advice: str
    count: int = 0
    first_index: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    examples: list[str] = field(default_factory=list)


@dataclass
class Analysis:
    """Result of analyzing one log stream."""

    findings: dict[str, Finding]
    signals: dict[str, list[str]]
    order: list[str]
    top_lines: list[tuple[int, str]]
    stats: dict
    severity: str


def normalize_line(line: str) -> str:
    """Collapse the variable parts of a line so repeats group together."""
    line = line.strip()
    for rx, repl in _NORMALIZERS:
        line = rx.sub(repl, line)
    return line


def analyze(
    text: str,
    patterns: list[Pattern],
    noise=None,
    redactor: Redactor | None = None,
    max_examples: int = 3,
    top_n: int = 10,
) -> Analysis:
    """Analyze log text against patterns. Pure function: no I/O, no side effects."""
    noise = DEFAULT_NOISE if noise is None else noise
    redactor = redactor or Redactor()
    findings: dict[str, Finding] = {}
    repeats: Counter = Counter()
    levels: Counter = Counter()
    sources: list[str] = []
    total = filtered = matched_lines = structured = 0
    first_ts = last_ts = None

    for raw in text.splitlines():
        if not raw.strip():
            continue
        mark = _SOURCE_MARK.match(raw.strip())
        if mark:
            sources.append(mark.group(1))
            continue
        total += 1
        ev = parse_line(raw, total)
        # health checks are noise unless they are themselves reporting a failure
        if LEVEL_RANK[ev.level] < LEVEL_RANK["error"] and any(rx.search(ev.raw) for rx in noise):
            filtered += 1
            continue
        levels[ev.level] += 1
        structured += ev.structured
        if ev.timestamp:
            first_ts = first_ts or ev.timestamp
            last_ts = ev.timestamp
        if ev.level != "debug":
            hit = False
            for pat in patterns:
                if not pat.regex.search(ev.text):
                    continue
                hit = True
                f = findings.get(pat.key)
                if f is None:
                    f = findings[pat.key] = Finding(
                        pat.key, pat.title, pat.signal, pat.severity, pat.advice,
                        first_index=ev.index, first_seen=ev.timestamp,
                    )
                f.count += 1
                f.last_seen = ev.timestamp or f.last_seen
                if len(f.examples) < max_examples:
                    f.examples.append(redactor(ev.raw)[:300])
            matched_lines += hit
            if hit or LEVEL_RANK[ev.level] >= LEVEL_RANK["unknown"]:
                repeats[normalize_line(redactor(ev.text))[:240]] += 1

    order = sorted(findings, key=lambda k: findings[k].first_index)
    ranked = sorted(findings.values(), key=lambda f: (-SEVERITY_RANK[f.severity], -f.count))
    signals = {
        sig: [f.key for f in ranked if f.signal == sig]
        for sig in SIGNALS
        if any(f.signal == sig for f in ranked)
    }
    severity = ranked[0].severity if ranked else "none"
    stats = {
        "lines_total": total,
        "lines_noise_filtered": filtered,
        "lines_analyzed": total - filtered,
        "lines_matched": matched_lines,
        "lines_structured": structured,
        "levels": dict(levels),
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "sources": sources,
    }
    return Analysis(
        findings={f.key: f for f in ranked},
        signals=signals,
        order=order,
        top_lines=[(n, msg) for msg, n in repeats.most_common(top_n)],
        stats=stats,
        severity=severity,
    )
