//! Registry payloads emitted by company-targeted scraping.

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// One record emitted from an official registry source.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RegistryRecordPayload {
    pub company_name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub matched_identifier: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub matched_identifier_kind: Option<String>,
    pub registry: String,
    pub record_type: String,
    pub title: String,
    pub source_url: String,
    pub fetched_at: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub published_at: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub snippet: Option<String>,
    pub data: Value,
}
