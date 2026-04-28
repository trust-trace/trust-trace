use std::fs;
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::Path;
use std::path::PathBuf;
use std::sync::Arc;
use std::sync::Mutex;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::thread;
use std::time::Duration;
use std::time::{SystemTime, UNIX_EPOCH};

use scuttle_crab::config::AppConfig;
use scuttle_crab::crawler::pipeline::crawl_with_config;
use scuttle_crab::utils::hash::hash_url;
use scuttle_crab::utils::url::normalize_url;

#[derive(Debug, Clone)]
struct CapturedRequest {
    path: String,
    headers: String,
    body: String,
}

fn temp_dir_path(name: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time should move forward")
        .as_nanos();

    std::env::temp_dir().join(format!("scuttle_crab_{name}_{nanos}"))
}

#[test]
fn crawl_reads_feed_and_emits_articles() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("crawl_pipeline");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let max_in_flight = Arc::new(AtomicUsize::new(0));
    let current_in_flight = Arc::new(AtomicUsize::new(0));
    let server = spawn_test_server(
        listener,
        3,
        max_in_flight.clone(),
        current_in_flight.clone(),
    );

    let sources_path = root.join("sources.json");
    let sources_json = format!(
        r#"[
          {{
            "name": "Example Feed",
            "feed_url": "http://{address}/feed.xml",
            "allowed_domains": ["127.0.0.1"],
            "credibility_score": 0.9,
            "credibility_label": "high"
          }}
        ]"#
    );
    fs::write(&sources_path, sources_json).expect("sources file should be written");

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: sources_path.display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: "https://api-krs.ms.gov.pl/api".to_string(),
        msig_api_base_url: "https://wyszukiwarka-msig.ms.gov.pl/api".to_string(),
        concurrency: 2,
    };

    let summary = runtime
        .block_on(crawl_with_config(&config))
        .expect("crawl should complete");

    server.join().expect("server thread should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");
    let lines: Vec<_> = outbox.lines().collect();
    let seen_urls =
        fs::read_to_string(root.join("seen_urls.jsonl")).expect("seen store should exist");

    assert_eq!(summary.sources, 1);
    assert_eq!(summary.discovered, 2);
    assert_eq!(summary.skipped, 0);
    assert_eq!(summary.emitted, 2);
    assert_eq!(summary.failed, 0);
    assert_eq!(lines.len(), 2);
    assert_eq!(seen_urls.lines().count(), 2);
    assert!(max_in_flight.load(Ordering::SeqCst) >= 2);
    assert!(outbox.contains("\"discovery_method\":\"rss\""));
    assert!(outbox.contains("\"credibility_label\":\"high\""));

    fs::remove_dir_all(&root).ok();
}

#[test]
fn crawl_delivers_emitted_articles_to_tarkov() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("crawl_tarkov_e2e");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let feed_listener = TcpListener::bind("127.0.0.1:0").expect("feed listener should bind");
    let feed_address = feed_listener.local_addr().expect("feed listener should have address");
    let feed_max_in_flight = Arc::new(AtomicUsize::new(0));
    let feed_current_in_flight = Arc::new(AtomicUsize::new(0));
    let feed_server = spawn_test_server(
        feed_listener,
        3,
        feed_max_in_flight.clone(),
        feed_current_in_flight.clone(),
    );

    let tarkov_listener = TcpListener::bind("127.0.0.1:0").expect("tarkov listener should bind");
    let tarkov_address = tarkov_listener
        .local_addr()
        .expect("tarkov listener should have address");
    let captured_requests = Arc::new(Mutex::new(Vec::<CapturedRequest>::new()));
    let tarkov_server = spawn_tarkov_capture_server(
        tarkov_listener,
        2,
        Arc::clone(&captured_requests),
    );

    let sources_path = root.join("sources.json");
    let sources_json = format!(
        r#"[
          {{
            "name": "Example Feed",
            "feed_url": "http://{feed_address}/feed.xml",
            "allowed_domains": ["127.0.0.1"],
            "credibility_score": 0.9,
            "credibility_label": "high"
          }}
        ]"#
    );
    fs::write(&sources_path, sources_json).expect("sources file should be written");

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: sources_path.display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: "https://api-krs.ms.gov.pl/api".to_string(),
        msig_api_base_url: "https://wyszukiwarka-msig.ms.gov.pl/api".to_string(),
        concurrency: 2,
    };

    unsafe {
        std::env::set_var("TARKOV_BASE_URL", format!("http://{}", tarkov_address));
        std::env::set_var("TARKOV_INGEST_PATH", "/v1/articles");
    }

    let summary = runtime
        .block_on(crawl_with_config(&config))
        .expect("crawl should complete");

    unsafe {
        std::env::remove_var("TARKOV_BASE_URL");
        std::env::remove_var("TARKOV_INGEST_PATH");
    }

    feed_server.join().expect("feed server thread should finish");
    tarkov_server.join().expect("tarkov server thread should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");
    let lines: Vec<_> = outbox.lines().collect();
    let requests = captured_requests.lock().expect("requests lock");

    assert_eq!(summary.sources, 1);
    assert_eq!(summary.discovered, 2);
    assert_eq!(summary.emitted, 2);
    assert_eq!(summary.failed, 0);
    assert_eq!(lines.len(), 2);
    assert_eq!(requests.len(), 2);
    assert!(requests.iter().all(|request| request.path == "/v1/articles"));
    assert!(requests
        .iter()
        .all(|request| request.headers.to_lowercase().contains("x-payload-version: 1")));
    assert!(requests
        .iter()
        .all(|request| request.headers.to_lowercase().contains("x-correlation-id:")));
    assert!(requests
        .iter()
        .all(|request| serde_json::from_str::<serde_json::Value>(&request.body).is_ok()));
    assert!(requests
        .iter()
        .all(|request| serde_json::from_str::<serde_json::Value>(&request.body)
            .expect("body should parse")
            .get("source")
            .is_some()));

    fs::remove_dir_all(&root).ok();
}

#[test]
fn crawl_skips_seen_urls_before_fetching() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("crawl_dedup");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let max_in_flight = Arc::new(AtomicUsize::new(0));
    let current_in_flight = Arc::new(AtomicUsize::new(0));
    let server = spawn_test_server(listener, 2, max_in_flight, current_in_flight);
    let article_url = format!("http://127.0.0.1:{}/article-1", address.port());

    let sources_path = root.join("sources.json");
    let sources_json = format!(
        r#"[
          {{
            "name": "Example Feed",
            "feed_url": "http://{address}/feed.xml",
            "allowed_domains": ["127.0.0.1"],
            "credibility_score": 0.9,
            "credibility_label": "high"
          }}
        ]"#
    );
    fs::write(&sources_path, sources_json).expect("sources file should be written");
    fs::write(
        root.join("seen_urls.jsonl"),
        format!(
            "{{\"url_hash\":\"{}\",\"canonical_url\":\"{}\",\"first_seen_at\":\"2026-04-27T08:16:12Z\",\"source\":\"Example Feed\"}}\n",
            hash_url(&normalize_url(&article_url).expect("url should normalize")),
            article_url
        ),
    )
    .expect("seen store should be primed");

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: sources_path.display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: "https://api-krs.ms.gov.pl/api".to_string(),
        msig_api_base_url: "https://wyszukiwarka-msig.ms.gov.pl/api".to_string(),
        concurrency: 2,
    };

    let summary = runtime
        .block_on(crawl_with_config(&config))
        .expect("crawl should complete");

    server.join().expect("server thread should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");

    assert_eq!(summary.discovered, 2);
    assert_eq!(summary.skipped, 1);
    assert_eq!(summary.emitted, 1);
    assert_eq!(outbox.lines().count(), 1);

    fs::remove_dir_all(&root).ok();
}

#[test]
fn crawl_discovers_articles_from_homepage_document() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("crawl_homepage");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let fixture_root = PathBuf::from("/home/tmk/hackaton/test_crawler");
    let server = spawn_fixture_server(listener, fixture_root, 9);

    let sources_path = root.join("sources.json");
    let sources_json = format!(
        r#"[
          {{
            "name": "MediaWatch Homepage",
            "page_url": "http://{address}/",
            "article_link_selector": "a.card",
            "allowed_domains": ["127.0.0.1"],
            "credibility_score": 0.8,
            "credibility_label": "medium"
          }}
        ]"#
    );
    fs::write(&sources_path, sources_json).expect("sources file should be written");

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: sources_path.display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: "https://api-krs.ms.gov.pl/api".to_string(),
        msig_api_base_url: "https://wyszukiwarka-msig.ms.gov.pl/api".to_string(),
        concurrency: 4,
    };

    let summary = runtime
        .block_on(crawl_with_config(&config))
        .expect("crawl should complete");

    server.join().expect("server thread should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");

    assert_eq!(summary.sources, 1);
    assert_eq!(summary.discovered, 8);
    assert_eq!(summary.skipped, 0);
    assert_eq!(summary.emitted, 8);
    assert_eq!(summary.failed, 0);
    assert_eq!(outbox.lines().count(), 8);
    assert!(outbox.contains("Cyfrowy Polsat ukrywa długi?"));
    assert!(outbox.contains("Solorz Family War Threatens CPS Governance"));

    fs::remove_dir_all(&root).ok();
}

#[test]
fn crawl_respects_page_depth_two() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("crawl_depth_two");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_depth_server(listener, 7);

    let sources_path = root.join("sources.json");
    let sources_json = format!(
        r#"[
          {{
            "name": "Depth Source",
            "page_url": "http://{address}/root",
            "article_link_selector": "a[href]",
            "allowed_domains": ["127.0.0.1"],
            "credibility_score": 0.7,
            "credibility_label": "medium",
            "max_depth": 2,
            "include_page_url": true
          }}
        ]"#
    );
    fs::write(&sources_path, sources_json).expect("sources file should be written");

    let config = AppConfig {
        companies_path: root.join("companies.json").display().to_string(),
        sources_path: sources_path.display().to_string(),
        seen_urls_path: root.join("seen_urls.jsonl").display().to_string(),
        outbox_path: root.join("outbox.jsonl").display().to_string(),
        krs_api_base_url: "https://api-krs.ms.gov.pl/api".to_string(),
        msig_api_base_url: "https://wyszukiwarka-msig.ms.gov.pl/api".to_string(),
        concurrency: 4,
    };

    let summary = runtime
        .block_on(crawl_with_config(&config))
        .expect("crawl should complete");

    server.join().expect("server thread should finish");

    let outbox = fs::read_to_string(root.join("outbox.jsonl")).expect("outbox should exist");

    assert_eq!(summary.discovered, 4);
    assert_eq!(summary.emitted, 4);
    assert_eq!(summary.failed, 0);
    assert!(outbox.contains("Root Article"));
    assert!(outbox.contains("Child Article"));
    assert!(outbox.contains("Grandchild Article"));
    assert!(outbox.contains("Sibling Article"));

    fs::remove_dir_all(&root).ok();
}

fn spawn_test_server(
    listener: TcpListener,
    expected_requests: usize,
    max_in_flight: Arc<AtomicUsize>,
    current_in_flight: Arc<AtomicUsize>,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        let mut workers = Vec::new();

        for _ in 0..expected_requests {
            let (mut stream, _) = listener.accept().expect("connection should succeed");
            let address = listener.local_addr().expect("address");
            let max_in_flight = Arc::clone(&max_in_flight);
            let current_in_flight = Arc::clone(&current_in_flight);

            workers.push(thread::spawn(move || {
                handle_request(&mut stream, address, &max_in_flight, &current_in_flight);
            }));
        }

        for worker in workers {
            worker.join().expect("worker should finish");
        }
    })
}

fn spawn_tarkov_capture_server(
    listener: TcpListener,
    expected_requests: usize,
    captured_requests: Arc<Mutex<Vec<CapturedRequest>>>,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        let mut workers = Vec::new();

        for _ in 0..expected_requests {
            let (mut stream, _) = listener.accept().expect("connection should succeed");
            let captured_requests = Arc::clone(&captured_requests);

            workers.push(thread::spawn(move || {
                handle_tarkov_request(&mut stream, &captured_requests);
            }));
        }

        for worker in workers {
            worker.join().expect("worker should finish");
        }
    })
}

fn handle_request(
    stream: &mut TcpStream,
    address: SocketAddr,
    max_in_flight: &AtomicUsize,
    current_in_flight: &AtomicUsize,
) {
    let mut buffer = [0; 2048];
    let bytes_read = stream
        .read(&mut buffer)
        .expect("request should be readable");
    let request = String::from_utf8_lossy(&buffer[..bytes_read]);
    let path = request
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .expect("request path should be present");

    let active = current_in_flight.fetch_add(1, Ordering::SeqCst) + 1;
    max_in_flight.fetch_max(active, Ordering::SeqCst);

    let body = match path {
        "/feed.xml" => format!(
            r#"<?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0">
              <channel>
                <title>Example Feed</title>
                <item><title>One</title><link>http://127.0.0.1:{}/article-1</link></item>
                <item><title>Two</title><link>http://127.0.0.1:{}/article-2</link></item>
              </channel>
            </rss>"#,
            address.port(),
            address.port()
        ),
        "/article-1" => article_html(
            "Article One",
            "First article body with enough text to pass extraction and be written to the outbox.",
        ),
        "/article-2" => article_html(
            "Article Two",
            "Second article body with enough text to pass extraction and prove concurrent fetch execution.",
        ),
        _ => String::from("not found"),
    };

    if matches!(path, "/article-1" | "/article-2") {
        thread::sleep(Duration::from_millis(50));
    }

    let status = if matches!(path, "/feed.xml" | "/article-1" | "/article-2") {
        "200 OK"
    } else {
        "404 Not Found"
    };
    let content_type = if path == "/feed.xml" {
        "application/rss+xml"
    } else {
        "text/html; charset=utf-8"
    };

    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    stream
        .write_all(response.as_bytes())
        .expect("response should be written");

    current_in_flight.fetch_sub(1, Ordering::SeqCst);
}

fn handle_tarkov_request(stream: &mut TcpStream, captured_requests: &Arc<Mutex<Vec<CapturedRequest>>>) {
    let mut buffer = [0; 8192];
    let bytes_read = stream
        .read(&mut buffer)
        .expect("request should be readable");
    let request = String::from_utf8_lossy(&buffer[..bytes_read]).to_string();
    let mut lines = request.lines();
    let request_line = lines.next().expect("request line should exist");
    let path = request_line
        .split_whitespace()
        .nth(1)
        .expect("request path should be present")
        .to_string();

    let mut headers = String::new();
    let mut body = String::new();
    let mut in_body = false;
    for line in lines {
        if line.is_empty() {
            in_body = true;
            continue;
        }
        if in_body {
            body.push_str(line);
        } else {
            headers.push_str(line);
            headers.push('\n');
        }
    }

    captured_requests.lock().expect("requests lock").push(CapturedRequest {
        path,
        headers,
        body,
    });

    let response = "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok";
    stream
        .write_all(response.as_bytes())
        .expect("response should be written");
}

fn article_html(title: &str, body: &str) -> String {
    format!(
        "<html><head><title>{title}</title></head><body><article><p>{body}</p></article></body></html>"
    )
}

fn article_page_with_links(title: &str, body: &str, links: &[&str]) -> String {
    let link_markup = links
        .iter()
        .map(|href| format!("<a href=\"{href}\">{href}</a>"))
        .collect::<Vec<_>>()
        .join("");

    format!(
        "<html><head><title>{title}</title></head><body><article><p>{body}</p></article>{link_markup}</body></html>"
    )
}

fn spawn_fixture_server(
    listener: TcpListener,
    fixture_root: PathBuf,
    expected_requests: usize,
) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        let mut workers = Vec::new();

        for _ in 0..expected_requests {
            let (mut stream, _) = listener.accept().expect("connection should succeed");
            let fixture_root = fixture_root.clone();

            workers.push(thread::spawn(move || {
                handle_fixture_request(&mut stream, &fixture_root);
            }));
        }

        for worker in workers {
            worker.join().expect("worker should finish");
        }
    })
}

fn spawn_depth_server(listener: TcpListener, expected_requests: usize) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        let mut workers = Vec::new();

        for _ in 0..expected_requests {
            let (mut stream, _) = listener.accept().expect("connection should succeed");

            workers.push(thread::spawn(move || {
                handle_depth_request(&mut stream);
            }));
        }

        for worker in workers {
            worker.join().expect("worker should finish");
        }
    })
}

fn handle_depth_request(stream: &mut TcpStream) {
    let mut buffer = [0; 2048];
    let bytes_read = stream
        .read(&mut buffer)
        .expect("request should be readable");
    let request = String::from_utf8_lossy(&buffer[..bytes_read]);
    let path = request
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .expect("request path should be present");

    let body = match path {
        "/root" => article_page_with_links(
            "Root Article",
            "Root article body with enough words to pass extraction.",
            &["/child", "/sibling"],
        ),
        "/child" => article_page_with_links(
            "Child Article",
            "Child article body with enough words to pass extraction.",
            &["/grandchild"],
        ),
        "/grandchild" => article_page_with_links(
            "Grandchild Article",
            "Grandchild article body with enough words to pass extraction.",
            &[],
        ),
        "/sibling" => article_page_with_links(
            "Sibling Article",
            "Sibling article body with enough words to pass extraction.",
            &[],
        ),
        _ => String::from("not found"),
    };

    let status = if matches!(path, "/root" | "/child" | "/grandchild" | "/sibling") {
        "200 OK"
    } else {
        "404 Not Found"
    };
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    stream
        .write_all(response.as_bytes())
        .expect("response should be written");
}

fn handle_fixture_request(stream: &mut TcpStream, fixture_root: &Path) {
    let mut buffer = [0; 2048];
    let bytes_read = stream
        .read(&mut buffer)
        .expect("request should be readable");
    let request = String::from_utf8_lossy(&buffer[..bytes_read]);
    let path = request
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .expect("request path should be present");

    let relative = match path {
        "/" => "index(1).html",
        other => other.trim_start_matches('/'),
    };
    let file_path = fixture_root.join(relative);

    let (status, body) = match fs::read_to_string(&file_path) {
        Ok(body) => ("200 OK", body),
        Err(_) => ("404 Not Found", String::from("not found")),
    };

    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    stream
        .write_all(response.as_bytes())
        .expect("response should be written");
}
