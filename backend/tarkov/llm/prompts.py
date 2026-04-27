"""Prompt templates for LLM extraction."""

ARTICLE_SUMMARY_PROMPT = """
Write a concise 2-3 sentence summary of this article focusing on business and regulatory events.

Article:
{article_text}

Summary (max 3 sentences):
""".strip()


EVENT_EXTRACTION_PROMPT = """
You are an AML analyst. Extract fraud and AML-related events from the article.
For each event include:
1. event_type
2. risk_level (1-10)
3. title
4. description
5. source_text (direct quote)
6. confidence (0.0-1.0)

Article: {article_text}
Firm Context: {firm_context}

Respond as JSON array.
""".strip()


PERSON_EXTRACTION_PROMPT = """
Extract all people mentioned in this text and include:
- name
- role
- description
- source_text
- confidence

Text:
{text}

Respond as JSON array.
""".strip()


CONNECTION_EXTRACTION_PROMPT = """
Identify connections between entities in this article.
Connection types: shared_director, business_relationship, activity_link.

Text: {text}
Companies: {companies}
People: {people}

Respond as JSON array.
""".strip()
