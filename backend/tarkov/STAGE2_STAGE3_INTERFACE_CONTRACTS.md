# Stage 2 -> Stage 3 Interface Contracts

## 1. Stage 2 exit envelope

```json
{
  "job_id": "uuid",
  "correlation_id": "string",
  "schema_version": "1",
  "company_id": 123,
  "article_id": "uuid",
  "processed_at": "2026-04-27T08:15:00Z",
  "events": ["event_id"],
  "people": ["person_id"],
  "connections": ["connection_event_id"],
  "source_refs": ["source_id"],
  "timeline_seed": {
    "company_age_years": 10,
    "initial_snapshot_count": 10
  }
}
```

## 2. Dispatch metadata

Every module call must carry the same metadata headers or top-level fields:

- `X-Correlation-Id`
- `X-Job-Id`
- `X-Schema-Version`
- `X-As-Of`

## 3. Event Classifier contract

### Input
- company context
- event list
- event dates
- source references

### Output
```json
{
  "module": "event_classifier",
  "score": 0.73,
  "confidence": 0.81,
  "analysis_ref": "string",
  "evidence_refs": ["event_id"]
}
```

### Side effect
- Write human-readable event analysis to the event record set.

## 4. NSA contract

### Input
- company context
- person list
- person-event links

### Output
```json
{
  "module": "nsa",
  "score": 0.61,
  "confidence": 0.74,
  "analysis_ref": "string",
  "evidence_refs": ["person_id"]
}
```

### Side effect
- Write per-person analysis text to the person record set.

## 5. TrustWeb contract

### Input
- anchor company
- graph neighborhood within depth 2
- normalized connection edges
- edge intensity values

### Output
```json
{
  "module": "trustweb",
  "score": 0.69,
  "confidence": 0.77,
  "analysis_ref": "string",
  "evidence_refs": ["connection_event_id"],
  "traversal_summary": {
    "depth": 2,
    "nodes_seen": 14,
    "edges_seen": 9
  }
}
```

### Side effect
- Persist edge analysis and traversal metadata for graph visualization.

## 6. Aggregation contract

```json
{
  "job_id": "uuid",
  "company_id": 123,
  "combined_score": 0.68,
  "weights_version": "v1",
  "module_scores": {
    "event_classifier": 0.73,
    "nsa": 0.61,
    "trustweb": 0.69
  }
}
```

Rules:
- weights must be versioned
- raw scores must be stored separately
- missing modules must not erase completed module outputs

## 7. Timeline contract

Each snapshot must include:
- `company_id`
- `snapshot_date`
- `combined_score`
- `module_scores`
- `weights_version`
- `job_id`

The number of snapshots should be driven by company age.

## 8. Logging contract

If anything unexpected happens, log it with:
- `correlation_id`
- `job_id`
- `schema_version`
- module name
- error message

The main pipeline stays centered on the successful handoff path.
