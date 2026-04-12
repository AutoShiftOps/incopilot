"""Run this to create a sample.log you can test against without any real services."""
from pathlib import Path

SAMPLE = """
2026-03-01 09:41:12 ERROR upstream timeout while reading response header from upstream
2026-03-01 09:41:13 ERROR upstream timeout while reading response header from upstream
2026-03-01 09:41:14 WARN  No space left on device
2026-03-01 09:41:14 ERROR connect() failed (111: Connection refused)
2026-03-01 09:41:15 ERROR HTTP 500 Internal Server Error POST /api/checkout
2026-03-01 09:41:15 ERROR HTTP 500 Internal Server Error POST /api/checkout
2026-03-01 09:41:16 fatal: panic in worker goroutine
Out of memory: Killed process 4321 (python3)
2026-03-01 09:41:17 WARN  restarting container due to failure
""".strip() + "\n"

Path("sample.log").write_text(SAMPLE, encoding="utf-8")
print("sample.log written — run: python -m incopilot file --path sample.log")
