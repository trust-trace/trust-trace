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
use crawler::fetch::fetch_article_text;

/// Run the binary with process arguments and print the command result.
pub fn run() -> anyhow::Result<()> {
    let runtime = tokio::runtime::Runtime::new()?;
    let output = runtime.block_on(run_with_args(std::env::args()))?;
    println!("{output}");
    Ok(())
}

/// Parse CLI arguments and execute the currently implemented command scaffold.
pub async fn run_with_args<I, T>(args: I) -> anyhow::Result<String>
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
        Command::FetchUrl { url } => {
            let (title, text) = fetch_article_text(&url).await?;
            format!("title: {title}\n\n{text}")
        }
        Command::TestSource { source } => format!("test-source scaffold ready: {source}"),
    };

    Ok(output)
}
