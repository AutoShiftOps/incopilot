import json
from datetime import datetime, timedelta, timezone

import pytest

from incopilot import cli, collectors, memory
from incopilot.analyzer import analyze
from incopilot.collectors import CollectorError
from incopilot.redact import Redactor
from incopilot.watch import FileFollower, Watcher, diff


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_follower_reads_only_new_lines_and_evicts_old_ones(tmp_path):
    log, clock = tmp_path / "a.log", Clock()
    log.write_text("ERROR old line\n")
    f = FileFollower(str(log), 60, clock)
    assert f.poll() == ""
    with open(log, "a") as fh:
        fh.write("ERROR one\nERROR tw")
    assert f.poll() == "ERROR one"
    with open(log, "a") as fh:
        fh.write("o\n")
    clock.t = 30
    assert f.poll() == "ERROR one\nERROR two"
    clock.t = 61
    assert f.poll() == "ERROR two"
    clock.t = 200
    assert f.poll() == ""


def test_follower_from_start_and_truncation(tmp_path):
    log, clock = tmp_path / "a.log", Clock()
    log.write_text("ERROR a\nERROR b\n")
    f = FileFollower(str(log), 600, clock, from_start=True)
    assert f.poll() == "ERROR a\nERROR b"
    log.write_text("ERROR c\n")  # truncated and rewritten, as log rotation does
    assert f.poll().endswith("ERROR c")


def test_follower_missing_file(tmp_path):
    with pytest.raises(CollectorError):
        FileFollower(str(tmp_path / "nope.log"), 60, Clock())


def test_diff_events(core):
    a = analyze("ERROR connection refused\n", core)
    b = analyze("ERROR connection refused\nERROR Out of memory\n", core)
    assert [e["event"] for e in diff(None, a)] == ["new", "severity"]
    events = diff(a, b)
    assert {(e["event"], e.get("key")) for e in events} == {("new", "oom_kill"), ("severity", None)}
    assert events[-1] == {"event": "severity", "from": "high", "to": "critical"}
    cleared = diff(b, analyze("INFO fine\n", core))
    assert sorted(e["event"] for e in cleared) == ["cleared", "cleared", "severity"]
    assert diff(b, b) == []


def make_watcher(core, texts, hist, now):
    it = iter(texts)
    return Watcher(lambda: next(it), core, None, Redactor(), "api", "file", hist, now=now)


def test_watcher_keeps_one_history_record_per_incident(core, tmp_path):
    hist = tmp_path / "h.jsonl"
    t = [datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)]
    w = make_watcher(core, [
        "INFO fine\n",
        "WARN slow query took longer than 2s\n",
        "WARN slow query took longer than 2s\nERROR connection pool exhausted\n",
        "ERROR connection pool exhausted\n",
        "INFO fine\n",
    ], hist, lambda: t[0])
    kinds = []
    for _ in range(5):
        kinds.append([e["event"] for e in w.tick()])
        t[0] += timedelta(seconds=15)
    assert kinds == [[], ["new", "severity"], ["new", "severity"], ["cleared"], ["cleared", "severity"]]
    rows = memory.load(hist)
    assert len(rows) == 1
    assert rows[0].keys == ["conn_limit", "slow"] and rows[0].first == "slow" and rows[0].severity == "high"
    assert w.peak.severity == "high" and len(w.peak.findings) == 2


def test_watcher_announces_a_past_match_once_and_keeps_notes(core, tmp_path):
    hist = tmp_path / "h.jsonl"
    old = memory.from_analysis(analyze("ERROR connection pool exhausted\n", core), "api-old", "file",
                               datetime(2026, 2, 1, tzinfo=timezone.utc))
    old.note = "raised pool size"
    memory.save(hist, [old])
    t = [datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)]
    pool = "ERROR connection pool exhausted\n"
    w = make_watcher(core, [pool, pool + pool, pool + "ERROR No space left on device\n"], hist, lambda: t[0])
    first = w.tick()
    seen = [e for e in first if e["event"] == "seen_before"]
    assert len(seen) == 1 and seen[0]["id"] == old.id and seen[0]["note"] == "raised pool size"
    assert seen[0]["days_ago"] == 28
    memory.set_note(hist, w.session_id, "my fix")
    assert [e for e in w.tick() if e["event"] == "seen_before"] == []
    assert [e for e in w.tick() if e["event"] == "seen_before"] == []
    mine = next(r for r in memory.load(hist) if r.id == w.session_id)
    assert mine.note == "my fix" and "disk_full" in mine.keys


def test_watcher_starts_a_new_incident_after_a_long_quiet_spell(core, tmp_path):
    hist = tmp_path / "h.jsonl"
    t = [datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)]
    w = make_watcher(core, ["ERROR connection refused\n", "INFO fine\n", "ERROR No space left on device\n"],
                     hist, lambda: t[0])
    w.tick()
    first_id = w.session_id
    t[0] += timedelta(minutes=5)
    w.tick()
    t[0] += timedelta(hours=3)
    w.tick()
    assert w.session_id != first_id and len(memory.load(hist)) == 2


def run_watch(argv, on_sleep=lambda n: None):
    clock = Clock()

    def sleep(seconds):
        clock.t += seconds
        on_sleep(clock.t)

    return cli.run_watch(cli.build_parser().parse_args(["watch"] + argv), sleep=sleep, clock=clock)


def test_cli_watch_file_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    log, hist = tmp_path / "app.log", tmp_path / "h.jsonl"
    log.write_text("ERROR something old: connection refused\n")
    script = {15: "WARN slow query took longer than 2s\n", 30: "ERROR Out of memory: Killed process 1\n"}

    def on_sleep(t):
        if t in script:
            with open(log, "a") as fh:
                fh.write(script[t])

    code = run_watch(["file", "--path", str(log), "--history", str(hist), "--duration", "60", "--html",
                      "--fail-on", "critical"], on_sleep)
    out = capsys.readouterr().out
    assert code == cli.EXIT_THRESHOLD
    assert "Watching" in out and "Slow operations" in out and "Out of memory" in out
    assert "Connection refused" not in out  # only lines written after watch started
    assert "Stopped after 5 checks. Peak severity: critical." in out and "Remembered as" in out
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["severity"] == "critical" and report["meta"]["source"] == "watch file"
    assert (tmp_path / "out" / "report.html").exists()
    assert len(memory.load(hist)) == 1


def test_cli_watch_json_emits_one_event_per_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    log = tmp_path / "app.log"
    log.write_text("")

    def on_sleep(t):
        if t == 15:
            with open(log, "a") as fh:
                fh.write("ERROR No space left on device\n")

    assert run_watch(["file", "--path", str(log), "--json", "--no-write", "--no-history",
                      "--duration", "30"], on_sleep) == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [e["event"] for e in events] == ["new", "severity"]
    assert events[0]["key"] == "disk_full" and "at" in events[0]


def test_cli_watch_command_source_uses_the_window(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    seen = []

    def fake_k8s(pod, selector, namespace, container, since, previous, context, tail, timeout):
        seen.append((pod, namespace, since, previous))
        return "ERROR Back-off restarting failed container\n" if len(seen) > 1 else "INFO ok\n"

    monkeypatch.setattr(collectors, "from_k8s", fake_k8s)
    assert run_watch(["k8s", "--pod", "deploy/api", "-n", "prod", "--window", "3", "--interval", "10",
                      "--duration", "20", "--no-write", "--no-history"]) == 0
    assert seen[0] == ("deploy/api", "prod", "3m", False) and len(seen) == 3
    out = capsys.readouterr().out
    assert "Watching prod/deploy/api" in out and "Restart loop" in out


def test_cli_watch_journal_since_format(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seen = []
    monkeypatch.setattr(collectors, "from_journal", lambda unit, since, t: seen.append(since) or "")
    run_watch(["journal", "--unit", "nginx", "--duration", "1", "--no-write", "-q"])
    assert seen[0] == "5 min ago"


def test_cli_watch_fails_fast_and_gives_up_after_repeated_errors(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert run_watch(["file", "--path", str(tmp_path / "nope.log")]) == cli.EXIT_ERROR
    assert run_watch(["file", "--path", "x.log.gz"]) == cli.EXIT_ERROR
    calls = []

    def flaky(container, since, t):
        calls.append(1)
        if len(calls) > 1:
            raise CollectorError("'docker' exited 1: No such container")
        return ""

    monkeypatch.setattr(collectors, "from_docker", flaky)
    assert run_watch(["docker", "--container", "api", "--no-write", "-q"]) == cli.EXIT_ERROR
    assert "source unavailable" in capsys.readouterr().err and len(calls) == 6


def test_cli_watch_stops_cleanly_on_ctrl_c(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    log = tmp_path / "app.log"
    log.write_text("ERROR No space left on device\n")

    def interrupt(seconds):
        raise KeyboardInterrupt

    args = cli.build_parser().parse_args(["watch", "file", "--path", str(log), "--from-start", "--no-history"])
    assert cli.run_watch(args, sleep=interrupt, clock=Clock()) == 0
    assert "Stopped after 1 checks" in capsys.readouterr().out
    assert (tmp_path / "out" / "report.md").exists()


def test_one_shot_sources_still_accept_since_and_previous():
    args = cli.build_parser().parse_args(["k8s", "--pod", "a", "--since", "2h", "--previous"])
    assert args.since == "2h" and args.previous
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["watch", "k8s", "--pod", "a", "--since", "2h"])
