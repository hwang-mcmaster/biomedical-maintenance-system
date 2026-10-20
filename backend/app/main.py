from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import psycopg

from .database import get_connection
from .schemas import Equipment, EquipmentCreate

app = FastAPI(title='Biomedical Maintenance API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_methods=['GET', 'POST'], allow_headers=['Content-Type'],
)


@app.get('/api/health')
def health():
    return {'status': 'ok', 'message': 'Biomedical Maintenance API is running'}


def database_error():
    # Do not expose connection strings, credentials, or database internals.
    return HTTPException(503, 'Database unavailable. Check backend configuration, network access, and equipment table setup.')


@app.get('/api/equipment', response_model=list[Equipment])
def equipment():
    try:
        with get_connection() as connection:
            return connection.execute(
                'SELECT id, name, type, location, status FROM equipment ORDER BY id'
            ).fetchall()
    except (psycopg.Error, RuntimeError):
        raise database_error() from None


@app.post('/api/equipment', response_model=Equipment, status_code=201)
def create_equipment(device: EquipmentCreate):
    try:
        with get_connection() as connection:
            saved = connection.execute(
                '''INSERT INTO equipment (name, type, location, status)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, name, type, location, status''',
                (device.name, device.type, device.location, device.status),
            ).fetchone()
        return saved
    except (psycopg.Error, RuntimeError):
        raise database_error() from None
