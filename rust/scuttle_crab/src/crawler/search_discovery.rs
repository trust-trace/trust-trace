//! DuckDuckGo-based company article discovery helpers.

use anyhow::{Context, bail};
use scraper::{Html, Selector};

const SEARCH_BASE_URL: &str = "https://html.duckduckgo.com/html/?q=";

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

pub fn parse_result_urls(html: &str) -> anyhow::Result<Vec<String>> {
    if html.contains("Unfortunately, bots use DuckDuckGo too") {
        bail!("duckduckgo challenge page returned");
    }

    let document = Html::parse_document(html);
    let selector = Selector::parse("a.result__a").expect("valid result selector");

    Ok(document
        .select(&selector)
        .filter_map(|node| node.value().attr("href"))
        .map(str::to_string)
        .collect())
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
        assert_eq!(
            urls,
            vec![
                "https://example.com/article-1".to_string(),
                "https://example.com/article-2".to_string(),
            ]
        );
    }

    #[test]
    fn uses_override_search_base_url_when_present() {
        unsafe {
            std::env::set_var(
                "SCUTTLE_COMPANY_SEARCH_BASE_URL",
                "http://localhost:9999/html/?q=",
            );
        }

        let url = build_search_url("Allegro");

        unsafe {
            std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
        }

        assert_eq!(url, "http://localhost:9999/html/?q=Allegro");
    }
}
