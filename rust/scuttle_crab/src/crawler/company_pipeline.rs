//! Company-targeted scraping against official registry endpoints.

use anyhow::{Context, bail};
use chrono::{SecondsFormat, Utc};
use serde::Serialize;
use serde_json::{Value, json};

use crate::config::AppConfig;
use crate::domain::company::{CompanyRecord, load_companies_if_exists};
use crate::domain::registry::RegistryRecordPayload;
use crate::storage::jsonl::JsonlOutbox;

const DEFAULT_USER_AGENT: &str = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36";
const KRZ_PORTAL_URL: &str = "https://krz.ms.gov.pl/";
const RNP_PORTAL_URL: &str = "https://www.podatki.gov.pl/e-urzad-skarbowy/";

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CompanyScrapeSummary {
    pub emitted: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ResolvedCompany {
    display_name: String,
    krs: String,
    nip: Option<String>,
    regon: Option<String>,
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
    let companies = load_companies_if_exists(&config.companies_path)?;
    let company = resolve_company(query, &companies)?;
    let client = build_registry_http_client()?;
    let fetched_at = Utc::now().to_rfc3339_opts(SecondsFormat::Secs, true);
    let outbox = JsonlOutbox::new(&config.outbox_path);

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

    let mut emitted = 0;

    emitted += append_registry_record(
        &outbox,
        build_registry_payload(
            &company,
            Some(("krs", company.krs.as_str())),
            "krs",
            "current_extract",
            "KRS odpis aktualny",
            &format!(
                "{}/krs/OdpisAktualny/{}",
                config.krs_api_base_url.trim_end_matches('/'),
                company.krs
            ),
            &fetched_at,
            None,
            Some("Aktualny odpis KRS dla wskazanej spółki.".to_string()),
            current_value.clone(),
        ),
    )?;

    emitted += append_registry_record(
        &outbox,
        build_registry_payload(
            &company,
            Some(("krs", company.krs.as_str())),
            "krs",
            "full_extract",
            "KRS odpis pełny",
            &format!(
                "{}/krs/OdpisPelny/{}",
                config.krs_api_base_url.trim_end_matches('/'),
                company.krs
            ),
            &fetched_at,
            None,
            Some("Pełna historia zmian KRS dla wskazanej spółki.".to_string()),
            full_value.clone(),
        ),
    )?;

    if let Some(filing_summary) = extract_json_path(
        &current_value,
        &["odpis", "dane", "dzial3", "wzmiankiOZlozonychDokumentach"],
    ) {
        emitted += append_registry_record(
            &outbox,
            build_registry_payload(
                &company,
                Some(("krs", company.krs.as_str())),
                "rdf",
                "financial_filings_summary",
                "RDF wzmianki o złożonych sprawozdaniach",
                &format!(
                    "{}/krs/OdpisAktualny/{}",
                    config.krs_api_base_url.trim_end_matches('/'),
                    company.krs
                ),
                &fetched_at,
                None,
                Some(
                    "Wzmianki o złożonych dokumentach finansowych widoczne w aktualnym odpisie KRS."
                        .to_string(),
                ),
                filing_summary,
            ),
        )?;
    }

    if let Some(rdf_events) = extract_rdf_events(&full_value) {
        emitted += append_registry_record(
            &outbox,
            build_registry_payload(
                &company,
                Some(("krs", company.krs.as_str())),
                "rdf",
                "filing_events",
                "RDF zdarzenia ze sprawozdań w historii KRS",
                &format!(
                    "{}/krs/OdpisPelny/{}",
                    config.krs_api_base_url.trim_end_matches('/'),
                    company.krs
                ),
                &fetched_at,
                None,
                Some(
                    "Wpisy historyczne KRS powiązane ze złożeniem dokumentów finansowych RDF."
                        .to_string(),
                ),
                rdf_events,
            ),
        )?;
    }

    for payload in
        scrape_msig_records(&client, &config.msig_api_base_url, &company, &fetched_at).await
    {
        emitted += append_registry_record(&outbox, payload)?;
    }

    emitted += append_registry_record(&outbox, scrape_krz_record(&company, &fetched_at))?;
    emitted += append_registry_record(&outbox, scrape_rnp_record(&company, &fetched_at))?;

    Ok(CompanyScrapeSummary { emitted })
}

fn append_registry_record(
    outbox: &JsonlOutbox,
    payload: RegistryRecordPayload,
) -> anyhow::Result<usize> {
    outbox.append(&payload)?;
    Ok(1)
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

    Ok(response
        .json()
        .await
        .with_context(|| format!("invalid json from {url}"))?)
}

async fn scrape_msig_records(
    client: &reqwest::Client,
    base_url: &str,
    company: &ResolvedCompany,
    fetched_at: &str,
) -> Vec<RegistryRecordPayload> {
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
        Err(error) => {
            return vec![build_registry_payload(
                company,
                Some(("krs", company.krs.as_str())),
                "msig",
                "lookup_unavailable",
                "MSiG wyszukiwanie niedostępne",
                &search_url,
                fetched_at,
                None,
                Some(format!("MSiG search request failed: {error}")),
                json!({
                    "reason": "request_failed",
                    "attempted_url": search_url,
                    "query": body,
                }),
            )];
        }
    };

    let status = response.status();
    if !status.is_success() {
        return vec![build_registry_payload(
            company,
            Some(("krs", company.krs.as_str())),
            "msig",
            "lookup_unavailable",
            "MSiG wyszukiwanie niedostępne",
            &search_url,
            fetched_at,
            None,
            Some(format!("MSiG search returned status {status}")),
            json!({
                "reason": "non_success_status",
                "status": status.as_u16(),
                "attempted_url": search_url,
                "query": body,
            }),
        )];
    }

    match response.json::<Value>().await {
        Ok(value) => vec![build_registry_payload(
            company,
            Some(("krs", company.krs.as_str())),
            "msig",
            "search_results",
            "MSiG wyniki wyszukiwania",
            &search_url,
            fetched_at,
            None,
            Some("Surowa odpowiedź wyszukiwarki ogłoszeń MSiG dla wskazanej spółki.".to_string()),
            value,
        )],
        Err(error) => vec![build_registry_payload(
            company,
            Some(("krs", company.krs.as_str())),
            "msig",
            "lookup_unavailable",
            "MSiG wyszukiwanie niedostępne",
            &search_url,
            fetched_at,
            None,
            Some(format!("MSiG returned invalid json: {error}")),
            json!({
                "reason": "invalid_json",
                "attempted_url": search_url,
                "query": body,
            }),
        )],
    }
}

fn scrape_krz_record(company: &ResolvedCompany, fetched_at: &str) -> RegistryRecordPayload {
    build_registry_payload(
        company,
        Some(("krs", company.krs.as_str())),
        "krz",
        "lookup_unavailable",
        "KRZ publiczne pobieranie niedostępne",
        KRZ_PORTAL_URL,
        fetched_at,
        None,
        Some(
            "KRZ jest jawny, ale brak stabilnego publicznego API do bezpośredniego pobierania danych w tym scraperze."
                .to_string(),
        ),
        json!({
            "reason": "no_public_api",
            "portal_url": KRZ_PORTAL_URL,
            "krs": company.krs,
            "nip": company.nip,
        }),
    )
}

fn scrape_rnp_record(company: &ResolvedCompany, fetched_at: &str) -> RegistryRecordPayload {
    build_registry_payload(
        company,
        company
            .nip
            .as_deref()
            .map(|value| ("nip", value))
            .or(Some(("krs", company.krs.as_str()))),
        "rnp",
        "lookup_unavailable",
        "RNP wymaga uwierzytelnionego dostępu",
        RNP_PORTAL_URL,
        fetched_at,
        None,
        Some(
            "RNP wymaga logowania do e-Urzędu Skarbowego albo uprawnionego konta PUE, więc bez poświadczeń nie ma publicznego scrapingu."
                .to_string(),
        ),
        json!({
            "reason": "authentication_required",
            "portal_url": RNP_PORTAL_URL,
            "krs": company.krs,
            "nip": company.nip,
        }),
    )
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

fn build_registry_payload(
    company: &ResolvedCompany,
    matched_identifier: Option<(&str, &str)>,
    registry: &str,
    record_type: &str,
    title: &str,
    source_url: &str,
    fetched_at: &str,
    published_at: Option<String>,
    snippet: Option<String>,
    data: Value,
) -> RegistryRecordPayload {
    RegistryRecordPayload {
        company_name: company.display_name.clone(),
        matched_identifier: matched_identifier.map(|(_, value)| value.to_string()),
        matched_identifier_kind: matched_identifier.map(|(kind, _)| kind.to_string()),
        registry: registry.to_string(),
        record_type: record_type.to_string(),
        title: title.to_string(),
        source_url: source_url.to_string(),
        fetched_at: fetched_at.to_string(),
        published_at,
        snippet,
        data,
    }
}

fn extract_json_path(source: &Value, path: &[&str]) -> Option<Value> {
    let mut current = source;

    for segment in path {
        current = current.get(*segment)?;
    }

    Some(current.clone())
}

fn extract_rdf_events(source: &Value) -> Option<Value> {
    let entries = source
        .get("odpis")?
        .get("naglowekP")?
        .get("wpis")?
        .as_array()?;

    let rdf_entries: Vec<Value> = entries
        .iter()
        .filter(|entry| {
            entry
                .get("sygnaturaAktSprawyDotyczacejWpisu")
                .and_then(Value::as_str)
                .map(|signature| signature.contains("RDF/"))
                .unwrap_or(false)
        })
        .cloned()
        .collect();

    if rdf_entries.is_empty() {
        None
    } else {
        Some(Value::Array(rdf_entries))
    }
}

#[cfg(test)]
mod tests {
    use super::{extract_rdf_events, resolve_company};
    use crate::domain::company::CompanyRecord;
    use serde_json::json;

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
    fn extracts_only_rdf_events_from_full_extract() {
        let full_extract = json!({
            "odpis": {
                "naglowekP": {
                    "wpis": [
                        {"sygnaturaAktSprawyDotyczacejWpisu": "PO.VIII NS-REJ.KRS/1/24/123"},
                        {"sygnaturaAktSprawyDotyczacejWpisu": "RDF/100/24/111"},
                        {"sygnaturaAktSprawyDotyczacejWpisu": "RDF/100/24/222"}
                    ]
                }
            }
        });

        let extracted = extract_rdf_events(&full_extract).expect("rdf entries should exist");
        let entries = extracted.as_array().expect("entries should be an array");

        assert_eq!(entries.len(), 2);
        assert_eq!(
            entries[0]["sygnaturaAktSprawyDotyczacejWpisu"],
            "RDF/100/24/111"
        );
    }
}
