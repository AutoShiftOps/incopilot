from incopilot.ai import AIResult
from incopilot.analyzer import analyze
from incopilot.reporter import (
    SCHEMA_VERSION,
    build_meta,
    build_report_json,
    build_report_md,
    safe_next_commands,
    suggest_next_steps,
    write_outputs,
)

_MUTATING = {"restart", "delete", "rm", "kill", "scale", "rollout", "apply", "stop", "prune", "drain", "exec",
             "start", "reload", "edit", "patch", "cordon"}


def _run(core, example_log):
    a = analyze(example_log.read_text(), core)
    meta = build_meta("file", str(example_log), "n/a")
    return a, meta


def test_markdown_report_sections(core, example_log):
    a, meta = _run(core, example_log)
    md = build_report_md(meta, a, safe_next_commands({}))
    for heading in ("# Incident triage report", "## Four Golden Signals", "## Findings",
                    "## Order of first appearance", "## Suggested next steps", "## Read-only checks to run next"):
        assert heading in md
    assert "CRITICAL" in md and "S3cr3tPass" not in md
    assert "AI hypothesis" not in md


def test_markdown_ai_section_states_it_is_unverified(core, example_log):
    a, meta = _run(core, example_log)
    md = build_report_md(meta, a, [], AIResult("anthropic", "m", text="Pool too small."))
    assert "## AI hypothesis (unverified)" in md and "Pool too small." in md
    md = build_report_md(meta, a, [], AIResult("none", "none", error="no key"))
    assert "Not available: no key" in md


def test_json_report_shape(core, example_log):
    a, meta = _run(core, example_log)
    rep = build_report_json(meta, a, safe_next_commands({}))
    assert rep["schema_version"] == SCHEMA_VERSION
    assert rep["severity"] == "critical" and rep["ai"] is None
    assert rep["findings"]["http_5xx"]["count"] == 5
    assert rep["order_of_first_appearance"][0] == "slow"
    assert set(rep) >= {"meta", "stats", "golden_signals", "top_repeating_lines", "suggestions",
                        "safe_next_commands", "safety_note"}


def test_clean_log_report(core):
    a = analyze("INFO all good\n", core)
    md = build_report_md(build_meta("file", "x", "n/a"), a, [])
    assert "NONE" in md and "No pattern matched." in md
    assert suggest_next_steps(a)[0].startswith("No known failure pattern")


def test_next_commands_are_read_only_and_quoted():
    cmds = safe_next_commands({
        "journal": {"unit": "nginx; rm -rf /"},
        "docker": {"container": "api"},
        "k8s": {"pod": "deploy/api", "selector": None, "namespace": "prod"},
    })
    text = "\n".join(c for _, c in cmds)
    assert "'nginx; rm -rf /'" in text
    assert "kubectl describe deploy/api -n prod" in text
    for _, cmd in safe_next_commands({"journal": {"unit": "nginx"}, "docker": {"container": "api"},
                                      "k8s": {"pod": None, "selector": "app=api", "namespace": None}}):
        assert not _MUTATING & set(cmd.split()), cmd


def test_write_outputs(tmp_path, core, example_log):
    a, meta = _run(core, example_log)
    paths = write_outputs(str(tmp_path / "nested" / "out"), "# md", build_report_json(meta, a, []))
    assert open(paths["report_md"]).read() == "# md"
    assert '"schema_version": "2"' in open(paths["report_json"]).read()
