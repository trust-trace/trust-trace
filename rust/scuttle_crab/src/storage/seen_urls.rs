//! Persistent seen-URL store for crawl deduplication.

use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::utils::hash::hash_url;
use crate::utils::url::normalize_url;

/// One JSONL record in the seen-URL store.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SeenUrlRecord {
    pub url_hash: String,
    pub canonical_url: String,
    pub first_seen_at: String,
    pub source: String,
}

/// In-memory index backed by a JSONL file of normalized URL hashes.
#[derive(Debug)]
pub struct SeenUrlStore {
    path: PathBuf,
    hashes: HashSet<String>,
}

impl SeenUrlStore {
    /// Load an existing seen-URL store, or create an empty in-memory view if the file does not exist.
    pub fn load(path: impl AsRef<Path>) -> anyhow::Result<Self> {
        let path = path.as_ref().to_path_buf();
        let mut hashes = HashSet::new();

        match fs::read_to_string(&path) {
            Ok(contents) => {
                for line in contents.lines().filter(|line| !line.trim().is_empty()) {
                    let record: SeenUrlRecord = serde_json::from_str(line)?;
                    hashes.insert(record.url_hash);
                }
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(error) => return Err(error.into()),
        }

        Ok(Self { path, hashes })
    }

    /// Check whether a URL has already been recorded after normalization and hashing.
    pub fn contains(&self, url: &str) -> anyhow::Result<bool> {
        let normalized = normalize_url(url)?;
        Ok(self.hashes.contains(&hash_url(&normalized)))
    }

    /// Record a new normalized URL if it has not already been seen.
    pub fn record(&mut self, url: &str, source: &str, first_seen_at: &str) -> anyhow::Result<bool> {
        let canonical_url = normalize_url(url)?;
        let url_hash = hash_url(&canonical_url);

        if self.hashes.contains(&url_hash) {
            return Ok(false);
        }

        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }

        let record = SeenUrlRecord {
            url_hash: url_hash.clone(),
            canonical_url,
            first_seen_at: first_seen_at.to_string(),
            source: source.to_string(),
        };

        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        serde_json::to_writer(&mut file, &record)?;
        file.write_all(b"\n")?;

        self.hashes.insert(url_hash);
        Ok(true)
    }
}
