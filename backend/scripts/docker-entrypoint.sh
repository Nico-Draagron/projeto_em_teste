#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! pg_isready -h ${DB_HOST:-postgres} -p ${DB_PORT:-5432} -U ${DB_USER:-weatherbiz}; do
  sleep 1
done

echo "PostgreSQL is ready!"

echo "Running migrations..."
alembic upgrade head

echo "Starting application..."
exec "$@"