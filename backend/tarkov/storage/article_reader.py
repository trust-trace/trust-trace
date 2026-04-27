"""Article reader for JSONL or API sources."""

from __future__ import annotations

import json
from typing import Iterator

import requests

from tarkov.schemas.article import ArticleIn


class ArticleReader:
    def __init__(self, source: str, path: str):
        self.source = source
        self.path = path

    def read_articles(self) -> Iterator[ArticleIn]:
        if self.source == "jsonl":
            with open(self.path, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    yield ArticleIn.model_validate(json.loads(line))
            return

        if self.source == "api":
            response = requests.get(self.path, timeout=30)
            response.raise_for_status()
            payload = response.json()
            for item in payload:
                yield ArticleIn.model_validate(item)
            return

        raise ValueError(f"Unsupported source type: {self.source}")

    def read_article_batch(self, batch_size: int = 100) -> Iterator[list[ArticleIn]]:
        batch: list[ArticleIn] = []
        for article in self.read_articles():
            batch.append(article)
            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch
