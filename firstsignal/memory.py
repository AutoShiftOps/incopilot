"""Incident memory: remember what each incident looked like, and recognize it next time.

Only the shape of an incident is stored: which patterns fired, in what order, how often,
on which target, plus a note you write. No log lines are kept.
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import _compat
from .analyzer import Analysis

SAME_INCIDENT_WINDOW = timedelta(minutes=60)
MATCH_THRESHOLD = 0.6
_FIRST_WEIGHT = 0.2


@dataclass
class Incident:
    """One remembered incident."""

    id: str
    recorded_at: str
    last_seen_at: str
    target: str
    source: str
    severity: str
    keys: list[str]
    first: str | None
    counts: dict[str, int] = field(default_factory=dict)
    runs: int = 1
    note: str = ""


@dataclass
class Match:
    """A past incident that resembles the current one."""

    incident: Incident
    similarity: float
    days_ago: int


def default_path() -> Path:
    """Where history lives: $FIRSTSIGNAL_HISTORY, or ~/.firstsignal/history.jsonl.

    History written under the old name (~/.incopilot) keeps being used until a new file exists.
    """
    env = _compat.getenv("HISTORY")
    if env:
        return Path(env)
    return _compat.prefer_existing(Path.home() / ".firstsignal" / "history.jsonl",
                                   Path.home() / f".{_compat.OLD_NAME}" / "history.jsonl")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def from_analysis(analysis: Analysis, target: str, source: str, now: datetime | None = None) -> Incident:
    """Reduce an analysis to its fingerprint."""
    now = now or _now()
    keys = sorted(analysis.findings)
    stamp = now.isoformat(timespec="seconds")
    return Incident(
        id=secrets.token_hex(4), recorded_at=stamp, last_seen_at=stamp, target=target, source=source,
        severity=analysis.severity, keys=keys, first=analysis.order[0] if analysis.order else None,
        counts={k: f.count for k, f in analysis.findings.items()},
    )


def similarity(a: Incident, b: Incident) -> float:
    """0..1. Mostly overlap of the patterns that fired, plus a bonus when the same one came first."""
    sa, sb = set(a.keys), set(b.keys)
    if not sa or not sb:
        return 0.0
    jaccard = len(sa & sb) / len(sa | sb)
    same_first = a.first is not None and a.first == b.first
    return round(jaccard * (1 - _FIRST_WEIGHT) + (_FIRST_WEIGHT if same_first else 0.0), 3)


def load(path: Path) -> list[Incident]:
    """Read history. Unreadable lines are skipped, never fatal."""
    out: list[Incident] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            out.append(Incident(**json.loads(line)))
        except (ValueError, TypeError):
            continue
    return out


def save(path: Path, incidents: list[Incident]) -> None:
    """Write history, private to the current user."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for inc in incidents:
            fh.write(json.dumps(asdict(inc), ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _same_incident(old: Incident, new: Incident) -> bool:
    """A re-run during the same incident: same target, same patterns, within the window."""
    return (old.target == new.target and old.keys == new.keys
            and _parse(new.recorded_at) - _parse(old.last_seen_at) <= SAME_INCIDENT_WINDOW)


def remember(path: Path, current: Incident, limit: int = 3) -> tuple[Incident, list[Match]]:
    """Find similar past incidents, then record this one.

    Re-running during the same incident updates the existing record instead of adding one,
    and that record is never reported as a past match.
    """
    history = load(path)
    ongoing = next((h for h in reversed(history) if _same_incident(h, current)), None)
    matches = []
    for past in history:
        if past is ongoing:
            continue
        score = similarity(current, past)
        if score >= MATCH_THRESHOLD:
            days = max(0, (_parse(current.recorded_at) - _parse(past.last_seen_at)).days)
            matches.append(Match(past, score, days))
    matches.sort(key=lambda m: (-m.similarity, m.days_ago))
    if ongoing is not None:
        ongoing.last_seen_at = current.recorded_at
        ongoing.runs += 1
        ongoing.counts, ongoing.severity = current.counts, current.severity
        recorded = ongoing
    else:
        while any(h.id == current.id for h in history):
            current.id = secrets.token_hex(4)
        history.append(current)
        recorded = current
    save(path, history)
    return recorded, matches[:limit]


def find_similar(path: Path, incident_id: str, limit: int = 3) -> list[Match]:
    """Past incidents similar to the stored incident with this id."""
    history = load(path)
    me = next((h for h in history if h.id == incident_id), None)
    if me is None:
        return []
    out = []
    for past in history:
        if past.id == me.id:
            continue
        score = similarity(me, past)
        if score >= MATCH_THRESHOLD:
            out.append(Match(past, score, max(0, (_parse(me.last_seen_at) - _parse(past.last_seen_at)).days)))
    out.sort(key=lambda m: (-m.similarity, m.days_ago))
    return out[:limit]


def upsert(path: Path, incident: Incident, limit: int = 3) -> list[Match]:
    """Create or replace one incident by id (used by watch) and return similar past incidents.

    A note already attached to the stored record is kept.
    """
    history = load(path)
    matches = []
    for past in history:
        if past.id == incident.id:
            continue
        score = similarity(incident, past)
        if score >= MATCH_THRESHOLD:
            days = max(0, (_parse(incident.last_seen_at) - _parse(past.last_seen_at)).days)
            matches.append(Match(past, score, days))
    matches.sort(key=lambda m: (-m.similarity, m.days_ago))
    for i, past in enumerate(history):
        if past.id == incident.id:
            incident.note = past.note
            history[i] = incident
            break
    else:
        history.append(incident)
    save(path, history)
    return matches[:limit]


def set_note(path: Path, incident_id: str, note: str) -> Incident | None:
    """Attach what fixed it. Returns the incident, or None if the id is unknown."""
    history = load(path)
    hit = next((h for h in history if h.id == incident_id), None)
    if hit is None:
        return None
    hit.note = note.strip()
    save(path, history)
    return hit


def forget(path: Path, incident_id: str) -> bool:
    """Remove one incident. Returns False if the id is unknown."""
    history = load(path)
    kept = [h for h in history if h.id != incident_id]
    if len(kept) == len(history):
        return False
    save(path, kept)
    return True


def matches_as_dicts(matches: list[Match]) -> list[dict]:
    """Shape matches for the JSON report."""
    return [
        {"id": m.incident.id, "last_seen_at": m.incident.last_seen_at, "days_ago": m.days_ago,
         "target": m.incident.target, "severity": m.incident.severity, "similarity": m.similarity,
         "first": m.incident.first, "note": m.incident.note}
        for m in matches
    ]
