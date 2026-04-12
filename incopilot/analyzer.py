import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .config import PATTERNS, NOISE, SIGNAL_MAP


@dataclass
class Finding:
    key: str
    count: int
    examples: List[str] = field(default_factory=list)


def _normalize_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?\b", "<TS>", line)
    line = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "<TS>", line)
    line = re.sub(r"\b[0-9a-f]{8,}\b", "<ID>", line, flags=re.IGNORECASE)
    line = re.sub(r"\b\d{5,}\b", "<N>", line)
    return line


def _is_noise(line: str) -> bool:
    return any(rx.search(line) for rx in NOISE)


def analyze(text: str, max_examples: int = 3) -> Tuple[Dict[str, Finding], List[str]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not _is_noise(ln)]

    matches: Dict[str, List[str]] = defaultdict(list)
    normalized_counts: Counter = Counter()

    for ln in lines:
        normalized_counts[_normalize_line(ln)] += 1
        for key, rx in PATTERNS.items():
            if rx.search(ln):
                matches[key].append(ln)

    findings: Dict[str, Finding] = {
        key: Finding(key=key, count=len(exs), examples=exs[:max_examples])
        for key, exs in matches.items()
    }

    top_lines = [f"{cnt}x {msg}" for msg, cnt in normalized_counts.most_common(10)]
    return findings, top_lines


def map_to_golden_signals(findings: Dict[str, Finding]) -> Dict[str, List[str]]:
    return {
        signal: [k for k in keys if k in findings and findings[k].count > 0]
        for signal, keys in SIGNAL_MAP.items()
        if any(k in findings and findings[k].count > 0 for k in keys)
    }
