# scuttle_crab Architecture

This document explains how the current crate is organized, what has already been implemented, and how that maps to the longer-term plan in `../SCUTTLE_CRAB.md`.

## Purpose

`scuttle_crab` is a Rust miniapp for collecting news and financial articles that can later feed a downstream company-scoring pipeline.

The intended crawler architecture is intentionally narrow:
- discover articles from curated sources
- fetch and normalize article content
- deduplicate article records across runs
- emit one outbound JSON payload per article

The crate is still in the foundation stage. The payload contract, persistence helpers, and emission path already exist. Discovery, fetching, extraction, and pipeline orchestration are the next layers to implement.

## Current State

Implemented now:
- CLI scaffolding for `crawl`, `fetch-url`, and `test-source`
- default runtime paths for local data files
- outbound payload domain models
- local JSONL outbox writer
- persistent seen-URL hash store
- integration tests for the current building blocks

Not implemented yet:
- HTTP client wrapper
- RSS or page discovery
- HTML extraction
- source-specific extraction hints
- end-to-end crawler pipeline
- structured crawl metrics and fetch error persistence

## High-Level Design

Target flow:

```text
source definitions
    -> discovery
    -> candidate article URLs
    -> URL normalization + dedup check
    -> fetch article
    -> extract article fields
    -> normalize into outbound payload
    -> append payload to JSONL outbox
    -> record canonical URL in seen-URL store
```

Current flow:

```text
main.rs
    -> lib.rs::run()
    -> clap CLI parsing
    -> AppConfig::default()
    -> scaffold response per command

supporting modules already provide:
    - payload schema
    - JSONL output writer
    - seen-URL persistence
```

## Module Map

### Entrypoints

- `src/main.rs`
  - Binary entrypoint.
  - Calls `scuttle_crab::run()`.

- `src/lib.rs`
  - Top-level execution helpers.
  - Parses CLI arguments.
  - Loads `AppConfig` defaults.
  - Routes to the currently scaffolded command behavior.

### CLI And Config

- `src/cli.rs`
  - Defines the public command-line interface with `clap`.
  - Current commands:
    - `crawl`
    - `fetch-url <url>`
    - `test-source <source>`

- `src/config.rs`
  - Stores the current default local file locations.
  - Current defaults:
    - `data/companies.json`
    - `data/seen_urls.jsonl`
    - `data/outbox.jsonl`

### Domain Models

- `src/domain/article.rs`
  - Defines the outbound payload contract.
  - Main types:
    - `ArticlePayload`
    - `ArticleSection`
    - `MetadataSection`
    - `ArticleText`

- `src/domain/source.rs`
  - Defines `SourceInfo` for publisher metadata in each payload.

### Storage

- `src/storage/jsonl.rs`
  - Implements `JsonlOutbox`.
  - Appends exactly one serialized `ArticlePayload` per line.
  - Creates the parent directory when needed.

- `src/storage/seen_urls.rs`
  - Implements `SeenUrlStore`.
  - Loads an in-memory hash set from a JSONL file.
  - Normalizes URLs before lookup and insert.
  - Persists `SeenUrlRecord` entries as one JSON object per line.

### Crawler Logic

- `src/crawler/mod.rs`
  - Namespace for discovery, fetching, extraction, normalization, deduplication, and emission modules.

### Utilities

- `src/utils/url.rs`
  - Normalizes URLs for deduplication.
  - Current normalization:
    - remove fragments
    - lowercase host
    - trim trailing slash on non-root paths

- `src/utils/hash.rs`
  - Hashes normalized URLs with SHA-256.

## Data Contracts

### Outbound Article Payload

The payload shape is already implemented and tested.

```json
{
  "source": {
    "name": "Reuters",
    "domain": "reuters.com",
    "url": "https://www.reuters.com/world/...",
    "credibility_score": 0.92,
    "credibility_label": "high"
  },
  "article": {
    "title": "Company X beats earnings expectations",
    "text": "Full normalized article text here...",
    "language": "en",
    "authors": ["Jane Doe"],
    "published_at": "2026-04-27T08:15:00Z",
    "scraped_at": "2026-04-27T08:16:12Z",
    "canonical_url": "https://www.reuters.com/world/...",
    "word_count": 845
  },
  "metadata": {
    "section": "markets",
    "region": "us",
    "discovery_method": "rss",
    "http_status": 200
  }
}
```

Explicitly excluded from the payload:
- `summary`
- `content_hash`

### Seen-URL Record

The dedup store persists one record per line.

```json
{"url_hash":"abc123...","canonical_url":"https://reuters.com/...","first_seen_at":"2026-04-27T08:16:12Z","source":"Reuters"}
```

## Persistence Model

The crate currently uses local file-based persistence instead of a database.

Rationale:
- low setup cost
- easy local debugging
- straightforward testability
- enough for MVP validation

Current local files:
- `data/companies.json`: reference data for fixed company/ticker matching
- `data/seen_urls.jsonl`: persistent dedup store across runs
- `data/outbox.jsonl`: outbound payload outbox

## Tests

Current tests cover the implemented foundation:
- `tests/cli.rs`: CLI parsing and default output paths
- `tests/jsonl_outbox.rs`: JSONL append behavior and parent directory creation
- `tests/payload_contract.rs`: payload serialization contract
- `tests/seen_urls.rs`: URL normalization and dedup persistence

This is good coverage for the current stage because the crate does not yet have live network or extraction logic.

## Plan Mapping

This section ties the current code to the plan in `../SCUTTLE_CRAB.md`.

### Phase 1: Scope And Architecture Definition

Status: partially implemented.

Implemented:
- outbound payload contract is defined in `src/domain/article.rs`
- source metadata contract is defined in `src/domain/source.rs`
- seen-URL store exists in `src/storage/seen_urls.rs`
- module layout is partially established
- baseline tests exist for payloads and dedup

Still missing:
- `crawler/http.rs`
- `crawler/discovery.rs`
- `crawler/extractor.rs`
- `crawler/pipeline.rs`
- fixture-based extraction test layout

### Phase 2: Project Foundation And Configuration

Status: partially implemented.

Implemented:
- dependency set added in `Cargo.toml`
- CLI added in `src/cli.rs`
- basic config defaults added in `src/config.rs`

Still missing:
- runtime configuration for concurrency, timeout, retry count, and source list
- structured logging setup in execution flow

### Phase 3: Source Discovery Strategy

Status: not implemented.

Next target:
- add source definitions
- start with RSS/Atom discovery
- enforce domain filtering and canonical URL dedup before fetch

### Phase 4: Fetching And Crawl Politeness

Status: not implemented.

Next target:
- add shared `reqwest::Client` wrapper
- support timeout, retry, user-agent, and bounded concurrency

### Phase 5: Article Extraction And Normalization

Status: not implemented.

Next target:
- extract title, metadata, body, and canonical URL from HTML
- normalize the result into `ArticlePayload`

### Phase 6: Company Relevance And Scoring Handoff

Status: not implemented locally.

Downstream systems own entity extraction, event classification, and scoring.

### Phase 7: CLI, Persistence, And Operability

Status: partially implemented.

Implemented:
- CLI command shapes exist
- JSONL outbox exists
- seen-URL persistence exists

Still missing:
- real crawl behavior behind CLI commands
- crawl metrics and structured failure logging
- source authoring documentation

### Phase 8: Testing And Hardening

Status: partially implemented.

Implemented:
- tests for the foundation modules

Still missing:
- fetch failure tests
- extractor fixture tests
- full pipeline integration tests

## How To Extend The Project

Recommended implementation order from here:

1. Add source definitions and discovery mode abstractions.
2. Add a shared HTTP client module.
3. Add extraction helpers that produce `ArticlePayload` inputs.
4. Add a pipeline module that composes dedup, fetch, extract, match, and outbox write.
5. Upgrade the CLI from scaffold outputs to real execution.
6. Add fixture-based and pipeline integration tests.

## Development Notes

Useful commands from `rust/scuttle_crab/`:

```bash
cargo build
cargo check
cargo test
cargo run -- --help
cargo run -- crawl
```

When adding new functionality, prefer extending the existing narrow contracts instead of introducing broader abstractions early. The current crate is easiest to evolve if discovery, fetch, extraction, normalization, deduplication, and persistence stay separate.
