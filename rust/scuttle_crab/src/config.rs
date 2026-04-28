//! Runtime configuration defaults.

use std::path::Path;

/// Local file paths used by the current scaffold and storage helpers.
#[derive(Debug, Clone)]
pub struct AppConfig {
    pub companies_path: String,
    pub sources_path: String,
    pub seen_urls_path: String,
    pub outbox_path: String,
    pub krs_api_base_url: String,
    pub msig_api_base_url: String,
    pub concurrency: usize,
}

impl AppConfig {
    /// Override the crawl sources file when the caller explicitly provides one.
    pub fn with_sources_path(mut self, sources_path: Option<String>) -> anyhow::Result<Self> {
        if let Some(sources_path) = sources_path {
            if !Path::new(&sources_path).exists() {
                anyhow::bail!("sources file not found: {sources_path}");
            }

            self.sources_path = sources_path;
        }

        Ok(self)
    }

    /// Maximum number of article results to fetch for company search.
    pub fn company_article_limit(&self) -> usize {
        std::env::var("SCUTTLE_COMPANY_ARTICLE_LIMIT")
            .ok()
            .and_then(|value| value.parse::<usize>().ok())
            .map(|value| value.clamp(1, 50))
            .unwrap_or(10)
    }

    pub fn bind_address(&self) -> String {
        std::env::var("SCUTTLE_BIND_ADDR")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or_else(|| "127.0.0.1:3000".to_string())
    }
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            companies_path: "data/companies.json".to_string(),
            sources_path: "data/sources.json".to_string(),
            seen_urls_path: "data/seen_urls.jsonl".to_string(),
            outbox_path: "data/outbox.jsonl".to_string(),
            krs_api_base_url: "https://api-krs.ms.gov.pl/api".to_string(),
            msig_api_base_url: "https://wyszukiwarka-msig.ms.gov.pl/api".to_string(),
            concurrency: 4,
        }
    }
}
