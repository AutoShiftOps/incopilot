import pytest

from firstsignal import settings
from firstsignal.settings import SettingsError


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = settings.load()
    assert s.packs == [] and s.patterns == [] and s.noise is None


def test_explicit_missing_file_is_an_error(tmp_path):
    with pytest.raises(SettingsError, match="not found"):
        settings.load(str(tmp_path / "nope.toml"))


def test_full_file(tmp_path):
    f = tmp_path / "firstsignal.toml"
    f.write_text('''
packs = ["core", "postgres"]
noise = ["/metrics"]

[redact]
extra = ["cust-[0-9]+"]

[ai]
provider = "ollama"
model = "llama3"

[[patterns]]
key = "ledger_mismatch"
regex = "ledger mismatch"
signal = "errors"
severity = "critical"
title = "Ledger mismatch"
advice = "Compare the two ledgers."
''')
    s = settings.load(str(f))
    assert s.packs == ["core", "postgres"] and len(s.noise) == 1 and len(s.redact_extra) == 1
    assert (s.ai_provider, s.ai_model) == ("ollama", "llama3")
    p = s.patterns[0]
    assert (p.key, p.signal, p.severity, p.pack) == ("ledger_mismatch", "errors", "critical", "custom")


@pytest.mark.parametrize("body,msg", [
    ('[[patterns]]\nkey = "a"\n', "'key' and 'regex' are required"),
    ('[[patterns]]\nkey = "a"\nregex = "("\n', "invalid regex"),
    ('[[patterns]]\nkey = "a"\nregex = "a"\nsignal = "vibes"\n', "signal must be one of"),
    ('[[patterns]]\nkey = "a"\nregex = "a"\nseverity = "none"\n', "severity must be"),
    ("packs = [", "firstsignal.toml"),
])
def test_invalid_files(tmp_path, body, msg):
    f = tmp_path / "firstsignal.toml"
    f.write_text(body)
    with pytest.raises(SettingsError, match=msg):
        settings.load(str(f))
