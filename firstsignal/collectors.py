"""Log collectors. Every collector is read-only and runs without a shell."""

from __future__ import annotations

import gzip
import os
import subprocess  # nosec B404
import sys

DEFAULT_TIMEOUT = 60
DEFAULT_MAX_BYTES = 5_000_000


class CollectorError(RuntimeError):
    """A log source could not be read."""


def _safe(value: str, what: str) -> str:
    """Reject values that a CLI tool would read as an option."""
    if value is None or str(value).strip() == "":
        raise CollectorError(f"{what} must not be empty")
    if str(value).startswith("-"):
        raise CollectorError(f"{what} must not start with '-': {value!r}")
    return str(value)


def tail_bytes(text: str, max_bytes: int) -> tuple[str, bool]:
    """Keep the last max_bytes of text, starting on a line boundary."""
    data = text.encode("utf-8", errors="replace")
    if max_bytes <= 0 or len(data) <= max_bytes:
        return text, False
    cut = data[-max_bytes:]
    nl = cut.find(b"\n")
    if 0 <= nl < len(cut) - 1:
        cut = cut[nl + 1:]
    return cut.decode("utf-8", errors="replace"), True


def _run(cmd: list[str], timeout: int, merge_stderr: bool = False) -> str:
    try:
        proc = subprocess.run(  # nosec B603
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CollectorError(f"'{cmd[0]}' was not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise CollectorError(f"'{cmd[0]}' did not finish within {timeout}s") from exc
    if proc.returncode != 0:
        detail = (proc.stdout if merge_stderr else proc.stderr or "").strip().splitlines()
        raise CollectorError(f"'{cmd[0]}' exited {proc.returncode}: {detail[-1] if detail else 'no output'}")
    return proc.stdout


def from_journal(unit: str, since: str = "30 min ago", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Read a systemd unit's journal."""
    return _run(
        ["journalctl", "-u", _safe(unit, "unit"), "--since", _safe(since, "since"),
         "--no-pager", "-o", "short-iso"],
        timeout,
    )


def from_docker(container: str, since: str = "1h", timeout: int = DEFAULT_TIMEOUT) -> str:
    """Read a container's logs. Docker replays app stderr on stderr, so both streams are kept."""
    return _run(
        ["docker", "logs", "--timestamps", "--since", _safe(since, "since"), _safe(container, "container")],
        timeout,
        merge_stderr=True,
    )


def from_k8s(
    pod: str | None = None,
    selector: str | None = None,
    namespace: str | None = None,
    container: str | None = None,
    since: str = "30m",
    previous: bool = False,
    context: str | None = None,
    tail: int = 5000,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Read pod logs with kubectl. `pod` may be a pod name or a reference such as deploy/api."""
    if bool(pod) == bool(selector):
        raise CollectorError("give exactly one of a pod (or deploy/name) and a label selector")
    cmd = ["kubectl"]
    if context:
        cmd += ["--context", _safe(context, "context")]
    cmd += ["logs", "--timestamps", "--prefix", f"--since={_safe(since, 'since')}", f"--tail={int(tail)}"]
    if namespace:
        cmd += ["-n", _safe(namespace, "namespace")]
    if selector:
        cmd += ["-l", _safe(selector, "selector"), "--max-log-requests=20"]
    else:
        cmd.append(_safe(pod, "pod"))
    if container:
        cmd += ["-c", _safe(container, "container")]
    else:
        cmd.append("--all-containers=true")
    if previous:
        cmd.append("--previous")
    return _run(cmd, timeout)


def from_file(path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    """Read a log file ('-' for stdin, .gz supported). Only the tail of large files is read."""
    if path == "-":
        return sys.stdin.read()
    try:
        if path.endswith(".gz"):
            with gzip.open(path, "rt", errors="replace") as fh:
                return fh.read()
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            if max_bytes > 0 and size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()  # drop the partial first line
            return fh.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise CollectorError(f"cannot read {path}: {exc.strerror or exc}") from exc


def join_sources(parts: list[tuple[str, str]]) -> str:
    """Join several (label, text) sources into one stream with source markers."""
    return "".join(f"=== SOURCE: {label} ===\n{text.rstrip()}\n\n" for label, text in parts)
