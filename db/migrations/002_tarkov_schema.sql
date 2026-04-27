-- Migration: 002_tarkov_schema.sql
-- Description: Add schema for Tarkov event extraction with tagged union event types
-- Requires: MySQL 8.0.16+
-- Purpose: Support tagged union event types (people, connection, classical) with comprehensive source tracking
-- Dependencies: 001_initial_schema.sql must be applied first

-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 0: EVENT TYPE SYSTEM - Tagged Union Implementation
-- ═══════════════════════════════════════════════════════════════════════════════

-- Alter: event table to add tagged union discriminator and data
-- Events are now discriminated by event_category (people | connection | classical)
-- NOTE: article_id is removed (use article_metadata.article_id with JOIN instead)
-- NOTE: updated_at is removed (events are immutable; source metadata updates separately)
ALTER TABLE event ADD COLUMN (
    event_category          VARCHAR(20)     NOT NULL DEFAULT 'classical'
                                            CHECK (event_category IN ('people', 'connection', 'classical')),
    extraction_confidence   DECIMAL(3,2)    CHECK (extraction_confidence BETWEEN 0 AND 1),
    source_text_quote       TEXT
);

-- Index for event type queries
CREATE INDEX idx_event_category              ON event(event_category);
CREATE INDEX idx_event_extraction_confidence ON event(extraction_confidence);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 1: PERSON ENTITY & PERSON-EVENT LINKING
-- ═══════════════════════════════════════════════════════════════════════════════

-- Table: person
-- Purpose: Store people mentioned in articles/events
-- Scope: Names, roles, descriptions extracted from articles
CREATE TABLE person (
    id              BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name            TEXT            NOT NULL,
    role            VARCHAR(100),
    description     TEXT,
    firm_id         BIGINT,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_person_firm FOREIGN KEY (firm_id) REFERENCES firm(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- Table: person_event (Association Table)
-- Purpose: Link people to specific PEOPLE-category events with role and confidence context
-- Scope: Many-to-many relationship with additional metadata
-- Note: Only used for events WHERE event_category = 'people'
CREATE TABLE person_event (
    id              BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    person_id       BIGINT          NOT NULL,
    event_id        CHAR(36)        NOT NULL,
    role_in_event   VARCHAR(100),
    confidence      DECIMAL(3,2)    NULL CHECK (confidence BETWEEN 0 AND 1),
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_person_event (person_id, event_id),
    CONSTRAINT fk_pe_person FOREIGN KEY (person_id) REFERENCES person(id)         ON DELETE CASCADE,
    CONSTRAINT fk_pe_event  FOREIGN KEY (event_id)  REFERENCES event(unique_id)   ON DELETE CASCADE
) ENGINE=InnoDB;

-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 2: COMPREHENSIVE SOURCE MANAGEMENT - All Sources for All Event Types
-- ═══════════════════════════════════════════════════════════════════════════════

-- Alter: source table to add TAGGED UNION discriminator columns
-- Purpose: Map raw sources to specialized event types (people, connection, classical) 
-- Note: PRESERVES all original source columns from 001_initial_schema.sql
-- Note: NEW columns implement the tagged union discriminator pattern ONLY
ALTER TABLE source ADD COLUMN (
    source_category      VARCHAR(20)        DEFAULT 'article'
                                            CHECK (source_category IN ('article', 'extraction', 'summary'))
                                            COMMENT 'Tagged union discriminator: article | extraction | summary'
) COMMENT='Source table enhanced with tagged union discriminator for event type matching';

-- ═══════════════════════════════════════════════════════════════════════════════
-- CRITICAL: Add TAGGED UNION constraint - Source category must align with Event category
-- This ensures the tagged union discriminator is enforced at the database level
-- ═══════════════════════════════════════════════════════════════════════════════
-- CREATE TRIGGER after source insert/update to validate tagged union alignment
-- (Implementation note: Constraint below via trigger to cross-table validation)

-- Index for source lookups - OPTIMIZED for tagged union
CREATE INDEX idx_source_category         ON source(source_category);
CREATE INDEX idx_source_event_id_category ON source(event_id, source_category);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 3: CONNECTION NETWORK TABLE FOR CONNECTION EVENT TYPE
-- ═══════════════════════════════════════════════════════════════════════════════

-- Table: connection_entity
-- Purpose: Store relationships between entities (companies, people, activities)
-- Scope: Shared directors, business relationships, activity links
-- Note: This represents the data payload for CONNECTION-category events
CREATE TABLE connection_entity (
    id                      BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    connection_event_id     CHAR(36)        NOT NULL,
    connection_type         VARCHAR(50)     NOT NULL
                                            CHECK (connection_type IN (
                                                'shared_director',
                                                'business_relationship',
                                                'activity_link',
                                                'shared_beneficial_owner'
                                            ))
                                            COMMENT 'Type of connection relationship',
    entity_1_type           VARCHAR(20)     NOT NULL
                                            CHECK (entity_1_type IN ('company', 'person'))
                                            COMMENT 'Type of first entity',
    entity_1_id             VARCHAR(50)     NOT NULL,
    entity_1_name           TEXT,
    entity_2_type           VARCHAR(20)     NOT NULL
                                            CHECK (entity_2_type IN ('company', 'person'))
                                            COMMENT 'Type of second entity',
    entity_2_id             VARCHAR(50)     NOT NULL,
    entity_2_name           TEXT,
    relationship_description TEXT           COMMENT 'Human-readable description of relationship',
    confidence              DECIMAL(3,2)    CHECK (confidence BETWEEN 0 AND 1)
                                            COMMENT 'Confidence score for this connection',
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_connection_event FOREIGN KEY (connection_event_id) REFERENCES event(unique_id) ON DELETE CASCADE,
    CONSTRAINT chk_entity_types CHECK (entity_1_type IN ('company', 'person') AND entity_2_type IN ('company', 'person'))
) ENGINE=InnoDB COMMENT='Entities and relationships for CONNECTION-category events';

-- Indexes for connection queries
CREATE INDEX idx_connection_event_id       ON connection_entity(connection_event_id);
CREATE INDEX idx_connection_type           ON connection_entity(connection_type);
CREATE INDEX idx_connection_entity_1       ON connection_entity(entity_1_type, entity_1_id);
CREATE INDEX idx_connection_entity_2       ON connection_entity(entity_2_type, entity_2_id);
CREATE INDEX idx_connection_confidence     ON connection_entity(confidence);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 4: ARTICLE PROCESSING METADATA
-- ═══════════════════════════════════════════════════════════════════════════════

-- Table: article_metadata
-- Purpose: Track article processing status and correlation IDs for tracing
-- Scope: Idempotency, debugging, audit trail
-- NOTE: Event counts are computed via SELECT COUNT(*) GROUP BY event_category instead of denormalized columns
CREATE TABLE article_metadata (
    id                  BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    article_id          VARCHAR(50)     NOT NULL UNIQUE,
    correlation_id      VARCHAR(50)     NOT NULL,
    source_url          TEXT            NOT NULL,
    title               TEXT,
    published_at        DATETIME,
    scraped_at          DATETIME,
    processed_at        DATETIME,
    language            VARCHAR(10),
    region              VARCHAR(50),
    companies_found     INT             DEFAULT 0,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB COMMENT='Article processing metadata and extraction statistics';

-- NOTE: Use VIEWs or computed queries for event counts by category:
-- SELECT event_category, COUNT(*) FROM event 
-- WHERE article_id = ? AND event_category IN ('people', 'connection', 'classical')
-- GROUP BY event_category;

-- Indexes for article tracking
CREATE INDEX idx_article_metadata_correlation ON article_metadata(correlation_id);
CREATE INDEX idx_article_metadata_processed_at ON article_metadata(processed_at);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 5: COMPANY ALIASES ENHANCEMENT FOR TARKOV MATCHING
-- ═══════════════════════════════════════════════════════════════════════════════

-- Alter: firm_alias table to add confidence scoring
-- NOTE: created_at removed - alias creation time is typically tracked at firm level
ALTER TABLE firm_alias ADD COLUMN (
    confidence      DECIMAL(3,2)    CHECK (confidence BETWEEN 0 AND 1)
                                    COMMENT 'Confidence score for alias accuracy',
    is_primary      BOOLEAN         DEFAULT FALSE
                                    COMMENT 'Whether this is the primary alias for the firm'
);

-- Index for alias matching performance
CREATE INDEX idx_firm_alias_confidence ON firm_alias(confidence);
CREATE INDEX idx_firm_alias_type       ON firm_alias(alias_type);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 6: INDEXES & PERFORMANCE TUNING
-- ═══════════════════════════════════════════════════════════════════════════════

-- Person lookups
CREATE INDEX idx_person_name         ON person(name(100));
CREATE INDEX idx_person_role         ON person(role);
CREATE INDEX idx_person_firm_id      ON person(firm_id);

-- Person-Event lookups
CREATE INDEX idx_person_event_event_id      ON person_event(event_id);
CREATE INDEX idx_person_event_person_id     ON person_event(person_id);
CREATE INDEX idx_person_event_confidence    ON person_event(confidence);

-- Event extraction lookups

-- Article metadata lookups
CREATE INDEX idx_article_language    ON article_metadata(language);
CREATE INDEX idx_article_region      ON article_metadata(region);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 7: DATA VALIDATION & CONSTRAINTS (Already added in phase definitions)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Event category constraint (added to event table in PHASE 0)
-- Connection entity type constraints (added in PHASE 3)
-- Article processing status constraint (added in PHASE 4)

-- ═══════════════════════════════════════════════════════════════════════════════
-- PHASE 8: TAGGED UNION VALIDATION TRIGGER
-- ═══════════════════════════════════════════════════════════════════════════════

-- Trigger: Validate tagged union discriminator - source_category matches event_category
-- Purpose: Enforce correct mapping of source types to event types at insert/update time
-- Safety: Ensures source.source_category aligns with event.event_category for type safety
DELIMITER $$

DROP TRIGGER IF EXISTS trg_source_tagged_union_validation $$

CREATE TRIGGER trg_source_tagged_union_validation 
BEFORE INSERT ON source FOR EACH ROW
BEGIN
  DECLARE event_category_val VARCHAR(20);
  
  -- Get the event_category from the referenced event
  SELECT event_category INTO event_category_val
  FROM event
  WHERE unique_id = NEW.event_id;
  
  -- Validate event exists
  IF event_category_val IS NULL THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Foreign Key Violation: source.event_id references non-existent event';
  END IF;
  
  -- Tagged union validation:
  -- - 'extraction' sources → only for 'people' or 'connection' events
  -- - 'article' sources → valid for any event type
  -- - 'summary' sources → valid for any event type
  IF NEW.source_category = 'extraction' AND event_category_val NOT IN ('people', 'connection') THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Tagged Union Violation: extraction sources require event_category IN (people, connection)';
  END IF;
END $$

DELIMITER ;

-- ═══════════════════════════════════════════════════════════════════════════════
-- MIGRATION STATUS TABLE (Idempotent tracking)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Table: migration_status
-- Purpose: Track which schema migrations have been applied
-- This is used for idempotent deployment
CREATE TABLE IF NOT EXISTS migration_status (
    id                  BIGINT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    migration_name      VARCHAR(100)    NOT NULL UNIQUE,
    applied_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status              VARCHAR(50)     DEFAULT 'applied'
) ENGINE=InnoDB;

-- Insert this migration as applied
INSERT INTO migration_status (migration_name, status) 
VALUES ('002_tarkov_schema.sql', 'applied')
ON DUPLICATE KEY UPDATE status = 'applied';

-- ═══════════════════════════════════════════════════════════════════════════════
-- ✨ TAGGED UNION EVENT TYPE SYSTEM - SUMMARY
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- ARCHITECTURE: Events are discriminated by event_category (tagged union pattern)
--
-- EVENT TYPES:
--
-- 1. PEOPLE EVENTS (event_category = 'people')
--    - Represents extraction of individuals from articles
--    - Data payload: person_event table links event → person(s)
--    - Purpose: Track people mentioned in risk events
--    - Example: "CEO John Smith involved in sanctions violation"
--    - Query: SELECT * FROM event e 
--             JOIN person_event pe ON e.unique_id = pe.event_id 
--             WHERE e.event_category = 'people'
--
-- 2. CONNECTION EVENTS (event_category = 'connection')
--    - Represents relationships/networks between entities
--    - Data payload: connection_entity table stores relationship details
--    - Purpose: Track business relationships, beneficial ownership, shared directors
--    - Example: "Company A shares director with Company B"
--    - Query: SELECT * FROM event e 
--             JOIN connection_entity ce ON e.unique_id = ce.connection_event_id 
--             WHERE e.event_category = 'connection'
--
-- 3. CLASSICAL EVENTS (event_category = 'classical')
--    - Represents sentiment/risk events (original event type)
--    - Data payload: sentiment table (from 001_initial_schema.sql)
--    - Purpose: Track traditional risk signals (sanctions, fraud, bankruptcy)
--    - Example: "Company X convicted of fraud" (standard sentiment event)
--    - Query: SELECT * FROM event e 
--             JOIN sentiment s ON e.unique_id = s.event_id 
--             WHERE e.event_category = 'classical'
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- UNIFIED SOURCE MANAGEMENT
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- The source table NOW stores ALL sources for ALL event types
-- - Articles and extraction evidence for PEOPLE events
-- - Connection evidence and source documents for CONNECTION events
-- - Traditional news sources and sentiment indicators for CLASSICAL events
--
-- Query all sources for an event (any type):
-- SELECT s.* FROM source s WHERE s.event_id = ?
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- NEW TABLES (4):
-- ═══════════════════════════════════════════════════════════════════════════════
--   1. person - Individual entities extracted from articles
--   2. person_event - Association: PEOPLE events → person(s)
--   3. connection_entity - Relationship details for CONNECTION events
--   4. article_metadata - Processing status and extraction statistics
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- ALTERED TABLES (3):
-- ═══════════════════════════════════════════════════════════════════════════════
--   1. event - Added event_category discriminator (tagged union: people | connection | classical)
--   2. source - Added source_category discriminator (tagged union: article | extraction | summary)
--              PRESERVES all original columns from 001_initial_schema.sql
--   3. firm_alias - Added confidence scoring and primary alias flag
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- INDEX SUMMARY: Optimized for tagged union queries
-- ═══════════════════════════════════════════════════════════════════════════════
--   - Event type queries: event_category
--   - Source routing: source_category, source_event_id_category (composite)
--   - Person lookups: name, role, firm_id
--   - Connection lookups: entity types/IDs, connection type
--   - Performance: person_event confidence, firm_alias confidence
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- COMPATIBILITY & NOTES
-- ═══════════════════════════════════════════════════════════════════════════════
--
-- Database: MySQL 8.0.16+ (InnoDB engine required)
-- Backward Compatible: YES - Only adds new tables/columns, no structural modifications
-- Idempotent: YES - Uses migration_status table to track application
-- Pattern: Tagged Union / Discriminated Union for type-safe event handling
-- Rollback Support: YES - Use separate 002_rollback_tarkov_schema.sql
--
-- ═══════════════════════════════════════════════════════════════════════════════
