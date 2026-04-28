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

Rules:
- Only return explicitly named human people.
- Exclude companies, departments, titles by themselves, and role fragments like "Director Jane" unless a full name is present.
- Prefer full names tied to a title or surrounding evidence.
""".strip()


CONNECTION_EXTRACTION_PROMPT = """
Extract relationships between entities (companies and people) and return ONLY JSON array.
Each object must include:
- entity_a
- entity_b
- relationship_type
- description
- confidence

Entities:
{companies}
{people}

Text:
{text}
""".strip()


COMPANY_MATCH_PROMPT = """
You are resolving company mentions in a news article.
Return ONLY a JSON array of the companies that best match the article.

Each object must include:
- company_name
- ticker
- matched_text
- confidence
- reason

Candidate companies:
{candidates}

Article:
{text}
""".strip()


COMPANY_DISCOVERY_PROMPT = """
You are an AML analyst extracting company names from a news article.
Identify ALL companies, corporations, or business entities mentioned in the text.
Return ONLY a JSON array.

Each object must include:
- company_name (the canonical/official company name)
- ticker (stock ticker if mentioned or known, null otherwise)
- matched_text (the exact text span in the article that refers to this company)
- confidence (0.0-1.0)
- aliases (array of alternative names/spellings found in the text)

Rules:
- Include parent companies, subsidiaries, and any named business entity.
- Do NOT include government agencies, courts, or regulatory bodies as companies.
- Do NOT include people names.
- Prefer official full company names (e.g. "Zondacrypto sp. z o.o." over "Zonda").
- If multiple spelling variants appear (e.g. "Zonda Crypto" and "Zondacrypto"), pick the most official as company_name and put variants in aliases.

Article:
{text}
""".strip()


FIRM_ENRICHMENT_PROMPT = """
You are enriching a company master record.
Use the article context and web search if needed to fill missing company data.
Prefer official registry, exchange, or company sources when verifying identifiers.

Return ONLY a JSON object with any of these keys when you can verify them:
- nip
- regon
- krs
- country
- aliases (array of strings)

Rules:
- Only return fields that are missing or empty in the current record.
- Do not guess identifiers.
- If a value cannot be verified, omit the key.
- Prefer official or authoritative sources.
- Include short source URLs in a "sources" array if you use web search.

Current firm:
{firm_json}

Article context:
{article_text}
""".strip()


PERSON_EXTRACTION_HYBRID_PROMPT = """
You are extracting people from a news article.
Return ONLY a JSON array.

Each object must include:
- name
- role
- description
- confidence
- source_text

Candidate snippets:
{candidates}

Article:
{text}

Event context:
{context}

Rules:
- Only return explicitly named human people.
- Exclude company names and bare roles.
- Do not return fragments like "Director Jane" or "Acme Corp".
- Prefer full names with surrounding role evidence.
""".strip()


CONNECTION_EXTRACTION_HYBRID_PROMPT = """
You are extracting connection events from a news article.
Infer direct relationships and multihop relationships when the article supports them.
Return ONLY a JSON array.

Each object must include:
- connection_type
- entity_1_type
- entity_1_id
- entity_1_name
- entity_2_type
- entity_2_id
- entity_2_name
- relationship_description
- confidence
- intensity

Known companies:
{companies}

Known people:
{people}

Known event context:
{events}

Article:
{text}
""".strip()


