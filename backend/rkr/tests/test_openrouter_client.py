"""OpenRouter transport tests."""

from __future__ import annotations

from rkr.llm.openrouter_client import chat_completion


def test_chat_completion_uses_openrouter_env(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setattr("rkr.llm.openrouter_client.httpx.Client", FakeClient)

    content = chat_completion([{"role": "user", "content": "hi"}])

    assert content == "ok"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer env-key"
    assert captured["headers"]["X-Title"] == "trust-trace"
    assert captured["json"]["model"] == "openai/gpt-4o-mini"
