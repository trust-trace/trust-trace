# NSA

News Sentiment Analysis module. Analyzes sentiment from news articles and sources.

## What it does

1. **Sentiment Scoring** - Analyzes article tone (positive, negative, neutral)
2. **Source Credibility** - Rates source reliability
3. **Impact Assessment** - Measures potential business impact

## Key function

```python
from nsa import analyze_sentiment

result = analyze_sentiment(article_text, source_url)
# Returns sentiment score, credibility rating, impact level
```

## Integration

Called by Stage 3 scoring pipeline to gather additional risk signals from news sentiment.