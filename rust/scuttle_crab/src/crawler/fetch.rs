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

    let article = extract_article_document(html);
    let ExtractedArticle { title, text, body_blocks, article_semantics } = article;
    let word_count = text.split_whitespace().count() as u32;

    if !has_substantial_body_block(&title, &body_blocks, article_semantics) {
        anyhow::bail!(
            "extracted article text looks unavailable for payload: {word_count} words from {source_url}"
        );
    }

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
    let article = extract_article_document(html);
    (article.title, article.text)
}

struct ExtractedArticle {
    title: String,
    text: String,
    body_blocks: Vec<String>,
    article_semantics: bool,
}

fn extract_article_document(html: &str) -> ExtractedArticle {
    let document = Html::parse_document(html);
    let title = extract_title(&document);
    let (text, body_blocks, article_semantics) = extract_visible_text(&document);

    ExtractedArticle { title, text, body_blocks, article_semantics }
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

fn extract_visible_text(document: &Html) -> (String, Vec<String>, bool) {
    let selector =
        Selector::parse("article, main, p, h1, h2, h3, li").expect("valid content selector");
    let semantic_selector = Selector::parse("article, main, p").expect("valid semantic selector");
    let mut parts: Vec<String> = Vec::new();

    for node in document.select(&selector) {
        let text = clean_text(&node.text().collect::<Vec<_>>().join(" "));
        if text.len() >= 12 {
            parts.push(text);
        }
    }

    let body_blocks = dedup_preserving_order(parts);
    let article_semantics = document.select(&semantic_selector).any(|node| {
        clean_text(&node.text().collect::<Vec<_>>().join(" ")).split_whitespace().count() >= 8
    });
    (body_blocks.join("\n\n"), body_blocks, article_semantics)
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

fn has_substantial_body_block(title: &str, body_blocks: &[String], article_semantics: bool) -> bool {
    let title_norm = normalized_text(title);
    let visible_words: usize = body_blocks.iter().map(|block| block.split_whitespace().count()).sum();
    let distinct_blocks = body_blocks.len();
    let max_block_words = body_blocks
        .iter()
        .map(|block| block.split_whitespace().count())
        .max()
        .unwrap_or(0);
    let repeated_title_only = body_blocks.len() == 1 && is_near_title_only_body(&title_norm, &body_blocks[0]);
    let strong_body_block = body_blocks.iter().any(|block| {
        let word_count = block.split_whitespace().count();
        word_count >= 18 && block.chars().any(|ch| matches!(ch, '.' | '!' | '?'))
    });
    let title_shell = title_norm.contains("unavailable") || title_norm.contains("not found");
    let boilerplate_shell = body_blocks.iter().any(|block| {
        let lowered = block.to_lowercase();
        lowered.contains("return to the homepage")
            || lowered.contains("site map")
            || lowered.contains("home contact news")
            || (title_shell && lowered.contains("could not be found"))
    });

    if repeated_title_only || boilerplate_shell {
        return false;
    }

    let positive_structure = distinct_blocks > 1 || strong_body_block || article_semantics;
    let density_ok = visible_words >= 8
        && (strong_body_block || distinct_blocks > 1 || article_semantics || max_block_words >= 8);

    positive_structure && density_ok
}

fn is_near_title_only_body(title_norm: &str, body_block: &str) -> bool {
    let body_norm = normalized_text(body_block);
    let title_words = title_norm.split_whitespace().count();
    let body_words = body_norm.split_whitespace().count();

    if body_norm == title_norm {
        return true;
    }

    if body_norm.starts_with(title_norm) {
        let remainder = body_norm[title_norm.len()..].trim();
        let remainder_words = remainder.split_whitespace().count();
        return remainder_words <= 3 && body_words <= title_words + 3;
    }

    if title_norm.starts_with(&body_norm) {
        let remainder = title_norm[body_norm.len()..].trim();
        let remainder_words = remainder.split_whitespace().count();
        return remainder_words <= 3 && title_words <= body_words + 3;
    }

    false
}

fn normalized_text(input: &str) -> String {
    input
        .to_lowercase()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

#[cfg(test)]
mod tests {
    use super::{build_article_payload, extract_text_from_html};
    use axum::{routing::get, Router};
    use tokio::net::TcpListener;

    async fn spawn_test_server(html: &'static str) -> String {
        let app = Router::new().route("/article", get(move || async move { html }));
        let listener = TcpListener::bind("127.0.0.1:0").await.expect("bind test server");
        let addr = listener.local_addr().expect("local addr");
        tokio::spawn(async move {
            axum::serve(listener, app).await.expect("serve test server");
        });
        format!("http://{}", addr)
    }

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

    #[test]
    fn allows_short_but_real_article_content() {
        let html = r#"
        <html>
          <head><title>Short Story</title></head>
          <body>
            <main>
              <p>Brief update: rain delayed the launch, but the event still opened tonight.</p>
            </main>
          </body>
        </html>
        "#;

        let payload = build_article_payload(
            "http://localhost:8787/short-story.html",
            html,
            200,
            "2026-04-27T14:00:00Z",
            "fetch-url",
        )
        .expect("payload should build");

        assert_eq!(payload.article.title, "Short Story");
        assert!(payload.article.text.0.contains("Brief update"));
        assert!(payload.article.word_count.unwrap_or(0) < 20);
    }

    #[test]
    fn allows_single_block_article_that_starts_with_title_and_continues() {
        let html = r#"
        <html>
          <head><title>Article 3</title></head>
          <body>
            <main>
              <p>Article 3 body text is long enough to count as a real article and keeps going with additional details, context, and facts about the topic.</p>
            </main>
          </body>
        </html>
        "#;

        let payload = build_article_payload(
            "http://localhost:8787/article-3.html",
            html,
            200,
            "2026-04-27T14:00:00Z",
            "fetch-url",
        )
        .expect("single-block article should build");

        assert_eq!(payload.article.title, "Article 3");
        assert!(payload.article.text.0.starts_with("Article 3 body text"));
        assert!(payload.article.word_count.unwrap_or(0) >= 20);
    }

    #[test]
    fn allows_single_block_article_with_title_prefixed_paragraph() {
        let html = r#"
        <html>
          <head><title>Root Article</title></head>
          <body>
            <main>
              <p>Root Article body with enough words to pass extraction and continue as a real paragraph.</p>
            </main>
          </body>
        </html>
        "#;

        let payload = build_article_payload(
            "http://localhost:8787/root-article.html",
            html,
            200,
            "2026-04-27T14:00:00Z",
            "fetch-url",
        )
        .expect("title-prefixed article should build");

        assert_eq!(payload.article.title, "Root Article");
        assert!(payload.article.text.0.contains("Root Article body with enough words"));
    }

    #[test]
    fn rejects_soft_404_like_page_even_with_enough_words() {
        let html = r#"
        <html>
          <head><title>Article Unavailable</title></head>
          <body>
            <main>
              <p>Sorry, this page is unavailable right now. The requested article could not be found on this site.</p>
              <p>Please return to the homepage or try again later for more updates and links.</p>
            </main>
          </body>
        </html>
        "#;

        let err = build_article_payload(
            "http://localhost:8787/missing.html",
            html,
            200,
            "2026-04-27T14:00:00Z",
            "fetch-url",
        )
        .expect_err("payload should be rejected");

        assert!(err
            .to_string()
            .contains("extracted article text looks unavailable for payload"));
    }

    #[test]
    fn rejects_title_only_page() {
        let html = r#"
        <html>
          <head><title>Page not found</title></head>
          <body><h1>Page not found</h1></body>
        </html>
        "#;

        let err = build_article_payload(
            "http://localhost:8787/page-not-found.html",
            html,
            200,
            "2026-04-27T14:00:00Z",
            "fetch-url",
        )
        .expect_err("title-only page should be rejected");

        assert!(err
            .to_string()
            .contains("extracted article text looks unavailable for payload"));
    }

    #[test]
    fn rejects_list_nav_shell_without_real_paragraph_content() {
        let html = r#"
        <html>
          <head><title>Site Map</title></head>
          <body>
            <main>
              <nav>
                <ul>
                  <li>Home</li>
                  <li>News</li>
                  <li>Contact</li>
                </ul>
              </nav>
            </main>
          </body>
        </html>
        "#;

        let err = build_article_payload(
            "http://localhost:8787/empty.html",
            html,
            200,
            "2026-04-27T14:00:00Z",
            "fetch-url",
        )
        .expect_err("list/nav shell should be rejected");

        assert!(err
            .to_string()
            .contains("extracted article text looks unavailable for payload"));
    }

    #[tokio::test]
    async fn fetch_article_payload_rejects_template_page_from_public_path() {
        let base = spawn_test_server(
            r#"<html>
              <head><title>Article Unavailable</title></head>
              <body>
                <main>
                  <p>This article is unavailable right now.</p>
                  <p>The requested article could not be found. Please return to the homepage.</p>
                </main>
              </body>
            </html>"#,
        )
        .await;

        let url = format!("{base}/article");
        let err = super::fetch_article_payload(&url)
            .await
            .expect_err("soft-404 should be rejected on public fetch path");

        assert!(err
            .to_string()
            .contains("extracted article text looks unavailable for payload"));
    }

    #[test]
    fn allows_legitimate_article_that_mentions_404_and_not_found() {
        let html = r#"
        <html>
          <head><title>Engineering Update</title></head>
          <body>
            <main>
              <h1>Engineering Update</h1>
              <p>We improved the 404 recovery flow and added a helpful not found message for the search UI.</p>
              <p>The article explains how the team handled edge cases without removing valid content.</p>
            </main>
          </body>
        </html>
        "#;

        let payload = build_article_payload(
            "http://localhost:8787/blog/engineering-update.html",
            html,
            200,
            "2026-04-27T14:00:00Z",
            "fetch-url",
        )
        .expect("real article should pass");

        assert_eq!(payload.article.title, "Engineering Update");
        assert!(payload.article.text.0.contains("404 recovery flow"));
        assert!(payload.article.text.0.contains("not found message"));
    }
}
