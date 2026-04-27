# Usage

`scuttle_crab` currently exposes scaffold commands that validate wiring and default paths.

## Commands

```bash
cargo run -- --help
cargo run -- crawl
cargo run -- crawl --sources-file data/custom-sources.json
cargo run -- fetch-url https://example.com/article
cargo run -- test-source reuters
```

`--sources-file` expects an existing JSON file.

## Output Shape

The intended crawler will emit one article payload per record. The current binary is scaffold-only. Payload metadata should stay operational:

- `section`
- `region`
- `discovery_method`
- `http_status`

Downstream systems own entity extraction, topic classification, and scoring.

## Local Files

- `data/seen_urls.jsonl`: dedup store for normalized URLs
- `data/outbox.jsonl`: outbound payload stream

## Notes

- The current binary is scaffold-first.
- Article collection, normalization, deduplication, and emission are the core responsibilities of the crate.

## Docker Compose

From the repository root:

```bash
docker compose up scuttle-crab
docker compose run --rm scuttle-crab crawl --sources-file data/custom-sources.json
```
