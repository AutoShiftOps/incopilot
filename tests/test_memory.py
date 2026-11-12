import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone

import pytest

from firstsignal import cli, memory
from firstsignal.analyzer import analyze

T0 = datetime(2026, 3, 1, 9, 45, tzinfo=timezone.utc)
POOL = "WARN slow query took longer than 2s\nERROR connection pool exhausted\nERROR request timed out\n"
DISK = "ERROR No space left on device\n"


def inc(core, text, target="api", when=T0):
    return memory.from_analysis(analyze(text, core), target, "file", when)


def test_fingerprint_holds_shape_not_log_text(core, example_log, tmp_path):
    path = tmp_path / "h.jsonl"
    memory.remember(path, inc(core, example_log.read_text()))
    raw = path.read_text()
    row = json.loads(raw)
    assert row["first"] == "slow" and "oom_kill" in row["keys"] and row["counts"]["http_5xx"] == 5
    for leaked in ("S3cr3tPass", "eyJhbGci", "checkout:", "10.0.3.17", "SELECT"):
        assert leaked not in raw


@pytest.mark.skipif(sys.platform == "win32", reason="Windows does not apply POSIX file modes")
def test_history_file_is_private(core, tmp_path):
    path = tmp_path / "d" / "h.jsonl"
    memory.remember(path, inc(core, POOL))
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_similar_incident_is_recognized_later(core, tmp_path):
    path = tmp_path / "h.jsonl"
    first, matches = memory.remember(path, inc(core, POOL))
    assert matches == []
    memory.set_note(path, first.id, "raised pool size to 30")
    _, matches = memory.remember(path, inc(core, POOL + "ERROR HTTP 503\n", target="api-2", when=T0 + timedelta(days=12)))
    assert len(matches) == 1
    m = matches[0]
    assert m.incident.id == first.id and m.days_ago == 12 and m.similarity >= 0.6
    assert m.incident.note == "raised pool size to 30"


def test_unrelated_incident_does_not_match(core, tmp_path):
    path = tmp_path / "h.jsonl"
    memory.remember(path, inc(core, POOL))
    _, matches = memory.remember(path, inc(core, DISK, when=T0 + timedelta(days=1)))
    assert matches == []


def test_rerun_during_same_incident_updates_instead_of_matching_itself(core, tmp_path):
    path = tmp_path / "h.jsonl"
    a, _ = memory.remember(path, inc(core, POOL))
    b, matches = memory.remember(path, inc(core, POOL, when=T0 + timedelta(minutes=10)))
    assert matches == [] and b.id == a.id and b.runs == 2
    assert len(memory.load(path)) == 1
    _, matches = memory.remember(path, inc(core, POOL, when=T0 + timedelta(hours=5)))
    assert len(matches) == 1 and len(memory.load(path)) == 2


def test_ids_stay_unique_even_within_the_same_second(core, tmp_path, monkeypatch):
    path = tmp_path / "h.jsonl"
    ids = iter(["aaaaaaaa", "aaaaaaaa", "bbbbbbbb"])
    monkeypatch.setattr(memory.secrets, "token_hex", lambda n: next(ids))
    memory.remember(path, inc(core, POOL, target="a"))
    memory.remember(path, inc(core, POOL, target="b"))
    assert [h.id for h in memory.load(path)] == ["aaaaaaaa", "bbbbbbbb"]


def test_similarity_rules(core):
    a, b = inc(core, POOL), inc(core, POOL)
    assert memory.similarity(a, b) == 1.0
    assert memory.similarity(a, inc(core, DISK)) == 0.0
    reordered = inc(core, "ERROR request timed out\nERROR connection pool exhausted\nWARN slow query took longer than 2s\n")
    assert memory.similarity(a, reordered) == 0.8  # same patterns, different first


def test_corrupt_lines_are_skipped_and_missing_file_is_empty(core, tmp_path):
    path = tmp_path / "h.jsonl"
    assert memory.load(path) == []
    memory.remember(path, inc(core, POOL))
    with open(path, "a") as fh:
        fh.write("{not json\n{\"id\": 1}\n")
    assert len(memory.load(path)) == 1


def test_note_and_forget(core, tmp_path):
    path = tmp_path / "h.jsonl"
    a, _ = memory.remember(path, inc(core, POOL))
    assert memory.set_note(path, "nope", "x") is None and not memory.forget(path, "nope")
    assert memory.forget(path, a.id) and memory.load(path) == []


def test_cli_records_and_reports_seen_before(example_log, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    hist = tmp_path / "h.jsonl"
    assert cli.run(["file", "--path", str(example_log), "--history", str(hist)]) == 0
    out = capsys.readouterr().out
    assert "Remembered as" in out and "Seen before" not in out
    rid = memory.load(hist)[0].id
    assert cli.run(["history", "--history", str(hist), "note", rid, "raised pool size [bold]x[/bold]"]) == 0
    # make the stored incident old enough to count as a past one
    rows = memory.load(hist)
    rows[0].last_seen_at = rows[0].recorded_at = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(timespec="seconds")
    memory.save(hist, rows)
    capsys.readouterr()
    assert cli.run(["file", "--path", str(example_log), "--history", str(hist), "--html"]) == 0
    out = capsys.readouterr().out
    assert "Seen before" in out and "3 days ago" in out and "Fix noted: raised pool size" in out
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["seen_before"][0]["id"] == rid and report["seen_before"][0]["similarity"] == 1.0
    assert "## Seen before" in (tmp_path / "out" / "report.md").read_text()
    assert '"seen_before":[{' in (tmp_path / "out" / "report.html").read_text()


def test_cli_no_history_and_clean_logs_record_nothing(example_log, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    hist = tmp_path / "h.jsonl"
    cli.run(["file", "--path", str(example_log), "--history", str(hist), "--no-history", "-q"])
    clean = tmp_path / "clean.log"
    clean.write_text("INFO fine\n")
    cli.run(["file", "--path", str(clean), "--history", str(hist), "-q"])
    assert not hist.exists()


def test_cli_history_list_and_errors(example_log, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    hist = tmp_path / "h.jsonl"
    assert cli.run(["history", "--history", str(hist), "list"]) == 0
    assert "No incidents remembered yet" in capsys.readouterr().out
    cli.run(["file", "--path", str(example_log), "--history", str(hist), "-q"])
    assert cli.run(["history", "--history", str(hist), "list"]) == 0
    assert "Remembered incidents" in capsys.readouterr().out
    assert cli.run(["history", "--history", str(hist), "note", "zzzz", "x"]) == cli.EXIT_ERROR
    assert cli.run(["history", "--history", str(hist), "forget", "zzzz"]) == cli.EXIT_ERROR
    assert cli.run(["history", "--history", str(hist), "forget", memory.load(hist)[0].id]) == 0


def test_unwritable_history_does_not_fail_the_run(example_log, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert cli.run(["file", "--path", str(example_log), "--history", str(blocker / "h.jsonl"), "--no-write"]) == 0
    assert "history not updated" in capsys.readouterr().err
