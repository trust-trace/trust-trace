use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use scuttle_crab::storage::seen_urls::SeenUrlStore;
use scuttle_crab::utils::hash::hash_url;
use scuttle_crab::utils::url::normalize_url;

fn temp_file_path(name: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time should move forward")
        .as_nanos();

    std::env::temp_dir().join(format!("scuttle_crab_{name}_{nanos}.jsonl"))
}

#[test]
fn normalizes_equivalent_urls_to_the_same_hash() {
    let a = normalize_url("https://Example.com/news/story/").expect("url should normalize");
    let b = normalize_url("https://example.com/news/story#top").expect("url should normalize");

    assert_eq!(a, "https://example.com/news/story");
    assert_eq!(a, b);
    assert_eq!(hash_url(&a), hash_url(&b));
}

#[test]
fn persists_seen_urls_across_reloads() {
    let path = temp_file_path("seen_urls_persist");

    let mut store = SeenUrlStore::load(&path).expect("store should load");
    assert!(store
        .record(
            "https://example.com/article",
            "Example",
            "2026-04-27T08:16:12Z"
        )
        .expect("record should be written"));

    let reloaded = SeenUrlStore::load(&path).expect("store should reload");
    fs::remove_file(&path).ok();

    assert!(reloaded
        .contains("https://example.com/article")
        .expect("contains should work"));
}

#[test]
fn skips_duplicate_urls_after_normalization() {
    let path = temp_file_path("seen_urls_dedup");

    let mut store = SeenUrlStore::load(&path).expect("store should load");

    assert!(store
        .record(
            "https://example.com/article/",
            "Example",
            "2026-04-27T08:16:12Z"
        )
        .expect("first insert should succeed"));
    assert!(!store
        .record(
            "https://example.com/article#top",
            "Example",
            "2026-04-27T08:20:12Z"
        )
        .expect("duplicate insert should be skipped"));

    fs::remove_file(&path).ok();
}
