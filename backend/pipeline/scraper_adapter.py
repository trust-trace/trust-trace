"""Adapter for invoking the Scuttle Crab scraper.

The Rust crate (``rust/scuttle_crab/``) does not yet have HTTP fetching or
keyword search, so this module provides:

1. ``ScraperAdapter`` — an abstract interface the orchestrator calls.
2. ``MockScraperAdapter`` — returns synthetic articles for testing.
3. ``HttpScraperAdapter`` — will call Scuttle Crab's HTTP API once available.

Each returned article is a dict matching the ``ArticleIn`` Pydantic schema
accepted by ``POST /v1/articles``.
"""

from __future__ import annotations

import abc
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ScraperAdapter(abc.ABC):
    @abc.abstractmethod
    async def scrape(self, query: str, limit: int) -> list[dict]:
        """Return up to *limit* article payloads for *query*."""


class MockScraperAdapter(ScraperAdapter):
    """Generates synthetic articles for pipeline testing."""

    async def scrape(self, query: str, limit: int) -> list[dict]:
        articles: list[dict] = []
        now = datetime.utcnow()
        for i in range(min(limit, 5)):
            article_id = str(uuid.uuid4())
            published = now - timedelta(days=(limit - i) * 7)
            articles.append({
                "source": {
                    "url": f"https://mock-news.example.com/{article_id}",
                    "retrieved_at": now.isoformat(),
                },
                "article": {
                    "title": f"[Mock] {query} — Article {i + 1}",
                    "text": (
                        f"Article about {query}. "
                        f"This company has been involved in recent financial activities. "
                        f"Regulators are monitoring the situation closely. "
                        f"Sources indicate potential compliance concerns related to {query}."
                    ),
                    "language": "en",
                    "published_at": published.isoformat(),
                    "canonical_url": None,
                },
                "metadata": {
                    "request_id": article_id,
                    "correlation_id": article_id,
                    "scraped_at": now.isoformat(),
                    "region": "EU",
                    "discovery_method": "mock",
                    "http_status": 200,
                },
            })
        logger.info("MockScraperAdapter: generated %d articles for query=%r", len(articles), query)
        return articles


class HttpScraperAdapter(ScraperAdapter):
    """Calls Scuttle Crab's HTTP API (not yet available)."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def scrape(self, query: str, limit: int) -> list[dict]:
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base_url}/scrape",
                json={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            return resp.json().get("articles", [])
