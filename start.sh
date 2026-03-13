#!/bin/bash

echo "=== CHE GOLOSO - Starting ==="
echo "PORT: ${PORT:-8000}"
echo "DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'YES' || echo 'NO')"
echo "DEBUG: ${DEBUG:-not set}"
echo "ALLOWED_HOSTS: ${ALLOWED_HOSTS:-not set}"
echo "RAILWAY_PUBLIC_DOMAIN: ${RAILWAY_PUBLIC_DOMAIN:-not set}"

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput || echo "WARNING: Migration failed, continuing..."

# Setup initial data
echo "Setting up initial data..."
python manage.py setup_initial_data || echo "WARNING: setup_initial_data failed, continuing..."

# Load kiosko products (idempotente - usa get_or_create, seguro de correr siempre)
echo "Loading kiosko products..."
python manage.py load_kiosko_products || echo "WARNING: load_kiosko_products failed, continuing..."

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || echo "WARNING: collectstatic failed, continuing..."

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
    --error-logfile - \
    --preload
