import json

import pytest

from incopilot import ai
from incopilot.analyzer import analyze

META = {"source": "file", "target": "x.log", "since": "n/a"}


@pytest.fixture
def analysis(core, example_log):
    return analyze(example_log.read_text(), core)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "INCOPILOT_AI_KEY", "INCOPILOT_AI_PROVIDER",
                "INCOPILOT_AI_MODEL", "INCOPILOT_AI_BASE_URL"):
        monkeypatch.delenv(var, raising=False)


def test_prompt_contains_summary_but_no_secrets_or_raw_log(analysis, example_log):
    prompt = ai.build_prompt(analysis, META)
    assert prompt.startswith("<findings>") and len(prompt) < ai.MAX_PROMPT_CHARS + 200
    payload = json.loads(prompt.split("<findings>\n")[1].split("\n</findings>")[0])
    assert payload["order_of_first_appearance"][0] == "slow"
    assert "S3cr3tPass" not in prompt and "eyJhbGci" not in prompt
    assert "GET /healthz" not in prompt  # lines that matched nothing are never sent


def test_no_provider_configured_is_a_soft_failure(analysis):
    res = ai.hypothesize(analysis, META)
    assert res.text is None and "no AI provider configured" in res.error


def test_missing_key_is_a_soft_failure(analysis):
    res = ai.hypothesize(analysis, META, provider="anthropic")
    assert res.text is None and "ANTHROPIC_API_KEY" in res.error


def test_anthropic_request_shape(analysis, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    seen = {}

    def post(url, headers, body, timeout):
        seen.update(url=url, headers=headers, body=body)
        return {"content": [{"type": "text", "text": " Pool exhausted. "}]}

    res = ai.hypothesize(analysis, META, post=post)
    assert res.text == "Pool exhausted." and res.provider == "anthropic"
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "k" and seen["body"]["system"] == ai.SYSTEM_PROMPT


def test_openai_compatible_request_shape(analysis, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    seen = {}

    def post(url, headers, body, timeout):
        seen.update(url=url, headers=headers, body=body)
        return {"choices": [{"message": {"content": "Likely the pool."}}]}

    res = ai.hypothesize(analysis, META, model="some-model", post=post)
    assert res.text == "Likely the pool."
    assert seen["url"].endswith("/chat/completions") and seen["headers"]["authorization"] == "Bearer k"
    assert seen["body"]["messages"][0]["role"] == "system"


def test_openai_requires_model(analysis, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert "--ai-model is required" in ai.hypothesize(analysis, META).error


def test_ollama_needs_no_key(analysis):
    res = ai.hypothesize(analysis, META, provider="ollama", model="llama3",
                         post=lambda *a: {"choices": [{"message": {"content": "ok"}}]})
    assert res.text == "ok"


@pytest.mark.parametrize("reply", [{}, {"content": []}, {"content": "nope"}, {"choices": []}])
def test_bad_provider_replies_do_not_raise(analysis, monkeypatch, reply):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    res = ai.hypothesize(analysis, META, post=lambda *a: reply)
    assert res.text is None and res.error


def test_provider_errors_do_not_raise(analysis, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

    def post(*a):
        raise ai.AIError("provider returned HTTP 529")

    assert ai.hypothesize(analysis, META, post=post).error == "provider returned HTTP 529"


def test_plain_http_is_refused_except_localhost():
    with pytest.raises(ai.AIError, match="https"):
        ai._post("http://example.com/v1/messages", {}, {}, 1)
    with pytest.raises(ai.AIError, match="https"):
        ai._post("file:///etc/passwd", {}, {}, 1)
