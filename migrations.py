# migrations.py
# Lightweight additive migrations (no Alembic in this project).
#
# db.create_all() only creates MISSING TABLES — it will NOT add new columns to
# tables that already exist (e.g. the live `clients` / `orders` tables on Railway
# PostgreSQL). Adding columns to an existing table requires ALTER TABLE.
#
# migrate_fb_columns() is idempotent: it inspects each table's existing columns
# and issues `ALTER TABLE ... ADD COLUMN` only for the ones that are missing.
# Works on both SQLite (local dev) and PostgreSQL (Railway prod).

from sqlalchemy import inspect, text

# Desired columns per table: (column_name, type, default_or_None)
# Types are written in a dialect-neutral form; booleans are normalised per
# dialect below (SQLite stores 0/1, PostgreSQL uses FALSE/TRUE).
_FB_COLUMNS = {
    'clients': [
        ('facebook_page_token', 'VARCHAR(255)', None),
        ('facebook_page_id', 'VARCHAR(64)', None),
        ('facebook_page_name', 'VARCHAR(120)', None),
        ('fb_auto_message_enabled', 'BOOLEAN', 'false'),
        ('fb_message_template', 'TEXT', None),
        ('fb_message_delay', 'INTEGER', '4'),
    ],
    'orders': [
        ('platform', 'VARCHAR(20)', "'tiktok'"),
        ('buyer_psid', 'VARCHAR(64)', None),
        ('fb_comment_id', 'VARCHAR(64)', None),
        ('message_sent', 'BOOLEAN', 'false'),
        ('message_failed', 'BOOLEAN', 'false'),
    ],
}


def _render_default(default, dialect_name):
    """Render a default literal appropriately for the active dialect."""
    if default is None:
        return None
    if default in ('false', 'true'):
        if dialect_name == 'sqlite':
            return '0' if default == 'false' else '1'
        return default.upper()  # PostgreSQL: FALSE / TRUE
    return default


def migrate_fb_columns(db):
    """Add any missing Facebook Auto-Messenger columns to clients/orders.

    Safe to run on every boot. Existing rows are backfilled with the column
    default (so old orders become platform='tiktok', message flags False).
    """
    inspector = inspect(db.engine)
    dialect_name = db.engine.dialect.name
    existing_tables = set(inspector.get_table_names())
    added = []

    for table, columns in _FB_COLUMNS.items():
        # If the table doesn't exist yet, db.create_all() will build it from the
        # model with all columns already present — nothing to migrate here.
        if table not in existing_tables:
            continue

        existing_cols = {col['name'] for col in inspector.get_columns(table)}

        for name, coltype, default in columns:
            if name in existing_cols:
                continue

            ddl = f'ALTER TABLE {table} ADD COLUMN {name} {coltype}'
            rendered_default = _render_default(default, dialect_name)
            if rendered_default is not None:
                ddl += f' DEFAULT {rendered_default}'

            try:
                with db.engine.begin() as conn:
                    conn.execute(text(ddl))
                added.append(f'{table}.{name}')
            except Exception as e:
                # Don't crash boot on a migration hiccup; log and continue so the
                # TikTok pipeline stays up even if a single ALTER fails.
                print(f"⚠️  migrate_fb_columns: could not add {table}.{name}: {e}")

    if added:
        print(f"✅ migrate_fb_columns: added {len(added)} column(s): {', '.join(added)}")
    else:
        print("✅ migrate_fb_columns: schema already up to date")

    return added
