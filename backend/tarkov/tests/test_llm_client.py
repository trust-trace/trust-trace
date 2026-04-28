"""LLM transport tests."""

from __future__ import annotations

from types import SimpleNamespace

from tarkov.llm.client import LLMClient


def test_openrouter_transport_uses_env_key_and_headers(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "hello from openrouter"}}]}

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
    monkeypatch.setattr("tarkov.llm.client.httpx.Client", FakeClient)

    client = LLMClient(provider="openrouter", model="openai/gpt-4o-mini", api_key="")
    text = client._complete("test prompt")

    assert text == "hello from openrouter"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer env-key"
    assert captured["json"]["model"] == "openai/gpt-4o-mini"


def test_openrouter_transport_enables_web_search(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, json):
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    monkeypatch.setattr("tarkov.llm.client.httpx.Client", FakeClient)

    client = LLMClient(provider="openrouter", model="openai/gpt-4o-mini", api_key="", web_search_enabled=True)
    client._complete("test prompt")

    assert captured["json"]["model"] == "openrouter/auto"
    assert captured["json"]["plugins"] == [{"id": "web"}]
