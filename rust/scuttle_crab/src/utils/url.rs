//! URL normalization helpers used for deduplication.

/// Normalize a URL for stable deduplication.
///
/// Current behavior:
/// - removes fragments
/// - lowercases the host
/// - trims a trailing slash from non-root paths
pub fn normalize_url(input: &str) -> anyhow::Result<String> {
    let mut url = url::Url::parse(input)?;
    url.set_fragment(None);

    if let Some(host) = url.host_str() {
        let lower = host.to_ascii_lowercase();
        url.set_host(Some(&lower))?;
    }

    let path = url.path().to_string();
    if path.len() > 1 && path.ends_with('/') {
        url.set_path(path.trim_end_matches('/'));
    }

    Ok(url.to_string())
}
