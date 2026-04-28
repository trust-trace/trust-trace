//! Company search orchestration.

use std::collections::HashSet;

use anyhow::bail;

use crate::config::AppConfig;
use crate::crawler::company_pipeline::{resolve_company_record, scrape_company_with_config};
use crate::crawler::delivery::maybe_deliver_to_tarkov;
use crate::crawler::fetch::{build_http_client, fetch_article_payload};
use crate::crawler::search_discovery::discover_company_article_urls;
use crate::storage::jsonl::JsonlOutbox;
use crate::storage::seen_urls::SeenUrlStore;

const REQUIRED_NEWS_ARTICLES: usize = 10;
const DISCOVERY_CANDIDATE_LIMIT: usize = 50;

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
    let company = resolve_company_record(config, query)?;

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

    if !news_only {
        match company.as_ref().and_then(|company| company.krs.clone()) {
            Some(krs) => match scrape_company_with_config(config, &krs).await {
                Ok(registry_summary) => {
                    summary.registry_emitted += registry_summary.emitted;
                    summary.registry_failed += registry_summary.failed;
                }
                Err(error) if registry_only => return Err(error),
                Err(_) => summary.registry_failed += 1,
            },
            None if registry_only => bail!("company is missing krs and nip for registry lookup"),
            None => {}
        }
    }

    Ok(summary)
}

async fn run_news_branch(
    config: &AppConfig,
    query: &str,
    summary: &mut SearchCompanySummary,
) -> anyhow::Result<()> {
    let client = build_http_client()?;
    let outbox = JsonlOutbox::new(&config.outbox_path);
    let mut seen_urls = SeenUrlStore::load(&config.seen_urls_path)?;
    let mut pending_urls = HashSet::new();
    let mut accepted_news_articles = 0usize;
    let required_news_articles = config.company_article_limit().min(REQUIRED_NEWS_ARTICLES);
    let urls = discover_company_article_urls(&client, query, DISCOVERY_CANDIDATE_LIMIT).await?;

    for url in urls {
        summary.news_discovered += 1;

        if seen_urls.contains(&url)? || !pending_urls.insert(url.clone()) {
            summary.news_skipped += 1;
            continue;
        }

        match fetch_article_payload(&url).await {
            Ok(payload) => {
                println!("NEWS {}", payload.source.url);
                outbox.append(&payload)?;

                let canonical_url = payload
                    .article
                    .canonical_url
                    .as_deref()
                    .unwrap_or(&payload.source.url);
                let recorded = seen_urls.record(
                    canonical_url,
                    &payload.source.name,
                    &payload.article.scraped_at,
                )?;

                if recorded {
                    summary.news_emitted += 1;
                    accepted_news_articles += 1;
                } else {
                    summary.news_skipped += 1;
                }

                match maybe_deliver_to_tarkov(&payload).await {
                    Ok(Some(_)) => summary.delivered += 1,
                    Ok(None) => {}
                    Err(_) => summary.delivery_failed += 1,
                }
            }
            Err(_) => summary.news_failed += 1,
        }

        if accepted_news_articles >= required_news_articles {
            break;
        }
    }

    if accepted_news_articles < required_news_articles {
        anyhow::bail!(
            "failed to deliver {required_news_articles} news articles after exhausting candidates"
        );
    }

    Ok(())
}
