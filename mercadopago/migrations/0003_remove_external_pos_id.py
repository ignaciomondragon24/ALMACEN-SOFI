# Generated migration to safely remove external_pos_id field

from django.db import migrations


class Migration(migrations.Migration):
    """
    This migration safely removes the external_pos_id field if it exists.
    It handles the case where the field was never created in production.
    """

    dependencies = [
        ('mercadopago', '0002_alter_mpcredentials_id_alter_pointdevice_id_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            # Forward: remove column if exists
            sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'mercadopago_pointdevice'
                    AND column_name = 'external_pos_id'
                ) THEN
                    ALTER TABLE mercadopago_pointdevice DROP COLUMN external_pos_id;
                END IF;
            END $$;
            """,
            # Reverse: add column back (optional, for rollback)
            reverse_sql="""
            ALTER TABLE mercadopago_pointdevice
            ADD COLUMN IF NOT EXISTS external_pos_id VARCHAR(100) DEFAULT '';
            """,
        ),
    ]
