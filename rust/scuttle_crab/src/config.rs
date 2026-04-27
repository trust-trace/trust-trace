//! Runtime configuration defaults.

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
