//! Outbound article payload schema.

use serde::{Deserialize, Serialize};

use crate::domain::source::SourceInfo;

/// Normalized article body text.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArticleText(pub String);

/// Article-specific fields in the outbound payload.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArticleSection {
    pub title: String,
    pub text: ArticleText,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub language: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub authors: Vec<String>,
    pub published_at: String,
    pub scraped_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub canonical_url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub word_count: Option<u32>,
}

/// Optional enrichment metadata attached to an article.
#[derive(Debug, Clone, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct MetadataSection {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub section: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub region: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub discovery_method: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub http_status: Option<u16>,
}

/// Full outbound payload emitted for one article.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ArticlePayload {
    pub source: SourceInfo,
    pub article: ArticleSection,
    #[serde(default)]
    pub metadata: MetadataSection,
}
