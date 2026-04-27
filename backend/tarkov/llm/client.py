"""LLM client with safe fallback behavior."""

from __future__ import annotations

import json
import os

import httpx

from tarkov.llm.prompts import (
    ARTICLE_SUMMARY_PROMPT,
    COMPANY_MATCH_PROMPT,
    CONNECTION_EXTRACTION_PROMPT,
    CONNECTION_EXTRACTION_HYBRID_PROMPT,
    EVENT_EXTRACTION_PROMPT,
    PERSON_EXTRACTION_PROMPT,
    PERSON_EXTRACTION_HYBRID_PROMPT,
)
from tarkov.schemas.parsed_result import LLMSummary
from tarkov.utils.text_utils import split_sentences


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        *,
        openrouter_base_url: str = "https://openrouter.ai/api/v1",
        openrouter_http_referer: str = "https://github.com/trust-trace/trust-trace",
        openrouter_x_title: str = "trust-trace",
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.openrouter_base_url = openrouter_base_url
        self.openrouter_http_referer = openrouter_http_referer
        self.openrouter_x_title = openrouter_x_title

    def generate_summary(self, article_text: str) -> LLMSummary:
        if not self.api_key:
            sentences = split_sentences(article_text)
            text = " ".join(sentences[:3]) if sentences else article_text[:350]
            return LLMSummary(text=text, confidence=0.55, key_topics=[])
        text = self._complete(ARTICLE_SUMMARY_PROMPT.format(article_text=article_text)).strip()
        return LLMSummary(text=text or article_text[:300], confidence=0.85, key_topics=[])

    def extract_events(self, article_text: str, firm_context: str):
        response = self._complete(EVENT_EXTRACTION_PROMPT.format(article_text=article_text, firm_context=firm_context))
        return self._parse_json_response(response)

    def extract_people(self, article_text: str, event_context: str):
        response = self._complete(PERSON_EXTRACTION_PROMPT.format(text=f"{article_text}\n{event_context}"))
        return self._parse_json_response(response)

    def extract_connections(self, article_text: str, companies: list[str], people: list[str]):
        response = self._complete(
            CONNECTION_EXTRACTION_PROMPT.format(
                text=article_text,
                companies=", ".join(companies),
                people=", ".join(people),
            )
        )
        return self._parse_json_response(response)

    def match_companies(self, article_text: str, candidates: list[dict]):
        response = self._complete(
            COMPANY_MATCH_PROMPT.format(
                text=article_text,
                candidates=json.dumps(candidates, ensure_ascii=False),
            )
        )
        return self._parse_json_response(response)

    def extract_people_hybrid(self, article_text: str, event_context: str, candidates: list[dict]):
        response = self._complete(
            PERSON_EXTRACTION_HYBRID_PROMPT.format(
                text=article_text,
                context=event_context,
                candidates=json.dumps(candidates, ensure_ascii=False),
            )
        )
        return self._parse_json_response(response)

    def extract_connections_hybrid(self, article_text: str, companies: list[str], people: list[str], events: list[str]):
        response = self._complete(
            CONNECTION_EXTRACTION_HYBRID_PROMPT.format(
                text=article_text,
                companies=json.dumps(companies, ensure_ascii=False),
                people=json.dumps(people, ensure_ascii=False),
                events=json.dumps(events, ensure_ascii=False),
            )
        )
        return self._parse_json_response(response)

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def _complete(self, prompt: str) -> str:
        if self.provider == "openai":
            return self._complete_openai(prompt)

        if self.provider == "openrouter":
            return self._complete_openrouter(prompt)

        if self.provider == "anthropic":
            try:
                from anthropic import Anthropic

                client = Anthropic(api_key=self.api_key)
                out = client.messages.create(
                    model=self.model,
                    max_tokens=800,
                    messages=[{"role": "user", "content": prompt}],
                )
                if out.content:
                    return getattr(out.content[0], "text", "")
            except Exception:
                return ""

        return ""

    def _complete_openai(self, prompt: str) -> str:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            out = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            return out.choices[0].message.content or ""
        except Exception:
            return ""

    def _complete_openrouter(self, prompt: str) -> str:
        api_key = self.api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            return ""

        referer = os.environ.get("OPENROUTER_HTTP_REFERER", self.openrouter_http_referer)
        title = os.environ.get("OPENROUTER_X_TITLE", self.openrouter_x_title)
        base_url = os.environ.get("OPENROUTER_BASE_URL", self.openrouter_base_url)

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": referer,
                        "X-Title": title,
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"] or ""
        except Exception:
            return ""

    @staticmethod
    def _parse_json_response(response: str):
        try:
            return json.loads(response)
        except Exception:
            return []
