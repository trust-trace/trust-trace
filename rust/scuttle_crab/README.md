# scuttle_crab

Rust miniapp for collecting news and financial articles for downstream processing.

## Status

Current crate state:
- core dependencies are configured in `Cargo.toml`
- CLI scaffolding exists for `crawl`, `fetch-url`, and `test-source`
- outbound payload structs are implemented in `src/domain/`
- local JSONL writing and seen-URL persistence are implemented in `src/storage/`
- collection, normalization, deduplication, and payload emission are the main data-flow concerns
- the full crawler pipeline is still in progress

The architecture and longer-term MVP decisions are documented in `../SCUTTLE_CRAB.md`. A crate-specific architecture guide now lives in `docs/ARCHITECTURE.md`. This README describes the code that exists today and how to use it.

## MVP Goal

Build a Rust crawler that:
- discovers articles from curated finance/news sources
- extracts normalized article text and metadata
- normalizes and deduplicates article records
- avoids re-scraping the same article twice
- writes one outbound JSON payload per article for a future endpoint

## What Exists Today

Implemented pieces:
- `src/cli.rs`: command-line interface and subcommands
- `src/config.rs`: default file locations for local data
- `src/domain/company.rs`: company reference records and loader used by the scaffold/config path
- `src/domain/`: outbound payload and source data models
- `src/storage/jsonl.rs`: append one payload per line to a JSONL outbox
- `src/storage/seen_urls.rs`: persist normalized URL hashes to skip duplicates across runs
- `src/utils/`: URL normalization and SHA-256 hashing helpers
- `tests/`: integration tests for CLI parsing, payload contract, JSONL output, company loading, and seen-URL storage

Not implemented yet:
- HTTP fetching
- feed or page discovery
- HTML extraction
- end-to-end crawl pipeline
- source-specific extraction rules

## Project Layout

```text
src/
  main.rs                # binary entrypoint
  lib.rs                 # top-level run helpers
  cli.rs                 # clap CLI definitions
  config.rs              # default data paths
  crawler/
    mod.rs               # crawler namespace
  domain/
    article.rs           # outbound payload schema
    source.rs            # source metadata in outbound payloads
  storage/
    jsonl.rs             # JSONL outbox writer
    seen_urls.rs         # persistent seen-URL store
  utils/
    hash.rs              # SHA-256 helpers
    url.rs               # URL normalization helpers
tests/
  cli.rs
  jsonl_outbox.rs
  payload_contract.rs
  seen_urls.rs
```

For a module-by-module explanation and plan mapping, see `docs/ARCHITECTURE.md`.

## Build And Test

From this directory:

```bash
cargo build
```

Run the binary:

```bash
cargo run
```

Run all tests:

```bash
cargo test
```

Run one test file:

```bash
cargo test --test seen_urls
```

Run tests matching a name:

```bash
cargo test seen_urls
```

Fast compile check:

```bash
cargo check
```

## CLI Usage

The binary currently exposes scaffold commands that confirm wiring and default paths.

Working directory:

```bash
cd rust/scuttle_crab
```

Show help:

```bash
cargo run -- --help
```

Run the default crawl using `data/sources.json`:

```bash
cargo run -- crawl
```

Run crawl with an explicit JSON file of source links:

```bash
cargo run -- crawl --sources-file data/custom-sources.json
```

The file passed to `--sources-file` must already exist.

Use a custom file when you want to hand the crawler a specific set of pages or feeds without replacing the default `data/sources.json`.

Example output:

```text
crawl scaffold ready: companies=data/companies.json, seen_urls=data/seen_urls.jsonl, outbox=data/outbox.jsonl
```

Debug a single URL command shape:

```bash
cargo run -- fetch-url https://example.com/article
```

Test a named source command shape:

```bash
cargo run -- test-source reuters
```

Supported CLI patterns:

```bash
cargo run -- crawl
cargo run -- crawl --sources-file data/custom-sources.json
cargo run -- fetch-url https://example.com/article
cargo run -- test-source reuters
```

## Docker Compose

From the repo root, start the crawler with its default command:

```bash
docker compose up scuttle-crab
```

Use Docker Compose but still call the CLI directly:

```bash
docker compose run --rm scuttle-crab crawl --sources-file data/custom-sources.json
docker compose run --rm scuttle-crab fetch-url https://example.com/article
docker compose run --rm scuttle-crab test-source reuters
```

How this works:
- the service defined in `/home/tmk/hackaton/docker-compose.yml` already points at the `scuttle_crab` binary
- `docker compose up scuttle-crab` runs the default `crawl` command
- `docker compose run --rm scuttle-crab ...` overrides that default and passes the rest of the arguments to the CLI
- `./rust/scuttle_crab` is bind-mounted into the container, so files under `data/` are available in both places

When using `--sources-file` with Docker, use a path relative to `rust/scuttle_crab`, for example `data/custom-sources.json`.

## How The Current Code Fits Together

Current flow:
1. `src/main.rs` calls `scuttle_crab::run()`.
2. `src/lib.rs` parses CLI arguments and loads default config.
3. The selected command returns a scaffold response.
4. Supporting modules already implement the data structures and persistence helpers that the future crawler pipeline will use.

Today, the most reusable parts are the payload contract, the JSONL outbox, the seen-URL store, and the article emission path.

## Core Data Files

Default local files:
- `data/companies.json`: company reference list used as a local input/config path
- `data/seen_urls.jsonl`: persistent dedup store of normalized URL hashes
- `data/outbox.jsonl`: one outbound payload per line

The app currently reports these paths through the `crawl` scaffold command. The helper modules are already able to create parent directories for JSONL-based storage when needed.

## Payload Contract

Each article is shaped as one outbound JSON payload with three sections:
- `source`
- `article`
- `metadata`

The serialization contract is tested in `tests/payload_contract.rs`.

Explicitly excluded from the payload:
- `summary`
- `content_hash`

## Dedup Behavior

The current seen-URL store works like this:
1. normalize the URL
2. hash the normalized URL with SHA-256
3. check whether the hash already exists in the local JSONL store
4. append a new record only after a successful first insert

This behavior is covered in `tests/seen_urls.rs`.

## Planned Stack

Core crates:
- `tokio`
- `reqwest`
- `scraper`

Recommended supporting crates:
- `serde`
- `serde_json`
- `clap`
- `tracing`
- `tracing-subscriber`
- `thiserror`
- `anyhow`
- `url`
- `chrono`
- `sha2`

Optional later:
- `feed-rs`
- `governor`

Example `data/companies.json`:

```json
[
  {
    "name": "Apple",
    "ticker": "AAPL",
    "aliases": ["Apple", "Apple Inc.", "NASDAQ:AAPL"],
    "exchange": "NASDAQ",
    "country": "US",
    "is_active": true
  }
]
```

## Source Discovery Direction

Recommended MVP order:
1. RSS/Atom feeds
2. Curated landing pages with selectors
3. Sitemap support later

Do not start with an open web crawler.

## Next Implementation Steps

1. Add feed or page discovery
2. Add HTTP fetching with retries, timeouts, and politeness controls
3. Add HTML extraction into the existing payload contract
4. Wire collection, normalization, and dedup into an end-to-end pipeline
5. Add fixture-based extraction tests
6. Extend the CLI from scaffold behavior to real crawl behavior

## Notes

- The current implementation is intentionally narrow and test-backed.
- The README describes the code that exists today plus the immediate next steps.
- The detailed product and architecture plan lives in `../SCUTTLE_CRAB.md`.
