use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use chrono::{DateTime, Utc};
use serde::Serialize;
use uuid::Uuid;

use crate::app::commands::CommandSummary;

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    Queued,
    Running,
    Succeeded,
    Failed,
}

#[derive(Debug, Clone, Serialize)]
pub struct JobRecord {
    pub job_id: Uuid,
    pub command: String,
    pub status: JobStatus,
    pub started_at: Option<DateTime<Utc>>,
    pub finished_at: Option<DateTime<Utc>>,
    pub summary: Option<CommandSummary>,
    pub error: Option<JobError>,
}

#[derive(Debug, Clone, Serialize)]
pub struct JobError {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, Default)]
pub struct JobRegistry {
    records: Arc<Mutex<HashMap<Uuid, JobRecord>>>,
}

impl JobRegistry {
    pub fn insert(&self, command: impl Into<String>) -> JobRecord {
        let record = JobRecord {
            job_id: Uuid::new_v4(),
            command: command.into(),
            status: JobStatus::Queued,
            started_at: None,
            finished_at: None,
            summary: None,
            error: None,
        };
        self.records
            .lock()
            .expect("job registry lock poisoned")
            .insert(record.job_id, record.clone());
        record
    }

    pub fn get(&self, job_id: Uuid) -> Option<JobRecord> {
        self.records
            .lock()
            .expect("job registry lock poisoned")
            .get(&job_id)
            .cloned()
    }

    pub fn mark_running(&self, job_id: Uuid) {
        if let Some(record) = self
            .records
            .lock()
            .expect("job registry lock poisoned")
            .get_mut(&job_id)
        {
            record.status = JobStatus::Running;
            record.started_at = Some(Utc::now());
        }
    }

    pub fn mark_succeeded(&self, job_id: Uuid, summary: CommandSummary) {
        if let Some(record) = self
            .records
            .lock()
            .expect("job registry lock poisoned")
            .get_mut(&job_id)
        {
            record.status = JobStatus::Succeeded;
            record.finished_at = Some(Utc::now());
            record.summary = Some(summary);
            if record.started_at.is_none() {
                record.started_at = Some(Utc::now());
            }
        }
    }

    pub fn mark_failed(&self, job_id: Uuid, code: impl Into<String>, message: impl Into<String>) {
        if let Some(record) = self
            .records
            .lock()
            .expect("job registry lock poisoned")
            .get_mut(&job_id)
        {
            record.status = JobStatus::Failed;
            record.finished_at = Some(Utc::now());
            record.error = Some(JobError {
                code: code.into(),
                message: message.into(),
            });
            if record.started_at.is_none() {
                record.started_at = Some(Utc::now());
            }
        }
    }
}
