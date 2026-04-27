use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use scuttle_crab::domain::article::{ArticlePayload, ArticleSection, ArticleText, MetadataSection};
use scuttle_crab::domain::source::SourceInfo;
use scuttle_crab::storage::jsonl::JsonlOutbox;

fn temp_file_path(name: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time should move forward")
        .as_nanos();

    std::env::temp_dir().join(format!("scuttle_crab_{name}_{nanos}.jsonl"))
}

fn sample_payload(title: &str) -> ArticlePayload {
    ArticlePayload {
        source: SourceInfo {
            name: "Reuters".to_string(),
            domain: "reuters.com".to_string(),
            url: "https://www.reuters.com/world/example".to_string(),
            credibility_score: 0.92,
            credibility_label: "high".to_string(),
        },
        article: ArticleSection {
            title: title.to_string(),
            text: ArticleText("Full normalized article text here...".to_string()),
            language: Some("en".to_string()),
            authors: vec!["Jane Doe".to_string()],
            published_at: "2026-04-27T08:15:00Z".to_string(),
            scraped_at: "2026-04-27T08:16:12Z".to_string(),
            canonical_url: Some("https://www.reuters.com/world/example".to_string()),
            word_count: Some(845),
        },
        metadata: MetadataSection {
            ..MetadataSection::default()
        },
    }
}

#[test]
fn appends_one_json_payload_per_line() {
    let path = temp_file_path("outbox_lines");
    let outbox = JsonlOutbox::new(&path);

    outbox
        .append(&sample_payload("Article one"))
        .expect("first payload should append");
    outbox
        .append(&sample_payload("Article two"))
        .expect("second payload should append");

    let raw = fs::read_to_string(&path).expect("outbox file should exist");
    fs::remove_file(&path).ok();

    let lines: Vec<_> = raw.lines().collect();
    assert_eq!(lines.len(), 2);

    let first: serde_json::Value =
        serde_json::from_str(lines[0]).expect("line should be valid json");
    let second: serde_json::Value =
        serde_json::from_str(lines[1]).expect("line should be valid json");
    assert_eq!(first["article"]["title"], "Article one");
    assert_eq!(second["article"]["title"], "Article two");
}

#[test]
fn creates_parent_directory_when_missing() {
    let path = temp_file_path("outbox_parent");
    let parent = path.with_extension("");
    let nested = parent.join("outbox.jsonl");
    let outbox = JsonlOutbox::new(&nested);

    outbox
        .append(&sample_payload("Nested article"))
        .expect("payload should append into nested directory");

    assert!(nested.exists());

    fs::remove_file(&nested).ok();
    fs::remove_dir_all(&parent).ok();
}
