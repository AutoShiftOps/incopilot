import io
import json

import pytest

from incopilot import __version__, ai, cli, collectors


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no stray incopilot.toml, reports land in tmp


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.run(["--version"])
    assert exc.value.code == 0 and __version__ in capsys.readouterr().out


def test_file_run_writes_reports(example_log, tmp_path, capsys):
    assert cli.run(["file", "--path", str(example_log)]) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "CRITICAL" in out and "First to appear: Slow operations" in out
    assert "Golden signals:" in out and "saturation critical" in out
    assert "Order of first appearance" in out and "09:41:07" in out
    assert out.index("Slow operations", out.index("Order of first appearance")) < out.rindex("Out of memory")
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["severity"] == "critical" and report["stats"]["truncated"] is False
    assert "S3cr3tPass" not in (tmp_path / "out" / "report.md").read_text()


def test_json_mode_prints_only_json(example_log, capsys):
    assert cli.run(["file", "--path", str(example_log), "--json", "--no-write"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["schema_version"] == "2"


def test_no_write_and_quiet(example_log, tmp_path, capsys):
    assert cli.run(["file", "--path", str(example_log), "--no-write", "-q"]) == cli.EXIT_OK
    assert capsys.readouterr().out == "" and not (tmp_path / "out").exists()


def test_fail_on_threshold(example_log, tmp_path):
    assert cli.run(["file", "--path", str(example_log), "-q", "--fail-on", "high"]) == cli.EXIT_THRESHOLD
    clean = tmp_path / "clean.log"
    clean.write_text("INFO fine\n")
    assert cli.run(["file", "--path", str(clean), "-q", "--fail-on", "low"]) == cli.EXIT_OK


def test_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("ERROR No space left on device\n"))
    assert cli.run(["file", "--path", "-", "--json", "--no-write"]) == cli.EXIT_OK
    assert "disk_full" in json.loads(capsys.readouterr().out)["findings"]


def test_missing_file_is_a_clean_error(capsys):
    assert cli.run(["file", "--path", "nope.log"]) == cli.EXIT_ERROR
    assert "cannot read nope.log" in capsys.readouterr().err


def test_unknown_pack_is_a_clean_error(example_log, capsys):
    assert cli.run(["file", "--path", str(example_log), "--packs", "nope"]) == cli.EXIT_ERROR
    assert "unknown pattern pack" in capsys.readouterr().err


def test_packs_option(tmp_path, capsys):
    log = tmp_path / "pg.log"
    log.write_text("ERROR:  deadlock detected\n")
    cli.run(["file", "--path", str(log), "--json", "--no-write"])
    assert "pg_deadlock" not in json.loads(capsys.readouterr().out)["findings"]
    cli.run(["file", "--path", str(log), "--json", "--no-write", "--packs", "core,postgres"])
    assert "pg_deadlock" in json.loads(capsys.readouterr().out)["findings"]


def test_config_file_patterns(tmp_path, capsys):
    (tmp_path / "incopilot.toml").write_text(
        '[[patterns]]\nkey = "ledger"\nregex = "ledger mismatch"\nseverity = "critical"\n')
    log = tmp_path / "a.log"
    log.write_text("WARN ledger mismatch\n")
    cli.run(["file", "--path", str(log), "--json", "--no-write"])
    assert json.loads(capsys.readouterr().out)["severity"] == "critical"


def test_k8s_source_and_next_commands(monkeypatch, capsys):
    seen = {}

    def fake(pod, selector, namespace, container, since, previous, context, tail, timeout):
        seen.update(pod=pod, namespace=namespace, since=since)
        return '[pod/api-1/app] 2026-03-01T09:41:14Z {"level":"error","msg":"Liveness probe failed"}\n'

    monkeypatch.setattr(collectors, "from_k8s", fake)
    assert cli.run(["k8s", "--pod", "deploy/api", "-n", "prod", "--packs", "all", "--json", "--no-write"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert seen == {"pod": "deploy/api", "namespace": "prod", "since": "30m"}
    assert "k8s_probe_failed" in rep["findings"] and rep["meta"]["target"] == "prod/deploy/api"
    assert any("kubectl get events -n prod" in c["cmd"] for c in rep["safe_next_commands"])


def test_bundle_merges_sources(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(collectors, "from_journal", lambda unit, since, t: "ERROR connection refused\n")
    monkeypatch.setattr(collectors, "from_docker", lambda c, since, t: "ERROR Out of memory\n")
    log = tmp_path / "x.log"
    log.write_text("ERROR No space left on device\n")
    assert cli.run(["bundle", "--unit", "nginx", "--container", "api", "--path", str(log),
                    "--json", "--no-write"]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert set(rep["findings"]) == {"conn_refused", "oom_kill", "disk_full"}
    assert len(rep["stats"]["sources"]) == 3 and rep["stats"]["lines_total"] == 3


def test_bundle_needs_a_source(capsys):
    assert cli.run(["bundle"]) == cli.EXIT_ERROR
    assert "at least one" in capsys.readouterr().err


def test_ai_is_off_by_default(example_log, monkeypatch, capsys):
    monkeypatch.setattr(ai, "hypothesize", lambda *a, **k: pytest.fail("AI must not be called without --ai"))
    cli.run(["file", "--path", str(example_log), "--json", "--no-write"])
    assert json.loads(capsys.readouterr().out)["ai"] is None


def test_ai_result_lands_in_report(example_log, monkeypatch, capsys):
    monkeypatch.setattr(ai, "hypothesize",
                        lambda *a, **k: ai.AIResult("anthropic", "m", text="Pool too small after deploy."))
    cli.run(["file", "--path", str(example_log), "--ai", "--json", "--no-write"])
    assert json.loads(capsys.readouterr().out)["ai"]["hypothesis"] == "Pool too small after deploy."


def test_ai_refuses_to_run_without_redaction(example_log, monkeypatch, capsys):
    monkeypatch.setattr(ai, "hypothesize", lambda *a, **k: pytest.fail("AI must not see unredacted logs"))
    cli.run(["file", "--path", str(example_log), "--ai", "--no-redact", "--json", "--no-write"])
    captured = capsys.readouterr()
    assert json.loads(captured.out)["ai"] is None and "--ai is ignored" in captured.err


def test_log_content_is_not_interpreted_as_markup(tmp_path, capsys):
    log = tmp_path / "a.log"
    log.write_text("ERROR [bold red]fatal[/] [link=http://evil]x[/link]\n")
    assert cli.run(["file", "--path", str(log)]) == cli.EXIT_OK
