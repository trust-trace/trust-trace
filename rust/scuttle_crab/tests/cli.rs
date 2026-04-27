use clap::Parser;
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use scuttle_crab::cli::{Cli, Command};
use scuttle_crab::config::AppConfig;
use scuttle_crab::crawler::company_pipeline::CompanyScrapeSummary;
use scuttle_crab::{format_company_scrape_output, run_with_args};

fn temp_file_path(name: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("time should move forward")
        .as_nanos();

    std::env::temp_dir().join(format!("scuttle_crab_{name}_{nanos}.json"))
}

#[test]
fn parses_crawl_subcommand() {
    let cli = Cli::parse_from(["scuttle_crab", "crawl"]);

    assert!(matches!(cli.command, Command::Crawl { .. }));
}

#[test]
fn parses_crawl_subcommand_with_sources_file() {
    let cli = Cli::parse_from([
        "scuttle_crab",
        "crawl",
        "--sources-file",
        "data/custom-sources.json",
    ]);

    match cli.command {
        Command::Crawl { sources_file } => {
            assert_eq!(sources_file.as_deref(), Some("data/custom-sources.json"))
        }
        _ => panic!("expected crawl command"),
    }
}

#[test]
fn parses_fetch_url_subcommand() {
    let cli = Cli::parse_from(["scuttle_crab", "fetch-url", "https://example.com/article"]);

    match cli.command {
        Command::FetchUrl { url } => assert_eq!(url, "https://example.com/article"),
        _ => panic!("expected fetch-url command"),
    }
}

#[test]
fn parses_scrape_company_subcommand() {
    let cli = Cli::parse_from(["scuttle_crab", "scrape-company", "Allegro"]);

    match cli.command {
        Command::ScrapeCompany { query } => assert_eq!(query, "Allegro"),
        _ => panic!("expected scrape-company command"),
    }
}

#[test]
fn fetch_url_command_is_parsed_with_localhost_url() {
    let cli = Cli::parse_from([
        "scuttle_crab",
        "fetch-url",
        "http://127.0.0.1:8787/en_01_solorz_succession.html",
    ]);

    match cli.command {
        Command::FetchUrl { url } => {
            assert_eq!(url, "http://127.0.0.1:8787/en_01_solorz_succession.html")
        }
        _ => panic!("expected fetch-url command"),
    }
}

#[test]
fn crawl_command_reports_default_data_paths() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let output = runtime
        .block_on(run_with_args(["scuttle_crab", "crawl"]))
        .expect("crawl should run");

    assert!(output.contains("sources="));
    assert!(output.contains("data/companies.json"));
    assert!(output.contains("data/sources.json"));
    assert!(output.contains("data/seen_urls.jsonl"));
    assert!(output.contains("data/outbox.jsonl"));
    assert!(!output.contains("scaffold"));
}

#[test]
fn crawl_command_reports_explicit_sources_file_path() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let sources_path = temp_file_path("custom_sources");
    fs::write(&sources_path, "[]").expect("sources file should be written");

    let output = runtime
        .block_on(run_with_args([
            "scuttle_crab",
            "crawl",
            "--sources-file",
            sources_path.to_str().expect("path should be utf-8"),
        ]))
        .expect("crawl should run");

    assert!(output.contains(&format!("sources_path={}", sources_path.display())));

    fs::remove_file(sources_path).ok();
}

#[test]
fn crawl_command_errors_for_missing_explicit_sources_file() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let missing_path = temp_file_path("missing_sources");

    let error = runtime
        .block_on(run_with_args([
            "scuttle_crab",
            "crawl",
            "--sources-file",
            missing_path.to_str().expect("path should be utf-8"),
        ]))
        .expect_err("crawl should fail when explicit sources file is missing");

    assert!(error.to_string().contains("sources file not found"));
}

#[test]
fn scrape_company_output_includes_extended_summary_fields() {
    let config = AppConfig::default();
    let summary = CompanyScrapeSummary {
        emitted: 3,
        failed: 1,
        krs_documents: 2,
        msig_documents: 1,
    };

    let output = format_company_scrape_output("Allegro", &summary, &config);

    assert!(output.contains("query=Allegro"));
    assert!(output.contains("failed=1"));
    assert!(output.contains("krs_documents=2"));
    assert!(output.contains("msig_documents=1"));
    assert!(output.contains("companies=data/companies.json"));
    assert!(output.contains("outbox=data/outbox.jsonl"));
    assert!(output.contains("krs_api=https://api-krs.ms.gov.pl/api"));
    assert!(output.contains("msig_api=https://wyszukiwarka-msig.ms.gov.pl/api"));
}
