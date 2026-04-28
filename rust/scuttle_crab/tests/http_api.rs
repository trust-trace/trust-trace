use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use serde_json::Value;
use tower::ServiceExt;

#[tokio::test]
async fn search_company_endpoint_queues_a_job() {
    let app = scuttle_crab::http::app(scuttle_crab::app::jobs::JobRegistry::default())
        .expect("app should build");

    let response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/commands/search-company")
                .header("content-type", "application/json")
                .body(Body::from(r#"{"query":"Allegro"}"#))
                .expect("request should build"),
        )
        .await
        .expect("request should succeed");

    assert_eq!(response.status(), StatusCode::ACCEPTED);
}

#[tokio::test]
async fn search_company_rejects_conflicting_flags() {
    let app = scuttle_crab::http::app(scuttle_crab::app::jobs::JobRegistry::default())
        .expect("app should build");

    let response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/commands/search-company")
                .header("content-type", "application/json")
                .body(Body::from(
                    r#"{"query":"Allegro","news_only":true,"registry_only":true}"#,
                ))
                .expect("request should build"),
        )
        .await
        .expect("request should succeed");

    assert_eq!(response.status(), StatusCode::UNPROCESSABLE_ENTITY);
}

#[tokio::test]
async fn scrape_company_endpoint_accepts_optional_registry_ids() {
    let app = scuttle_crab::http::app(scuttle_crab::app::jobs::JobRegistry::default())
        .expect("app should build");

    let response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/commands/scrape-company")
                .header("content-type", "application/json")
                .body(Body::from(
                    r#"{"query":"Allegro","krs":"0000123456","nip":"1234567890"}"#,
                ))
                .expect("request should build"),
        )
        .await
        .expect("request should succeed");

    assert_eq!(response.status(), StatusCode::ACCEPTED);

    let body = axum::body::to_bytes(response.into_body(), usize::MAX)
        .await
        .expect("body should read");
    let json: Value = serde_json::from_slice(&body).expect("json should parse");
    assert_eq!(json["data"]["command"], "scrape-company");
    assert_eq!(json["data"]["status"], "queued");
}

#[tokio::test]
async fn health_endpoint_returns_ok() {
    let app = scuttle_crab::http::app(scuttle_crab::app::jobs::JobRegistry::default())
        .expect("app should build");

    let response = app
        .oneshot(
            Request::builder()
                .method("GET")
                .uri("/api/v1/health")
                .body(Body::empty())
                .expect("request should build"),
        )
        .await
        .expect("request should succeed");

    assert_eq!(response.status(), StatusCode::OK);
}

#[tokio::test]
async fn every_command_endpoint_accepts_a_job_request() {
    let app = scuttle_crab::http::app(scuttle_crab::app::jobs::JobRegistry::default())
        .expect("app should build");

    for (uri, body) in [
        ("/api/v1/commands/crawl", r#"{}"#),
        (
            "/api/v1/commands/fetch-url",
            r#"{"url":"https://example.com/article"}"#,
        ),
        (
            "/api/v1/commands/scrape-company",
            r#"{"query":"Allegro"}"#,
        ),
        (
            "/api/v1/commands/search-company",
            r#"{"query":"Allegro"}"#,
        ),
        ("/api/v1/commands/test-source", r#"{"source":"reuters"}"#),
    ] {
        let response = app
            .clone()
            .oneshot(
                Request::builder()
                    .method("POST")
                    .uri(uri)
                    .header("content-type", "application/json")
                    .body(Body::from(body))
                    .expect("request should build"),
            )
            .await
            .expect("request should succeed");

        assert_eq!(response.status(), StatusCode::ACCEPTED, "{uri}");
    }
}

#[tokio::test]
async fn queued_job_is_visible_via_job_endpoint() {
    let registry = scuttle_crab::app::jobs::JobRegistry::default();
    let app = scuttle_crab::http::app(registry).expect("app should build");

    let queued = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/commands/search-company")
                .header("content-type", "application/json")
                .body(Body::from(r#"{"query":"Allegro"}"#))
                .expect("request should build"),
        )
        .await
        .expect("queue request should succeed");

    assert_eq!(queued.status(), StatusCode::ACCEPTED);

    let queued_body = axum::body::to_bytes(queued.into_body(), usize::MAX)
        .await
        .expect("body should read");
    let queued_json: Value = serde_json::from_slice(&queued_body).expect("json should parse");
    let job_id = queued_json["data"]["job_id"]
        .as_str()
        .expect("job id should be present");

    let job_response = app
        .oneshot(
            Request::builder()
                .method("GET")
                .uri(format!("/api/v1/jobs/{job_id}"))
                .body(Body::empty())
                .expect("request should build"),
        )
        .await
        .expect("job request should succeed");

    assert_eq!(job_response.status(), StatusCode::OK);
}

#[tokio::test]
async fn job_endpoint_returns_failed_status_for_execution_error() {
    unsafe {
        std::env::remove_var("TARKOV_BASE_URL");
    }

    let app = scuttle_crab::http::app(scuttle_crab::app::jobs::JobRegistry::default())
        .expect("app should build");

    let queued = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/commands/fetch-url")
                .header("content-type", "application/json")
                .body(Body::from(
                    r#"{"url":"https://example.com/article"}"#,
                ))
                .expect("request should build"),
        )
        .await
        .expect("request should succeed");

    let queued_body = axum::body::to_bytes(queued.into_body(), usize::MAX)
        .await
        .expect("body should read");
    let queued_json: Value = serde_json::from_slice(&queued_body).expect("json should parse");
    let job_id = queued_json["data"]["job_id"]
        .as_str()
        .expect("job id should be present");

    tokio::time::sleep(std::time::Duration::from_millis(25)).await;

    let response = app
        .oneshot(
            Request::builder()
                .method("GET")
                .uri(format!("/api/v1/jobs/{job_id}"))
                .body(Body::empty())
                .expect("request should build"),
        )
        .await
        .expect("request should succeed");

    assert_eq!(response.status(), StatusCode::OK);

    let response_body = axum::body::to_bytes(response.into_body(), usize::MAX)
        .await
        .expect("body should read");
    let response_json: Value = serde_json::from_slice(&response_body).expect("json should parse");
    assert_eq!(response_json["data"]["status"], "failed");
}
