"""firstsignal watch: follow a source, re-analyze a sliding window, and report only what changes."""

from __future__ import annotations

import os
import secrets
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import memory
from .analyzer import Analysis, analyze
from .collectors import CollectorError
from .patterns import SEVERITY_RANK

MAX_BUFFER_LINES = 50_000
READ_CHUNK = 5_000_000
MAX_PARTIAL = 1_000_000
MAX_FAILURES = 5
QUIET_GAP = timedelta(minutes=60)


class FileFollower:
    """Follow a growing log file and keep the lines that arrived within the window."""

    def __init__(self, path: str, window_seconds: float, clock, from_start: bool = False):
        self.path, self.window, self.clock = path, window_seconds, clock
        self.buf: deque = deque(maxlen=MAX_BUFFER_LINES)
        self.partial = b""
        st = self._stat()
        self.inode = st.st_ino
        self.offset = 0 if from_start else st.st_size

    def _stat(self):
        try:
            return os.stat(self.path)
        except OSError as exc:
            raise CollectorError(f"cannot read {self.path}: {exc.strerror or exc}") from exc

    def poll(self) -> str:
        """Read what was appended since the last poll and return the current window."""
        st = self._stat()
        if st.st_ino != self.inode or st.st_size < self.offset:  # rotated or truncated
            self.inode, self.offset, self.partial = st.st_ino, 0, b""
        try:
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                data = fh.read(READ_CHUNK)
                self.offset = fh.tell()
        except OSError as exc:
            raise CollectorError(f"cannot read {self.path}: {exc.strerror or exc}") from exc
        now = self.clock()
        lines = (self.partial + data).split(b"\n")
        self.partial = lines.pop()
        if len(self.partial) > MAX_PARTIAL:  # a very long line with no newline yet
            lines.append(self.partial)
            self.partial = b""
        for line in lines:
            if line.endswith(b"\r"):  # CRLF line endings (Windows)
                line = line[:-1]
            self.buf.append((now, line.decode("utf-8", errors="replace")))
        while self.buf and now - self.buf[0][0] > self.window:
            self.buf.popleft()
        return "\n".join(line for _, line in self.buf)


def diff(prev: Analysis | None, cur: Analysis) -> list[dict]:
    """Events describing how the findings changed between two windows."""
    before = prev.findings if prev else {}
    events = []
    for key, f in cur.findings.items():
        if key not in before:
            events.append({"event": "new", "key": key, "title": f.title, "severity": f.severity,
                           "signal": f.signal, "count": f.count})
    for key, f in before.items():
        if key not in cur.findings:
            events.append({"event": "cleared", "key": key, "title": f.title})
    was = prev.severity if prev else "none"
    if cur.severity != was:
        events.append({"event": "severity", "from": was, "to": cur.severity})
    return events


class Watcher:
    """One watch session. Call tick() repeatedly; each call returns the change events."""

    def __init__(self, poll, patterns, noise, redactor, target: str, source: str,
                 history_path: Path | None = None, now=lambda: datetime.now(timezone.utc)):
        self.poll, self.patterns, self.noise, self.redactor = poll, patterns, noise, redactor
        self.target, self.source, self.history_path, self.now = target, source, history_path, now
        self.current: Analysis | None = None
        self.peak: Analysis | None = None
        self.ticks = 0
        self._new_session()
        self._last_active: datetime | None = None

    def _new_session(self) -> None:
        self.session_id = secrets.token_hex(4)
        self.started_at: str | None = None
        self.seen: dict[str, int] = {}   # key -> highest count, in order of first appearance
        self.session_severity = "none"
        self.announced: set[str] = set()

    def tick(self) -> list[dict]:
        """Poll once, analyze the window, and return what changed. Raises CollectorError."""
        analysis = analyze(self.poll(), self.patterns, noise=self.noise, redactor=self.redactor)
        self.ticks += 1
        events = diff(self.current, analysis)
        self.current = analysis
        rank = (SEVERITY_RANK[analysis.severity], len(analysis.findings))
        if self.peak is None or rank >= (SEVERITY_RANK[self.peak.severity], len(self.peak.findings)):
            self.peak = analysis
        if analysis.findings:
            events += self._remember(analysis)
        stamp = self.now().astimezone().strftime("%H:%M:%S")
        for ev in events:
            ev["at"] = stamp
        return events

    def _remember(self, analysis: Analysis) -> list[dict]:
        now = self.now()
        if self._last_active is not None and now - self._last_active > QUIET_GAP:
            self._new_session()  # long quiet spell: this is a different incident
        self._last_active = now
        changed = False
        for key in analysis.order:
            count = analysis.findings[key].count
            if key not in self.seen or count > self.seen[key]:
                changed = changed or key not in self.seen
                self.seen[key] = max(count, self.seen.get(key, 0))
        if SEVERITY_RANK[analysis.severity] > SEVERITY_RANK[self.session_severity]:
            self.session_severity, changed = analysis.severity, True
        if self.history_path is None or not changed:
            return []
        stamp = now.isoformat(timespec="seconds")
        self.started_at = self.started_at or stamp
        incident = memory.Incident(
            id=self.session_id, recorded_at=self.started_at, last_seen_at=stamp, target=self.target,
            source=self.source, severity=self.session_severity, keys=sorted(self.seen),
            first=next(iter(self.seen)), counts=dict(self.seen), runs=self.ticks,
        )
        try:
            matches = memory.upsert(self.history_path, incident)
        except OSError:
            return []
        events = []
        for m in memory.matches_as_dicts(matches):
            if m["id"] not in self.announced:
                self.announced.add(m["id"])
                events.append({"event": "seen_before", **m})
        return events
