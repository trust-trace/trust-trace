# RKR

Risk Keywords Regex - Pre-filter module that scans articles for risk-related keywords before sending to Stage 2.

## What it does

1. **Keyword Scanning** - Reads raw articles from Scuttle Crab
2. **Pattern Matching** - Matches against hardcoded regex keyword patterns
3. **Risk Scoring** - Assigns a risk_score based on matches
4. **Filtering** - Outputs only articles exceeding relevance threshold

## Position in Pipeline

```
Stage 1: Scuttle Crab → articles.jsonl
         ↓
  Step 1.5: RKR → rkr_articles.jsonl (filtered)
         ↓
Stage 2: Tarkov → PostgreSQL
```

## Key components

- `keywords/risk_keywords.py` - Single source of truth for all keyword patterns
- `scanner/regex_engine.py` - Compiles and runs regex patterns
- `scanner/article_scorer.py` - Computes risk_score from matches
- `pipeline/processor.py` - Streaming JSONL processor
- `config.py` - Environment configuration

## Usage

```bash
python -m rkr.main --input articles.jsonl --output filtered.jsonl --threshold 0.3
```

## Score interpretation

- 1.0 = Highest risk (multiple keyword matches)
- 0.0 = No risk detected