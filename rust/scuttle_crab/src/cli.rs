//! CLI definitions for the crawler binary.

use clap::{Parser, Subcommand};

/// Top-level command-line arguments.
#[derive(Debug, Parser)]
#[command(name = "scuttle_crab")]
#[command(about = "Miniapp for crawling finance and news articles")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

/// Supported subcommands for the current scaffold.
#[derive(Debug, Clone, Subcommand)]
pub enum Command {
    /// Run the crawler pipeline.
    Crawl {
        /// Override the JSON sources file used for discovery.
        #[arg(long)]
        sources_file: Option<String>,
    },
    /// Fetch a single URL for debugging.
    FetchUrl { url: String },
    /// Scrape official company registry data for one company.
    ScrapeCompany { query: String },
    /// Search company news and optional official registry records.
    SearchCompany {
        query: String,
        #[arg(long, conflicts_with = "registry_only")]
        news_only: bool,
        #[arg(long, conflicts_with = "news_only")]
        registry_only: bool,
    },
    /// Validate one configured source.
    TestSource { source: String },
}
