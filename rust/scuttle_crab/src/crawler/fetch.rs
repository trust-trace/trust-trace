//! Fetch and extract readable text from article pages.

use anyhow::Context;
use scraper::{Html, Selector};

/// Fetch one URL and return extracted title and readable text.
pub async fn fetch_article_text(url: &str) -> anyhow::Result<(String, String)> {
    let response = reqwest::get(url)
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
    let selector = Selector::parse("article, main, p, h1, h2, h3, li").expect("valid content selector");
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
    use super::extract_text_from_html;

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
}
