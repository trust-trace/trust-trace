# Scraper API

`scuttle_crab` runs as an HTTP service that queues background jobs and delivers payloads directly to Tarkov.

## Requirements

Required environment variable:

```bash
export TARKOV_BASE_URL=http://127.0.0.1:8080
```

Optional environment variables:

```bash
export SCUTTLE_BIND_ADDR=127.0.0.1:3000
export TARKOV_INGEST_PATH=/v1/articles
export TARKOV_TIMEOUT_SECS=15
export SCUTTLE_COMPANY_ARTICLE_LIMIT=10
```

## Start The Service

```bash
cargo run
```

## Health Check

```bash
curl http://127.0.0.1:3000/api/v1/health
```

Expected response: `200 OK`

## Queue Commands

### Crawl

```bash
curl -X POST http://127.0.0.1:3000/api/v1/commands/crawl \
  -H 'content-type: application/json' \
  -d '{}'
```

With explicit sources file:

```bash
curl -X POST http://127.0.0.1:3000/api/v1/commands/crawl \
  -H 'content-type: application/json' \
  -d '{"sources_file":"data/custom-sources.json"}'
```

### Fetch One URL

```bash
curl -X POST http://127.0.0.1:3000/api/v1/commands/fetch-url \
  -H 'content-type: application/json' \
  -d '{"url":"https://example.com/article"}'
```

### Scrape Company Registry

```bash
curl -X POST http://127.0.0.1:3000/api/v1/commands/scrape-company \
  -H 'content-type: application/json' \
  -d '{"query":"Allegro"}'
```

### Search Company

```bash
curl -X POST http://127.0.0.1:3000/api/v1/commands/search-company \
  -H 'content-type: application/json' \
  -d '{"query":"Allegro"}'
```

News only:

```bash
curl -X POST http://127.0.0.1:3000/api/v1/commands/search-company \
  -H 'content-type: application/json' \
  -d '{"query":"Allegro","news_only":true}'
```

Registry only:

```bash
curl -X POST http://127.0.0.1:3000/api/v1/commands/search-company \
  -H 'content-type: application/json' \
  -d '{"query":"Allegro","registry_only":true}'
```

### Test Source

```bash
curl -X POST http://127.0.0.1:3000/api/v1/commands/test-source \
  -H 'content-type: application/json' \
  -d '{"source":"reuters"}'
```

## Job Lifecycle

Every command endpoint returns `202 Accepted` and a job identifier:

```json
{
  "data": {
    "job_id": "6df44d72-2eb8-4ee6-bf8f-b9e92c6d4ca2",
    "command": "search-company",
    "status": "queued"
  }
}
```

Poll job state:

```bash
curl http://127.0.0.1:3000/api/v1/jobs/6df44d72-2eb8-4ee6-bf8f-b9e92c6d4ca2
```

Example success response:

```json
{
  "data": {
    "job_id": "6df44d72-2eb8-4ee6-bf8f-b9e92c6d4ca2",
    "command": "search-company",
    "status": "succeeded",
    "started_at": "2026-04-28T12:00:00Z",
    "finished_at": "2026-04-28T12:00:10Z",
    "summary": {
      "delivered": 4,
      "delivery_failed": 0,
      "message": "search-company finished: delivered=4"
    },
    "error": null
  }
}
```

Example failure response:

```json
{
  "data": {
    "job_id": "6df44d72-2eb8-4ee6-bf8f-b9e92c6d4ca2",
    "command": "fetch-url",
    "status": "failed",
    "started_at": "2026-04-28T12:00:00Z",
    "finished_at": "2026-04-28T12:00:01Z",
    "summary": null,
    "error": {
      "code": "job_failed",
      "message": "TARKOV_BASE_URL must be configured for API execution"
    }
  }
}
```

## Notes

- API mode delivers directly to Tarkov.
- API mode does not write to `data/outbox.jsonl`.
- Seen-URL deduplication still uses `data/seen_urls.jsonl`.
- Job state is in memory and is lost if the process restarts.
