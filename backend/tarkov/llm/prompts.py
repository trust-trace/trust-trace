"""Prompt templates used by the optional LLM integration."""

ARTICLE_SUMMARY_PROMPT = """
You are an AML analyst assistant.
Summarize the article in 2-3 sentences with focus on compliance, fraud, sanctions, or investigation risk.

Article:
{article_text}

Return plain text only.
""".strip()


EVENT_EXTRACTION_PROMPT = """
You are an AML analyst.
Extract risk-relevant events from the article and return ONLY JSON array.

Each object must include:
- event_type
- title
- description
- risk_level (1-10)
- confidence (0.0-1.0)
- source_text (direct quote)

Firm context:
{firm_context}

Article:
{article_text}
""".strip()


PERSON_EXTRACTION_PROMPT = """
Extract people from the text and return ONLY JSON array.
Each object must include:
- name
- role
- description
- confidence
- source_text

Text:
{text}
""".strip()


