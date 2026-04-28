use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};

use scuttle_crab::config::AppConfig;
use scuttle_crab::crawler::search_pipeline::search_company_with_config;

fn env_lock() -> &'static Mutex<()> {
    static ENV_LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    ENV_LOCK.get_or_init(|| Mutex::new(()))
}

fn temp_dir_path(name: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time should move forward")
        .as_nanos();

    std::env::temp_dir().join(format!("scuttle_crab_{name}_{nanos}"))
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

fn write_company_fixture(root: &Path) {
    fs::write(
        root.join("companies.json"),
        r#"[
          {
            "name": "InPost",
            "ticker": "INPST",
            "aliases": ["inpost", "inpost sa"],
            "official_name": "INPOST SPÓŁKA AKCYJNA",
            "krs": "0000543759",
            "nip": "6793108059",
            "regon": "360781085"
          }
        ]"#,
    )
    .expect("companies file should be written");
}

#[test]
fn search_company_news_only_emits_articles_to_outbox() {
    let _guard = env_lock().lock().expect("env lock should be available");
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_news_only");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_search_server(listener, 3, false);

    let config = config_for_root(&root, &address.to_string());

    unsafe {
        std::env::set_var(
            "SCUTTLE_COMPANY_SEARCH_BASE_URL",
            format!("http://{address}/html/?q="),
        );
        std::env::set_var("SCUTTLE_COMPANY_ARTICLE_LIMIT", "2");
    }

    let summary = runtime
        .block_on(search_company_with_config(&config, "Allegro", true, false))
        .expect("search should complete");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
        std::env::remove_var("SCUTTLE_COMPANY_ARTICLE_LIMIT");
    }

    server.join().expect("server should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");

    assert_eq!(summary.news_discovered, 2);
    assert_eq!(summary.news_emitted, 2);
    assert_eq!(summary.registry_emitted, 0);
    assert_eq!(outbox.lines().count(), 2);

    fs::remove_dir_all(&root).ok();
}

#[test]
fn search_company_registry_only_uses_company_identifiers() {
    let _guard = env_lock().lock().expect("env lock should be available");
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_registry_only");
    fs::create_dir_all(&root).expect("temp dir should be created");
    write_company_fixture(&root);

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_registry_server(listener, 3);

    let config = config_for_root(&root, &address.to_string());

    let summary = runtime
        .block_on(search_company_with_config(&config, "InPost", false, true))
        .expect("search should complete");

    server.join().expect("server should finish");

    assert_eq!(summary.news_discovered, 0);
    assert!(summary.registry_emitted >= 2);

    fs::remove_dir_all(&root).ok();
}

#[test]
fn search_company_registry_only_fails_when_identifiers_are_missing() {
    let _guard = env_lock().lock().expect("env lock should be available");
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_registry_missing_ids");
    fs::create_dir_all(&root).expect("temp dir should be created");

    fs::write(
        root.join("companies.json"),
        r#"[{"name":"No Id Co","ticker":"NIC","aliases":["no id co"]}]"#,
    )
    .expect("companies file should be written");

    let config = config_for_root(&root, "127.0.0.1:9");

    let error = runtime
        .block_on(search_company_with_config(&config, "No Id Co", false, true))
        .expect_err("registry-only should fail");

    assert!(error.to_string().contains("missing krs and nip"));

    fs::remove_dir_all(&root).ok();
}

#[test]
fn search_company_fails_when_news_results_never_produce_ten_articles() {
    let _guard = env_lock().lock().expect("env lock should be available");
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_partial_success");
    fs::create_dir_all(&root).expect("temp dir should be created");
    write_company_fixture(&root);

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_registry_server(listener, 4);

    let config = config_for_root(&root, &address.to_string());

    unsafe {
        std::env::set_var(
            "SCUTTLE_COMPANY_SEARCH_BASE_URL",
            format!("http://{address}/html/?q="),
        );
    }

    let summary = runtime
        .block_on(search_company_with_config(&config, "InPost", false, false))
        .expect("combined search should complete even when news does not produce ten articles");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
    }

    server.join().expect("server should finish");

    assert!(summary.news_failed >= 1);
    assert!(summary.registry_failed >= 1);

    fs::remove_dir_all(&root).ok();
}

#[test]
fn search_company_counts_tarkov_delivery_failures_without_losing_outbox_records() {
    let _guard = env_lock().lock().expect("env lock should be available");
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_delivery_failures");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_search_server(listener, 2, false);

    let config = config_for_root(&root, &address.to_string());

    unsafe {
        std::env::set_var(
            "SCUTTLE_COMPANY_SEARCH_BASE_URL",
            format!("http://{address}/html/?q="),
        );
        std::env::set_var("SCUTTLE_COMPANY_ARTICLE_LIMIT", "1");
        std::env::set_var("TARKOV_BASE_URL", "http://127.0.0.1:1");
        std::env::set_var("TARKOV_INGEST_PATH", "/v1/articles");
    }

    let summary = runtime
        .block_on(search_company_with_config(&config, "Allegro", true, false))
        .expect("search should complete");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
        std::env::remove_var("SCUTTLE_COMPANY_ARTICLE_LIMIT");
        std::env::remove_var("TARKOV_BASE_URL");
        std::env::remove_var("TARKOV_INGEST_PATH");
    }

    server.join().expect("server should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");

    assert_eq!(summary.news_emitted, 1);
    assert_eq!(summary.delivery_failed, 1);
    assert_eq!(outbox.lines().count(), 1);

    fs::remove_dir_all(&root).ok();
}

#[test]
fn search_company_delivers_exactly_ten_news_articles_when_candidates_are_available() {
    let _guard = env_lock().lock().expect("env lock should be available");
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_exact_ten");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_contract_server(listener, 12, 2);

    let config = config_for_root(&root, &address.to_string());

    unsafe {
        std::env::set_var(
            "SCUTTLE_COMPANY_SEARCH_BASE_URL",
            format!("http://{address}/html/?q="),
        );
    }

    let summary = runtime
        .block_on(search_company_with_config(&config, "InPost", true, false))
        .expect("search should complete");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
    }

    server.join().expect("server should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");
    assert_eq!(summary.news_emitted, 10);
    assert_eq!(summary.registry_emitted, 0);
    assert_eq!(outbox.lines().count(), 10);

    fs::remove_dir_all(&root).ok();
}

#[test]
fn search_company_fails_when_fewer_than_ten_valid_news_articles_exist() {
    let _guard = env_lock().lock().expect("env lock should be available");
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("search_company_under_ten");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_contract_server(listener, 9, 0);

    let config = config_for_root(&root, &address.to_string());

    unsafe {
        std::env::set_var(
            "SCUTTLE_COMPANY_SEARCH_BASE_URL",
            format!("http://{address}/html/?q="),
        );
    }

    let error = runtime
        .block_on(search_company_with_config(&config, "InPost", true, false))
        .expect_err("search should fail");

    unsafe {
        std::env::remove_var("SCUTTLE_COMPANY_SEARCH_BASE_URL");
    }

    server.join().expect("server should finish");

    assert!(error.to_string().contains("10 news articles"));

    fs::remove_dir_all(&root).ok();
}

fn spawn_search_server(
    listener: TcpListener,
    expected_requests: usize,
    blocked: bool,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        for _ in 0..expected_requests {
            let (mut stream, _) = listener.accept().expect("request should arrive");
            let request = read_request(&mut stream);
            let path = request_path(&request);

            let body = if path.starts_with("/blocked/") {
                r#"Unfortunately, bots use DuckDuckGo too"#.to_string()
            } else if path.starts_with("/html/") {
                if blocked {
                    r#"Unfortunately, bots use DuckDuckGo too"#.to_string()
                } else {
                    format!(
                        r#"<html><body>
                        <a class="result__a" href="http://127.0.0.1:{}/article-1">Article 1</a>
                        <a class="result__a" href="http://127.0.0.1:{}/article-2">Article 2</a>
                        </body></html>"#,
                        listener.local_addr().expect("addr").port(),
                        listener.local_addr().expect("addr").port(),
                    )
                }
            } else if path == "/article-1" {
                r#"<html><head><title>Article 1</title></head><body><article><p>This is the first article paragraph with enough content to survive extraction.</p></article></body></html>"#.to_string()
            } else {
                r#"<html><head><title>Article 2</title></head><body><article><p>This is the second article paragraph with enough content to survive extraction.</p></article></body></html>"#.to_string()
            };

            write_http_ok(&mut stream, &body);
        }
    })
}

fn spawn_registry_server(
    listener: TcpListener,
    expected_requests: usize,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        for _ in 0..expected_requests {
            let (mut stream, _) = listener.accept().expect("request should arrive");
            let request = read_request(&mut stream);
            let path = request_path(&request);

            let body = if path.starts_with("/html/") || path.starts_with("/blocked/") {
                r#"Unfortunately, bots use DuckDuckGo too"#.to_string()
            } else if path.ends_with("/krs/OdpisAktualny/0000543759") {
                r#"{"odpis":{"dane":{"dzial3":{"wzmianki":[{"dataZlozenia":"21.04.2026"}]}}}}"#
                    .to_string()
            } else if path.ends_with("/krs/OdpisPelny/0000543759") {
                r#"{"odpis":{"historia":{"zmiany":[{"wpis":"Zmiana zarządu"}]}}}"#.to_string()
            } else {
                r#"{"items":[{"publicationDate":"2026-04-20","title":"MSiG ogłoszenie InPost","content":"Treść ogłoszenia"}]}"#
                    .to_string()
            };

            write_http_ok(&mut stream, &body);
        }
    })
}

fn spawn_contract_server(
    listener: TcpListener,
    total_results: usize,
    dead_results: usize,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        for _ in 0..(1 + total_results) {
            let (mut stream, _) = listener.accept().expect("request should arrive");
            let request = read_request(&mut stream);
            let path = request_path(&request);

            if path.starts_with("/html/") {
                let mut html = String::from("<html><body>");
                for index in 0..total_results {
                    let suffix = index + 1;
                    html.push_str(&format!(
                        "<a class=\"result__a\" href=\"http://127.0.0.1:{}/article-{}\">Article {}</a>",
                        listener.local_addr().expect("addr").port(),
                        suffix,
                        suffix
                    ));
                }
                html.push_str("</body></html>");
                write_http_ok(&mut stream, &html);
            } else if path.contains("/article-") {
                let index = path
                    .split('-')
                    .next_back()
                    .and_then(|value| value.parse::<usize>().ok())
                    .unwrap_or(0);
                if index <= dead_results {
                    let response =
                        "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
                    stream
                        .write_all(response.as_bytes())
                        .expect("response should write");
                } else {
                    let body = format!(
                        "<html><head><title>Article {index}</title></head><body><article><p>Article {index} body text is long enough to be extracted successfully, with enough detail and punctuation to satisfy the article extractor reliably.</p></article></body></html>"
                    );
                    write_http_ok(&mut stream, &body);
                }
            } else {
                let response =
                    "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
                stream
                    .write_all(response.as_bytes())
                    .expect("response should write");
            }
        }
    })
}

fn read_request(stream: &mut TcpStream) -> String {
    let mut buffer = [0_u8; 8192];
    let bytes_read = stream
        .read(&mut buffer)
        .expect("request should be readable");
    String::from_utf8_lossy(&buffer[..bytes_read]).to_string()
}

fn request_path(request: &str) -> String {
    request
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .unwrap_or("/")
        .to_string()
}

fn write_http_ok(stream: &mut TcpStream, body: &str) {
    let response = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        body.len(),
        body
    );
    stream
        .write_all(response.as_bytes())
        .expect("response should write");
}
