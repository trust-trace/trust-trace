"""Tests for scraper adapter."""

import asyncio

import pytest

from pipeline.scraper_adapter import MockScraperAdapter


class TestMockScraperAdapter:
    def test_returns_articles(self):
        adapter = MockScraperAdapter()
        articles = asyncio.run(adapter.scrape("Orion Capital", 5))
        assert len(articles) == 5

    def test_respects_limit(self):
        adapter = MockScraperAdapter()
        articles = asyncio.run(adapter.scrape("Test", 3))
        assert len(articles) == 3

    def test_caps_at_5(self):
        adapter = MockScraperAdapter()
        articles = asyncio.run(adapter.scrape("Test", 100))
        assert len(articles) == 5

    def test_article_structure(self):
        adapter = MockScraperAdapter()
        articles = asyncio.run(adapter.scrape("TestCo", 1))
        art = articles[0]
        assert "source" in art
        assert "article" in art
        assert "metadata" in art
        assert "url" in art["source"]
        assert "title" in art["article"]
        assert "text" in art["article"]
        assert "TestCo" in art["article"]["title"]
        assert "TestCo" in art["article"]["text"]
