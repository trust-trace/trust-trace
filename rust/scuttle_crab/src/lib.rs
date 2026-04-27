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
use crawler::company_pipeline::scrape_company_with_config;
use crawler::fetch::fetch_article_payload;
use crawler::pipeline::crawl_with_config;
use storage::jsonl::JsonlOutbox;

pub fn format_company_scrape_output(
    query: &str,
    summary: &crawler::company_pipeline::CompanyScrapeSummary,
    config: &AppConfig,
) -> String {
    format!(
        "company scrape complete: query={}, emitted={}, failed={}, krs_documents={}, msig_documents={}, companies={}, outbox={}, krs_api={}, msig_api={}",
        query,
        summary.emitted,
        summary.failed,
        summary.krs_documents,
        summary.msig_documents,
        config.companies_path,
        config.outbox_path,
        config.krs_api_base_url,
        config.msig_api_base_url
    )
}

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

    let output = match cli.command {
        Command::Crawl { sources_file } => {
            let config = AppConfig::default().with_sources_path(sources_file)?;
            let summary = crawl_with_config(&config).await?;
            format!(
                "crawl complete: sources={}, discovered={}, skipped={}, emitted={}, failed={}, companies={}, sources_path={}, seen_urls={}, outbox={}",
                summary.sources,
                summary.discovered,
                summary.skipped,
                summary.emitted,
                summary.failed,
                config.companies_path,
                config.sources_path,
                config.seen_urls_path,
                config.outbox_path
            )
        }
        Command::FetchUrl { url } => {
            let config = AppConfig::default();
            let payload = fetch_article_payload(&url).await?;
            let outbox = JsonlOutbox::new(&config.outbox_path);
            outbox.append(&payload)?;

            let text_preview = payload.article.text.0.chars().take(200).collect::<String>();

            format!(
                "payload appended to {}\nsource={}\ntitle={}\nwords={}\n\npreview:\n{}",
                config.outbox_path,
                payload.source.url,
                payload.article.title,
                payload.article.word_count.unwrap_or(0),
                text_preview
            )
        }
        Command::ScrapeCompany { query } => {
            let config = AppConfig::default();
            let summary = scrape_company_with_config(&config, &query).await?;
            format_company_scrape_output(&query, &summary, &config)
        }
        Command::TestSource { source } => format!("test-source scaffold ready: {source}"),
    };

    Ok(output)
}
