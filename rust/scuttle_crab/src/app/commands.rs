use serde::{Deserialize, Serialize};

use std::collections::HashSet;
use std::net::IpAddr;
use std::path::{Component, Path};

use anyhow::bail;

use crate::config::AppConfig;
use crate::crawler::company_pipeline::{resolve_company_record, scrape_company_payloads_with_config};
use crate::crawler::delivery::{deliver_to_tarkov, required_tarkov_delivery_config};
use crate::crawler::discovery::discover_urls;
use crate::crawler::fetch::{build_http_client, fetch_article_payload, fetch_article_payload_for_source};
use crate::crawler::search_discovery::discover_company_article_urls;
use crate::domain::source::{SourceInfo, load_sources};
use crate::storage::seen_urls::SeenUrlStore;

#[derive(Debug, Clone)]
pub enum CommandRequest {
    Crawl {
        sources_file: Option<String>,
    },
    FetchUrl {
        url: String,
    },
    ScrapeCompany {
        query: String,
    },
    SearchCompany {
        query: String,
        news_only: bool,
        registry_only: bool,
    },
    TestSource {
        source: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CommandSummary {
    pub delivered: usize,
    pub delivery_failed: usize,
    pub message: String,
}

pub async fn execute_command(request: CommandRequest) -> anyhow::Result<CommandSummary> {
    match request {
        CommandRequest::Crawl { sources_file } => execute_crawl(sources_file).await,
        CommandRequest::FetchUrl { url } => execute_fetch_url(&url).await,
        CommandRequest::ScrapeCompany { query } => execute_scrape_company(&query).await,
        CommandRequest::SearchCompany {
            query,
            news_only,
            registry_only,
        } => execute_search_company(&query, news_only, registry_only).await,
        CommandRequest::TestSource { source } => execute_test_source(&source).await,
    }
}

async fn execute_crawl(sources_file: Option<String>) -> anyhow::Result<CommandSummary> {
    required_tarkov_delivery_config()?;
    let config = AppConfig::default().with_sources_path(validate_api_sources_file(sources_file.as_deref())?)?;
    let client = build_http_client()?;
    let mut seen_urls = SeenUrlStore::load(&config.seen_urls_path)?;
    let mut pending_urls = HashSet::new();
    let mut delivered = 0;
    let mut delivery_failed = 0;

    for source in load_sources(&config.sources_path)? {
        let urls = discover_urls(&client, &source).await?;
        for url in urls {
            if ensure_public_http_url(&url).is_err() {
                continue;
            }

            if seen_urls.contains(&url)? || !pending_urls.insert(url.clone()) {
                continue;
            }

            let source_info = SourceInfo {
                name: source.name.clone(),
                domain: url::Url::parse(&url)
                    .ok()
                    .and_then(|parsed| parsed.host_str().map(str::to_string))
                    .unwrap_or_else(|| "unknown".to_string()),
                url: url.clone(),
                credibility_score: source.credibility_score,
                credibility_label: source.credibility_label.clone(),
            };
            let payload = fetch_article_payload_for_source(&url, Some(source_info), "rss").await?;
            let canonical_url = payload
                .article
                .canonical_url
                .clone()
                .unwrap_or_else(|| payload.source.url.clone());

            match deliver_to_tarkov(&payload).await {
                Ok(_) => {
                    seen_urls.record(&canonical_url, &payload.source.name, &payload.article.scraped_at)?;
                    delivered += 1;
                }
                Err(_) => delivery_failed += 1,
            }
        }
    }

    if delivery_failed > 0 {
        bail!("failed to deliver one or more crawl payloads to Tarkov");
    }

    Ok(CommandSummary {
        delivered,
        delivery_failed,
        message: format!("crawl finished: delivered={delivered}"),
    })
}

async fn execute_fetch_url(url: &str) -> anyhow::Result<CommandSummary> {
    required_tarkov_delivery_config()?;
    ensure_public_http_url(url)?;
    let payload = fetch_article_payload(url).await?;
    deliver_to_tarkov(&payload).await?;
    Ok(CommandSummary {
        delivered: 1,
        delivery_failed: 0,
        message: format!("fetch-url delivered payload for {url}"),
    })
}

async fn execute_scrape_company(query: &str) -> anyhow::Result<CommandSummary> {
    required_tarkov_delivery_config()?;
    let result = scrape_company_payloads_with_config(&AppConfig::default(), query).await?;
    let mut delivered = 0;
    let mut delivery_failed = 0;

    for payload in result.payloads {
        match deliver_to_tarkov(&payload).await {
            Ok(_) => delivered += 1,
            Err(_) => delivery_failed += 1,
        }
    }

    if delivery_failed > 0 {
        bail!("failed to deliver one or more registry payloads to Tarkov");
    }

    Ok(CommandSummary {
        delivered,
        delivery_failed,
        message: format!("scrape-company finished: delivered={delivered}"),
    })
}

async fn execute_search_company(
    query: &str,
    news_only: bool,
    registry_only: bool,
) -> anyhow::Result<CommandSummary> {
    required_tarkov_delivery_config()?;
    if news_only && registry_only {
        bail!("news_only and registry_only cannot both be true");
    }

    let config = AppConfig::default();
    let company = resolve_company_record(&config, query)?;
    let mut delivered = 0;
    let mut delivery_failed = 0;

    if !registry_only {
        let client = build_http_client()?;
        let search_query = company.as_ref().map(|value| value.name.as_str()).unwrap_or(query);
        let urls = discover_company_article_urls(&client, search_query, config.company_article_limit()).await?;
        let mut seen_urls = SeenUrlStore::load(&config.seen_urls_path)?;
        let mut pending_urls = HashSet::new();

        for url in urls {
            if ensure_public_http_url(&url).is_err() {
                continue;
            }

            if seen_urls.contains(&url)? || !pending_urls.insert(url.clone()) {
                continue;
            }

            let payload = fetch_article_payload(&url).await?;
            let canonical_url = payload
                .article
                .canonical_url
                .clone()
                .unwrap_or_else(|| payload.source.url.clone());

            match deliver_to_tarkov(&payload).await {
                Ok(_) => {
                    seen_urls.record(&canonical_url, &payload.source.name, &payload.article.scraped_at)?;
                    delivered += 1;
                }
                Err(_) => delivery_failed += 1,
            }
        }
    }

    if !news_only {
        let lookup = company.ok_or_else(|| anyhow::anyhow!("company is missing krs and nip for registry lookup"))?;
        let lookup_query = lookup.krs.clone().or(lookup.nip.clone()).ok_or_else(|| anyhow::anyhow!("company is missing krs and nip for registry lookup"))?;
        let result = scrape_company_payloads_with_config(&config, &lookup_query).await?;
        for payload in result.payloads {
            match deliver_to_tarkov(&payload).await {
                Ok(_) => delivered += 1,
                Err(_) => delivery_failed += 1,
            }
        }
    }

    if delivery_failed > 0 {
        bail!("failed to deliver one or more search-company payloads to Tarkov");
    }

    Ok(CommandSummary {
        delivered,
        delivery_failed,
        message: format!("search-company finished: delivered={delivered}"),
    })
}

async fn execute_test_source(source: &str) -> anyhow::Result<CommandSummary> {
    let config = AppConfig::default();
    let sources = load_sources(&config.sources_path)?;
    if !sources.iter().any(|candidate| candidate.name.eq_ignore_ascii_case(source)) {
        bail!("source '{source}' was not found in {}", config.sources_path);
    }

    Ok(CommandSummary {
        delivered: 0,
        delivery_failed: 0,
        message: format!("test-source resolved {source}"),
    })
}

fn validate_api_sources_file(sources_file: Option<&str>) -> anyhow::Result<Option<String>> {
    let Some(sources_file) = sources_file else {
        return Ok(None);
    };

    let path = Path::new(sources_file);
    if path.is_absolute() {
        bail!("sources_file must stay under data/");
    }

    let mut components = path.components();
    let first = components.next();
    if first != Some(Component::Normal(std::ffi::OsStr::new("data"))) {
        bail!("sources_file must stay under data/");
    }

    if path.components().any(|component| matches!(component, Component::ParentDir)) {
        bail!("sources_file must stay under data/");
    }

    Ok(Some(sources_file.to_string()))
}

fn ensure_public_http_url(url: &str) -> anyhow::Result<()> {
    let parsed = url::Url::parse(url)?;
    if !matches!(parsed.scheme(), "http" | "https") {
        bail!("url must be a public http/https url");
    }

    let host = parsed.host_str().ok_or_else(|| anyhow::anyhow!("url must include a host"))?;
    if host.eq_ignore_ascii_case("localhost") {
        bail!("url must be a public http/https url");
    }

    if let Ok(ip) = host.parse::<IpAddr>() {
        let forbidden = match ip {
            IpAddr::V4(ip) => {
                ip.is_private()
                    || ip.is_loopback()
                    || ip.is_link_local()
                    || ip.is_broadcast()
                    || ip.is_documentation()
                    || ip.is_unspecified()
            }
            IpAddr::V6(ip) => ip.is_loopback() || ip.is_unspecified() || ip.is_unique_local(),
        };

        if forbidden {
            bail!("url must be a public http/https url");
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{CommandRequest, ensure_public_http_url, execute_command, validate_api_sources_file};

    #[tokio::test]
    async fn api_execution_requires_tarkov_delivery_config() {
        unsafe {
            std::env::remove_var("TARKOV_BASE_URL");
        }

        let error = execute_command(CommandRequest::FetchUrl {
            url: "https://example.com/article".to_string(),
        })
        .await
        .expect_err("execution should fail without tarkov config");

        assert!(error.to_string().contains("TARKOV_BASE_URL"));
    }

    #[test]
    fn rejects_loopback_fetch_urls() {
        let error = ensure_public_http_url("http://127.0.0.1:8080/private")
            .expect_err("loopback url should be rejected");

        assert!(error.to_string().contains("public http/https url"));
    }

    #[test]
    fn accepts_public_https_urls() {
        ensure_public_http_url("https://example.com/article")
            .expect("public https url should be accepted");
    }

    #[test]
    fn rejects_sources_file_outside_data_directory() {
        let error = validate_api_sources_file(Some("/etc/passwd"))
            .expect_err("absolute path should be rejected");

        assert!(error.to_string().contains("data/"));
    }

    #[test]
    fn accepts_sources_file_inside_data_directory() {
        let path = validate_api_sources_file(Some("data/custom-sources.json"))
            .expect("data path should be accepted");

        assert_eq!(path.as_deref(), Some("data/custom-sources.json"));
    }
}
