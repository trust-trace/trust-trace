//! Fetch and extract readable text from article pages.

use anyhow::Context;
use chrono::{SecondsFormat, Utc};
use scraper::{Html, Selector};
use url::Url;

use crate::domain::article::{ArticlePayload, ArticleSection, ArticleText, MetadataSection};
use crate::domain::source::SourceInfo;

const DEFAULT_USER_AGENT: &str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36";

/// Build the shared HTTP client used for live fetches.
pub fn build_http_client() -> anyhow::Result<reqwest::Client> {
    Ok(reqwest::Client::builder()
        .user_agent(DEFAULT_USER_AGENT)
        .http1_only()
        .build()?)
}

/// Fetch one URL and return extracted title and readable text.
pub async fn fetch_article_text(url: &str) -> anyhow::Result<(String, String)> {
    let response = build_http_client()?
        .get(url)
        .send()
        .await
        .with_context(|| format!("request failed for {url}"))?
        .error_for_status()
        .with_context(|| format!("non-success status for {url}"))?;

    let html = response
        .text()
        .await
        .with_context(|| format!("failed to read body for {url}"))?;

    Ok(extract_text_from_html(&html))
}

/// Fetch one URL and return a fully-constructed outbound article payload.
pub async fn fetch_article_payload(url: &str) -> anyhow::Result<ArticlePayload> {
    fetch_article_payload_for_source(url, None, "fetch-url").await
}

/// Fetch one URL and return a payload enriched with source-specific metadata.
pub async fn fetch_article_payload_for_source(
    url: &str,
    source_info: Option<SourceInfo>,
    discovery_method: &str,
) -> anyhow::Result<ArticlePayload> {
    let response = build_http_client()?
        .get(url)
        .send()
        .await
        .with_context(|| format!("request failed for {url}"))?
        .error_for_status()
        .with_context(|| format!("non-success status for {url}"))?;

    let http_status = response.status().as_u16();
    let final_url = response.url().to_string();
    let html = response
        .text()
        .await
        .with_context(|| format!("failed to read body for {final_url}"))?;

    let scraped_at = Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true);
    let mut payload = build_article_payload(
        &final_url,
        &html,
        http_status,
        &scraped_at,
        discovery_method,
    )?;

    if let Some(source_info) = source_info {
        payload.source.name = source_info.name;
        payload.source.credibility_score = source_info.credibility_score;
        payload.source.credibility_label = source_info.credibility_label;
    }

    Ok(payload)
}

/// Build a payload from HTML and request metadata.
pub fn build_article_payload(
    source_url: &str,
    html: &str,
    http_status: u16,
    scraped_at: &str,
    discovery_method: &str,
) -> anyhow::Result<ArticlePayload> {
    let parsed = Url::parse(source_url)
        .with_context(|| format!("invalid source url for payload: {source_url}"))?;
    let domain = parsed.host_str().unwrap_or("unknown").to_string();
    let source_name = domain.strip_prefix("www.").unwrap_or(&domain).to_string();

    let (title, text) = extract_text_from_html(html);
    let word_count = text.split_whitespace().count() as u32;

    Ok(ArticlePayload {
        source: SourceInfo {
            name: source_name,
            domain,
            url: source_url.to_string(),
            credibility_score: 0.5,
            credibility_label: "unrated".to_string(),
        },
        article: ArticleSection {
            title,
            text: ArticleText(text),
            language: None,
            authors: Vec::new(),
            published_at: scraped_at.to_string(),
            scraped_at: scraped_at.to_string(),
            canonical_url: Some(source_url.to_string()),
            word_count: Some(word_count),
        },
        metadata: MetadataSection {
            section: None,
            region: None,
            discovery_method: Some(discovery_method.to_string()),
            http_status: Some(http_status),
            ..MetadataSection::default()
        },
    })
}

/// Parse raw HTML into a title and visible article text.
pub fn extract_text_from_html(html: &str) -> (String, String) {
    let document = Html::parse_document(html);
    let title = extract_title(&document);
    let text = extract_visible_text(&document);
    (title, text)
}

fn extract_title(document: &Html) -> String {
    let selector = Selector::parse("title").expect("valid title selector");

    document
        .select(&selector)
        .next()
        .map(|node| clean_text(&node.text().collect::<Vec<_>>().join(" ")))
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| "untitled".to_string())
}

fn extract_visible_text(document: &Html) -> String {
    let selector =
        Selector::parse("article, main, p, h1, h2, h3, li").expect("valid content selector");
    let mut parts: Vec<String> = Vec::new();

    for node in document.select(&selector) {
        let text = clean_text(&node.text().collect::<Vec<_>>().join(" "));
        if text.len() >= 20 {
            parts.push(text);
        }
    }

    dedup_preserving_order(parts).join("\n\n")
}

fn dedup_preserving_order(parts: Vec<String>) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    let mut out = Vec::new();

    for part in parts {
        if seen.insert(part.clone()) {
            out.push(part);
        }
    }

    out
}

fn clean_text(input: &str) -> String {
    input.split_whitespace().collect::<Vec<_>>().join(" ")
}

#[cfg(test)]
mod tests {
    use super::{build_article_payload, extract_text_from_html};

    #[test]
    fn extracts_title_and_main_visible_text() {
        let html = r#"
        <html>
          <head>
            <title>Example Story</title>
            <style>.hidden { display: none; }</style>
            <script>console.log('noise');</script>
          </head>
          <body>
            <main>
              <h1>Breaking: Example Story</h1>
              <p>This is a readable paragraph with enough length to be kept in output text.</p>
              <p>This is another paragraph that should also appear in the extracted content output.</p>
            </main>
          </body>
        </html>
        "#;

        let (title, text) = extract_text_from_html(html);

        assert_eq!(title, "Example Story");
        assert!(text.contains("Breaking: Example Story"));
        assert!(text.contains("readable paragraph with enough length"));
        assert!(!text.contains("console.log"));
    }

    #[test]
    fn builds_full_payload_from_html_and_source_metadata() {
        let html = r#"
        <html>
          <head><title>Payload Title</title></head>
          <body>
            <article>
              <p>First visible paragraph long enough to be retained by extraction logic.</p>
              <p>Second paragraph also long enough to count toward word count in payload.</p>
            </article>
          </body>
        </html>
        "#;

        let payload = build_article_payload(
            "http://localhost:8787/en_01_solorz_succession.html",
            html,
            200,
            "2026-04-27T14:00:00Z",
            "fetch-url",
        )
        .expect("payload should build");

        assert_eq!(payload.source.domain, "localhost");
        assert_eq!(
            payload.source.url,
            "http://localhost:8787/en_01_solorz_succession.html"
        );
        assert_eq!(payload.source.credibility_label, "unrated");
        assert_eq!(payload.article.title, "Payload Title");
        assert!(payload.article.text.0.contains("First visible paragraph"));
        assert_eq!(payload.article.scraped_at, "2026-04-27T14:00:00Z");
        assert_eq!(payload.article.published_at, "2026-04-27T14:00:00Z");
        assert_eq!(payload.metadata.http_status, Some(200));
        assert_eq!(
            payload.metadata.discovery_method.as_deref(),
            Some("fetch-url")
        );
        assert!(payload.article.word_count.unwrap_or(0) > 0);
    }
}
