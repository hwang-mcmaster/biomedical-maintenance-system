import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / '.env')


def get_connection():
    required = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_SSLROOTCERT']
    if any(not os.getenv(key) for key in required):
        raise RuntimeError('Database configuration is incomplete. Check backend/.env.')
    cert = Path(os.environ['DB_SSLROOTCERT'])
    if not cert.is_absolute():
        cert = BACKEND_DIR / cert
    if not cert.is_file():
        raise RuntimeError('Database CA certificate is missing. Check DB_SSLROOTCERT.')
    return psycopg.connect(
        host=os.environ['DB_HOST'], port=os.environ['DB_PORT'],
        dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'], sslmode='verify-full',
        sslrootcert=str(cert), connect_timeout=10, row_factory=dict_row,
    )
