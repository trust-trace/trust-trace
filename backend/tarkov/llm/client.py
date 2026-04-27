"""LLM client wrapper supporting OpenAI/Anthropic fallback behavior."""

from __future__ import annotations

import json

from tarkov.llm.prompts import (
    ARTICLE_SUMMARY_PROMPT,
    CONNECTION_EXTRACTION_PROMPT,
    EVENT_EXTRACTION_PROMPT,
    PERSON_EXTRACTION_PROMPT,
)
from tarkov.schemas.parsed_result import LLMSummary
from tarkov.utils.text_utils import split_sentences


class LLMClient:
    def __init__(self, provider: str, model: str, api_key: str):
        self.provider = provider
        self.model = model
        self.api_key = api_key

    def generate_summary(self, article_text: str) -> LLMSummary:
        if not self.api_key:
            sentences = split_sentences(article_text)
            text = " ".join(sentences[:3]) if sentences else article_text[:350]
            return LLMSummary(text=text, confidence=0.55, key_topics=[])

        prompt = ARTICLE_SUMMARY_PROMPT.format(article_text=article_text)
        text = self._complete(prompt)
        return LLMSummary(text=text.strip(), confidence=0.85, key_topics=[])

    def extract_events(self, article_text: str, firm_context: str):
        prompt = EVENT_EXTRACTION_PROMPT.format(article_text=article_text, firm_context=firm_context)
        response = self._complete(prompt)
        return self._parse_json_response(response)

    def extract_people(self, article_text: str, event_context: str):
        prompt = PERSON_EXTRACTION_PROMPT.format(text=article_text + "\n" + event_context)
        response = self._complete(prompt)
        return self._parse_json_response(response)

    def extract_connections(self, article_text: str, companies: list[str], people: list[str]):
        prompt = CONNECTION_EXTRACTION_PROMPT.format(
            text=article_text,
            companies=", ".join(companies),
            people=", ".join(people),
        )
        response = self._complete(prompt)
        return self._parse_json_response(response)

    def _complete(self, prompt: str) -> str:
        if self.provider == "openai":
            try:
                from openai import OpenAI

                client = OpenAI(api_key=self.api_key)
                result = client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                )
                return result.choices[0].message.content or ""
            except Exception:
                return ""

        if self.provider == "anthropic":
            try:
                from anthropic import Anthropic

                client = Anthropic(api_key=self.api_key)
                message = client.messages.create(
                    model=self.model,
                    max_tokens=800,
                    messages=[{"role": "user", "content": prompt}],
                )
                if message.content:
                    return getattr(message.content[0], "text", "")
            except Exception:
                return ""

        return ""

    @staticmethod
    def _parse_json_response(response: str):
        try:
            return json.loads(response)
        except Exception:
            return []
