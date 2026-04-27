#!/bin/bash
set -e

# Extract credentials from NEO4J_AUTH (format: username/password)
if [ -n "$NEO4J_AUTH" ] && [ "$NEO4J_AUTH" != "none" ]; then
    _NEO4J_USER="${NEO4J_AUTH%%/*}"
    _NEO4J_PASS="${NEO4J_AUTH#*/}"
else
    _NEO4J_USER="neo4j"
    _NEO4J_PASS="neo4j"
fi

# Start Neo4j using the official entrypoint in background
/startup/docker-entrypoint.sh neo4j &
_NEO4J_PID=$!

echo "[init] Waiting for Neo4j bolt on localhost:7687..."
MAX_WAIT=120
ELAPSED=0
until cypher-shell -a "bolt://localhost:7687" -u "$_NEO4J_USER" -p "$_NEO4J_PASS" "RETURN 1;" > /dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
        echo "[init] Timed out waiting for Neo4j"
        exit 1
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done
echo "[init] Neo4j is ready."

MIGRATIONS_DIR="/var/lib/neo4j/migrations"
MIGRATION_COUNT=$(find "$MIGRATIONS_DIR" -maxdepth 1 -name "*.cypher" 2>/dev/null | wc -l)

if [ "$MIGRATION_COUNT" -eq 0 ]; then
    echo "[init] No migration files found in $MIGRATIONS_DIR"
else
    echo "[init] Found $MIGRATION_COUNT migration(s). Running..."
    for f in $(find "$MIGRATIONS_DIR" -maxdepth 1 -name "*.cypher" | sort); do
        echo "[init] Running: $(basename "$f")"
        if cypher-shell -a "bolt://localhost:7687" -u "$_NEO4J_USER" -p "$_NEO4J_PASS" -f "$f"; then
            echo "[init] ✓ $(basename "$f")"
        else
            echo "[init] ✗ $(basename "$f") FAILED"
            exit 1
        fi
    done
    echo "[init] All migrations complete."
fi

wait $_NEO4J_PID
