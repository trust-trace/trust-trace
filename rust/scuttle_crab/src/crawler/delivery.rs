//! Optional delivery bridge from scuttle_crab into Tarkov.

use std::time::Duration;

use anyhow::Context;

use crate::domain::article::ArticlePayload;

const DEFAULT_INGEST_PATH: &str = "/v1/articles";
const DEFAULT_TIMEOUT_SECS: u64 = 15;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TarkovDeliveryConfig {
    base_url: String,
    ingest_path: String,
    timeout_secs: u64,
}

impl TarkovDeliveryConfig {
    pub fn new(base_url: String, ingest_path: String, timeout_secs: u64) -> Self {
        Self {
            base_url,
            ingest_path,
            timeout_secs: timeout_secs.max(1),
        }
    }

    pub fn from_env() -> Option<Self> {
        let base_url = std::env::var("TARKOV_BASE_URL").ok()?.trim().to_string();
        if base_url.is_empty() {
            return None;
        }

        let ingest_path = std::env::var("TARKOV_INGEST_PATH")
            .unwrap_or_else(|_| DEFAULT_INGEST_PATH.to_string());
        let timeout_secs = std::env::var("TARKOV_TIMEOUT_SECS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .filter(|value| *value > 0)
            .unwrap_or(DEFAULT_TIMEOUT_SECS);

        Some(Self::new(base_url, ingest_path, timeout_secs))
    }

    fn ingest_url(&self) -> String {
        format!("{}{}", self.base_url.trim_end_matches('/'), self.ingest_path)
    }

    async fn deliver(&self, payload: &ArticlePayload) -> anyhow::Result<DeliveryOutcome> {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(self.timeout_secs))
            .build()?;
        let correlation_id = uuid::Uuid::new_v4().to_string();
        let url = self.ingest_url();

        let response = client
            .post(&url)
            .header("Content-Type", "application/json")
            .header("X-Payload-Version", "1")
            .header("X-Correlation-Id", &correlation_id)
            .json(payload)
            .send()
            .await
            .with_context(|| format!("request failed for {url}"))?;

        let status = response.status();
        if status.is_success() {
            return Ok(DeliveryOutcome {
                correlation_id,
                status: status.as_u16(),
                duplicate: false,
            });
        }

        if status.as_u16() == 409 {
            return Ok(DeliveryOutcome {
                correlation_id,
                status: status.as_u16(),
                duplicate: true,
            });
        }

        let body = response.text().await.unwrap_or_default();
        anyhow::bail!("tarkov delivery failed with status {status}: {body}");
    }
}

pub fn required_tarkov_delivery_config() -> anyhow::Result<TarkovDeliveryConfig> {
    TarkovDeliveryConfig::from_env().ok_or_else(|| anyhow::anyhow!("TARKOV_BASE_URL must be configured for API execution"))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeliveryOutcome {
    pub correlation_id: String,
    pub status: u16,
    pub duplicate: bool,
}

pub async fn maybe_deliver_to_tarkov(payload: &ArticlePayload) -> anyhow::Result<Option<DeliveryOutcome>> {
    let Some(config) = TarkovDeliveryConfig::from_env() else {
        return Ok(None);
    };

    Ok(Some(config.deliver(payload).await?))
}

pub async fn deliver_to_tarkov(payload: &ArticlePayload) -> anyhow::Result<DeliveryOutcome> {
    required_tarkov_delivery_config()?.deliver(payload).await
}

#[cfg(test)]
mod tests {
    use super::TarkovDeliveryConfig;
    use crate::domain::article::{ArticlePayload, ArticleSection, ArticleText, MetadataSection};
    use crate::domain::source::SourceInfo;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::sync::{Arc, Mutex};
    use std::thread;

    fn sample_payload() -> ArticlePayload {
        ArticlePayload {
            source: SourceInfo {
                name: "Reuters".to_string(),
                domain: "reuters.com".to_string(),
                url: "https://www.reuters.com/world/example".to_string(),
                credibility_score: 0.92,
                credibility_label: "high".to_string(),
            },
            article: ArticleSection {
                title: "Company X beats earnings expectations".to_string(),
                text: ArticleText("Full normalized article text here...".to_string()),
                language: Some("en".to_string()),
                authors: vec!["Jane Doe".to_string()],
                published_at: "2026-04-27T08:15:00Z".to_string(),
                scraped_at: "2026-04-27T08:16:12Z".to_string(),
                canonical_url: Some("https://www.reuters.com/world/example".to_string()),
                word_count: Some(845),
            },
            metadata: MetadataSection {
                section: Some("markets".to_string()),
                region: Some("us".to_string()),
                discovery_method: Some("rss".to_string()),
                http_status: Some(200),
                ..MetadataSection::default()
            },
        }
    }

    #[tokio::test]
    async fn posts_payload_to_tarkov_ingest_endpoint() {
        let listener = TcpListener::bind("127.0.0.1:0").expect("listener should bind");
        let address = listener.local_addr().expect("listener should have address");
        let received = Arc::new(Mutex::new(String::new()));
        let headers = Arc::new(Mutex::new(String::new()));
        let received_body = Arc::clone(&received);
        let received_headers = Arc::clone(&headers);

        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().expect("client should connect");
            let mut buffer = [0_u8; 8192];
            let bytes_read = stream.read(&mut buffer).expect("request should be readable");
            let request = String::from_utf8_lossy(&buffer[..bytes_read]).to_string();
            let mut lines = request.lines();
            let _request_line = lines.next().unwrap_or_default().to_string();
            let mut header_dump = String::new();
            let mut body = String::new();
            let mut in_body = false;
            for line in lines {
                if line.is_empty() {
                    in_body = true;
                    continue;
                }
                if in_body {
                    body.push_str(line);
                } else {
                    header_dump.push_str(line);
                    header_dump.push('\n');
                }
            }
            *received_body.lock().expect("body lock") = body;
            *received_headers.lock().expect("headers lock") = header_dump;
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
                .expect("response should write");
        });

        let config = TarkovDeliveryConfig::new(format!("http://{}", address), "/v1/articles".to_string(), 5);
        let outcome = config
            .deliver(&sample_payload())
            .await
            .expect("delivery should succeed");
        assert_eq!(outcome.status, 200);
        assert!(!outcome.duplicate);
        assert!(!outcome.correlation_id.is_empty());

        server.join().expect("server thread should finish");

        let body = received.lock().expect("body lock").clone();
        let headers = headers.lock().expect("headers lock").clone().to_lowercase();
        assert!(body.contains("\"source\""));
        assert!(body.contains("\"article\""));
        assert!(headers.contains("x-payload-version: 1"));
        assert!(headers.contains("x-correlation-id:"));
    }
}
