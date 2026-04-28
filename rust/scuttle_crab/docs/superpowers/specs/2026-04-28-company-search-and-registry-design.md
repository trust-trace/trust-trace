# Company Search And Registry Design

## Purpose

Add a new `search-company <query>` command to `scuttle_crab` that collects both public news coverage and official registry records for a company in one run, then emits everything through the existing article payload contract used by `backend/tarkov`.

## Problem

The crate currently splits company-related retrieval into separate behaviors:

- article crawling is driven by curated source discovery
- company registry scraping is driven by `scrape-company <query>`

That does not match the intended operator workflow. The desired behavior is:

1. search for a company by name
2. discover a limited set of relevant news articles
3. fetch official registry records using `krs` or `nip` when available
4. print what was found
5. write payloads to the outbox
6. send the same payloads to the existing Tarkov ingest endpoint

The operator should not need to run separate commands for news and registry enrichment.

## Scope

This design covers:

- a new `search-company <query>` CLI command
- DuckDuckGo-based article discovery using the company name
- registry enrichment in the same run using `krs` or `nip`
- optional branch selection via `--news-only` and `--registry-only`
- an environment variable to cap the number of article results
- outbox writes, console printing, and Tarkov delivery for both branches
- summary reporting and tests

This design does not cover:

- replacing the existing curated `crawl` pipeline
- changing the Tarkov payload schema
- introducing a generic search-engine abstraction
- advanced result ranking, ML scoring, or entity disambiguation beyond local company lookup
- removing `scrape-company`; it can remain for direct registry-only workflows unless later deprecated

## Recommended Approach

Add a new `search-company` command that orchestrates two independent branches:

- a news branch driven by the user-facing company name
- a registry branch driven by resolved `krs` or `nip`

Why this is the right choice:

- it matches the desired operator workflow directly
- it keeps the existing `crawl` command focused on source-based crawling
- it reuses the existing `ArticlePayload`, outbox writer, and Tarkov delivery path
- it allows partial success when one branch is unavailable
- it keeps the change surface smaller than overloading current commands

Alternatives considered:

1. Extend `scrape-company` to also search news.
Rejected because it mixes official registry collection with open-web article discovery under a command name that currently implies registries only.

2. Extend `crawl` to accept a company query and perform search-engine discovery.
Rejected because `crawl` is source-oriented, not query-oriented, and the resulting configuration and semantics would become less clear.

3. Replace all current company flows with one large generic company intelligence pipeline.
Rejected for now because it expands scope unnecessarily and would force broader refactoring before validating the operator workflow.

## Command Contract

### New Command

Add:

```bash
cargo run -- search-company "Allegro"
cargo run -- search-company "Allegro" --news-only
cargo run -- search-company "Allegro" --registry-only
```

### Query Usage

- the original `query` string is used as the news-search phrase
- company lookup attempts to resolve the query against `data/companies.json`
- registry retrieval uses resolved identifiers rather than the typed query when available

### Registry Identifier Preference

For the registry branch, prefer:

1. `krs`
2. `nip`
3. skip registry branch if neither exists in default combined mode

In `--registry-only` mode, missing identifiers should be treated as a clear failure.

### Branch Selection

Default behavior:

- run both branches

Optional flags:

- `--news-only`: run only the news discovery and article branch
- `--registry-only`: run only the official registry branch

`--news-only` and `--registry-only` should be mutually exclusive.

## Configuration

### Environment Variable

Add:

- `SCUTTLE_COMPANY_ARTICLE_LIMIT`

Behavior:

- default value: `10`
- applies only to the news branch
- clamp to a safe range such as `1..=50`

This is intentionally an environment variable rather than a CLI flag to keep the first command shape small.

### Existing Delivery Configuration

Reuse the existing Tarkov delivery environment variables already supported by `src/crawler/delivery.rs`:

- `TARKOV_BASE_URL`
- `TARKOV_INGEST_PATH`
- `TARKOV_TIMEOUT_SECS`

No new delivery endpoint or schema should be introduced.

## Target Behavior

For `search-company <query>` in default mode:

1. Resolve the company from `data/companies.json` when possible.
2. Start a news-search branch using the company name or original query.
3. Start a registry branch when `krs` or `nip` is available.
4. Convert both article and registry results into `ArticlePayload` records.
5. Print one line per emitted payload to the terminal.
6. Append each emitted payload to `data/outbox.jsonl`.
7. Attempt delivery of each payload to `backend/tarkov` through the existing delivery bridge.
8. Print a final summary with branch-specific counters.

The main output rule remains:

- one discovered article or registry document = one `ArticlePayload`

## Architecture

Target flow:

```text
search-company <query>
    -> resolve company record once
    -> branch A: DuckDuckGo discovery with company name
        -> candidate URLs
        -> URL normalization + dedup check
        -> fetch and extract article
    -> branch B: registry lookup with krs or nip
        -> fetch official registry documents
        -> map each document to article-shaped payload
    -> merge outputs
    -> print payload URL lines
    -> append to outbox
    -> deliver to Tarkov
    -> print combined summary
```

### Module Direction

Minimal-change direction:

- `src/cli.rs`
  - add `SearchCompany { query, news_only, registry_only }`
- `src/lib.rs`
  - dispatch the new command
  - format the combined summary string
- `src/config.rs`
  - add helper access for `SCUTTLE_COMPANY_ARTICLE_LIMIT`
- `src/crawler/search_discovery.rs`
  - implement DuckDuckGo search result fetching and parsing
- `src/crawler/search_pipeline.rs`
  - implement news branch orchestration and overall command aggregation
- `src/crawler/company_pipeline.rs`
  - keep current registry fetch logic and reuse it from the combined command where possible

Avoid introducing a generic search-provider abstraction in this step. The first version should target DuckDuckGo only.

## News Branch Design

### Discovery Input

- use the company name for the search phrase when a company record is resolved
- otherwise fall back to the original query string

### Discovery Source

Use DuckDuckGo result pages as a lightweight discovery layer.

Constraints:

- use a standard browser user-agent
- parse only the search result links needed for crawling
- stop after the configured article limit
- treat challenge or anti-bot pages as handled branch failures

### Deduplication

Before fetching any discovered URL:

- normalize the URL with the existing URL helper
- check the existing `SeenUrlStore`
- skip previously seen URLs

This keeps behavior aligned with the existing crawler architecture.

### Fetch And Extraction

Use the existing article fetch/extract path rather than adding a second article parser.

The news branch should:

- call the existing article payload fetch helper for each candidate URL
- reuse the same payload contract already used by `fetch-url`
- treat per-URL failures as item failures, not whole-branch failures

## Registry Branch Design

### Identifier Usage

The registry branch should not use the human-entered company name for final official fetches when better identifiers exist.

Instead:

- use `krs` when present
- otherwise use `nip` when present

The operator query is mainly for company resolution and the news-search phrase.

### Output Contract

Registry outputs should remain article-shaped payloads using the existing mapping already implemented in `company_pipeline.rs`.

This preserves a single downstream contract for both news and official records.

### Branch Availability

In default combined mode:

- if the company cannot be resolved to `krs` or `nip`, skip the registry branch and continue with news

In `--registry-only` mode:

- missing identifiers should be a command failure

## Output Behavior

### Console Output

Print one line per emitted payload, for example:

```text
NEWS https://example.com/article
REGISTRY https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/0000635012
```

This keeps runs inspectable without changing the payload schema.

### Outbox

Every successfully emitted payload should be appended to the existing outbox path:

- `data/outbox.jsonl`

### Tarkov Delivery

Every successfully emitted payload should be sent through the existing `maybe_deliver_to_tarkov()` path.

Delivery failure should not discard the payload from the outbox.

## Summary Contract

The final command output should distinguish branch results clearly.

Recommended counters:

- `news_discovered`
- `news_skipped`
- `news_emitted`
- `news_failed`
- `registry_emitted`
- `registry_failed`
- `delivered`
- `delivery_failed`

Optional context fields:

- `query`
- `outbox`
- `companies`
- whether registry identifiers were found

## Error Handling

### Command-Level Rules

`--news-only`:

- succeed if the news branch completes its run, even if it emits zero items

`--registry-only`:

- succeed if the registry branch completes
- fail clearly if required identifiers are missing

Default combined mode:

- run both branches independently
- allow partial success
- fail overall only when both branches fail hard

### News Branch Errors

- DuckDuckGo challenge or block page:
  - mark the news branch as failed
  - continue registry branch in combined mode
- zero search results:
  - not a hard failure
- per-URL fetch or extraction failure:
  - count item failure
  - continue with the remaining URLs

### Registry Branch Errors

- missing `krs` and `nip`:
  - skip in default mode
  - fail in `--registry-only`
- registry request failures:
  - count as registry failure for the affected branch work
  - continue news branch in combined mode

### Persistence And Delivery Errors

- outbox write failure:
  - hard failure for that payload operation
- Tarkov delivery failure:
  - count separately
  - keep the payload in the outbox

This preserves the outbox as the durable local record.

## Testing Strategy

Primary coverage should be integration-first, matching the current crate style.

Required tests:

1. `search-company` CLI parsing accepts the new command and flags.
2. `--news-only` runs without requiring registry identifiers.
3. `--registry-only` fails clearly when identifiers are missing.
4. the news branch respects `SCUTTLE_COMPANY_ARTICLE_LIMIT`.
5. discovered URLs already present in the seen-url store are skipped.
6. successful news items emit `ArticlePayload` lines to the outbox.
7. successful registry items emit `ArticlePayload` lines to the outbox.
8. default combined mode can succeed when news fails but registry succeeds.
9. default combined mode can succeed when registry fails but news succeeds.
10. overall command fails only when both branches fail hard in combined mode.
11. Tarkov delivery is attempted for emitted payloads and delivery failures are counted without removing outbox records.
12. terminal summary contains separate counters for news, registry, and delivery.

Recommended test implementation notes:

- use local HTTP fixtures for DuckDuckGo-like result pages instead of live network calls
- use local HTTP fixtures for registry endpoints, following the style already used in `tests/company_pipeline.rs`
- avoid network-dependent tests against live DuckDuckGo

## Compatibility Notes

- the existing `crawl` command remains source-oriented and unchanged
- the existing article payload contract remains unchanged
- the existing Tarkov ingest path remains unchanged
- `scrape-company` can remain available for direct registry workflows unless a later cleanup removes it

## Implementation Constraints

- prefer minimal edits in the current module layout
- do not introduce backward-compatibility modes unless explicitly needed
- keep one payload contract across news and registry paths
- reuse existing fetching, payload, outbox, dedup, and Tarkov delivery code where practical
- keep DuckDuckGo logic narrowly scoped so it can be replaced later if needed

## Expected Outcome

After implementation, `search-company <query>` will behave as a combined company intelligence collection command. It will search public articles by company name, fetch official registry records using `krs` or `nip` when available, print emitted items, save them to the outbox, and send them to `backend/tarkov` using the existing article-style payload contract.
