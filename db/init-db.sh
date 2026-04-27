#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h localhost -U "$POSTGRES_USER" > /dev/null 2>&1; do
  sleep 1
done

echo "PostgreSQL is ready!"

# Create database if it doesn't exist
psql -U "$POSTGRES_USER" -h localhost << EOF
SELECT 'CREATE DATABASE "$POSTGRES_DB"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$POSTGRES_DB')\gexec
EOF

echo "Database '$POSTGRES_DB' is ready."

# Run all SQL migrations in /db/migrations in alphabetical order
MIGRATIONS_DIR="/db/migrations"

if [ ! -d "$MIGRATIONS_DIR" ]; then
  echo "Migrations directory not found at $MIGRATIONS_DIR"
  exit 0
fi

# Count migration files
MIGRATION_COUNT=$(find "$MIGRATIONS_DIR" -type f -name "*.sql" | wc -l)

if [ "$MIGRATION_COUNT" -eq 0 ]; then
  echo "No migration files found in $MIGRATIONS_DIR"
  exit 0
fi

echo "Found $MIGRATION_COUNT migration file(s). Running migrations..."

# Execute each SQL file in alphabetical order
for migration_file in $(find "$MIGRATIONS_DIR" -type f -name "*.sql" | sort); do
  echo "Running migration: $(basename "$migration_file")"
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -h localhost < "$migration_file"
  if [ $? -eq 0 ]; then
    echo "✓ Migration completed: $(basename "$migration_file")"
  else
    echo "✗ Migration failed: $(basename "$migration_file")"
    exit 1
  fi
done

echo "All migrations completed successfully!"
