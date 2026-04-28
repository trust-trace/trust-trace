use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};

use scuttle_crab::config::AppConfig;
use scuttle_crab::crawler::company_pipeline::scrape_company_articles_with_config;
use scuttle_crab::crawler::company_pipeline::scrape_company_with_config;
use scuttle_crab::domain::article::ArticlePayload;

fn temp_dir_path(name: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time should move forward")
        .as_nanos();

    std::env::temp_dir().join(format!("scuttle_crab_{name}_{nanos}"))
}

#[test]
fn scrape_company_emits_article_payloads_for_krs_and_msig() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("company_pipeline");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_krs_server(listener, 3, false, false, false);

    fs::write(
        root.join("companies.json"),
        r#"[
          {
            "name": "Allegro",
            "ticker": "ALE",
            "aliases": ["allegro", "allegro.pl"],
            "official_name": "ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ",
            "krs": "0000635012",
            "nip": "5252674798",
            "regon": "36533155300000"
          }
        ]"#,
    )
    .expect("companies file should be written");

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: root.join("sources.json").display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: format!("http://{address}"),
        msig_api_base_url: format!("http://{address}"),
        concurrency: 2,
    };

    let summary = runtime
        .block_on(scrape_company_with_config(&config, "allegro"))
        .expect("company scrape should complete");

    server.join().expect("server should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");
    let lines: Vec<ArticlePayload> = outbox
        .lines()
        .map(|line| serde_json::from_str(line).expect("line should deserialize"))
        .collect();

    assert_eq!(summary.emitted, 3);
    assert_eq!(summary.krs_documents, 2);
    assert_eq!(summary.msig_documents, 1);
    assert_eq!(summary.failed, 0);
    assert_eq!(lines.len(), 3);
    assert!(lines
        .iter()
        .all(|payload| !payload.article.title.is_empty()));
    assert!(lines
        .iter()
        .all(|payload| !payload.article.text.0.is_empty()));
    assert!(lines.iter().all(|payload| payload.metadata.companies
        == vec!["ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ"]));
    assert!(lines
        .iter()
        .any(|payload| payload.metadata.discovery_method.as_deref() == Some("registry_krs")));
    assert!(lines
        .iter()
        .any(|payload| payload.metadata.discovery_method.as_deref() == Some("registry_msig")));
    assert!(lines.iter().any(|payload| {
        payload.metadata.discovery_method.as_deref() == Some("registry_msig")
            && payload.article.published_at == "2026-04-20"
    }));

    fs::remove_dir_all(&root).ok();
}

#[test]
fn scrape_company_counts_msig_failures() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("company_pipeline_msig_failure");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_krs_server(listener, 3, true, false, false);

    fs::write(
        root.join("companies.json"),
        r#"[
          {
            "name": "Allegro",
            "ticker": "ALE",
            "aliases": ["allegro", "allegro.pl"],
            "official_name": "ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ",
            "krs": "0000635012",
            "nip": "5252674798",
            "regon": "36533155300000"
          }
        ]"#,
    )
    .expect("companies file should be written");

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: root.join("sources.json").display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: format!("http://{address}"),
        msig_api_base_url: format!("http://{address}"),
        concurrency: 2,
    };

    let summary = runtime
        .block_on(scrape_company_with_config(&config, "allegro"))
        .expect("company scrape should complete");

    server.join().expect("server should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");
    let lines: Vec<ArticlePayload> = outbox
        .lines()
        .map(|line| serde_json::from_str(line).expect("line should deserialize"))
        .collect();

    assert_eq!(summary.emitted, 2);
    assert_eq!(summary.krs_documents, 2);
    assert_eq!(summary.msig_documents, 0);
    assert_eq!(summary.failed, 1);
    assert_eq!(lines.len(), 2);

    fs::remove_dir_all(&root).ok();
}

#[test]
fn scrape_company_counts_msig_malformed_items_shape_as_failure() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("company_pipeline_msig_malformed");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_krs_server(listener, 3, false, false, true);

    write_company_fixture(&root);

    let config = config_for_root(&root, &address.to_string());

    let summary = runtime
        .block_on(scrape_company_with_config(&config, "allegro"))
        .expect("company scrape should complete");

    server.join().expect("server should finish");

    assert_eq!(summary.emitted, 2);
    assert_eq!(summary.krs_documents, 2);
    assert_eq!(summary.msig_documents, 0);
    assert_eq!(summary.failed, 1);

    fs::remove_dir_all(&root).ok();
}

#[test]
fn scrape_company_succeeds_when_msig_fails_but_krs_succeeds() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("company_pipeline_msig_partial_failure");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_krs_server(listener, 3, true, false, false);

    write_company_fixture(&root);

    let config = config_for_root(&root, &address.to_string());

    let summary = runtime
        .block_on(scrape_company_with_config(&config, "allegro"))
        .expect("company scrape should complete");

    server.join().expect("server should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");
    let lines: Vec<ArticlePayload> = outbox
        .lines()
        .map(|line| serde_json::from_str(line).expect("line should deserialize"))
        .collect();

    assert_eq!(summary.emitted, 2);
    assert_eq!(summary.krs_documents, 2);
    assert_eq!(summary.msig_documents, 0);
    assert_eq!(summary.failed, 1);
    assert_eq!(lines.len(), 2);

    fs::remove_dir_all(&root).ok();
}

#[test]
fn scrape_company_articles_preserves_successes_after_later_fetch_failure() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("company_articles_partial_failure");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = thread::spawn(move || {
        for _ in 0..3 {
            let (mut stream, _) = listener.accept().expect("request should arrive");
            let request = read_request(&mut stream);
            let request_path = request_path(&request);

            if request_path.starts_with("/html/?q=") {
                let body = format!(
                    r#"<html><body><a class="result__a" href="http://{address}/article-1">Article 1</a><a class="result__a" href="http://{address}/article-2">Article 2</a></body></html>"#
                );
                let response = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                    body.len(),
                    body
                );
                stream
                    .write_all(response.as_bytes())
                    .expect("response should write");
            } else if request_path == "/article-1" {
                let body = r#"<html><head><title>First Article</title></head><body><article><p>First article body text is long enough.</p></article></body></html>"#;
                let response = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                    body.len(),
                    body
                );
                stream
                    .write_all(response.as_bytes())
                    .expect("response should write");
            } else if request_path == "/article-2" {
                let response = "HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
                stream
                    .write_all(response.as_bytes())
                    .expect("response should write");
            } else {
                panic!("unexpected request path: {request_path}");
            }
        }
    });

    fs::write(
        root.join("companies.json"),
        r#"[
          {
            "name": "Allegro",
            "ticker": "ALE",
            "aliases": ["allegro"],
            "official_name": "ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ",
            "krs": "0000635012"
          }
        ]"#,
    )
    .expect("companies file should be written");

    unsafe {
        std::env::set_var(
            "SCUTTLE_COMPANY_SEARCH_BASE_URL",
            format!("http://{address}/html/?q="),
        );
    }

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: root.join("sources.json").display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: format!("http://{address}"),
        msig_api_base_url: format!("http://{address}"),
        concurrency: 2,
    };

    let result = runtime
        .block_on(scrape_company_articles_with_config(&config, "allegro"))
        .expect("company article scrape should complete");

    server.join().expect("server should finish");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
    }

    assert_eq!(result.summary.emitted, 1);
    assert_eq!(result.summary.failed, 1);
    assert_eq!(result.payloads.len(), 1);
    assert_eq!(result.payloads[0].article.title, "First Article");

    fs::remove_dir_all(&root).ok();
}

#[test]
fn scrape_company_fails_when_krs_current_extract_fails() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("company_pipeline_krs_failure");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_krs_server(listener, 1, false, true, false);

    write_company_fixture(&root);

    let config = config_for_root(&root, &address.to_string());

    let error = runtime
        .block_on(scrape_company_with_config(&config, "allegro"))
        .expect_err("company scrape should fail");

    server.join().expect("server should finish");

    assert!(error.to_string().contains("current KRS extract"));

    fs::remove_dir_all(&root).ok();
}

fn spawn_krs_server(
    listener: TcpListener,
    expected_requests: usize,
    fail_msig: bool,
    fail_current_krs: bool,
    malformed_msig: bool,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        for _ in 0..expected_requests {
            let (mut stream, _) = listener.accept().expect("request should arrive");
            let request = read_request(&mut stream);
            let request_path = request_path(&request);

            if fail_current_krs && request_path.ends_with("/krs/OdpisAktualny/0000635012") {
                let response = "HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
                stream
                    .write_all(response.as_bytes())
                    .expect("response should write");
                continue;
            }

            let body = if request_path.ends_with("/krs/OdpisAktualny/0000635012") {
                r#"{
                  "odpis": {
                    "dane": {
                      "dzial3": {
                        "wzmiankiOZlozonychDokumentach": {
                          "wzmiankaOZlozeniuRocznegoSprawozdaniaFinansowego": [
                            {
                              "dataZlozenia": "21.04.2026",
                              "zaOkresOdDo": "OD 01.01.2025 DO 31.12.2025"
                            }
                          ]
                        }
                      }
                    }
                  }
                }"#
            } else if request_path.ends_with("/krs/OdpisPelny/0000635012") {
                r#"{
                  "odpis": {
                    "naglowekP": {
                      "wpis": [
                        {
                          "sygnaturaAktSprawyDotyczacejWpisu": "PO.VIII NS-REJ.KRS/1/24/123"
                        },
                        {
                          "sygnaturaAktSprawyDotyczacejWpisu": "RDF/813201/26/580"
                        }
                      ]
                    }
                  }
                }"#
            } else if request_path.ends_with("/Monitor/Search") {
                assert!(request.starts_with("POST /Monitor/Search HTTP/1.1"));
                if fail_msig {
                    let response = "HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
                    stream
                        .write_all(response.as_bytes())
                        .expect("response should write");
                    continue;
                }
                if malformed_msig {
                    r#"{
                      "publisher": "MSiG",
                      "entityName": "ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ"
                    }"#
                } else {
                    r#"{
                  "items": [
                    {
                      "publisher": "MSiG",
                      "entityName": "ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ",
                      "krs": "0000635012",
                      "position": 12345,
                      "publicationDate": "2026-04-20"
                    }
                  ]
                }"#
                }
            } else {
                panic!("unexpected request path: {request_path}");
            };

            let response = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                body.len(),
                body
            );
            stream
                .write_all(response.as_bytes())
                .expect("response should write");
        }
    })
}

fn read_request(stream: &mut TcpStream) -> String {
    let mut buffer = [0u8; 4096];
    let read = stream
        .read(&mut buffer)
        .expect("request should be readable");
    String::from_utf8_lossy(&buffer[..read]).to_string()
}

fn request_path(request: &str) -> String {
    let first_line = request
        .lines()
        .next()
        .expect("request should contain a line");
    let mut parts = first_line.split_whitespace();
    let _method = parts.next().expect("request should contain a method");
    parts
        .next()
        .expect("request should contain a path")
        .to_string()
}

fn write_company_fixture(root: &Path) {
    fs::write(
        root.join("companies.json"),
        r#"[
          {
            "name": "Allegro",
            "ticker": "ALE",
            "aliases": ["allegro", "allegro.pl"],
            "official_name": "ALLEGRO SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ",
            "krs": "0000635012",
            "nip": "5252674798",
            "regon": "36533155300000"
          }
        ]"#,
    )
    .expect("companies file should be written");
}

fn config_for_root(root: &Path, address: &str) -> AppConfig {
    AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: root.join("sources.json").display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: format!("http://{address}"),
        msig_api_base_url: format!("http://{address}"),
        concurrency: 2,
    }
}
