//! RSS/Atom discovery helpers.

use std::collections::{HashSet, VecDeque};

use anyhow::Context;
use scraper::{Html, Selector};
use url::Url;

use crate::domain::source::CrawlSource;
use crate::utils::url::normalize_url;

/// Discover article URLs from one configured source.
pub async fn discover_urls(
    client: &reqwest::Client,
    source: &CrawlSource,
) -> anyhow::Result<Vec<String>> {
    if let Some(feed_url) = &source.feed_url {
        return discover_feed_urls(client, source, feed_url).await;
    }

    if let Some(page_url) = &source.page_url {
        return discover_page_urls(client, source, page_url).await;
    }

    Ok(Vec::new())
}

async fn discover_feed_urls(
    client: &reqwest::Client,
    source: &CrawlSource,
    feed_url: &str,
) -> anyhow::Result<Vec<String>> {
    let response = client
        .get(feed_url)
        .send()
        .await
        .with_context(|| format!("request failed for feed {feed_url}"))?
        .error_for_status()
        .with_context(|| format!("non-success status for feed {feed_url}"))?;

    let body = response
        .bytes()
        .await
        .with_context(|| format!("failed to read feed body for {feed_url}"))?;
    let feed = feed_rs::parser::parse(body.as_ref())
        .with_context(|| format!("failed to parse feed {feed_url}"))?;

    let mut seen = HashSet::new();
    let mut urls = Vec::new();

    for entry in feed.entries {
        for link in entry.links {
            if !source.allows_url(&link.href) {
                continue;
            }

            let Ok(normalized) = normalize_url(&link.href) else {
                continue;
            };

            if seen.insert(normalized.clone()) {
                urls.push(normalized);
                break;
            }
        }
    }

    Ok(urls)
}

async fn discover_page_urls(
    client: &reqwest::Client,
    source: &CrawlSource,
    page_url: &str,
) -> anyhow::Result<Vec<String>> {
    let mut queue = VecDeque::from([(page_url.to_string(), 0usize)]);
    let mut visited_pages = HashSet::new();
    let mut discovered_urls = Vec::new();
    let mut discovered_set = HashSet::new();

    while let Some((current_url, depth)) = queue.pop_front() {
        let normalized_current = normalize_url(&current_url)
            .with_context(|| format!("invalid page url {current_url}"))?;
        if !visited_pages.insert(normalized_current.clone()) {
            continue;
        }

        let should_emit_current = depth > 0 || source.include_page_url;
        if should_emit_current && discovered_set.insert(normalized_current.clone()) {
            discovered_urls.push(normalized_current.clone());
        }

        if depth >= source.max_depth {
            continue;
        }

        let child_urls = discover_links_on_page(client, source, &current_url).await?;
        for child_url in child_urls {
            if !visited_pages.contains(&child_url) {
                queue.push_back((child_url, depth + 1));
            }
        }
    }

    Ok(discovered_urls)
}

async fn discover_links_on_page(
    client: &reqwest::Client,
    source: &CrawlSource,
    page_url: &str,
) -> anyhow::Result<Vec<String>> {
    let selector_text = source.article_link_selector.as_deref().unwrap_or("a[href]");
    let selector = Selector::parse(selector_text)
        .map_err(|_| anyhow::anyhow!("invalid article link selector: {selector_text}"))?;

    let response = client
        .get(page_url)
        .send()
        .await
        .with_context(|| format!("request failed for page {page_url}"))?
        .error_for_status()
        .with_context(|| format!("non-success status for page {page_url}"))?;
    let final_page_url = response.url().clone();
    let body = response
        .text()
        .await
        .with_context(|| format!("failed to read page body for {page_url}"))?;

    let document = Html::parse_document(&body);
    let mut seen = HashSet::new();
    let mut urls = Vec::new();

    for node in document.select(&selector) {
        let Some(href) = node.value().attr("href") else {
            continue;
        };

        let Ok(resolved) = final_page_url.join(href) else {
            continue;
        };

        if !is_http_url(&resolved) || !source.allows_url(resolved.as_str()) {
            continue;
        }

        let Ok(normalized) = normalize_url(resolved.as_str()) else {
            continue;
        };

        if seen.insert(normalized.clone()) {
            urls.push(normalized);
        }
    }

    Ok(urls)
}

fn is_http_url(url: &Url) -> bool {
    matches!(url.scheme(), "http" | "https")
}
