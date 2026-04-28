-- Migration: 001_create_reasoning_traces_table (SQLite version)
-- Created: 2026-04-28
-- Stage 2: Database Schema for Reasoning Traces

CREATE TABLE reasoning_traces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  classifier_name TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  correlation_id TEXT,
  trace_data TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_reasoning_traces_classifier_created ON reasoning_traces (classifier_name, created_at);
CREATE INDEX ix_reasoning_traces_correlation_id ON reasoning_traces (correlation_id);
CREATE INDEX ix_reasoning_traces_entity_id ON reasoning_traces (entity_id);

-- Commentary:
-- - id: Primary key, auto-incrementing INTEGER (SQLite equivalent)
-- - classifier_name: Name of classifier (EEM, NSA, RKR, Tarkov, Market)
-- - entity_type: Type of entity (event, person, article, etc.)
-- - entity_id: ID of the entity being traced
-- - correlation_id: Links to parent event/article for multi-classifier tracing
-- - trace_data: TEXT to store JSON domain-specific trace objects
-- - created_at: Timestamp of trace creation
-- - Indexes optimized for:
--   * Querying by classifier and date range
--   * Retrieving traces by correlation ID
--   * Querying by entity ID
