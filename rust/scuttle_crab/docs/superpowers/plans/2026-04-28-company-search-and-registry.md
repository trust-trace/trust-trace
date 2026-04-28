# Company Search And Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `search-company` command that searches company news via DuckDuckGo, optionally fetches official registry records via `krs` or `nip`, writes all emitted payloads to the outbox, and sends them to Tarkov.

**Architecture:** Keep the change small by adding a new search orchestrator next to the existing feed and registry pipelines. Reuse the current article payload contract, seen-URL store, JSONL outbox, Tarkov delivery path, and company registry pipeline instead of introducing new schemas or abstractions.

**Tech Stack:** Rust, tokio, clap, reqwest, scraper, serde_json, existing `scuttle_crab` crawler/storage modules

---

## File Map

- Modify: `src/cli.rs`
  - Add `SearchCompany` command and mutually exclusive branch flags.
- Modify: `src/config.rs`
  - Add environment-backed article-limit helper.
- Modify: `src/lib.rs`
  - Route the new command and format the combined summary string.
- Modify: `src/crawler/mod.rs`
  - Export new crawler modules.
- Create: `src/crawler/search_discovery.rs`
  - Implement DuckDuckGo query URL building and result-link extraction.
- Create: `src/crawler/search_pipeline.rs`
  - Implement combined command orchestration, branch selection, payload emission, outbox persistence, and Tarkov delivery accounting.
- Modify: `src/crawler/company_pipeline.rs`
  - Expose a small registry helper reusable from `search-company`.
- Modify: `tests/cli.rs`
  - Add parser and output-format coverage for `search-company`.
- Create: `tests/search_pipeline.rs`
  - Add integration coverage for article limit, branch modes, partial success, and delivery behavior.

### Task 1: Add CLI Surface And Config Helper

**Files:**
- Modify: `src/cli.rs`
- Modify: `src/config.rs`
- Test: `tests/cli.rs`

- [ ] **Step 1: Write the failing CLI parsing tests**

Add these tests to `tests/cli.rs` near the existing command parser tests:

```rust
#[test]
fn parses_search_company_subcommand() {
    let cli = Cli::parse_from(["scuttle_crab", "search-company", "Allegro"]);

    match cli.command {
        Command::SearchCompany {
            query,
            news_only,
            registry_only,
        } => {
            assert_eq!(query, "Allegro");
            assert!(!news_only);
            assert!(!registry_only);
        }
        _ => panic!("expected search-company command"),
    }
}

#[test]
fn parses_search_company_news_only_flag() {
    let cli = Cli::parse_from([
        "scuttle_crab",
        "search-company",
        "Allegro",
        "--news-only",
    ]);

    match cli.command {
        Command::SearchCompany {
            query,
            news_only,
            registry_only,
        } => {
            assert_eq!(query, "Allegro");
            assert!(news_only);
            assert!(!registry_only);
        }
        _ => panic!("expected search-company command"),
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test cli parses_search_company_subcommand -- --exact`

Expected: FAIL with an error that `SearchCompany` does not exist yet.

- [ ] **Step 3: Add the new CLI command**

Update `src/cli.rs` so `Command` includes the new variant:

```rust
#[derive(Debug, Clone, Subcommand)]
pub enum Command {
    Crawl {
        #[arg(long)]
        sources_file: Option<String>,
    },
    FetchUrl { url: String },
    ScrapeCompany { query: String },
    SearchCompany {
        query: String,
        #[arg(long, conflicts_with = "registry_only")]
        news_only: bool,
        #[arg(long, conflicts_with = "news_only")]
        registry_only: bool,
    },
    TestSource { source: String },
}
```

- [ ] **Step 4: Add the article-limit config helper**

Append this helper to `src/config.rs`:

```rust
impl AppConfig {
    pub fn company_article_limit(&self) -> usize {
        std::env::var("SCUTTLE_COMPANY_ARTICLE_LIMIT")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .map(|value| value.clamp(1, 50))
            .unwrap_or(10)
    }
}
```

- [ ] **Step 5: Run tests to verify the new parser passes**

Run: `cargo test --test cli parses_search_company_subcommand parses_search_company_news_only_flag`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/cli.rs src/config.rs tests/cli.rs
git commit -m "feat: add search-company cli surface"
```

### Task 2: Add Search Discovery Parsing

**Files:**
- Create: `src/crawler/search_discovery.rs`
- Modify: `src/crawler/mod.rs`
- Test: `src/crawler/search_discovery.rs`

- [ ] **Step 1: Write the failing search-discovery unit tests**

Create `src/crawler/search_discovery.rs` with tests first:

```rust
#[cfg(test)]
mod tests {
    use super::{build_search_url, parse_result_urls};

    #[test]
    fn builds_duckduckgo_search_url_from_query() {
        let url = build_search_url("Allegro news");
        assert!(url.starts_with("https://html.duckduckgo.com/html/?q="));
        assert!(url.contains("Allegro%20news") || url.contains("Allegro+news"));
    }

    #[test]
    fn extracts_result_links_from_duckduckgo_html() {
        let html = r#"
        <html>
          <body>
            <a class="result__a" href="https://example.com/article-1">Article 1</a>
            <a class="result__a" href="https://example.com/article-2">Article 2</a>
          </body>
        </html>
        "#;

        let urls = parse_result_urls(html).expect("links should parse");
        assert_eq!(urls, vec![
            "https://example.com/article-1".to_string(),
            "https://example.com/article-2".to_string(),
        ]);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test search_discovery --lib`

Expected: FAIL because the module and functions are not implemented yet.

- [ ] **Step 3: Implement the minimal search-discovery module**

Replace the new file with this implementation:

```rust
//! DuckDuckGo-based company article discovery helpers.

use anyhow::{Context, bail};
use scraper::{Html, Selector};

const SEARCH_BASE_URL: &str = "https://html.duckduckgo.com/html/?q=";

pub fn build_search_url(query: &str) -> String {
    format!("{SEARCH_BASE_URL}{}", url::form_urlencoded::byte_serialize(query.as_bytes()).collect::<String>())
}

pub fn parse_result_urls(html: &str) -> anyhow::Result<Vec<String>> {
    if html.contains("Unfortunately, bots use DuckDuckGo too") {
        bail!("duckduckgo challenge page returned");
    }

    let document = Html::parse_document(html);
    let selector = Selector::parse("a.result__a").expect("valid result selector");
    let urls = document
        .select(&selector)
        .filter_map(|node| node.value().attr("href"))
        .map(str::to_string)
        .collect::<Vec<_>>();

    if urls.is_empty() {
        return Ok(Vec::new());
    }

    Ok(urls)
}

pub async fn discover_company_article_urls(
    client: &reqwest::Client,
    query: &str,
    limit: usize,
) -> anyhow::Result<Vec<String>> {
    let url = build_search_url(query);
    let html = client
        .get(&url)
        .send()
        .await
        .with_context(|| format!("request failed for {url}"))?
        .error_for_status()
        .with_context(|| format!("non-success status for {url}"))?
        .text()
        .await
        .with_context(|| format!("failed to read body for {url}"))?;

    let mut urls = parse_result_urls(&html)?;
    urls.truncate(limit.max(1));
    Ok(urls)
}
```

Update `src/crawler/mod.rs`:

```rust
pub mod search_discovery;
pub mod search_pipeline;
```

- [ ] **Step 4: Run tests to verify the module passes**

Run: `cargo test search_discovery --lib`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crawler/mod.rs src/crawler/search_discovery.rs
git commit -m "feat: add duckduckgo search discovery helpers"
```

### Task 3: Add Search Summary And Output Formatting

**Files:**
- Create: `src/crawler/search_pipeline.rs`
- Modify: `src/lib.rs`
- Test: `tests/cli.rs`

- [ ] **Step 1: Write the failing summary-format test**

Add this test to `tests/cli.rs`:

```rust
#[test]
fn search_company_output_includes_branch_counters() {
    let summary = scuttle_crab::crawler::search_pipeline::SearchCompanySummary {
        news_discovered: 4,
        news_skipped: 1,
        news_emitted: 2,
        news_failed: 1,
        registry_emitted: 3,
        registry_failed: 0,
        delivered: 4,
        delivery_failed: 1,
    };

    let output = scuttle_crab::format_search_company_output("Allegro", &summary, true, &AppConfig::default());

    assert!(output.contains("query=Allegro"));
    assert!(output.contains("news_discovered=4"));
    assert!(output.contains("registry_emitted=3"));
    assert!(output.contains("delivery_failed=1"));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test cli search_company_output_includes_branch_counters -- --exact`

Expected: FAIL because the summary type and formatter do not exist yet.

- [ ] **Step 3: Add the summary type and formatter**

Create `src/crawler/search_pipeline.rs` with the summary struct only for now:

```rust
//! Company search orchestration.

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SearchCompanySummary {
    pub news_discovered: usize,
    pub news_skipped: usize,
    pub news_emitted: usize,
    pub news_failed: usize,
    pub registry_emitted: usize,
    pub registry_failed: usize,
    pub delivered: usize,
    pub delivery_failed: usize,
}
```

Add this formatter to `src/lib.rs` near `format_company_scrape_output`:

```rust
pub fn format_search_company_output(
    query: &str,
    summary: &crawler::search_pipeline::SearchCompanySummary,
    registry_identifiers_found: bool,
    config: &AppConfig,
) -> String {
    format!(
        "search company complete: query={}, news_discovered={}, news_skipped={}, news_emitted={}, news_failed={}, registry_emitted={}, registry_failed={}, delivered={}, delivery_failed={}, registry_identifiers_found={}, companies={}, outbox={}",
        query,
        summary.news_discovered,
        summary.news_skipped,
        summary.news_emitted,
        summary.news_failed,
        summary.registry_emitted,
        summary.registry_failed,
        summary.delivered,
        summary.delivery_failed,
        registry_identifiers_found,
        config.companies_path,
        config.outbox_path,
    )
}
```

- [ ] **Step 4: Run the summary-format test**

Run: `cargo test --test cli search_company_output_includes_branch_counters -- --exact`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crawler/search_pipeline.rs src/lib.rs tests/cli.rs
git commit -m "feat: add search-company summary formatting"
```

### Task 4: Implement News-Only Search Pipeline

**Files:**
- Modify: `src/crawler/search_pipeline.rs`
- Modify: `src/lib.rs`
- Test: `tests/search_pipeline.rs`

- [ ] **Step 1: Write the failing news-only integration test**

Create `tests/search_pipeline.rs` with this first test:

```rust
#[test]
fn search_company_news_only_emits_articles_to_outbox() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_news_only");
    std::fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = std::net::TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_search_server(listener);

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: root.join("sources.json").display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: format!("http://{address}"),
        msig_api_base_url: format!("http://{address}"),
        concurrency: 2,
    };

    unsafe {
        std::env::set_var("SCUTTLE_COMPANY_SEARCH_BASE_URL", format!("http://{address}/html/?q="));
        std::env::set_var("SCUTTLE_COMPANY_ARTICLE_LIMIT", "2");
    }

    let summary = runtime
        .block_on(scuttle_crab::crawler::search_pipeline::search_company_with_config(
            &config,
            "Allegro",
            true,
            false,
        ))
        .expect("search should complete");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
        std::env::remove_var("SCUTTLE_COMPANY_ARTICLE_LIMIT");
    }

    server.join().expect("server should finish");

    let outbox = std::fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");
    assert_eq!(summary.news_discovered, 2);
    assert_eq!(summary.news_emitted, 2);
    assert_eq!(summary.registry_emitted, 0);
    assert_eq!(outbox.lines().count(), 2);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test search_pipeline search_company_news_only_emits_articles_to_outbox -- --exact`

Expected: FAIL because `search_company_with_config` does not exist yet.

- [ ] **Step 3: Implement the minimal news-only path**

Extend `src/crawler/search_pipeline.rs` with this implementation:

```rust
use std::collections::HashSet;

use anyhow::bail;

use crate::config::AppConfig;
use crate::crawler::delivery::maybe_deliver_to_tarkov;
use crate::crawler::fetch::{build_http_client, fetch_article_payload};
use crate::crawler::search_discovery::discover_company_article_urls;
use crate::storage::jsonl::JsonlOutbox;
use crate::storage::seen_urls::SeenUrlStore;

pub async fn search_company_with_config(
    config: &AppConfig,
    query: &str,
    news_only: bool,
    registry_only: bool,
) -> anyhow::Result<SearchCompanySummary> {
    if news_only && registry_only {
        bail!("--news-only and --registry-only cannot be used together");
    }

    let mut summary = SearchCompanySummary::default();

    if !registry_only {
        run_news_branch(config, query, &mut summary).await?;
    }

    if registry_only {
        bail!("registry-only branch not implemented yet");
    }

    Ok(summary)
}

async fn run_news_branch(
    config: &AppConfig,
    query: &str,
    summary: &mut SearchCompanySummary,
) -> anyhow::Result<()> {
    let client = build_http_client()?;
    let limit = config.company_article_limit();
    let outbox = JsonlOutbox::new(&config.outbox_path);
    let mut seen_urls = SeenUrlStore::load(&config.seen_urls_path)?;
    let mut pending = HashSet::new();

    let urls = discover_company_article_urls(&client, query, limit).await?;

    for url in urls {
        summary.news_discovered += 1;
        if seen_urls.contains(&url)? || !pending.insert(url.clone()) {
            summary.news_skipped += 1;
            continue;
        }

        match fetch_article_payload(&url).await {
            Ok(payload) => {
                println!("NEWS {}", payload.source.url);
                outbox.append(&payload)?;
                let recorded = seen_urls.record(
                    payload.article.canonical_url.as_deref().unwrap_or(&payload.source.url),
                    &payload.source.name,
                    &payload.article.scraped_at,
                )?;
                if recorded {
                    summary.news_emitted += 1;
                } else {
                    summary.news_skipped += 1;
                }

                match maybe_deliver_to_tarkov(&payload).await {
                    Ok(Some(_)) => summary.delivered += 1,
                    Ok(None) => {}
                    Err(_) => summary.delivery_failed += 1,
                }
            }
            Err(_) => {
                summary.news_failed += 1;
            }
        }
    }

    Ok(())
}
```

Update `src/lib.rs` command dispatch:

```rust
        Command::SearchCompany {
            query,
            news_only,
            registry_only,
        } => {
            let config = AppConfig::default();
            let summary = crawler::search_pipeline::search_company_with_config(
                &config,
                &query,
                news_only,
                registry_only,
            )
            .await?;
            format_search_company_output(&query, &summary, false, &config)
        }
```

- [ ] **Step 4: Run the news-only integration test**

Run: `cargo test --test search_pipeline search_company_news_only_emits_articles_to_outbox -- --exact`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crawler/search_pipeline.rs src/lib.rs tests/search_pipeline.rs
git commit -m "feat: add news-only company search pipeline"
```

### Task 5: Make Search Discovery Configurable For Tests

**Files:**
- Modify: `src/crawler/search_discovery.rs`
- Test: `tests/search_pipeline.rs`

- [ ] **Step 1: Write the failing configurable-base-url unit test**

Add this test to `src/crawler/search_discovery.rs`:

```rust
#[test]
fn uses_override_search_base_url_when_present() {
    unsafe {
        std::env::set_var("SCUTTLE_COMPANY_SEARCH_BASE_URL", "http://localhost:9999/html/?q=");
    }

    let url = build_search_url("Allegro");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
    }

    assert_eq!(url, "http://localhost:9999/html/?q=Allegro");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test search_discovery::tests::uses_override_search_base_url_when_present --lib`

Expected: FAIL because the override is not read yet.

- [ ] **Step 3: Implement the override**

Replace the constant access in `src/crawler/search_discovery.rs` with:

```rust
fn search_base_url() -> String {
    std::env::var("SCUTTLE_COMPANY_SEARCH_BASE_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| SEARCH_BASE_URL.to_string())
}

pub fn build_search_url(query: &str) -> String {
    format!(
        "{}{}",
        search_base_url(),
        url::form_urlencoded::byte_serialize(query.as_bytes()).collect::<String>()
    )
}
```

- [ ] **Step 4: Run the unit test and the news-only integration test**

Run: `cargo test search_discovery::tests::uses_override_search_base_url_when_present --lib && cargo test --test search_pipeline search_company_news_only_emits_articles_to_outbox -- --exact`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crawler/search_discovery.rs tests/search_pipeline.rs
git commit -m "test: make company search discovery configurable"
```

### Task 6: Reuse Registry Pipeline From Search Command

**Files:**
- Modify: `src/crawler/company_pipeline.rs`
- Modify: `src/crawler/search_pipeline.rs`
- Test: `tests/search_pipeline.rs`

- [ ] **Step 1: Write the failing registry-only integration test**

Add this test to `tests/search_pipeline.rs`:

```rust
#[test]
fn search_company_registry_only_uses_company_identifiers() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_registry_only");
    std::fs::create_dir_all(&root).expect("temp dir should be created");
    write_company_fixture(&root);

    let listener = std::net::TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_registry_server(listener);

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: root.join("sources.json").display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: format!("http://{address}"),
        msig_api_base_url: format!("http://{address}"),
        concurrency: 2,
    };

    let summary = runtime
        .block_on(scuttle_crab::crawler::search_pipeline::search_company_with_config(
            &config,
            "allegro",
            false,
            true,
        ))
        .expect("search should complete");

    server.join().expect("server should finish");

    assert_eq!(summary.news_discovered, 0);
    assert!(summary.registry_emitted >= 2);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test search_pipeline search_company_registry_only_uses_company_identifiers -- --exact`

Expected: FAIL because the registry-only path is not wired.

- [ ] **Step 3: Expose a reusable registry resolver helper**

Add this public helper to `src/crawler/company_pipeline.rs` near the existing internal resolver:

```rust
pub fn resolve_company_record(
    config: &AppConfig,
    query: &str,
) -> anyhow::Result<Option<CompanyRecord>> {
    let companies = load_companies_if_exists(&config.companies_path)?;
    Ok(companies
        .into_iter()
        .find(|company| company.matches_query(query)))
}
```

- [ ] **Step 4: Reuse the existing registry pipeline from search orchestration**

Update `src/crawler/search_pipeline.rs`:

```rust
use crate::crawler::company_pipeline::{resolve_company_record, scrape_company_with_config};

pub async fn search_company_with_config(
    config: &AppConfig,
    query: &str,
    news_only: bool,
    registry_only: bool,
) -> anyhow::Result<SearchCompanySummary> {
    if news_only && registry_only {
        anyhow::bail!("--news-only and --registry-only cannot be used together");
    }

    let mut summary = SearchCompanySummary::default();
    let company = resolve_company_record(config, query)?;

    if !registry_only {
        run_news_branch(config, company.as_ref().map(|company| company.name.as_str()).unwrap_or(query), &mut summary).await?;
    }

    if !news_only {
        match company.as_ref().and_then(|company| company.krs.clone().or(company.nip.clone())) {
            Some(registry_query) => match scrape_company_with_config(config, &registry_query).await {
                Ok(registry_summary) => {
                    summary.registry_emitted += registry_summary.emitted;
                    summary.registry_failed += registry_summary.failed;
                    summary.delivered += registry_summary.emitted.saturating_sub(registry_summary.failed);
                }
                Err(error) if registry_only => return Err(error),
                Err(_) => summary.registry_failed += 1,
            },
            None if registry_only => anyhow::bail!("company is missing krs and nip for registry lookup"),
            None => {}
        }
    }

    Ok(summary)
}
```

- [ ] **Step 5: Run the registry-only integration test**

Run: `cargo test --test search_pipeline search_company_registry_only_uses_company_identifiers -- --exact`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/crawler/company_pipeline.rs src/crawler/search_pipeline.rs tests/search_pipeline.rs
git commit -m "feat: reuse registry pipeline from search-company"
```

### Task 7: Add Missing-Identifiers And Partial-Success Coverage

**Files:**
- Modify: `tests/search_pipeline.rs`

- [ ] **Step 1: Write the failing missing-identifiers registry-only test**

Add this test to `tests/search_pipeline.rs`:

```rust
#[test]
fn search_company_registry_only_fails_when_identifiers_are_missing() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_registry_missing_ids");
    std::fs::create_dir_all(&root).expect("temp dir should be created");

    std::fs::write(
        root.join("companies.json"),
        r#"[{"name":"No Id Co","ticker":"NIC","aliases":["no id co"]}]"#,
    )
    .expect("companies file should be written");

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: root.join("sources.json").display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: "https://api-krs.ms.gov.pl/api".to_string(),
        msig_api_base_url: "https://wyszukiwarka-msig.ms.gov.pl/api".to_string(),
        concurrency: 2,
    };

    let error = runtime
        .block_on(scuttle_crab::crawler::search_pipeline::search_company_with_config(
            &config,
            "No Id Co",
            false,
            true,
        ))
        .expect_err("registry-only should fail");

    assert!(error.to_string().contains("missing krs and nip"));
}
```

- [ ] **Step 2: Write the failing partial-success test**

Add this second test to `tests/search_pipeline.rs`:

```rust
#[test]
fn search_company_succeeds_when_news_fails_but_registry_succeeds() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_partial_success");
    std::fs::create_dir_all(&root).expect("temp dir should be created");
    write_company_fixture(&root);

    let listener = std::net::TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_registry_only_server(listener);

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: root.join("sources.json").display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: format!("http://{address}"),
        msig_api_base_url: format!("http://{address}"),
        concurrency: 2,
    };

    unsafe {
        std::env::set_var("SCUTTLE_COMPANY_SEARCH_BASE_URL", format!("http://{address}/blocked/?q="));
    }

    let summary = runtime
        .block_on(scuttle_crab::crawler::search_pipeline::search_company_with_config(
            &config,
            "allegro",
            false,
            false,
        ))
        .expect("combined search should still succeed");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
    }

    server.join().expect("server should finish");

    assert!(summary.news_failed >= 1);
    assert!(summary.registry_emitted >= 2);
}
```

- [ ] **Step 3: Run the new tests to verify current failures**

Run: `cargo test --test search_pipeline search_company_registry_only_fails_when_identifiers_are_missing search_company_succeeds_when_news_fails_but_registry_succeeds`

Expected: the missing-identifiers test should pass or fail depending on current wording, and the partial-success test should FAIL until branch errors are softened.

- [ ] **Step 4: Make combined-mode news failures non-fatal**

Adjust `search_company_with_config` in `src/crawler/search_pipeline.rs` so the news branch is isolated in combined mode:

```rust
    if !registry_only {
        let search_query = company
            .as_ref()
            .map(|company| company.name.as_str())
            .unwrap_or(query);

        match run_news_branch(config, search_query, &mut summary).await {
            Ok(()) => {}
            Err(error) if news_only => return Err(error),
            Err(_) => summary.news_failed += 1,
        }
    }
```

- [ ] **Step 5: Run the search-pipeline tests again**

Run: `cargo test --test search_pipeline`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/crawler/search_pipeline.rs tests/search_pipeline.rs
git commit -m "test: cover search-company partial success cases"
```

### Task 8: Add Delivery Accounting For Search Branches

**Files:**
- Modify: `tests/search_pipeline.rs`
- Modify: `src/crawler/search_pipeline.rs`

- [ ] **Step 1: Write the failing delivery-count integration test**

Add this test to `tests/search_pipeline.rs`:

```rust
#[test]
fn search_company_counts_tarkov_delivery_failures_without_losing_outbox_records() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_delivery_failures");
    std::fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = std::net::TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_search_server(listener);

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: root.join("sources.json").display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: format!("http://{address}"),
        msig_api_base_url: format!("http://{address}"),
        concurrency: 2,
    };

    unsafe {
        std::env::set_var("SCUTTLE_COMPANY_SEARCH_BASE_URL", format!("http://{address}/html/?q="));
        std::env::set_var("SCUTTLE_COMPANY_ARTICLE_LIMIT", "1");
        std::env::set_var("TARKOV_BASE_URL", "http://127.0.0.1:1");
        std::env::set_var("TARKOV_INGEST_PATH", "/v1/articles");
    }

    let summary = runtime
        .block_on(scuttle_crab::crawler::search_pipeline::search_company_with_config(
            &config,
            "Allegro",
            true,
            false,
        ))
        .expect("search should complete");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
        std::env::remove_var("SCUTTLE_COMPANY_ARTICLE_LIMIT");
        std::env::remove_var("TARKOV_BASE_URL");
        std::env::remove_var("TARKOV_INGEST_PATH");
    }

    server.join().expect("server should finish");

    let outbox = std::fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");
    assert_eq!(summary.news_emitted, 1);
    assert_eq!(summary.delivery_failed, 1);
    assert_eq!(outbox.lines().count(), 1);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cargo test --test search_pipeline search_company_counts_tarkov_delivery_failures_without_losing_outbox_records -- --exact`

Expected: FAIL if delivery failures are not counted consistently.

- [ ] **Step 3: Fix delivery accounting only if needed**

If the test fails, normalize the news-branch delivery counting in `src/crawler/search_pipeline.rs` to this exact match block:

```rust
                match maybe_deliver_to_tarkov(&payload).await {
                    Ok(Some(_)) => summary.delivered += 1,
                    Ok(None) => {}
                    Err(_) => summary.delivery_failed += 1,
                }
```

Do not remove the outbox append before delivery.

- [ ] **Step 4: Run the delivery-failure test**

Run: `cargo test --test search_pipeline search_company_counts_tarkov_delivery_failures_without_losing_outbox_records -- --exact`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/crawler/search_pipeline.rs tests/search_pipeline.rs
git commit -m "fix: count search-company delivery failures"
```

### Task 9: Final Verification And Docs Check

**Files:**
- Modify: `tests/cli.rs` if output wording changed during implementation
- Modify: `README.md` or `docs/USAGE.md` only if the command needs user-facing documentation immediately

- [ ] **Step 1: Run targeted tests for the new feature**

Run: `cargo test --test cli && cargo test --test search_pipeline && cargo test --test company_pipeline`

Expected: PASS

- [ ] **Step 2: Run the full crate test suite**

Run: `cargo test`

Expected: PASS

- [ ] **Step 3: Run a fast compile check**

Run: `cargo check`

Expected: PASS

- [ ] **Step 4: Update docs only if command help or usage is now stale**

If needed, add this usage block to `docs/USAGE.md` or `README.md`:

```text
cargo run -- search-company "Allegro"
cargo run -- search-company "Allegro" --news-only
cargo run -- search-company "Allegro" --registry-only
```

- [ ] **Step 5: Commit final verification or docs changes**

```bash
git add README.md docs/USAGE.md tests/cli.rs tests/search_pipeline.rs
git commit -m "docs: document company search command"
```

## Self-Review

- Spec coverage checked:
  - new `search-company` command: Tasks 1, 3, 4, 6
  - DuckDuckGo discovery: Tasks 2, 4, 5
  - env var article limit: Tasks 1, 4, 5
  - registry enrichment via `krs` or `nip`: Tasks 6, 7
  - outbox writes and Tarkov delivery: Tasks 4, 8
  - partial-success and branch-specific failure handling: Task 7
  - tests and summary output: Tasks 3, 7, 8, 9
- Placeholder scan checked:
  - no `TODO`, `TBD`, or “similar to above” placeholders remain
- Type consistency checked:
  - `SearchCompanySummary`, `search_company_with_config`, `format_search_company_output`, and `resolve_company_record` names are used consistently across tasks
