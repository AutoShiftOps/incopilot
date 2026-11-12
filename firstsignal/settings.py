"""Optional firstsignal.toml: extra patterns, noise filters, packs and redaction rules."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import _compat
from .patterns import SEVERITY_RANK, SIGNALS, Pattern

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10 only
    import tomli as tomllib

DEFAULT_FILE = "firstsignal.toml"


class SettingsError(ValueError):
    """The settings file is invalid."""


@dataclass
class Settings:
    """Values read from firstsignal.toml. Everything is optional."""

    packs: list[str] = field(default_factory=list)
    patterns: list[Pattern] = field(default_factory=list)
    noise: list[re.Pattern] | None = None
    redact_extra: list[re.Pattern] = field(default_factory=list)
    ai_provider: str | None = None
    ai_model: str | None = None
    path: str | None = None


def _compile(rx: str, where: str) -> re.Pattern:
    try:
        return re.compile(rx, re.IGNORECASE)
    except re.error as exc:
        raise SettingsError(f"{where}: invalid regex {rx!r}: {exc}") from exc


def load(path: str | None = None) -> Settings:
    """Load settings from `path`, or ./firstsignal.toml if it exists, else defaults."""
    explicit = path is not None
    file = Path(path) if path else _compat.prefer_existing(Path(DEFAULT_FILE), Path(f"{_compat.OLD_NAME}.toml"))
    if not file.is_file():
        if explicit:
            raise SettingsError(f"config file not found: {file}")
        return Settings()
    try:
        data = tomllib.loads(file.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SettingsError(f"{file}: {exc}") from exc

    out = Settings(path=str(file))
    out.packs = [str(p) for p in data.get("packs", [])]
    if "noise" in data:
        out.noise = [_compile(rx, f"{file} noise") for rx in data["noise"]]
    out.redact_extra = [_compile(rx, f"{file} redact.extra") for rx in data.get("redact", {}).get("extra", [])]
    ai = data.get("ai", {})
    out.ai_provider, out.ai_model = ai.get("provider"), ai.get("model")

    for i, item in enumerate(data.get("patterns", []), 1):
        where = f"{file} patterns[{i}]"
        try:
            key, rx = item["key"], item["regex"]
        except (KeyError, TypeError) as exc:
            raise SettingsError(f"{where}: 'key' and 'regex' are required") from exc
        signal = item.get("signal", "errors")
        severity = item.get("severity", "medium")
        if signal not in SIGNALS:
            raise SettingsError(f"{where}: signal must be one of {', '.join(SIGNALS)}")
        if severity not in SEVERITY_RANK or severity == "none":
            raise SettingsError(f"{where}: severity must be low, medium, high or critical")
        out.patterns.append(Pattern(
            key=str(key), regex=_compile(rx, where), signal=signal, severity=severity,
            title=str(item.get("title", key)), advice=str(item.get("advice", "")), pack="custom",
        ))
    return out
