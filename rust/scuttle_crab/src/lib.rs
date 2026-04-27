//! Top-level library entrypoints for the `scuttle_crab` binary.

pub mod cli;
pub mod config;
pub mod crawler;
pub mod domain;
pub mod storage;
pub mod utils;

use clap::Parser;
use cli::{Cli, Command};
use config::AppConfig;

/// Run the binary with process arguments and print the command result.
pub fn run() -> anyhow::Result<()> {
    let output = run_with_args(std::env::args())?;
    println!("{output}");
    Ok(())
}

/// Parse CLI arguments and execute the currently implemented command scaffold.
pub fn run_with_args<I, T>(args: I) -> anyhow::Result<String>
where
    I: IntoIterator<Item = T>,
    T: Into<std::ffi::OsString> + Clone,
{
    let cli = Cli::parse_from(args);
    let config = AppConfig::default();

    let output = match cli.command {
        Command::Crawl => format!(
            "crawl scaffold ready: companies={}, seen_urls={}, outbox={}",
            config.companies_path, config.seen_urls_path, config.outbox_path
        ),
        Command::FetchUrl { url } => format!("fetch-url scaffold ready: {url}"),
        Command::TestSource { source } => format!("test-source scaffold ready: {source}"),
    };

    Ok(output)
}
