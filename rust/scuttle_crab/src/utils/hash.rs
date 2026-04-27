//! Hashing helpers.

use sha2::{Digest, Sha256};

/// Hash a normalized URL with SHA-256 and return the lowercase hex digest.
pub fn hash_url(url: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(url.as_bytes());
    format!("{:x}", hasher.finalize())
}
