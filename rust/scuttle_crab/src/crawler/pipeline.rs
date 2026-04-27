//! Feed-based crawl orchestration.

use std::collections::HashSet;
use std::sync::Arc;

use tokio::sync::Semaphore;
use tokio::task::JoinSet;

use crate::config::AppConfig;
use crate::crawler::discovery::discover_urls;
use crate::crawler::fetch::{build_article_payload, build_http_client};
use crate::domain::source::{CrawlSource, SourceInfo, load_sources};
use crate::storage::jsonl::JsonlOutbox;
use crate::storage::seen_urls::SeenUrlStore;

/// Aggregate crawl metrics for one run.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CrawlSummary {
    pub sources: usize,
    pub discovered: usize,
    pub skipped: usize,
    pub emitted: usize,
    pub failed: usize,
}

/// Run the feed-based crawl pipeline using the supplied config.
pub async fn crawl_with_config(config: &AppConfig) -> anyhow::Result<CrawlSummary> {
    let sources = load_sources(&config.sources_path)?;
    let mut summary = CrawlSummary {
        sources: sources.len(),
        ..CrawlSummary::default()
    };

    if sources.is_empty() {
        return Ok(summary);
    }

    let client = build_http_client()?;
    let semaphore = Arc::new(Semaphore::new(config.concurrency.max(1)));
    let mut seen_urls = SeenUrlStore::load(&config.seen_urls_path)?;
    let mut pending_urls = HashSet::new();
    let outbox = JsonlOutbox::new(&config.outbox_path);
    let mut join_set = JoinSet::new();

    for source in sources {
        let urls = match discover_urls(&client, &source).await {
            Ok(urls) => urls,
            Err(_) => {
                summary.failed += 1;
                continue;
            }
        };

        for url in urls {
            summary.discovered += 1;

            if seen_urls.contains(&url)? || !pending_urls.insert(url.clone()) {
                summary.skipped += 1;
                continue;
            }

            let client = client.clone();
            let semaphore = Arc::clone(&semaphore);
            let source = source.clone();

            join_set.spawn(async move {
                let _permit = semaphore
                    .acquire_owned()
                    .await
                    .expect("semaphore should be available");
                fetch_one(client, source, url).await
            });
        }
    }

    while let Some(result) = join_set.join_next().await {
        match result {
            Ok(Ok((source_name, canonical_url, payload))) => {
                outbox.append(&payload)?;
                let recorded =
                    seen_urls.record(&canonical_url, &source_name, &payload.article.scraped_at)?;
                if recorded {
                    summary.emitted += 1;
                } else {
                    summary.skipped += 1;
                }
            }
            Ok(Err(_)) | Err(_) => {
                summary.failed += 1;
            }
        }
    }

    Ok(summary)
}

async fn fetch_one(
    client: reqwest::Client,
    source: CrawlSource,
    url: String,
) -> anyhow::Result<(String, String, crate::domain::article::ArticlePayload)> {
    let response = client.get(&url).send().await?.error_for_status()?;
    let http_status = response.status().as_u16();
    let final_url = response.url().to_string();

    if !source.allows_url(&final_url) {
        anyhow::bail!("final article url is outside allowed domains: {final_url}");
    }

    let html = response.text().await?;
    let source_info = SourceInfo {
        name: source.name.clone(),
        domain: payload_domain(&final_url),
        url: final_url.clone(),
        credibility_score: source.credibility_score,
        credibility_label: source.credibility_label.clone(),
    };
    let mut payload = build_article_payload(
        &final_url,
        &html,
        http_status,
        &chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
        "rss",
    )?;
    payload.source = source_info;

    Ok((source.name, final_url, payload))
}

fn payload_domain(url: &str) -> String {
    url::Url::parse(url)
        .ok()
        .and_then(|parsed| parsed.host_str().map(str::to_string))
        .unwrap_or_else(|| "unknown".to_string())
}
