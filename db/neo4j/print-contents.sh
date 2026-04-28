#!/bin/sh
set -eu

CONTAINER="${NEO4J_CONTAINER:-trust-trace-db}"
ADDRESS="${NEO4J_ADDRESS:-bolt://localhost:7687}"
USER="${NEO4J_USER:-neo4j}"
PASSWORD="${NEO4J_PASSWORD:-trusttrace}"
LIMIT="${NEO4J_DUMP_LIMIT:-100}"

run_query() {
  docker exec "$CONTAINER" cypher-shell -a "$ADDRESS" -u "$USER" -p "$PASSWORD" "$1"
}

printf 'Neo4j snapshot\n'
printf 'container: %s\n' "$CONTAINER"
printf 'address: %s\n\n' "$ADDRESS"

printf 'Counts\n'
run_query 'MATCH (n) OPTIONAL MATCH ()-[r]->() RETURN count(DISTINCT n) AS nodes, count(DISTINCT r) AS relationships;'

printf '\nNodes (limit %s)\n' "$LIMIT"
run_query "MATCH (n) RETURN id(n) AS node_id, labels(n) AS labels, properties(n) AS properties ORDER BY node_id LIMIT ${LIMIT};"

printf '\nRelationships (limit %s)\n' "$LIMIT"
run_query "MATCH (source)-[r]->(target) RETURN id(r) AS rel_id, labels(source) AS source_labels, properties(source) AS source_properties, type(r) AS rel_type, properties(r) AS rel_properties, labels(target) AS target_labels, properties(target) AS target_properties ORDER BY rel_id LIMIT ${LIMIT};"
