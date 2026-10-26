"""Run from backend/: python -m app.migrate. Uses the existing secure DB settings."""
from pathlib import Path
import psycopg
from .database import get_connection

MIGRATION = Path(__file__).resolve().parents[2] / 'database/migrations/001_eight_field_dataset.sql'


def migrate():
    with get_connection() as connection:
        connection.execute(MIGRATION.read_text(encoding='utf-8'), prepare=False)
    print('Eight-field dataset migration committed. Existing records and legacy columns preserved.')


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
