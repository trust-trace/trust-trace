# RKR — Risk Keywords Regex | Implementation Plan

## Position in Pipeline

```
[Stage 1: Scuttle Crab]   articles.jsonl
            ↓
     [Step 1.5: RKR]       rkr_articles.jsonl
            ↓
   [Stage 2: Tarkov]       PostgreSQL
```

RKR is a standalone Python filter module. It reads raw articles from Scuttle Crab,
scans them against hardcoded keyword-regex patterns, assigns a `risk_score`, and
outputs only articles that exceed the relevance threshold. Tarkov receives pre-filtered
articles instead of raw noise.

---

## File Structure

```
backend/
└── rkr/
    ├── __init__.py
    │
    ├── main.py                          # CLI entry point
    │
    ├── keywords/
    │   ├── __init__.py
    │   └── risk_keywords.py             # Single source of truth for all keywords
    │
    ├── scanner/
    │   ├── __init__.py
    │   ├── regex_engine.py              # Compiles patterns once, runs finditer matching
    │   └── article_scorer.py            # Computes risk_score from matches
    │
    ├── pipeline/
    │   ├── __init__.py
    │   └── processor.py                 # Streaming JSONL → RKR → filtered output
    │
    ├── schemas/
    │   ├── __init__.py
    │   └── rkr_result.py                # Pydantic: RkrMatch, RkrResult, EnrichedArticle
    │
    └── tests/
        ├── __init__.py
        ├── fixtures/
        │   └── sample_articles.jsonl
        ├── test_regex_engine.py
        ├── test_scorer.py
        └── test_processor.py
```

---

## File Responsibilities

| File | Responsibility |
|---|---|
| `risk_keywords.py` | ~145 EN+PL keywords with category, compiled regex pattern, and weight. Only place to edit keywords. |
| `rkr_result.py` | Pydantic models: `RkrMatch` (one matched keyword), `RkrResult` (article result), `EnrichedArticle` (original article + `rkr` field) |
| `regex_engine.py` | Compiles all patterns **once** at startup. Method `scan(text, title)` returns `list[RkrMatch]`. Title hits get ×1.5 multiplier. |
| `article_scorer.py` | Computes `risk_score` (0.0–1.0) from `list[RkrMatch]` and decides `passed_threshold` (default: ≥ 0.3) |
| `processor.py` | Reads `articles.jsonl` line by line (streaming). For each article: engine → scorer → enriches with `rkr` field. Above threshold → `rkr_articles.jsonl`, below → `rkr_rejected.jsonl` |
| `main.py` | CLI: `scan`, `stats` (dry-run), `list-keywords` |

---

## Keyword Categories

| Category | Weight | Description |
|---|---|---|
| `terrorism_financing` | 1.0 | Financing of terrorist activity |
| `sanctions` | 0.95 | OFAC, SDN, EU/UN sanctions lists |
| `money_laundering` | 0.9 | AML core terms, structuring, smurfing |
| `fraud` | 0.85 | Ponzi, embezzlement, market manipulation |
| `corruption` | 0.8 | Bribery, kickbacks, abuse of power |
| `regulatory_action` | 0.75 | KNF, SEC, FCA, enforcement actions |
| `tax_evasion` | 0.7 | Offshore, shell companies, VAT carousel |
| `cybercrime` | 0.65 | Ransomware, phishing, data breach |
| `bankruptcy` | 0.6 | Insolvency, liquidation, receivership |

---

## Output Format

Original Scuttle Crab article enriched with an `rkr` field:

```json
{
  "source": { "..." },
  "article": { "..." },
  "metadata": { "..." },
  "rkr": {
    "matched_keywords": [
      {
        "keyword": "money laundering",
        "category": "money_laundering",
        "weight": 0.9,
        "in_title": true,
        "context": "...accused of money laundering by..."
      }
    ],
    "categories_hit": ["money_laundering", "fraud"],
    "risk_score": 0.76,
    "passed_threshold": true
  }
}
```

---

## CLI

```bash
# Main usage
python -m rkr.main scan --input articles.jsonl --output rkr_articles.jsonl

# Custom threshold
python -m rkr.main scan --input articles.jsonl --threshold 0.4

# Dry-run: statistics only, no file write
python -m rkr.main stats --input articles.jsonl

# Inspect keywords by category
python -m rkr.main list-keywords --category fraud
```

---

## Scoring Logic

```
title_multiplier = 1.5   # keyword in title is worth more
base_score = sum(match.weight * (title_multiplier if match.in_title else 1.0)
                 for match in matches)
risk_score = clamp(base_score / normalization_constant, 0.0, 1.0)
passed_threshold = risk_score >= THRESHOLD  # default 0.3
```

---

## Integration with Tarkov (Stage 2)

- Tarkov reads `rkr_articles.jsonl` instead of raw `articles.jsonl`
- `article["rkr"]["categories_hit"]` acts as a hint — Tarkov knows which event types to look for without scanning all categories
- `rkr.risk_score` can seed `event.risk_level` as a baseline before Tarkov's own calculation
- Tarkov can skip LLM extraction for low `risk_score` articles (cost optimization)

---

## Integration with DB Schema

The existing `risk_keywords` table in `001_initial_schema.sql` can be seeded from `risk_keywords.py`:

```sql
CREATE TABLE risk_keywords (
    id          BIGINT,
    keyword     VARCHAR(255) UNIQUE,
    category    VARCHAR(100),
    base_weight DECIMAL(4,3)
);
```

For MVP, keywords are hardcoded in Python only. DB seeding is optional.

---

## Implementation Order

1. `risk_keywords.py` — keyword list (foundation of everything)
2. `rkr_result.py` — Pydantic schemas (data contract)
3. `regex_engine.py` — compile + match
4. `article_scorer.py` — scoring
5. `processor.py` — streaming pipeline
6. `main.py` — CLI
7. tests + fixtures
