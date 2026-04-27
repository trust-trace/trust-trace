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
    Crawl,
    /// Fetch a single URL for debugging.
    FetchUrl { url: String },
    /// Validate one configured source.
    TestSource { source: String },
}
