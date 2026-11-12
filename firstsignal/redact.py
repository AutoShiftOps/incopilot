"""Secret redaction. Applied to everything that leaves the process: reports and AI prompts."""

from __future__ import annotations

import re

_RULES = [
    # scheme://user:password@host
    (re.compile(r"(\b[a-z][a-z0-9+.-]*://[^\s:/@]+:)[^\s@/]+(@)", re.IGNORECASE), r"\1<REDACTED>\2"),
    # Authorization headers and bearer tokens
    (re.compile(r"\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE), r"\1 <REDACTED>"),
    # key=value / "key": "value" secrets
    (re.compile(
        r"(\b(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|private[_-]?key"
        r"|client[_-]?secret|session[_-]?id|cookie)\b[\"']?\s*[:=]\s*[\"']?)[^\s\"',;&}]+",
        re.IGNORECASE), r"\1<REDACTED>"),
    # JSON Web Tokens
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"), "<REDACTED_JWT>"),
    # Cloud and vendor key shapes
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "<REDACTED_AWS_KEY>"),
    (re.compile(r"\b(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{20,}\b"), "<REDACTED_TOKEN>"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "<REDACTED_TOKEN>"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "<REDACTED_TOKEN>"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "<REDACTED_PRIVATE_KEY>"),
    # Email addresses
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<EMAIL>"),
]
_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")


class Redactor:
    """Masks secrets in text. Disabled instances return text unchanged."""

    def __init__(self, enabled: bool = True, redact_ips: bool = False, extra=()):
        self.enabled = enabled
        self.rules = list(_RULES)
        if redact_ips:
            self.rules.append((_IPV4, "<IP>"))
        for rx in extra:
            self.rules.append((rx if hasattr(rx, "sub") else re.compile(rx), "<REDACTED>"))

    def __call__(self, text: str) -> str:
        if not self.enabled or not text:
            return text
        for rx, repl in self.rules:
            text = rx.sub(repl, text)
        return text
