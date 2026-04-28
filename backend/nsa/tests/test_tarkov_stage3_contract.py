from __future__ import annotations

import pytest

from tarkov.pipeline.stage3_clients import NSAClient


@pytest.mark.asyncio
async def test_nsa_client_posts_company_score_payload(monkeypatch) -> None:
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json():
            return {"status": "ok"}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("requests.post", fake_post)

    client = NSAClient("https://nsa.example.test/")
    result = await client.score_company(42, "cid-123")

    assert captured == {
        "url": "https://nsa.example.test/score/company",
        "json": {"correlation_id": "cid-123", "firm_id": 42},
        "timeout": 15,
    }
    assert result == {"status": "ok"}
