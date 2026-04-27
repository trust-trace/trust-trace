//! Source metadata included with outbound payloads.

use serde::{Deserialize, Serialize};

/// Identifies the source that produced an article.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SourceInfo {
    pub name: String,
    pub domain: String,
    pub url: String,
    pub credibility_score: f32,
    pub credibility_label: String,
}
