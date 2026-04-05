# Generated migration to safely remove external_pos_id field

from django.db import migrations


def remove_external_pos_id(apps, schema_editor):
    """Remove external_pos_id column if it exists."""
    from django.db import connection
    cursor = connection.cursor()
    # Check if column exists
    columns = [col.name for col in connection.introspection.get_table_description(cursor, 'mercadopago_pointdevice')]
    if 'external_pos_id' in columns:
        # SQLite doesn't support DROP COLUMN before 3.35, so we just skip
        # In production (PostgreSQL), this works fine
        try:
            cursor.execute('ALTER TABLE mercadopago_pointdevice DROP COLUMN external_pos_id')
        except Exception:
            pass  # Column doesn't exist or can't be dropped (old SQLite)


class Migration(migrations.Migration):

    dependencies = [
        ('mercadopago', '0002_alter_mpcredentials_id_alter_pointdevice_id_and_more'),
    ]

    operations = [
        migrations.RunPython(remove_external_pos_id, migrations.RunPython.noop),
    ]
