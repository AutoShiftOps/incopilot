import pytest

from incopilot.redact import Redactor


@pytest.mark.parametrize("text,secret", [
    ("postgres://app:hunter2pass@db:5432/x", "hunter2pass"),
    ("Authorization: Bearer abcdef1234567890", "abcdef1234567890"),
    ('{"password": "p@ssw0rd!"}', "p@ssw0rd!"),
    ("api_key=sk_live_abc123 other=1", "sk_live_abc123"),
    ("token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.abcDEF123456ghiJKL", "eyJhbGci"),
    ("aws key AKIAIOSFODNN7EXAMPLE used", "AKIAIOSFODNN7EXAMPLE"),
    ("github ghp_abcdefghijklmnopqrstuvwxyz0123456789", "ghp_abcdefghij"),
    ("mail from jane.doe@example.com", "jane.doe@example.com"),
])
def test_secrets_are_masked(text, secret):
    assert secret not in Redactor()(text)


def test_non_secrets_survive():
    line = "ERROR [api] connect() failed (111: Connection refused) while connecting to db.internal"
    assert Redactor()(line) == line


def test_ips_only_when_asked():
    assert "10.0.3.17" in Redactor()("client 10.0.3.17")
    assert Redactor(redact_ips=True)("client 10.0.3.17") == "client <IP>"


def test_disabled_and_extra_rules():
    assert Redactor(enabled=False)("password=abc") == "password=abc"
    assert Redactor(extra=[r"cust-\d+"])("order for cust-99812") == "order for <REDACTED>"
