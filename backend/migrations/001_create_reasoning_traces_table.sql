-- Migration: 001_create_reasoning_traces_table
-- Created: 2026-04-28
-- Stage 2: Database Schema for Reasoning Traces

CREATE TABLE reasoning_traces (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  classifier_name VARCHAR(50) NOT NULL,
  entity_type VARCHAR(100) NOT NULL,
  entity_id VARCHAR(255) NOT NULL,
  correlation_id VARCHAR(255),
  trace_data LONGTEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  
  INDEX ix_reasoning_traces_classifier_created (classifier_name, created_at),
  INDEX ix_reasoning_traces_correlation_id (correlation_id),
  INDEX ix_reasoning_traces_entity_id (entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Commentary:
-- - id: Primary key, auto-incrementing BIGINT for large-scale deployments
-- - classifier_name: Name of classifier (EEM, NSA, RKR, Tarkov, Market)
-- - entity_type: Type of entity (event, person, article, etc.)
-- - entity_id: ID of the entity being traced
-- - correlation_id: Links to parent event/article for multi-classifier tracing
-- - trace_data: LONGTEXT to store JSON domain-specific trace objects
-- - created_at: Timestamp of trace creation
-- - Indexes optimized for:
--   * Querying by classifier and date range
--   * Retrieving traces by correlation ID
--   * Querying by entity ID
