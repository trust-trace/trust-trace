# Self-contained PostgreSQL image with automatic migration loading
FROM postgres:16-alpine

# Set environment variables for PostgreSQL
ENV POSTGRES_USER=postgres \
    POSTGRES_PASSWORD=postgres \
    POSTGRES_DB=trusttrace

# Copy the initialization script
COPY db/init-db.sh /docker-entrypoint-initdb.d/99-run-migrations.sh

# Copy migrations folder
COPY db/migrations /db/migrations

# Make the initialization script executable
RUN chmod +x /docker-entrypoint-initdb.d/99-run-migrations.sh

# Expose PostgreSQL port
EXPOSE 5432

# Use the default entrypoint which will run scripts in /docker-entrypoint-initdb.d/
# This is built into the postgres image
