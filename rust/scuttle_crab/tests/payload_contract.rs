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
            region: Some("us".to_string()),
            discovery_method: Some("rss".to_string()),
            http_status: Some(200),
            ..MetadataSection::default()
        },
    };

    let value = serde_json::to_value(payload).expect("payload should serialize");

    assert_eq!(value["source"]["name"], "Reuters");
    assert_eq!(
        value["article"]["title"],
        "Company X beats earnings expectations"
    );
    assert!(value["metadata"].get("tags").is_none());
    assert!(value["metadata"].get("tickers").is_none());
    assert!(value["metadata"].get("companies").is_none());
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

#[test]
fn serializes_registry_metadata_fields_when_present() {
    let payload = ArticlePayload {
        source: SourceInfo {
            name: "KRS".to_string(),
            domain: "api-krs.ms.gov.pl".to_string(),
            url: "https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/0000635012".to_string(),
            credibility_score: 1.0,
            credibility_label: "official".to_string(),
        },
        article: ArticleSection {
            title: "KRS odpis aktualny - Allegro".to_string(),
            text: ArticleText("Example body".to_string()),
            language: Some("pl".to_string()),
            authors: Vec::new(),
            published_at: "2026-04-27T08:15:00Z".to_string(),
            scraped_at: "2026-04-27T08:16:12Z".to_string(),
            canonical_url: Some(
                "https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/0000635012".to_string(),
            ),
            word_count: Some(2),
        },
        metadata: MetadataSection {
            section: None,
            region: Some("pl".to_string()),
            discovery_method: Some("registry_krs".to_string()),
            http_status: Some(200),
            companies: vec!["ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ".to_string()],
            tags: vec!["krs".to_string(), "current_extract".to_string()],
        },
    };

    let value = serde_json::to_value(&payload).expect("payload should serialize");

    assert_eq!(
        value["metadata"]["companies"][0],
        "ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ"
    );
    assert_eq!(value["metadata"]["tags"][0], "krs");
    assert_eq!(value["metadata"]["tags"][1], "current_extract");
}
