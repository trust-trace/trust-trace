use scuttle_crab::domain::article::{ArticlePayload, ArticleSection, ArticleText, MetadataSection};
use scuttle_crab::domain::source::SourceInfo;

#[test]
fn serializes_outbound_article_payload_without_summary_or_content_hash() {
    let payload = ArticlePayload {
        source: SourceInfo {
            name: "Reuters".to_string(),
            domain: "reuters.com".to_string(),
            url: "https://www.reuters.com/world/example".to_string(),
            credibility_score: 0.92,
            credibility_label: "high".to_string(),
        },
        article: ArticleSection {
            title: "Company X beats earnings expectations".to_string(),
            text: ArticleText("Full normalized article text here...".to_string()),
            language: Some("en".to_string()),
            authors: vec!["Jane Doe".to_string()],
            published_at: "2026-04-27T08:15:00Z".to_string(),
            scraped_at: "2026-04-27T08:16:12Z".to_string(),
            canonical_url: Some("https://www.reuters.com/world/example".to_string()),
            word_count: Some(845),
        },
        metadata: MetadataSection {
            section: Some("markets".to_string()),
            tags: vec!["earnings".to_string(), "stocks".to_string()],
            tickers: vec!["AAPL".to_string()],
            companies: vec!["Apple".to_string()],
            region: Some("us".to_string()),
            discovery_method: Some("rss".to_string()),
            http_status: Some(200),
        },
    };

    let value = serde_json::to_value(payload).expect("payload should serialize");

    assert_eq!(value["source"]["name"], "Reuters");
    assert_eq!(
        value["article"]["title"],
        "Company X beats earnings expectations"
    );
    assert_eq!(value["metadata"]["tickers"][0], "AAPL");
    assert!(value["article"].get("summary").is_none());
    assert!(value["article"].get("content_hash").is_none());
}

#[test]
fn omits_optional_fields_when_they_are_missing() {
    let payload = ArticlePayload {
        source: SourceInfo {
            name: "Example News".to_string(),
            domain: "example.com".to_string(),
            url: "https://example.com/article".to_string(),
            credibility_score: 0.75,
            credibility_label: "medium".to_string(),
        },
        article: ArticleSection {
            title: "Example article".to_string(),
            text: ArticleText("Text".to_string()),
            language: None,
            authors: Vec::new(),
            published_at: "2026-04-27T10:00:00Z".to_string(),
            scraped_at: "2026-04-27T10:05:00Z".to_string(),
            canonical_url: None,
            word_count: None,
        },
        metadata: MetadataSection::default(),
    };

    let value = serde_json::to_value(payload).expect("payload should serialize");

    assert!(value["article"].get("language").is_none());
    assert!(value["article"].get("canonical_url").is_none());
    assert!(value["article"].get("word_count").is_none());
    assert!(value["metadata"].get("section").is_none());
    assert!(value["metadata"].get("http_status").is_none());
}
