//! RSS-based company article discovery helpers.

use anyhow::Context;
use feed_rs::parser;

const SEARCH_BASE_URL: &str = "https://www.bing.com/news/search?q=";

fn search_base_url() -> String {
    std::env::var("SCUTTLE_COMPANY_SEARCH_BASE_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| SEARCH_BASE_URL.to_string())
}

pub fn build_search_url(query: &str) -> String {
    format!(
        "{}{}&format=rss",
        search_base_url(),
        url::form_urlencoded::byte_serialize(query.as_bytes()).collect::<String>()
    )
}

pub fn parse_result_urls(feed_xml: &str) -> anyhow::Result<Vec<String>> {
    let feed = parser::parse(feed_xml.as_bytes()).context("failed to parse search RSS feed")?;
    Ok(feed
        .entries
        .into_iter()
        .filter_map(|entry| entry.links.into_iter().next())
        .filter_map(|link| unwrap_result_link(&link.href))
        .collect())
}

fn unwrap_result_link(raw: &str) -> Option<String> {
    let parsed = url::Url::parse(raw).ok()?;
    if parsed.domain() == Some("www.bing.com") {
        for (key, value) in parsed.query_pairs() {
            if key == "url" {
                return Some(value.into_owned());
            }
        }
    }

    Some(raw.to_string())
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
    fn builds_bing_news_rss_search_url_from_query() {
        let url = build_search_url("Allegro news");
        assert!(url.starts_with("https://www.bing.com/news/search?q="));
        assert!(url.contains("Allegro%20news") || url.contains("Allegro+news"));
        assert!(url.ends_with("&format=rss"));
    }

    #[test]
    fn extracts_direct_links_from_bing_rss() {
        let xml = r#"
        <rss version="2.0">
          <channel>
            <item>
              <title>Article 1</title>
              <link>http://www.bing.com/news/apiclick.aspx?url=https%3A%2F%2Fexample.com%2Farticle-1&amp;foo=bar</link>
            </item>
            <item>
              <title>Article 2</title>
              <link>https://example.com/article-2</link>
            </item>
          </channel>
        </rss>
        "#;

        let urls = parse_result_urls(xml).expect("links should parse");
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
                "http://localhost:9999/news/search?q=",
            );
        }

        let url = build_search_url("Allegro");

        unsafe {
            std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
        }

        assert_eq!(url, "http://localhost:9999/news/search?q=Allegro&format=rss");
    }
}
