"""The former name, incopilot, keeps working for one release."""

import sys

from firstsignal import _compat, cli, memory, settings


def test_new_env_var_wins(monkeypatch):
    monkeypatch.setenv("INCOPILOT_AI_MODEL", "old")
    monkeypatch.setenv("FIRSTSIGNAL_AI_MODEL", "new")
    assert _compat.getenv("AI_MODEL") == "new"


def test_old_env_var_is_read(monkeypatch):
    monkeypatch.delenv("FIRSTSIGNAL_AI_MODEL", raising=False)
    monkeypatch.setenv("INCOPILOT_AI_MODEL", "old")
    assert _compat.getenv("AI_MODEL") == "old"


def test_old_history_env_var(monkeypatch, tmp_path):
    monkeypatch.delenv("FIRSTSIGNAL_HISTORY", raising=False)
    monkeypatch.setenv("INCOPILOT_HISTORY", str(tmp_path / "h.jsonl"))
    assert memory.default_path() == tmp_path / "h.jsonl"


def test_history_keeps_using_old_folder_until_a_new_one_exists(monkeypatch, tmp_path):
    monkeypatch.delenv("FIRSTSIGNAL_HISTORY", raising=False)
    monkeypatch.delenv("INCOPILOT_HISTORY", raising=False)
    monkeypatch.setattr(memory.Path, "home", lambda: tmp_path)
    assert memory.default_path() == tmp_path / ".firstsignal" / "history.jsonl"
    old = tmp_path / ".incopilot" / "history.jsonl"
    old.parent.mkdir()
    old.write_text("")
    assert memory.default_path() == old
    new = tmp_path / ".firstsignal" / "history.jsonl"
    new.parent.mkdir()
    new.write_text("")
    assert memory.default_path() == new


def test_old_config_file_is_read(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "incopilot.toml").write_text('packs = ["core", "nginx"]\n')
    assert settings.load().packs == ["core", "nginx"]
    (tmp_path / "firstsignal.toml").write_text('packs = ["core"]\n')
    assert settings.load().packs == ["core"]


def test_old_command_prints_a_note_on_stderr(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["incopilot", "--version"])
    try:
        cli.main()
    except SystemExit:
        pass
    out = capsys.readouterr()
    assert "now firstsignal" in out.err
    assert "now firstsignal" not in out.out
