"""Adapter for invoking the Scuttle Crab scraper.

Provides:

1. ``ScraperAdapter`` — an abstract interface the orchestrator calls.
2. ``MockScraperAdapter`` — returns synthetic articles for testing.
3. ``ScuttleCrabAdapter`` — submits a ``scrape-company`` job to Scuttle
   Crab's async HTTP API, polls until the job finishes, and returns a
   ``ScrapeResult`` indicating how many articles were delivered.

Scuttle Crab delivers articles **directly** to Tarkov via its own
``deliver_to_tarkov`` bridge — the adapter does *not* return article
payloads.  Instead, ``ScrapeResult.delivered_directly`` tells the
orchestrator that articles already entered the ingestion path and the
manual ``_enqueue_articles`` step should be skipped.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    """Value object returned by every ``ScraperAdapter.scrape`` call."""

    articles: list[dict] = field(default_factory=list)
    delivered_directly: bool = False
    delivered_count: int = 0


class ScraperAdapter(abc.ABC):
    @abc.abstractmethod
    async def scrape(self, query: str, limit: int) -> ScrapeResult:
        """Scrape articles for *query*.

        Implementations that deliver articles to Tarkov on their own should
        return ``ScrapeResult(delivered_directly=True, ...)``.
        """


class MockScraperAdapter(ScraperAdapter):
    """Generates synthetic articles for pipeline testing."""

    async def scrape(self, query: str, limit: int) -> ScrapeResult:
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
        return ScrapeResult(articles=articles)


class ScuttleCrabAdapter(ScraperAdapter):
    """Submits ``scrape-company`` jobs to the Scuttle Crab HTTP API.

    Articles are delivered by Scuttle Crab directly to Tarkov, so this
    adapter returns ``ScrapeResult(delivered_directly=True)``.
    """

    _TERMINAL_STATUSES = frozenset({"succeeded", "failed"})

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 300.0,
        poll_interval: float = 2.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._poll_interval = poll_interval

    async def scrape(self, query: str, limit: int) -> ScrapeResult:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            job_id = await self._submit(client, query)
            summary = await self._poll_until_done(client, job_id)

        delivered = summary.get("delivered", 0) if summary else 0
        logger.info(
            "ScuttleCrabAdapter: job %s finished — delivered %d articles for query=%r",
            job_id, delivered, query,
        )
        return ScrapeResult(delivered_directly=True, delivered_count=delivered)

    async def _submit(self, client, query: str) -> str:
        resp = await client.post(
            f"{self._base_url}/api/v1/commands/scrape-company",
            json={"query": query},
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        job_id = data["job_id"]
        logger.info("ScuttleCrabAdapter: submitted scrape-company job %s for query=%r", job_id, query)
        return job_id

    async def _poll_until_done(self, client, job_id: str) -> dict | None:
        deadline = asyncio.get_event_loop().time() + self._timeout
        url = f"{self._base_url}/api/v1/jobs/{job_id}"

        while True:
            resp = await client.get(url)
            resp.raise_for_status()
            record = resp.json()["data"]
            status = record["status"]

            if status in self._TERMINAL_STATUSES:
                if status == "failed":
                    error = record.get("error", {})
                    logger.error(
                        "ScuttleCrabAdapter: job %s failed — %s: %s",
                        job_id, error.get("code", "unknown"), error.get("message", ""),
                    )
                return record.get("summary")

            if asyncio.get_event_loop().time() > deadline:
                logger.error("ScuttleCrabAdapter: job %s timed out after %.0fs", job_id, self._timeout)
                return None

            await asyncio.sleep(self._poll_interval)
