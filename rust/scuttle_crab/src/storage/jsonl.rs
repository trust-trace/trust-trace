//! JSONL outbox writer.

use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use serde::Serialize;

/// Appends serialized payloads to a JSONL file.
#[derive(Debug, Clone)]
pub struct JsonlOutbox {
    path: PathBuf,
}

impl JsonlOutbox {
    /// Create a writer targeting the provided JSONL path.
    pub fn new(path: impl AsRef<Path>) -> Self {
        Self {
            path: path.as_ref().to_path_buf(),
        }
    }

    /// Append one payload as a single JSON line.
    pub fn append<T: Serialize>(&self, payload: &T) -> anyhow::Result<()> {
        if let Some(parent) = self.path.parent() {
            fs::create_dir_all(parent)?;
        }

        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        serde_json::to_writer(&mut file, payload)?;
        file.write_all(b"\n")?;

        Ok(())
    }
}
