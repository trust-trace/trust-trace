# AML Scoring Pipeline

## Overview

The AML (Anti-Money Laundering) scoring system is a multi-stage pipeline that collects public information about companies, extracts relevant events, and produces a trust score timeline. The pipeline has three sequential stages followed by three parallelizable scoring modules.

---

## Stage 1: Rust-Based Scraper — Scuttle Crab

A Rust crawler that collects news and financial articles for downstream company scoring.

- **Language:** Rust
- **Purpose:** Discovery, fetching, extraction, normalization, and relevance tagging of articles
- **Output:** Normalized JSON payload per article (written to JSONL for MVP)
- **Key capabilities:**
  - RSS/Atom feed parsing and curated page discovery
  - HTML extraction with source-specific selector overrides
  - URL deduplication via persistent seen-URL hash store
  - Company/ticker relevance tagging using a local reference dictionary
- **Detailed spec:** `rust/SCUTTLE_CRAB.md`

---

## Stage 2: Event Extraction — Tarkov

The first parsing module. Receives raw articles from Stage 1 and extracts structured data.

- **Integration:** Connected to the PostgreSQL database
- **Responsibilities:**
  - Find references to existing companies in the database, or create new company records
  - Identify events related to money laundering and fraud, then persist them to the database
  - Identify people related to those events and persist them to the database
- **Approach:** Supports both keyword-based search algorithms and LLM-powered extraction modules

---

## Stage 3: Main AML Scoring Pipeline

Triggered when sufficient information about a specific company has been collected. This stage orchestrates the final scoring.

- **Runtime:** Long-running Python classification process
- **Flow:**
  1. Invoke three external scoring modules (can run asynchronously in parallel)
  2. Collect the three scores
  3. Combine them using a weighted mathematical equation (weights are tunable)
  4. Produce a **score timeline**, not a single final score
- **Timeline scoring logic:**
  - Based on the company's age, generate multiple score snapshots across the company's lifetime
  - Example: a 10-year-old company should receive approximately 10 score snapshots
  - All timeline scores are persisted to the database

---

## External Scoring Modules

These three modules are invoked by Stage 3 and can run asynchronously in parallel. Each returns a numeric score to the main pipeline.

### Module A: Event Classifier

- **Input:** All events associated with the company
- **Method:** Analyzes the impact of each event; heavily LLM-based
- **Output:** A single aggregate score
- **Side effects:**
  - Each event has a specific date, enabling direct timeline placement
  - Writes detailed human-readable event analysis to the database (displayed on the frontend)

### Module B: NSA — Name Scoring Adjudicator

- **Trigger condition:** Only runs if there is a list of people involved with the company or its events
- **Method:** Performs background checks on each person; LLM-based with external MCP tool integrations for background verification
- **Output:** An average score across all checked individuals
- **Side effects:**
  - Writes a per-person analysis description to the database

### Module C: TrustWeb — Graph-Based Correlation Engine

> **This is the unique selling point of the project.**

- **Method:** Uses a graph database to find correlations between fraud activity across companies
- **Key behaviors:**
  - Stores edges representing relationships between companies
  - Classifies connection intensity for each edge
  - Maximum traversal depth: 2
- **Output:** An averaged score fed back to the main AML scoring pipeline
- **Frontend integration:** The graph is displayed as an advanced interactive visualization on the frontend

---

## Architecture Diagram (Text)

```
[Stage 1: Scuttle Crab]         Rust scraper → raw articles (JSONL)
        ↓
[Stage 2: Tarkov]               Event extraction → companies, events, people (PostgreSQL)
        ↓
[Stage 3: AML Scoring Pipeline] Python orchestrator (triggered per company)
        ├── [Module A: Event Classifier]    → event impact score
        ├── [Module B: NSA]                 → people background score
        └── [Module C: TrustWeb]            → graph correlation score
        ↓
   Weighted combination → score timeline (PostgreSQL)
```
