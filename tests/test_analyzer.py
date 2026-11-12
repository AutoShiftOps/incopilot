import re

import pytest

from firstsignal.analyzer import analyze, normalize_line
from firstsignal.patterns import PACKS, SEVERITY_RANK, SIGNALS, Pattern, resolve_packs
from firstsignal.redact import Redactor


@pytest.mark.parametrize("line,key", [
    ("Out of memory: Killed process 4321 (python3)", "oom_kill"),
    ("write /var/log/app.log: No space left on device", "disk_full"),
    ("accept4() failed (24: Too many open files)", "fd_exhaustion"),
    ("connection pool exhausted (10/10 in use)", "conn_limit"),
    ("context deadline exceeded", "timeout"),
    ("upstream timeout while reading response header", "timeout"),
    ("connect() failed (111: Connection refused)", "conn_refused"),
    ("recv() failed (104: Connection reset by peer)", "conn_reset"),
    ("getaddrinfo ENOTFOUND db.internal", "dns"),
    ("x509: certificate has expired or is not yet valid", "tls"),
    ("open /etc/app/key: permission denied", "permission"),
    ('"POST /api HTTP/1.1" 502 157', "http_5xx"),
    ("upstream returned status=503", "http_5xx"),
    ("panic: runtime error: index out of range", "panic_fatal"),
    ("Back-off restarting failed container", "restart_loop"),
    ("rate limit exceeded for client", "rate_limited"),
])
def test_core_patterns_match(core, line, key):
    assert key in analyze(line, core).findings


@pytest.mark.parametrize("line", [
    "request took 512 ms",
    "INFO config loaded timeout=30s retries=5",
    "served 5000 requests",
    "order 503 shipped",
])
def test_core_patterns_do_not_false_positive(core, line):
    assert analyze(line, core).findings == {}


def test_health_checks_are_filtered_unless_failing(core):
    a = analyze("INFO GET /healthz 200\nERROR GET /healthz connection refused", core)
    assert a.stats["lines_noise_filtered"] == 1
    assert a.findings["conn_refused"].count == 1


def test_debug_lines_are_not_matched(core):
    assert analyze("DEBUG simulated connection refused for test", core).findings == {}


def test_severity_signals_and_order(core, example_log):
    a = analyze(example_log.read_text(), core)
    assert a.severity == "critical"
    assert set(a.signals) == set(SIGNALS)
    assert a.order[0] == "slow"
    assert a.order.index("conn_limit") < a.order.index("http_5xx") < a.order.index("oom_kill")
    assert list(a.findings)[0] == "oom_kill"  # most severe first
    assert a.findings["http_5xx"].count == 5
    assert a.findings["conn_limit"].first_seen == "2026-03-01T09:41:12Z"


def test_examples_and_top_lines_are_redacted(core, example_log):
    a = analyze(example_log.read_text(), core, redactor=Redactor())
    blob = repr(a.findings) + repr(a.top_lines)
    assert "S3cr3tPass" not in blob
    assert "eyJhbGci" not in blob


def test_empty_input(core):
    a = analyze("", core)
    assert a.severity == "none" and a.findings == {} and a.stats["lines_total"] == 0


def test_source_markers_are_not_counted(core):
    a = analyze("=== SOURCE: docker api ===\nERROR connection refused\n", core)
    assert a.stats["lines_total"] == 1
    assert a.stats["sources"] == ["docker api"]


def test_custom_pattern(core):
    pat = Pattern("ledger", re.compile("ledger mismatch"), "errors", "critical", "Ledger", "Check it.", "custom")
    assert analyze("WARN ledger mismatch for account", core + [pat]).severity == "critical"


def test_normalize_line_groups_variable_parts():
    a = normalize_line("2026-03-01T09:41:12Z req 550e8400-e29b-41d4-a716-446655440000 from 10.0.0.1:443 took 1500ms")
    b = normalize_line("2026-03-01T09:42:55Z req 123e4567-e89b-12d3-a456-426614174000 from 10.0.9.9:8080 took 20ms")
    assert a == b


def test_every_pack_is_well_formed():
    keys = [p.key for p in resolve_packs(["all"])]
    assert len(keys) == len(set(keys))
    for pack in PACKS.values():
        for p in pack:
            assert p.signal in SIGNALS and SEVERITY_RANK[p.severity] > 0 and p.advice


def test_unknown_pack_is_rejected():
    with pytest.raises(ValueError):
        resolve_packs(["nope"])
