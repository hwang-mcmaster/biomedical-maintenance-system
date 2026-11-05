"""Run from backend/: python -m app.migrate. Uses the existing secure DB settings."""
from pathlib import Path
import psycopg
from .database import get_connection

MIGRATION_DIR = Path(__file__).resolve().parents[2] / 'database/migrations'
MIGRATIONS = [MIGRATION_DIR / name for name in ['002_calculated_metrics.sql', '003_equipment_metadata.sql']]


def migrate():
    with get_connection() as connection:
        for migration in MIGRATIONS:
            connection.execute(migration.read_text(encoding='utf-8'), prepare=False)
    print('Calculated metrics and equipment metadata migrations committed. Existing records preserved.')


if __name__ == '__main__':
    try:
        migrate()
    except (psycopg.Error, RuntimeError) as error:
        # Migration SQL messages are safe only when explicitly raised by this file.
        if isinstance(error, psycopg.errors.RaiseException):
            print(error.diag.message_primary)
        else:
            print(f'Migration rolled back ({type(error).__name__}). Check connection, schema, and constraints.')
        raise SystemExit(1)
