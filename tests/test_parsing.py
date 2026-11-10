from incopilot.parsing import normalize_level, parse_line


def test_plain_line_level_and_timestamp():
    ev = parse_line("2026-03-01T09:41:12Z ERROR [api] boom")
    assert ev.level == "error"
    assert ev.timestamp == "2026-03-01T09:41:12Z"
    assert not ev.structured


def test_nginx_bracket_level():
    assert parse_line("2026/03/01 09:41:12 [crit] 12#12: something").level == "fatal"


def test_logfmt_level():
    assert parse_line('time=x level=warning msg="slow"').level == "warn"


def test_json_line_builds_text_from_message_error_and_status():
    ev = parse_line('{"ts":"2026-03-01T09:41:14Z","level":"error","msg":"request failed",'
                    '"status":503,"error":"upstream timed out"}')
    assert ev.structured
    assert ev.level == "error"
    assert ev.timestamp == "2026-03-01T09:41:14Z"
    assert ev.text == "request failed upstream timed out status=503"


def test_kubectl_prefix_and_timestamp_before_json():
    ev = parse_line('[pod/api-7d9f/app] 2026-03-01T09:41:14.123456789Z {"level":50,"msg":"db down"}')
    assert ev.structured
    assert ev.level == "error"
    assert ev.text == "db down"
    assert ev.timestamp.startswith("2026-03-01T09:41:14")


def test_broken_json_falls_back_to_plain_text():
    ev = parse_line('{"level":"error", oops}')
    assert not ev.structured
    assert ev.text == '{"level":"error", oops}'


def test_numeric_levels():
    assert [normalize_level(n) for n in (10, 30, 40, 50, 60)] == ["debug", "info", "warn", "error", "fatal"]
    assert normalize_level(None) == "unknown"
