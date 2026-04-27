use clap::Parser;

use scuttle_crab::cli::{Cli, Command};
use scuttle_crab::run_with_args;

#[test]
fn parses_crawl_subcommand() {
    let cli = Cli::parse_from(["scuttle_crab", "crawl"]);

    assert!(matches!(cli.command, Command::Crawl));
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
fn crawl_command_reports_default_data_paths() {
    let runtime = tokio::runtime::Runtime::new().expect("runtime should initialize");
    let output = runtime
        .block_on(run_with_args(["scuttle_crab", "crawl"]))
        .expect("crawl should run");

    assert!(output.contains("data/companies.json"));
    assert!(output.contains("data/seen_urls.jsonl"));
    assert!(output.contains("data/outbox.jsonl"));
}
