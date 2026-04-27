//! Company reference records and loaders.

use std::fs;
use std::io::ErrorKind;
use std::path::Path;

use serde::{Deserialize, Serialize};

/// One company entry from the local reference file.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CompanyRecord {
    pub name: String,
    pub ticker: String,
    pub aliases: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub official_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub krs: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub nip: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub regon: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub exchange: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub country: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub is_active: Option<bool>,
}

impl CompanyRecord {
    /// Check whether the company can be resolved from the provided query.
    pub fn matches_query(&self, query: &str) -> bool {
        let normalized_query = normalize_company_query(query);

        if normalize_company_query(&self.name) == normalized_query
            || normalize_company_query(&self.ticker) == normalized_query
            || self
                .official_name
                .as_ref()
                .map(|value| normalize_company_query(value) == normalized_query)
                .unwrap_or(false)
            || self
                .krs
                .as_ref()
                .map(|value| normalize_company_query(value) == normalized_query)
                .unwrap_or(false)
            || self
                .nip
                .as_ref()
                .map(|value| normalize_company_query(value) == normalized_query)
                .unwrap_or(false)
            || self
                .regon
                .as_ref()
                .map(|value| normalize_company_query(value) == normalized_query)
                .unwrap_or(false)
        {
            return true;
        }

        self.aliases
            .iter()
            .any(|alias| normalize_company_query(alias) == normalized_query)
    }
}

/// Load company reference data from a JSON file.
pub fn load_companies(path: impl AsRef<Path>) -> anyhow::Result<Vec<CompanyRecord>> {
    let raw = fs::read_to_string(path)?;
    let companies = serde_json::from_str(&raw)?;
    Ok(companies)
}

/// Load company reference data and treat missing files as an empty list.
pub fn load_companies_if_exists(path: impl AsRef<Path>) -> anyhow::Result<Vec<CompanyRecord>> {
    match fs::read_to_string(path) {
        Ok(raw) => Ok(serde_json::from_str(&raw)?),
        Err(error) if error.kind() == ErrorKind::NotFound => Ok(Vec::new()),
        Err(error) => Err(error.into()),
    }
}

fn normalize_company_query(input: &str) -> String {
    input.trim().to_ascii_lowercase()
}
