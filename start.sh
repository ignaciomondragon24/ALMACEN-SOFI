#!/bin/bash
set -e

echo "=== CHE GOLOSO - Starting ==="
echo "PORT: ${PORT:-8000}"
echo "DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'YES' || echo 'NO')"

# Run migrations with timeout (60s max)
echo "Running migrations..."
timeout 60 python manage.py migrate --noinput 2>&1 || echo "WARNING: Migration failed or timed out, continuing..."

# Setup initial data (non-blocking)
echo "Setting up initial data..."
timeout 30 python manage.py setup_initial_data 2>&1 || echo "WARNING: setup_initial_data failed, continuing..."

# Start gunicorn
echo "Starting gunicorn on port ${PORT:-8000}..."
exec gunicorn superrecord.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 2 \
    --threads 2 \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --timeout 120 \
    --log-file - \
    --access-logfile - \
    --error-logfile -
