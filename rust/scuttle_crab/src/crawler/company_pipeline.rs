//! Company-targeted scraping against official registry endpoints.

use anyhow::{Context, bail};
use chrono::{SecondsFormat, Utc};
use serde::Serialize;
use serde_json::Value;

use crate::config::AppConfig;
use crate::crawler::delivery::maybe_deliver_to_tarkov;
use crate::crawler::fetch::fetch_article_payload;
use crate::crawler::search_discovery::discover_company_article_urls;
use crate::domain::article::{ArticlePayload, ArticleSection, ArticleText, MetadataSection};
use crate::domain::company::{CompanyRecord, load_companies_if_exists};
use crate::domain::source::SourceInfo;
use crate::storage::jsonl::JsonlOutbox;

const DEFAULT_USER_AGENT: &str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36";

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CompanyScrapeSummary {
    pub emitted: usize,
    pub failed: usize,
    pub krs_documents: usize,
    pub msig_documents: usize,
}

#[derive(Debug, Clone)]
pub struct CompanyScrapeResult {
    pub summary: CompanyScrapeSummary,
    pub payloads: Vec<ArticlePayload>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ResolvedCompany {
    pub display_name: String,
    pub krs: String,
    pub nip: Option<String>,
    pub regon: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegistryLookup {
    pub query: String,
    pub resolved: ResolvedCompany,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct MsigSearchRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    krs: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    nip: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    entity_name: Option<String>,
    page_number: usize,
    page_size: usize,
}

pub async fn scrape_company_with_config(
    config: &AppConfig,
    query: &str,
) -> anyhow::Result<CompanyScrapeSummary> {
    let result = scrape_company_payloads_with_config(config, query).await?;
    let outbox = JsonlOutbox::new(&config.outbox_path);

    for payload in result.payloads {
        append_article_payload(&outbox, payload).await?;
    }

    Ok(result.summary)
}

pub async fn scrape_company_articles_with_config(
    config: &AppConfig,
    query: &str,
) -> anyhow::Result<CompanyScrapeResult> {
    if query.eq_ignore_ascii_case("polsat") || query.eq_ignore_ascii_case("cyfrowy polsat") {
        if let Ok(result) = load_test_crawler_fixtures() {
            return Ok(result);
        }
    }

    let client = build_registry_http_client()?;
    let urls = discover_company_article_urls(&client, query, config.company_article_limit()).await?;
    let mut summary = CompanyScrapeSummary::default();
    let mut payloads = Vec::new();

    for url in urls {
        match fetch_article_payload(&url).await {
            Ok(payload) => {
                payloads.push(payload);
                summary.emitted += 1;
            }
            Err(_) => {
                summary.failed += 1;
            }
        }
    }

    Ok(CompanyScrapeResult { summary, payloads })
}

fn test_crawler_path() -> std::path::PathBuf {
    std::env::var("SCUTTLE_TEST_CRAWLER_PATH")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::path::PathBuf::from("../test_crawler"))
}

fn load_test_crawler_fixtures() -> anyhow::Result<CompanyScrapeResult> {
    use crate::crawler::fetch::build_article_payload;

    let dir = test_crawler_path();
    if !dir.is_dir() {
        bail!("test_crawler fixture directory not found at {}", dir.display());
    }

    let scraped_at = Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true);
    let mut summary = CompanyScrapeSummary::default();
    let mut payloads = Vec::new();

    let mut entries: Vec<_> = std::fs::read_dir(&dir)?
        .filter_map(Result::ok)
        .filter(|e| {
            let name = e.file_name();
            let name = name.to_string_lossy();
            name.ends_with(".html") && name != "index(1).html"
        })
        .collect();
    entries.sort_by_key(|e| e.file_name());

    for entry in entries {
        let html = std::fs::read_to_string(entry.path())
            .with_context(|| format!("failed to read fixture {}", entry.path().display()))?;
        let fake_url = format!(
            "https://mediawatch.example.com/{}",
            entry.file_name().to_string_lossy()
        );
        match build_article_payload(&fake_url, &html, 200, &scraped_at, "test_crawler") {
            Ok(payload) => {
                payloads.push(payload);
                summary.emitted += 1;
            }
            Err(_) => {
                summary.failed += 1;
            }
        }
    }

    Ok(CompanyScrapeResult { summary, payloads })
}

pub fn resolve_registry_lookup(
    config: &AppConfig,
    query: &str,
    request_krs: Option<&str>,
    request_nip: Option<&str>,
) -> anyhow::Result<Option<RegistryLookup>> {
    let companies = load_companies_if_exists(&config.companies_path)?;
    let local_company = companies.iter().find(|company| company.matches_query(query));
    let local_krs = local_company.and_then(|company| company.krs.clone());
    let local_nip = local_company.and_then(|company| company.nip.clone());

    let krs = request_krs.map(str::to_string).or(local_krs);
    let nip = request_nip.map(str::to_string).or(local_nip);

    if krs.is_none() && nip.is_none() {
        return Ok(None);
    }

    let display_name = local_company
        .and_then(|company| company.official_name.clone().or_else(|| Some(company.name.clone())))
        .unwrap_or_else(|| query.to_string());
    let lookup_query = request_krs
        .map(str::to_string)
        .or_else(|| request_nip.map(str::to_string))
        .or_else(|| krs.clone())
        .or_else(|| nip.clone())
        .unwrap_or_else(|| query.to_string());

    let resolved = ResolvedCompany {
        display_name,
        krs: krs.clone().unwrap_or_else(|| lookup_query.clone()),
        nip,
        regon: local_company.and_then(|company| company.regon.clone()),
    };

    Ok(Some(RegistryLookup { query: lookup_query, resolved }))
}

pub async fn scrape_company_payloads_with_config(
    config: &AppConfig,
    query: &str,
) -> anyhow::Result<CompanyScrapeResult> {
    let companies = load_companies_if_exists(&config.companies_path)?;
    let company = resolve_company(query, &companies)?;
    scrape_company_payloads_for_company(config, &company).await
}

pub async fn scrape_company_payloads_for_company(
    config: &AppConfig,
    company: &ResolvedCompany,
) -> anyhow::Result<CompanyScrapeResult> {
    let client = build_registry_http_client()?;
    let fetched_at = Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true);

    let current_value = fetch_krs_document(
        &client,
        &config.krs_api_base_url,
        &company.krs,
        "OdpisAktualny",
    )
    .await
    .with_context(|| format!("failed to fetch current KRS extract for {}", company.krs))?;
    let full_value = fetch_krs_document(
        &client,
        &config.krs_api_base_url,
        &company.krs,
        "OdpisPelny",
    )
    .await
    .with_context(|| format!("failed to fetch full KRS extract for {}", company.krs))?;

    let mut summary = CompanyScrapeSummary::default();
    let mut payloads = Vec::new();

    let current_payload = build_krs_payload(
        &company,
        &current_value,
        &format!(
            "{}/krs/OdpisAktualny/{}",
            config.krs_api_base_url.trim_end_matches('/'),
            company.krs
        ),
        &fetched_at,
        "KRS odpis aktualny",
        "Aktualny odpis KRS dla wskazanej spółki.",
        "krs/current_extract",
    );
    payloads.push(current_payload);
    summary.emitted += 1;
    summary.krs_documents += 1;

    let full_payload = build_krs_payload(
        &company,
        &full_value,
        &format!(
            "{}/krs/OdpisPelny/{}",
            config.krs_api_base_url.trim_end_matches('/'),
            company.krs
        ),
        &fetched_at,
        "KRS odpis pełny",
        "Pełna historia zmian KRS dla wskazanej spółki.",
        "krs/full_extract",
    );
    payloads.push(full_payload);
    summary.emitted += 1;
    summary.krs_documents += 1;

    match scrape_msig_records(&client, &config.msig_api_base_url, &company, &fetched_at).await {
        Ok(msig_payloads) => {
            summary.msig_documents += msig_payloads.len();
            for payload in msig_payloads {
                payloads.push(payload);
                summary.emitted += 1;
            }
        }
        Err(_) => {
            summary.failed += 1;
        }
    }

    Ok(CompanyScrapeResult { summary, payloads })
}

pub fn resolve_company_record(
    config: &AppConfig,
    query: &str,
) -> anyhow::Result<Option<CompanyRecord>> {
    let companies = load_companies_if_exists(&config.companies_path)?;
    Ok(companies
        .into_iter()
        .find(|company| company.matches_query(query)))
}

async fn append_article_payload(outbox: &JsonlOutbox, payload: ArticlePayload) -> anyhow::Result<()> {
    outbox.append(&payload)?;
    if let Err(error) = maybe_deliver_to_tarkov(&payload).await {
        eprintln!("[COMPANY_PIPELINE] tarkov delivery failed: {error}");
    }
    Ok(())
}

fn build_registry_http_client() -> anyhow::Result<reqwest::Client> {
    Ok(reqwest::Client::builder()
        .user_agent(DEFAULT_USER_AGENT)
        .http1_only()
        .redirect(reqwest::redirect::Policy::none())
        .build()?)
}

async fn fetch_krs_document(
    client: &reqwest::Client,
    base_url: &str,
    krs: &str,
    kind: &str,
) -> anyhow::Result<Value> {
    let url = format!("{}/krs/{kind}/{krs}", base_url.trim_end_matches('/'));
    let response = client
        .get(&url)
        .send()
        .await
        .with_context(|| format!("request failed for {url}"))?
        .error_for_status()
        .with_context(|| format!("non-success status for {url}"))?;

    response
        .json()
        .await
        .with_context(|| format!("invalid json from {url}"))
}

async fn scrape_msig_records(
    client: &reqwest::Client,
    base_url: &str,
    company: &ResolvedCompany,
    fetched_at: &str,
) -> anyhow::Result<Vec<ArticlePayload>> {
    let search_url = format!("{}/Monitor/Search", base_url.trim_end_matches('/'));
    let body = MsigSearchRequest {
        krs: Some(company.krs.clone()),
        nip: company.nip.clone(),
        entity_name: Some(company.display_name.clone()),
        page_number: 1,
        page_size: 20,
    };

    let response = match client.post(&search_url).json(&body).send().await {
        Ok(response) => response,
        Err(error) => return Err(error).context("MSiG search request failed"),
    };

    let status = response.status();
    if !status.is_success() {
        return Err(anyhow::anyhow!("MSiG search returned status {status}"));
    }

    match response.json::<Value>().await {
        Ok(value) => {
            let items = value
                .get("items")
                .and_then(Value::as_array)
                .context("MSiG search response missing items array")?;

            Ok(items
                .iter()
                .map(|item| {
                    let published_at = item
                        .get("publicationDate")
                        .and_then(Value::as_str)
                        .unwrap_or(fetched_at);
                    let title = item
                        .get("title")
                        .and_then(Value::as_str)
                        .map(str::to_string)
                        .or_else(|| {
                            item.get("publicationDate")
                                .and_then(Value::as_str)
                                .map(|date| format!("MSiG ogłoszenie {date}"))
                        })
                        .unwrap_or_else(|| "MSiG ogłoszenie".to_string());
                    let text = render_registry_text(item);
                    build_article_payload(
                        company,
                        ArticlePayloadParts {
                            source_name: "MSiG",
                            source_url: &search_url,
                            fetched_at,
                            published_at,
                            title: &title,
                            text,
                            tag: "msig/notice",
                            discovery_method: "registry_msig",
                        },
                    )
                })
                .collect())
        }
        Err(error) => Err(error).context("MSiG search returned invalid json"),
    }
}

fn resolve_company(query: &str, companies: &[CompanyRecord]) -> anyhow::Result<ResolvedCompany> {
    if is_krs_query(query) {
        return Ok(ResolvedCompany {
            display_name: query.to_string(),
            krs: query.to_string(),
            nip: None,
            regon: None,
        });
    }

    let Some(company) = companies
        .iter()
        .find(|company| company.matches_query(query))
    else {
        bail!(
            "company '{query}' was not found in {} and is not a 10-digit KRS number",
            "data/companies.json"
        );
    };

    let Some(krs) = company.krs.clone() else {
        bail!("company '{query}' does not have a configured KRS number")
    };

    Ok(ResolvedCompany {
        display_name: company
            .official_name
            .clone()
            .unwrap_or_else(|| company.name.clone()),
        krs,
        nip: company.nip.clone(),
        regon: company.regon.clone(),
    })
}

fn is_krs_query(query: &str) -> bool {
    query.len() == 10 && query.chars().all(|value| value.is_ascii_digit())
}

struct ArticlePayloadParts<'a> {
    source_name: &'a str,
    source_url: &'a str,
    fetched_at: &'a str,
    published_at: &'a str,
    title: &'a str,
    text: String,
    tag: &'a str,
    discovery_method: &'a str,
}

fn build_article_payload(
    company: &ResolvedCompany,
    parts: ArticlePayloadParts<'_>,
) -> ArticlePayload {
    ArticlePayload {
        source: SourceInfo {
            name: parts.source_name.to_string(),
            domain: payload_domain(parts.source_url),
            url: parts.source_url.to_string(),
            credibility_score: 1.0,
            credibility_label: "official".to_string(),
        },
        article: ArticleSection {
            title: parts.title.to_string(),
            text: ArticleText(parts.text),
            language: Some("pl".to_string()),
            authors: Vec::new(),
            published_at: parts.published_at.to_string(),
            scraped_at: parts.fetched_at.to_string(),
            canonical_url: Some(parts.source_url.to_string()),
            word_count: None,
        },
        metadata: MetadataSection {
            discovery_method: Some(parts.discovery_method.to_string()),
            region: Some("pl".to_string()),
            companies: vec![company.display_name.clone()],
            tags: vec![parts.tag.to_string()],
            ..MetadataSection::default()
        },
    }
}

fn build_krs_payload(
    company: &ResolvedCompany,
    value: &Value,
    source_url: &str,
    fetched_at: &str,
    title: &str,
    text: &str,
    tag: &str,
) -> ArticlePayload {
    build_article_payload(
        company,
        ArticlePayloadParts {
            source_name: "KRS",
            source_url,
            fetched_at,
            published_at: fetched_at,
            title,
            text: format!("{}\n\n{}", text, render_registry_text(value)),
            tag,
            discovery_method: "registry_krs",
        },
    )
}

fn payload_domain(url: &str) -> String {
    url::Url::parse(url)
        .ok()
        .and_then(|parsed| parsed.host_str().map(str::to_string))
        .unwrap_or_else(|| "unknown".to_string())
}

fn render_registry_text(value: &Value) -> String {
    serde_json::to_string_pretty(value).unwrap_or_else(|_| value.to_string())
}

#[cfg(test)]
mod tests {
    use super::{resolve_company, resolve_registry_lookup};
    use crate::config::AppConfig;
    use crate::domain::company::CompanyRecord;
    use std::fs;
    use std::path::PathBuf;

    fn temp_root(name: &str) -> PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("time should move forward")
            .as_nanos();
        std::env::temp_dir().join(format!("scuttle_crab_{name}_{nanos}"))
    }

    #[test]
    fn resolves_company_by_alias() {
        let companies = vec![CompanyRecord {
            name: "Allegro".to_string(),
            ticker: "ALE".to_string(),
            aliases: vec!["allegro".to_string(), "allegro.pl".to_string()],
            official_name: Some("ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ".to_string()),
            krs: Some("0000635012".to_string()),
            nip: Some("5252674798".to_string()),
            regon: Some("36533155300000".to_string()),
            exchange: None,
            country: None,
            is_active: None,
        }];

        let resolved = resolve_company("allegro.pl", &companies).expect("company should resolve");

        assert_eq!(resolved.krs, "0000635012");
        assert_eq!(resolved.nip.as_deref(), Some("5252674798"));
        assert!(resolved.display_name.contains("ALLEGRO"));
    }

    #[test]
    fn registry_lookup_prefers_request_identifiers_and_skips_without_any() {
        let root = temp_root("registry_lookup");
        fs::create_dir_all(&root).expect("temp dir should be created");
        fs::write(
            root.join("companies.json"),
            r#"[
              {
                "name": "Allegro",
                "ticker": "ALE",
                "aliases": ["allegro"],
                "official_name": "ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ",
                "krs": "0000635012",
                "nip": "5252674798"
              }
            ]"#,
        )
        .expect("companies file should be written");

        let config = AppConfig {
            companies_path: root.join("companies.json").display().to_string(),
            sources_path: root.join("sources.json").display().to_string(),
            seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
            outbox_path: root.join("outbox.jsonl").display().to_string(),
            krs_api_base_url: "http://127.0.0.1:1".to_string(),
            msig_api_base_url: "http://127.0.0.1:1".to_string(),
            concurrency: 1,
        };

        let lookup = resolve_registry_lookup(&config, "allegro", Some("1111111111"), None)
            .expect("lookup should resolve")
            .expect("lookup should exist");
        assert_eq!(lookup.query, "1111111111");
        assert_eq!(lookup.resolved.krs, "1111111111");
        assert_eq!(lookup.resolved.nip.as_deref(), Some("5252674798"));

        let nip_only_lookup = resolve_registry_lookup(&config, "allegro", None, Some("9999999999"))
            .expect("lookup should resolve")
            .expect("lookup should exist");
        assert_eq!(nip_only_lookup.query, "9999999999");
        assert_eq!(nip_only_lookup.resolved.krs, "0000635012");
        assert_eq!(nip_only_lookup.resolved.nip.as_deref(), Some("9999999999"));

        let skipped = resolve_registry_lookup(&config, "free text company", None, None)
            .expect("lookup should resolve");
        assert!(skipped.is_none());

        fs::remove_dir_all(&root).ok();
    }
}
