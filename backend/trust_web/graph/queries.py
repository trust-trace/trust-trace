"""Cypher query constants for TrustWeb graph operations."""

# ── Node ensure (MERGE by Postgres ID) ────────────────────────────────────

MERGE_COMPANY_NODE = """\
MERGE (c:Company {company_id: $company_id})
SET c.name = $name
"""

MERGE_PERSON_NODE = """\
MERGE (p:Person {person_id: $person_id})
SET p.name = $name
"""

MERGE_EVENT_NODE = """\
MERGE (e:Event {event_id: $event_id})
SET e.title = $title, e.risk_level = $risk_level, e.event_type = $event_type
"""

# ── CONNECTION edge (between any two entity types) ─────────────────────────
# Entity nodes are matched by their type-specific ID property.
# The caller substitutes label_a/label_b and id_prop_a/id_prop_b before use.

MERGE_CONNECTION_EDGE = """\
MATCH (a:{label_a} {{{id_prop_a}: $entity_1_id}})
MATCH (b:{label_b} {{{id_prop_b}: $entity_2_id}})
MERGE (a)-[r:CONNECTION {{source_event_id: $event_id}}]->(b)
SET r.type = $connection_type,
    r.intensity = $intensity,
    r.llm_description = $llm_description,
    r.source_url = $source_url,
    r.source_title = $source_title,
    r.scored_at = datetime()
"""

# ── ABOUT edge (Company → Event) ──────────────────────────────────────────

MERGE_ABOUT_EDGE = """\
MATCH (c:Company {company_id: $firm_id})
MATCH (e:Event {event_id: $event_id})
MERGE (c)-[:ABOUT]->(e)
"""

# ── INVOLVED_IN edge (Person → Event) ─────────────────────────────────────

MERGE_INVOLVED_IN_EDGE = """\
MATCH (p:Person {person_id: $person_id})
MATCH (e:Event {event_id: $event_id})
MERGE (p)-[r:INVOLVED_IN]->(e)
SET r.role_in_event = $role, r.confidence = $confidence
"""

# ── AFFILIATED_WITH edge (Company → Person) ────────────────────────────────

MERGE_AFFILIATED_WITH_EDGE = """\
MATCH (c:Company {company_id: $firm_id})
MATCH (p:Person {person_id: $person_id})
MERGE (c)-[r:AFFILIATED_WITH]->(p)
SET r.role = $role
"""

# ── Subgraph extraction ───────────────────────────────────────────────────

EXTRACT_SUBGRAPH = """\
MATCH path = (root:Company {{company_id: $firm_id}})-[*1..{max_depth}]-(neighbor)
WITH root, neighbor, relationships(path) AS rels, nodes(path) AS path_nodes, length(path) AS depth
RETURN DISTINCT
  neighbor,
  labels(neighbor) AS neighbor_labels,
  [r IN rels | {{
    type: type(r),
    intensity: r.intensity,
    conn_type: r.type,
    llm_description: r.llm_description,
    source_url: r.source_url,
    source_title: r.source_title,
    source_id: startNode(r).company_id,
    source_person_id: startNode(r).person_id,
    source_event_id_prop: startNode(r).event_id,
    target_id: endNode(r).company_id,
    target_person_id: endNode(r).person_id,
    target_event_id_prop: endNode(r).event_id
  }}] AS edge_info,
  depth
ORDER BY depth
"""

# ── Check if edge already has intensity scored ─────────────────────────────

CHECK_CONNECTION_SCORED = """\
MATCH (a)-[r:CONNECTION {source_event_id: $event_id}]->(b)
RETURN r.intensity IS NOT NULL AS scored
"""
