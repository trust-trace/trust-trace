# Usage

`scuttle_crab` now runs as an HTTP service that queues background jobs.

## Startup

```bash
export TARKOV_BASE_URL=http://127.0.0.1:8080
export SCUTTLE_BIND_ADDR=127.0.0.1:3000
cargo run
```

## Endpoints

```bash
curl http://127.0.0.1:3000/api/v1/health

curl -X POST http://127.0.0.1:3000/api/v1/commands/crawl \
  -H 'content-type: application/json' \
  -d '{}'

curl -X POST http://127.0.0.1:3000/api/v1/commands/fetch-url \
  -H 'content-type: application/json' \
  -d '{"url":"https://example.com/article"}'

curl -X POST http://127.0.0.1:3000/api/v1/commands/scrape-company \
  -H 'content-type: application/json' \
  -d '{"query":"Allegro"}'

curl -X POST http://127.0.0.1:3000/api/v1/commands/search-company \
  -H 'content-type: application/json' \
  -d '{"query":"Allegro","news_only":false,"registry_only":false}'

curl -X POST http://127.0.0.1:3000/api/v1/commands/test-source \
  -H 'content-type: application/json' \
  -d '{"source":"reuters"}'

curl http://127.0.0.1:3000/api/v1/jobs/<job-id>
```

## Output Shape

The intended crawler emits one article payload per record to Tarkov. Payload metadata should stay operational:

- `section`
- `region`
- `discovery_method`
- `http_status`

Downstream systems own entity extraction, topic classification, and scoring.

## Local Files

- `data/seen_urls.jsonl`: dedup store for normalized URLs
- `data/outbox.jsonl`: legacy local outbox used by older non-API tests only

## Notes

- The HTTP service is the primary runtime surface.
- Article collection, normalization, deduplication, and emission are the core responsibilities of the crate.

## Docker Compose

From the repository root:

```bash
docker compose up scuttle-crab
docker compose run --rm scuttle-crab crawl --sources-file data/custom-sources.json
docker compose run --rm scuttle-crab fetch-url https://example.com/article
docker compose run --rm scuttle-crab test-source reuters
```

`docker compose up scuttle-crab` runs the default `crawl` command.

`docker compose run --rm scuttle-crab ...` lets you use the same CLI inside Docker with explicit subcommands and arguments.
