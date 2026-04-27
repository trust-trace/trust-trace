// Migration: 001_initial_schema.cypher
// Description: Neo4j schema for trust-trace (graph contains connections only; primary data stored in Postgres)
//
// Graph model:
//
// NODES
//   (:Company)         — company/firm node (mirrors Postgres firm.id as company_id)
//   (:Person)          — person node (mirrors Postgres person.id as person_id)
//   (:Event)           — event node (mirrors Postgres event.unique_id as event_id)
//
// RELATIONSHIPS
//   (:Company)-[:ABOUT]->(:Event)
//   (:Person)-[:INVOLVED_IN {role_in_event, confidence}]->(:Event)
//   (:Company)-[:AFFILIATED_WITH {role}]->(:Person)
//
// Connection relationships (typed + intensity) between Company and Person nodes — these represent graph-only connection edges
//   (:Company|:Person)-[:CONNECTION {type: 'SHARED_DIRECTOR'|'BUSINESS_RELATIONSHIP'|'ACTIVITY_LINK'|'SHARED_BENEFICIAL_OWNER', intensity: float, description: string, source_event_id: string}]->(:Company|:Person)
//
// Notes:
// - The main canonical data remains in Postgres. Neo4j stores lightweight nodes with foreign-key style properties pointing to Postgres records
//   to allow fast graph traversals and connection analytics.
// - Node properties use postgres ids: company_id (int), person_id (int), event_id (string/uuid)
//

// ─────────────────────────────────────────
// Constraints
// ─────────────────────────────────────────

CREATE CONSTRAINT company_id_unique IF NOT EXISTS
  FOR (c:Company) REQUIRE c.company_id IS UNIQUE;

CREATE CONSTRAINT person_id_unique IF NOT EXISTS
  FOR (p:Person) REQUIRE p.person_id IS UNIQUE;

CREATE CONSTRAINT event_id_unique IF NOT EXISTS
  FOR (e:Event) REQUIRE e.event_id IS UNIQUE;

// ─────────────────────────────────────────
// Indexes
// ─────────────────────────────────────────

CREATE INDEX company_name_idx IF NOT EXISTS
  FOR (c:Company) ON (c.full_name);

CREATE INDEX person_name_idx IF NOT EXISTS
  FOR (p:Person) ON (p.name);

CREATE INDEX event_type_idx IF NOT EXISTS
  FOR (e:Event) ON (e.event_type);

CREATE INDEX connection_type_idx IF NOT EXISTS
  FOR ()-[r:CONNECTION]-() ON (r.type);

CREATE INDEX connection_intensity_idx IF NOT EXISTS
  FOR ()-[r:CONNECTION]-() ON (r.intensity);
