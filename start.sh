#!/bin/bash

echo "=== CHE GOLOSO - Starting ==="
echo "PORT: ${PORT:-8000}"
echo "DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'YES' || echo 'NO')"
echo "DEBUG: ${DEBUG:-not set}"
echo "ALLOWED_HOSTS: ${ALLOWED_HOSTS:-not set}"
echo "RAILWAY_PUBLIC_DOMAIN: ${RAILWAY_PUBLIC_DOMAIN:-not set}"

# Fix directo de tabla M2M rota (antes de migrations, idempotente)
echo "Checking granel M2M table..."
python -c "
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'superrecord.settings')
import django
django.setup()
from django.db import connection
if connection.vendor != 'postgresql':
    print('  SQLite: skip')
    sys.exit(0)
with connection.cursor() as c:
    # Verificar si las tablas base existen
    c.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='granel_caramelera')\")
    if not c.fetchone()[0]:
        print('  granel_caramelera no existe aun, skip')
        sys.exit(0)
    c.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='stocks_product')\")
    if not c.fetchone()[0]:
        print('  stocks_product no existe aun, skip')
        sys.exit(0)
    # Ver columnas actuales
    c.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='granel_caramelera_productos_autorizados' ORDER BY ordinal_position\")
    cols = [r[0] for r in c.fetchall()]
    print(f'  Columnas M2M: {cols}')
    if 'product_id' in cols:
        print('  product_id OK, no se necesita fix')
        sys.exit(0)
    print('  FIXING: drop + recreate M2M table...')
    c.execute('DROP TABLE IF EXISTS granel_caramelera_productos_autorizados CASCADE')
    c.execute(\"\"\"
        CREATE TABLE granel_caramelera_productos_autorizados (
            id BIGSERIAL PRIMARY KEY,
            caramelera_id BIGINT NOT NULL REFERENCES granel_caramelera(id) DEFERRABLE INITIALLY DEFERRED,
            product_id BIGINT NOT NULL REFERENCES stocks_product(id) DEFERRABLE INITIALLY DEFERRED,
            CONSTRAINT granel_car_pa_uniq UNIQUE (caramelera_id, product_id)
        )
    \"\"\")
    c.execute('CREATE INDEX ON granel_caramelera_productos_autorizados(caramelera_id)')
    c.execute('CREATE INDEX ON granel_caramelera_productos_autorizados(product_id)')
    print('  M2M table FIXED OK')
" 2>&1 || echo "WARNING: M2M fix skipped"

# Pre-flight: ensure mercadopago migration state is consistent
echo "Checking mercadopago migration state..."
python -c "
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'superrecord.settings')
import django; django.setup()
from django.db import connection
if connection.vendor != 'postgresql':
    sys.exit(0)
with connection.cursor() as c:
    # Check if migration 0003 is recorded as applied but 0004 is not
    c.execute(\"SELECT name FROM django_migrations WHERE app='mercadopago' ORDER BY id\")
    applied = [r[0] for r in c.fetchall()]
    print(f'  Applied mercadopago migrations: {applied}')
    if '0003_remove_external_pos_id' in applied and '0004_add_qr_flow_and_optional_device' not in applied:
        print('  0003 applied but 0004 missing — will let migrate handle it')
    if '0003_remove_external_pos_id' not in applied:
        print('  0003 not yet applied — will run during migrate')
" 2>&1 || echo "WARNING: migration pre-check skipped"

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput || echo "WARNING: Migration failed, continuing..."

# Defensive: ensure mercadopago_mpcredentials.external_pos_id and
# mercadopago_paymentintent.payment_flow exist even if migration 0004 didn't apply.
# This unblocks production immediately if Django migrations got stuck for any reason.
echo "Verifying mercadopago QR fields..."
python -c "
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'superrecord.settings')
import django; django.setup()
from django.db import connection
if connection.vendor != 'postgresql':
    print('  SQLite: skip')
    sys.exit(0)
with connection.cursor() as c:
    # Skip if base table doesn't exist yet
    c.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='mercadopago_mpcredentials')\")
    if not c.fetchone()[0]:
        print('  mercadopago_mpcredentials no existe aun, skip')
        sys.exit(0)

    # 1) external_pos_id en mpcredentials
    c.execute(\"\"\"
        SELECT 1 FROM information_schema.columns
        WHERE table_name='mercadopago_mpcredentials' AND column_name='external_pos_id'
    \"\"\")
    if not c.fetchone():
        print('  Adding mpcredentials.external_pos_id ...')
        c.execute(\"\"\"
            ALTER TABLE mercadopago_mpcredentials
            ADD COLUMN external_pos_id varchar(100) NOT NULL DEFAULT ''
        \"\"\")
        print('  external_pos_id added OK')
    else:
        print('  external_pos_id OK')

    # 2) payment_flow en paymentintent
    c.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='mercadopago_paymentintent')\")
    if c.fetchone()[0]:
        c.execute(\"\"\"
            SELECT 1 FROM information_schema.columns
            WHERE table_name='mercadopago_paymentintent' AND column_name='payment_flow'
        \"\"\")
        if not c.fetchone():
            print('  Adding paymentintent.payment_flow ...')
            c.execute(\"\"\"
                ALTER TABLE mercadopago_paymentintent
                ADD COLUMN payment_flow varchar(20) NOT NULL DEFAULT 'qr'
            \"\"\")
            print('  payment_flow added OK')
        else:
            print('  payment_flow OK')

        # 3) device puede ser NULL (QR no requiere device)
        c.execute(\"\"\"
            SELECT is_nullable FROM information_schema.columns
            WHERE table_name='mercadopago_paymentintent' AND column_name='device_id'
        \"\"\")
        row = c.fetchone()
        if row and row[0] == 'NO':
            print('  Making paymentintent.device_id nullable ...')
            c.execute(\"ALTER TABLE mercadopago_paymentintent ALTER COLUMN device_id DROP NOT NULL\")
            print('  device_id is now nullable OK')
        else:
            print('  device_id nullable OK')

    # 4) Marcar migración 0004 como aplicada para que Django no intente correrla otra vez
    c.execute(\"SELECT 1 FROM django_migrations WHERE app='mercadopago' AND name='0004_add_qr_flow_and_optional_device'\")
    if not c.fetchone():
        c.execute(\"\"\"
            INSERT INTO django_migrations (app, name, applied)
            VALUES ('mercadopago', '0004_add_qr_flow_and_optional_device', NOW())
        \"\"\")
        print('  Marked migration 0004 as applied')
" 2>&1 || echo "WARNING: mercadopago field repair skipped"

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
