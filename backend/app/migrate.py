"""Apply database migrations in order. Run from backend/: python -m app.migrate

Applied files are recorded in schema_migrations, so a rerun only applies new files.
All pending files run in one transaction: any failure rolls everything back.

001_eight_field_dataset.sql is the superseded snapshot-era migration and is
intentionally not listed. A fresh database starts from database/equipment.sql.
Every listed file is re-runnable, so a database set up before schema_migrations
existed is safe: the first run re-checks each file and records it.
"""
from pathlib import Path
import psycopg
from .database import get_connection

MIGRATION_DIR = Path(__file__).resolve().parents[2] / 'database' / 'migrations'
MIGRATIONS = [
    '002_calculated_metrics.sql',
    '003_equipment_metadata.sql',
    '004_maintenance_workflow.sql',
    '005_authentication.sql',
    '006_review_workflow.sql',
]


def migrate():
    applied = []
    with get_connection() as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS schema_migrations ('
                           'filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())')
        done = {row['filename'] for row in connection.execute('SELECT filename FROM schema_migrations').fetchall()}
        for name in MIGRATIONS:
            if name in done:
                continue
            connection.execute((MIGRATION_DIR / name).read_text(encoding='utf-8'), prepare=False)
            connection.execute('INSERT INTO schema_migrations(filename) VALUES (%s)', (name,))
            applied.append(name)
    if applied:
        print('Applied and recorded: ' + ', '.join(applied) + '. Existing records preserved.')
    else:
        print('Database is up to date. No migrations applied.')


if __name__ == '__main__':
    try:
        migrate()
    except (psycopg.Error, RuntimeError) as error:
        # Migration SQL messages are safe only when explicitly raised by these files.
        if isinstance(error, psycopg.errors.RaiseException):
            print(error.diag.message_primary)
        else:
            print(f'Migration rolled back ({type(error).__name__}). Check connection, schema, and constraints.')
        raise SystemExit(1)
