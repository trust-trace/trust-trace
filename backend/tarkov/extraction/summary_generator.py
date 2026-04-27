"""LLM summary generation for articles."""

from __future__ import annotations

from tarkov.keywords.aml_keywords import AML_KEYWORDS
from tarkov.schemas.parsed_result import LLMSummary
from tarkov.utils.text_utils import split_sentences


class SummaryGenerator:
    """Generates article summaries for source persistence."""

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate_article_summary(self, article_text: str) -> LLMSummary:
        if self.llm_client is not None:
            return self.llm_client.generate_summary(article_text)

        sentences = split_sentences(article_text)
        summary_text = " ".join(sentences[:3]) if sentences else article_text[:300]
        return LLMSummary(
            text=summary_text,
            confidence=0.6,
            key_topics=self.extract_key_topics(summary_text),
        )

    def extract_key_topics(self, summary: str) -> list[str]:
        lowered = summary.lower()
        topics: list[str] = []
        for event_type, keywords in AML_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                topics.append(event_type)
        return topics or ["general_business"]
