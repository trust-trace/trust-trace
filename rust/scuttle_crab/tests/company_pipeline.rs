use std::fs;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};

use scuttle_crab::config::AppConfig;
use scuttle_crab::crawler::company_pipeline::scrape_company_with_config;

fn temp_dir_path(name: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time should move forward")
        .as_nanos();

    std::env::temp_dir().join(format!("scuttle_crab_{name}_{nanos}"))
}

#[test]
fn scrape_company_emits_krs_and_rdf_records() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let root = temp_dir_path("company_pipeline");
    fs::create_dir_all(&root).expect("temp dir should be created");

    let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
    let address = listener.local_addr().expect("listener should have address");
    let server = spawn_krs_server(listener, 3);

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
    let lines: Vec<_> = outbox.lines().collect();

    assert_eq!(summary.emitted, 7);
    assert_eq!(lines.len(), 7);
    assert!(outbox.contains("\"registry\":\"krs\""));
    assert!(outbox.contains("\"record_type\":\"financial_filings_summary\""));
    assert!(outbox.contains("\"record_type\":\"filing_events\""));
    assert!(outbox.contains("\"registry\":\"msig\""));
    assert!(outbox.contains("\"registry\":\"krz\""));
    assert!(outbox.contains("\"registry\":\"rnp\""));

    fs::remove_dir_all(&root).ok();
}

fn spawn_krs_server(listener: TcpListener, expected_requests: usize) -> thread::JoinHandle<()> {
    thread::spawn(move || {
        for _ in 0..expected_requests {
            let (mut stream, _) = listener.accept().expect("request should arrive");
            let request = read_request(&mut stream);
            let request_path = request_path(&request);

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
