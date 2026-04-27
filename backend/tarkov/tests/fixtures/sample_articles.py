from __future__ import annotations

from datetime import datetime

from tarkov.schemas.article import ArticleIn


SAMPLE_ARTICLE_1 = ArticleIn(
    source={
        "name": "Global Business Daily",
        "domain": "example.com",
        "url": "https://example.com/articles/acme-probe",
        "credibility_score": 0.82,
        "credibility_label": "high",
    },
    article={
        "title": "Acme Corp faces fraud and money laundering allegations",
        "text": (
            "CEO John Smith of Acme Corp is under investigation for fraud. "
            "Regulators also flagged suspicious transaction patterns suggesting money laundering. "
            "Director Jane Doe denied wrongdoing."
        ),
        "published_at": datetime(2025, 10, 1, 8, 0, 0),
        "scraped_at": datetime(2025, 10, 1, 9, 0, 0),
        "canonical_url": "https://example.com/articles/acme-probe",
        "authors": ["Alice Reporter"],
        "language": "en",
    },
    metadata={
        "section": "investigations",
        "tags": ["fraud", "aml"],
        "tickers": ["ACME"],
        "companies": ["Acme Corp"],
        "region": "EU",
        "discovery_method": "crawler",
        "http_status": 200,
    },
)
