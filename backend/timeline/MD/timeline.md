# Timeline

Date-bucketing logic used by EEM and TrustWeb for temporal analysis. Groups events into time buckets for visualization and scoring.

## What it does

Divides a firm's lifetime into equal time buckets (default: 8 buckets) for:
- Timeline visualization in frontend
- Temporal scoring in EEM and TrustWeb
- Event grouping by time period

## Key function

```python
from timeline.buckets import compute_timeline_buckets, TimelineBucket

buckets = compute_timeline_buckets(firm_created_at, as_of=None, n_buckets=8)
# Returns list of TimelineBucket with index, start, end, label
```

## Bucket structure

- `index` - Bucket number (0 to n_buckets-1)
- `start` - Inclusive start datetime
- `end` - Exclusive end datetime (last bucket includes today)
- `label` - Human-readable label like "2019-03 → 2020-03"