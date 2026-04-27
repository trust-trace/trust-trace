"""Summary generation helpers."""

from __future__ import annotations

from tarkov.keywords.aml_keywords import AML_KEYWORDS
from tarkov.schemas.parsed_result import LLMSummary
from tarkov.utils.text_utils import split_sentences


class SummaryGenerator:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate_article_summary(self, article_text: str) -> LLMSummary:
        if self.llm_client is not None:
            return self.llm_client.generate_summary(article_text)
        sentences = split_sentences(article_text)
        text = " ".join(sentences[:3]) if sentences else article_text[:300]
        return LLMSummary(text=text, confidence=0.6, key_topics=self.extract_key_topics(text))

    @staticmethod
    def extract_key_topics(summary: str) -> list[str]:
        lowered = summary.lower()
        topics = [event_type for event_type, words in AML_KEYWORDS.items() if any(word in lowered for word in words)]
        return topics or ["general_business"]
