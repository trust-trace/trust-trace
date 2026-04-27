# SCUTTLE_CRAB Implementation Plan

**Goal:** Build a Rust crawler that collects news and financial articles for downstream company scoring.

**Architecture:** Start with curated source discovery instead of open-ended crawling. Keep the crawler focused on discovery, fetching, extraction, normalization, and relevance tagging, while treating scoring as a separate downstream stage. The miniapp should produce a minimal outbound JSON payload per article and maintain a local persistent seen-URL hash store to avoid re-scraping the same article.

**Tech Stack:** `tokio`, `reqwest`, `scraper`, `serde`, `serde_json`, `clap`, `tracing`, `thiserror`, `url`, `chrono`, `sha2`, optionally `feed-rs` and a rate-limiter crate.

## Requirements Restatement
Build a Rust-based crawler for collecting news and financial articles that can later feed a company-scoring pipeline. Start from the existing `scuttle_crab` crate and design an MVP that uses `reqwest` for HTTP, `tokio` for async execution, and `scraper` for HTML parsing, while leaving room for stronger source adapters, deduplication, and entity/company matching. The crawler should prioritize reliable article discovery, normalized article extraction, crawl politeness, and a clean output format that downstream scoring can consume.

## Implementation Phases

[Phase 1: Scope and architecture definition]
- Step 1.1: Define the MVP crawl scope in `rust/SCUTTLE_CRAB.md` and later mirror it in code: which sources are allowed (RSS feeds, sitemap pages, category pages, direct URLs), what counts as an “article”, and what output fields are required.
- Step 1.2: Lock the normalized article contract for `scuttle_crab` around the future endpoint payload and internal crawler needs.
- Step 1.3: Define the outbound JSON payload for one article per POST. Recommended payload shape:
  - `source`: source identity and credibility
  - `article`: article content and timestamps
  - `metadata`: optional enrichment fields
- Step 1.4: Required outbound payload fields:
  - `source.name`
  - `source.domain`
  - `source.url`
  - `source.credibility_score`
  - `source.credibility_label`
  - `article.title`
  - `article.text`
  - `article.published_at`
  - `article.scraped_at`
- Step 1.5: Recommended optional outbound payload fields:
  - `article.authors`
  - `article.language`
  - `article.canonical_url`
  - `article.word_count`
  - `metadata.section`
  - `metadata.tags`
  - `metadata.tickers`
  - `metadata.companies`
  - `metadata.region`
  - `metadata.discovery_method`
  - `metadata.http_status`
- Step 1.6: Explicitly exclude `summary` and `content_hash` from the outbound payload.
- Step 1.7: Choose the first storage/output target for the MVP. Recommendation: newline-delimited JSON (`articles.jsonl`) before adding SQLite or Postgres.
- Step 1.8: Add a local persistent seen-URL hash store so the crawler can skip articles that were already scraped in earlier runs.
- Step 1.9: Add a local company reference store for ticker and alias matching. Recommendation: `data/companies.json`, loaded into memory at startup.
- Step 1.10: Start with a fixed list of companies/tickers for MVP matching, not open-ended company detection.
- Step 1.11: Define the initial crate/module layout under `rust/scuttle_crab/src/`:
  - `main.rs` - CLI entrypoint
  - `cli.rs` - command parsing
  - `config.rs` - runtime configuration
  - `crawler/mod.rs` - orchestration
  - `crawler/http.rs` - shared reqwest client, retries, headers, timeout
  - `crawler/discovery.rs` - link/source discovery
  - `crawler/extractor.rs` - article extraction from HTML
  - `crawler/matcher.rs` - ticker and company alias matching
  - `crawler/pipeline.rs` - fetch -> parse -> normalize flow
  - `domain/article.rs` - article schema
  - `domain/company.rs` - company reference schema
  - `domain/source.rs` - source definitions
  - `storage/jsonl.rs` - output writer
  - `storage/seen_urls.rs` - persistent seen-URL hash store
  - `utils/hash.rs` - URL hash helpers
  - `utils/url.rs` - URL normalization helpers
- Step 1.12: Define the test layout before implementation:
  - `tests/http_client.rs`
  - `tests/discovery.rs`
  - `tests/extractor.rs`
  - `tests/matcher.rs`
  - `tests/pipeline.rs`
  - `tests/seen_urls.rs`
  - `tests/fixtures/*.html`

[Phase 2: Project foundation and configuration]
- Step 2.1: Expand `rust/scuttle_crab/Cargo.toml` with the core dependency set.
- Step 2.2: Recommended dependencies:
  - Required: `tokio`, `reqwest`, `scraper`
  - Strongly recommended: `serde`, `serde_json`, `clap`, `tracing`, `tracing-subscriber`, `thiserror`, `anyhow`, `url`, `chrono`, `sha2`
  - Optional but likely valuable: `regex`, `robots.txt parser crate`, `governor` (rate limiting), `feed-rs` (RSS/Atom), `sqlx` or `rusqlite` (if storage grows beyond JSONL)
- Step 2.3: Add configuration support for user agent, concurrency, request timeout, retry count, output path, and source list.
- Step 2.4: Add structured logging early so crawl failures are diagnosable.

[Phase 3: Source discovery strategy]
- Step 3.1: Avoid building a totally open web crawler first; for MVP, support curated discovery modes in this order:
  - RSS/Atom feeds
  - Known finance/news landing pages with selector-based link extraction
  - Optional sitemap parsing later
- Step 3.2: Implement a source abstraction so each source declares:
  - source name
  - entry URL/feed URL
  - allowed domains
  - article link selectors or discovery mode
  - optional extraction hints
- Step 3.3: Add URL normalization and domain filtering so the crawler stays inside approved sites.
- Step 3.4: Add dedup at discovery time using canonicalized URLs.
- Step 3.5: Hash the normalized canonical URL and check the local seen-URL store before scraping an article.
- Step 3.6: Strengthen URL normalization before hashing so common canonical equivalents do not bypass dedup.
  - strip fragments
  - lowercase the host
  - trim trailing slashes on non-root paths
  - drop explicit default ports (`:80` for HTTP, `:443` for HTTPS)
  - define which tracking query params should be removed for MVP (at minimum `utm_*`)

[Phase 4: Fetching and crawl politeness]
- Step 4.1: Build a shared async HTTP client wrapper around `reqwest::Client`.
- Step 4.2: Support per-request timeout, retry with backoff for transient errors, and a descriptive user-agent.
- Step 4.3: Add concurrency limits so `tokio` tasks do not overwhelm sources.
- Step 4.4: Add crawl politeness controls:
  - optional robots.txt compliance
  - per-domain rate limiting
  - redirect handling
  - content-type validation (only parse HTML/XML when expected)
- Step 4.5: Persist fetch failures as structured errors instead of silently skipping them.

[Phase 5: Article extraction and normalization]
- Step 5.1: Start with a generic extractor in `crawler/extractor.rs` using `scraper` for title, meta tags, canonical URL, publish date, and body candidates.
- Step 5.2: Expect generic extraction to be imperfect; design for source-specific selector overrides in `domain/source.rs`.
- Step 5.3: Normalize extracted content into the shared `Article` struct in `domain/article.rs`.
- Step 5.4: Reject low-quality records (missing title/body, wrong domain, suspiciously short content).
- Step 5.5: After a successful extraction, record the canonical URL hash in the local seen-URL store.

[Phase 6: Company relevance and scoring handoff]
- Step 6.1: Keep the crawler separate from scoring logic, but include the fields scoring will need.
- Step 6.2: Add a first-pass company matching strategy:
  - ticker dictionary or company name list input from `data/companies.json`
  - simple text matching over title + body
  - optional source metadata for market sections
- Step 6.3: Mark each record with relevance metadata rather than final score (example: `matched_companies`, `matched_tickers`, `relevance_reason`).
- Step 6.4: Treat full scoring as a downstream pipeline so the crawler remains focused and testable.
- Step 6.5: Use deterministic matching rules for MVP:
  - exact ticker matches
  - case-insensitive alias matches
  - higher confidence when matches appear in the title or multiple times
- Step 6.6: When multiple aliases for the same company overlap, prefer the most specific alias actually present in the text so stored match evidence is accurate.
  - example: prefer `Apple Inc.` over `Apple` when both aliases exist and the article contains `Apple Inc.`
- Step 6.7: Defer open-ended "detect any company name" support to a later phase.

[Phase 7: CLI, persistence, and operability]
- Step 7.1: Add a small CLI in `main.rs` / `cli.rs` with commands such as:
  - `crawl` - discover + fetch + extract + write output
  - `fetch-url` - debug one URL
  - `test-source` - validate selectors against one source
- Step 7.2: Implement JSONL output first in `storage/jsonl.rs`.
- Step 7.3: Implement the local seen-URL hash store in `storage/seen_urls.rs`.
- Step 7.4: Emit crawl metrics in logs: pages fetched, articles extracted, duplicates skipped from the seen-URL store, failures by source.
- Step 7.5: Document how to add a new source without changing core crawler logic.

[Phase 8: Testing and hardening]
- Step 8.1: Add unit tests for URL normalization, URL hashing, seen-URL persistence, and article schema validation.
- Step 8.2: Add fixture-based parser tests using saved HTML in `tests/fixtures/` so extraction is deterministic.
- Step 8.3: Add integration tests for the end-to-end pipeline using local fixture inputs instead of live websites.
- Step 8.4: Add failure-path tests for timeout, invalid HTML, duplicate URLs, and missing metadata.
- Step 8.5: Add regression tests for URL canonicalization edge cases in `tests/seen_urls.rs`.
  - verify explicit default ports normalize to the same URL
  - verify `utm_*` query parameters do not create distinct dedup hashes
  - verify non-tracking query parameters that change resource identity are preserved
- Step 8.6: Add regression tests for overlapping alias matches in `tests/matcher.rs`.
  - verify `matched_text` records the most specific alias present
  - verify alias ordering in `data/companies.json` does not change the emitted evidence
- Step 8.7: Only after the crawler is stable, evaluate adding database persistence, message queues, or distributed crawling.

## Dependency Recommendation
- Keep your original choices: `reqwest`, `scraper`, and `tokio` are the right MVP foundation.
- Add `serde` and `serde_json` early so the crawler has a stable output contract.
- Add `tracing` and `tracing-subscriber` early so crawl failures are diagnosable.
- Prefer `feed-rs` if RSS/Atom feeds are part of the MVP, because feed parsing is a better starting point than scraping every landing page.
- Consider `governor` or a similar crate only when you implement per-domain rate limiting; it is helpful but not required on day one.

## Dependencies
- Existing Rust project: `rust/scuttle_crab`
- Core libraries:
  - `reqwest` for HTTP
  - `tokio` for async runtime
  - `scraper` for HTML parsing
- Recommended supporting libraries:
  - `serde`, `serde_json` for structured config/output
  - `clap` for CLI
  - `tracing`, `tracing-subscriber` for observability
  - `thiserror`, `anyhow` for error handling
  - `url` for canonicalization
  - `chrono` for timestamps
  - `sha2` for content hashing
  - `feed-rs` if RSS/Atom feeds are a primary source type
  - a robots.txt parser and/or `governor` if politeness controls are required in MVP
- External inputs/services needed:
  - a curated list of news/finance sources
  - local company/ticker reference list for article relevance tagging
  - target output location (`articles.jsonl`, SQLite, or database)

## Outbound Payload Contract
The miniapp should prepare one JSON payload per article for a future endpoint.

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
    "tags": ["earnings", "stocks"],
    "tickers": ["AAPL"],
    "companies": ["Apple"],
    "region": "us",
    "discovery_method": "rss",
    "http_status": 200
  }
}
```

Notes:
- Do not include `summary` in the outbound payload.
- Do not include `content_hash` in the outbound payload.
- Send one article per POST when endpoint delivery is added.

## Local Dedup Strategy
- Use a local persistent seen-URL store to avoid scraping the same article twice across runs.
- Hash the normalized canonical URL, not the article body, for MVP dedup.
- Check the seen-URL store before fetching/parsing the article.
- Record the URL hash after a successful extraction.
- A simple JSONL or line-based store is enough for MVP.

Example dedup record:

```json
{"url_hash":"abc123...","canonical_url":"https://reuters.com/...","first_seen_at":"2026-04-27T08:16:12Z","source":"Reuters"}
```

## Company Reference Store
- Use a local file `data/companies.json` for the MVP ticker and alias dictionary.
- Load it into memory at startup.
- Each company record should include:
  - `name`
  - `ticker`
  - `aliases`
  - optional `exchange`
  - optional `country`
  - optional `is_active`

Example company record:

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

## Future Open-Ended Company Detection
- The MVP should use a fixed company list only.
- If open-ended company detection is needed later, the recommended next step is a named-entity-recognition style pass plus a validation layer against a trusted company registry.
- Do not add this to the MVP because it increases noise, ambiguity, and debugging cost.

## Risks
- HIGH: Generic HTML extraction is unreliable across publishers; a one-size-fits-all parser will miss bodies, dates, or canonical links on many sites.
- HIGH: Anti-bot protections, robots.txt restrictions, and aggressive rate limits may block scraping from some financial publishers.
- HIGH: Scope creep into “full company scoring” can derail the crawler; extraction and scoring should stay separate.
- MEDIUM: Duplicate content across syndication partners, mirrors, and updated URLs can pollute downstream scoring unless canonicalization and seen-URL dedup are implemented early.
- MEDIUM: Entity/company matching can produce noisy false positives if it relies only on naive substring matching.
- MEDIUM: Entity/company matching can produce noisy false positives if aliases are too broad or ambiguous.
- MEDIUM: Overlapping aliases can produce inaccurate `matched_text` evidence unless the matcher prefers the most specific match actually found in the article.
- MEDIUM: Async concurrency without strong limits may cause unstable crawls, source bans, or difficult-to-reproduce parsing failures.
- LOW: Starting with JSONL may require a later migration to SQLite/Postgres, but it is the fastest path for MVP validation.
- LOW: Some useful crates may need evaluation for maintenance quality before adoption.

## Estimated Complexity
MEDIUM-HIGH.
- Planning and architecture: ~0.5-1 day
- MVP crawler (RSS + curated page discovery + extraction + JSONL output): ~3-5 days
- Hardening, fixtures, dedup, relevance tagging, and operability: ~3-5 more days
- Total realistic MVP range: ~1-2 weeks depending on source diversity and extraction accuracy expectations

## Recommended MVP Order
1. Build the normalized `Article` schema and JSONL writer.
2. Add curated source definitions and RSS/Atom discovery first.
3. Add page fetching with retries, timeouts, and concurrency limits.
4. Add generic extraction with source-specific overrides.
5. Add seen-URL deduplication and company/ticker relevance tagging.
6. Add CLI commands and fixture-based tests.

## Recommendation
Proceed with a narrow MVP first: RSS/Atom + a few curated finance/news sources + JSONL output. That will validate the architecture quickly without getting stuck on anti-bot defenses or overly broad scraping logic.

**WAITING FOR CONFIRMATION**: Proceed with this plan? (yes/no/modify)
