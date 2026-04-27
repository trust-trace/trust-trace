//! Company reference records and loaders.

use std::fs;
use std::path::Path;

use serde::{Deserialize, Serialize};

/// One company entry from the local reference file.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CompanyRecord {
    pub name: String,
    pub ticker: String,
    pub aliases: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub exchange: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub country: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub is_active: Option<bool>,
}

/// Load company reference data from a JSON file.
pub fn load_companies(path: impl AsRef<Path>) -> anyhow::Result<Vec<CompanyRecord>> {
    let raw = fs::read_to_string(path)?;
    let companies = serde_json::from_str(&raw)?;
    Ok(companies)
}
