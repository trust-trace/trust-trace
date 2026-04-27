//! Source metadata included with outbound payloads.

use std::fs;
use std::path::Path;

use serde::{Deserialize, Serialize};
use url::Url;

/// Feed source configuration used for discovery.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CrawlSource {
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub feed_url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub page_url: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub article_link_selector: Option<String>,
    #[serde(default = "default_max_depth")]
    pub max_depth: usize,
    #[serde(default)]
    pub include_page_url: bool,
    pub allowed_domains: Vec<String>,
    #[serde(default = "default_credibility_score")]
    pub credibility_score: f32,
    #[serde(default = "default_credibility_label")]
    pub credibility_label: String,
}

/// Identifies the source that produced an article.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SourceInfo {
    pub name: String,
    pub domain: String,
    pub url: String,
    pub credibility_score: f32,
    pub credibility_label: String,
}

impl CrawlSource {
    /// Return the configured discovery URL for this source.
    pub fn discovery_url(&self) -> Option<&str> {
        self.feed_url.as_deref().or(self.page_url.as_deref())
    }

    /// Check whether the given URL belongs to one of the configured domains.
    pub fn allows_url(&self, candidate_url: &str) -> bool {
        let Ok(parsed) = Url::parse(candidate_url) else {
            return false;
        };

        let Some(host) = parsed.host_str() else {
            return false;
        };

        self.allowed_domains.iter().any(|domain| {
            let normalized = domain.to_ascii_lowercase();
            let host = host.to_ascii_lowercase();
            host == normalized || host.ends_with(&format!(".{normalized}"))
        })
    }
}

/// Load crawl sources from a JSON file. Missing files are treated as an empty source list.
pub fn load_sources(path: impl AsRef<Path>) -> anyhow::Result<Vec<CrawlSource>> {
    match fs::read_to_string(path) {
        Ok(raw) => Ok(serde_json::from_str(&raw)?),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(Vec::new()),
        Err(error) => Err(error.into()),
    }
}

fn default_credibility_score() -> f32 {
    0.5
}

fn default_credibility_label() -> String {
    "unrated".to_string()
}

fn default_max_depth() -> usize {
    1
}
