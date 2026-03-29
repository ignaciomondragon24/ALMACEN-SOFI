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

# Flush business data if requested (set FLUSH_ON_DEPLOY=true in Railway env vars, then remove it after deploy)
if [ "$FLUSH_ON_DEPLOY" = "true" ]; then
    echo "*** FLUSH_ON_DEPLOY detected — wiping all business data (keeping users)... ***"
    python manage.py flush_data --yes || echo "WARNING: flush_data failed, continuing..."
    echo "*** Flush complete. REMOVE the FLUSH_ON_DEPLOY env var now to prevent re-flush. ***"
fi

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
