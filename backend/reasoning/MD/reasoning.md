# Reasoning

Stores and formats reasoning traces from LLM decisions. Provides audit trail for scoring explanations.

## What it does

1. **Trace Collection** - Captures LLM reasoning decisions and context
2. **Storage** - Persists traces to database for audit
3. **Formatting** - Formats traces for display in frontend

## Key components

- `collectors/` - Different collectors for each module (eem, tarkov, rkr, nsa, market)
- `formatters.py` - Formats reasoning traces for output
- `storage.py` - Database storage for traces
- `session.py` - Session management for reasoning

## Usage

```python
from reasoning import ReasoningTrace

trace = ReasoningTrace(
    module="trust_web",
    firm_id=123,
    decision="Created CONNECTION edge",
    evidence="Both firms share same director",
    confidence=0.85
)
trace.save()
```