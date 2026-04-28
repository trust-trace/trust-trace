use axum::{
    Json, Router,
    extract::{Path, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::app::{commands::CommandRequest, jobs::JobRegistry};

#[derive(Debug, Clone)]
struct AppState {
    registry: JobRegistry,
}

#[derive(Debug, Deserialize)]
struct SearchCompanyRequest {
    query: String,
    #[serde(default)]
    news_only: bool,
    #[serde(default)]
    registry_only: bool,
}

#[derive(Debug, Deserialize)]
struct CrawlRequest {
    sources_file: Option<String>,
}

#[derive(Debug, Deserialize)]
struct FetchUrlRequest {
    url: String,
}

#[derive(Debug, Deserialize)]
struct ScrapeCompanyRequest {
    query: String,
    krs: Option<String>,
    nip: Option<String>,
}

#[derive(Debug, Deserialize)]
struct TestSourceRequest {
    source: String,
}

#[derive(Debug, Serialize)]
struct DataEnvelope<T> {
    data: T,
}

#[derive(Debug, Serialize)]
struct StartJobResponse {
    job_id: String,
    command: String,
    status: &'static str,
}

#[derive(Debug, Serialize)]
struct ErrorEnvelope {
    error: ErrorResponse,
}

#[derive(Debug, Serialize)]
struct ErrorResponse {
    code: &'static str,
    message: &'static str,
}

pub fn app(registry: JobRegistry) -> anyhow::Result<Router> {
    Ok(Router::new()
        .route("/api/v1/health", get(health))
        .route("/api/v1/jobs/{id}", get(get_job))
        .route("/api/v1/commands/crawl", post(queue_crawl))
        .route("/api/v1/commands/fetch-url", post(queue_fetch_url))
        .route("/api/v1/commands/scrape-company", post(queue_scrape_company))
        .route("/api/v1/commands/search-company", post(queue_search_company))
        .route("/api/v1/commands/test-source", post(queue_test_source))
        .with_state(AppState { registry }))
}

async fn health() -> StatusCode {
    StatusCode::OK
}

async fn get_job(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<DataEnvelope<crate::app::jobs::JobRecord>>, (StatusCode, Json<ErrorEnvelope>)> {
    let job_id = Uuid::parse_str(&id).map_err(|_| invalid_job())?;
    let record = state.registry.get(job_id).ok_or_else(not_found)?;
    Ok(Json(DataEnvelope { data: record }))
}

async fn queue_search_company(
    State(state): State<AppState>,
    Json(request): Json<SearchCompanyRequest>,
) -> Response {
    if request.news_only && request.registry_only {
        return (
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(ErrorEnvelope {
                error: ErrorResponse {
                    code: "validation_error",
                    message: "news_only and registry_only cannot both be true",
                },
            }),
        )
            .into_response();
    }

    let command = CommandRequest::SearchCompany {
        query: request.query,
        news_only: request.news_only,
        registry_only: request.registry_only,
    };
    let record = queue_command(state.registry.clone(), "search-company", command);
    accepted_response(record).into_response()
}

async fn queue_crawl(
    State(state): State<AppState>,
    Json(request): Json<CrawlRequest>,
) -> Response {
    let command = CommandRequest::Crawl {
        sources_file: request.sources_file,
    };
    let record = queue_command(state.registry.clone(), "crawl", command);
    accepted_response(record).into_response()
}

async fn queue_fetch_url(
    State(state): State<AppState>,
    Json(request): Json<FetchUrlRequest>,
) -> Response {
    let command = CommandRequest::FetchUrl { url: request.url };
    let record = queue_command(state.registry.clone(), "fetch-url", command);
    accepted_response(record).into_response()
}

async fn queue_scrape_company(
    State(state): State<AppState>,
    Json(request): Json<ScrapeCompanyRequest>,
) -> Response {
    let command = scrape_company_command(request);
    let record = queue_command(state.registry.clone(), "scrape-company", command);
    accepted_response(record).into_response()
}

fn scrape_company_command(request: ScrapeCompanyRequest) -> CommandRequest {
    CommandRequest::ScrapeCompany {
        query: request.query,
        krs: request.krs,
        nip: request.nip,
    }
}

async fn queue_test_source(
    State(state): State<AppState>,
    Json(request): Json<TestSourceRequest>,
) -> Response {
    let command = CommandRequest::TestSource {
        source: request.source,
    };
    let record = queue_command(state.registry.clone(), "test-source", command);
    accepted_response(record).into_response()
}

fn queue_command(
    registry: JobRegistry,
    command_name: &'static str,
    command: CommandRequest,
) -> crate::app::jobs::JobRecord {
    let record = registry.insert(command_name);
    let job_id = record.job_id;
    tokio::spawn(async move {
        registry.mark_running(job_id);
        match crate::app::commands::execute_command(command).await {
            Ok(summary) => registry.mark_succeeded(job_id, summary),
            Err(error) => registry.mark_failed(job_id, "job_failed", error.to_string()),
        }
    });
    record
}

fn accepted_response(record: crate::app::jobs::JobRecord) -> (StatusCode, Json<DataEnvelope<StartJobResponse>>) {
    (
        StatusCode::ACCEPTED,
        Json(DataEnvelope {
            data: StartJobResponse {
                job_id: record.job_id.to_string(),
                command: record.command,
                status: "queued",
            },
        }),
    )
}

fn invalid_job() -> (StatusCode, Json<ErrorEnvelope>) {
    (
        StatusCode::BAD_REQUEST,
        Json(ErrorEnvelope {
            error: ErrorResponse {
                code: "invalid_job_id",
                message: "job id must be a valid uuid",
            },
        }),
    )
}

fn not_found() -> (StatusCode, Json<ErrorEnvelope>) {
    (
        StatusCode::NOT_FOUND,
        Json(ErrorEnvelope {
            error: ErrorResponse {
                code: "not_found",
                message: "job was not found",
            },
        }),
    )
}

#[cfg(test)]
mod tests {
    use super::{scrape_company_command, ScrapeCompanyRequest};

    #[test]
    fn scrape_company_command_preserves_krs_and_nip() {
        let request: ScrapeCompanyRequest = serde_json::from_str(
            r#"{"query":"Allegro","krs":"0000123456","nip":"1234567890"}"#,
        )
        .expect("request should deserialize");

        match scrape_company_command(request) {
            crate::app::commands::CommandRequest::ScrapeCompany { query, krs, nip } => {
                assert_eq!(query, "Allegro");
                assert_eq!(krs.as_deref(), Some("0000123456"));
                assert_eq!(nip.as_deref(), Some("1234567890"));
            }
            _ => panic!("expected scrape-company command"),
        }
    }
}
