import logging
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from . import repository
from .assessment import assess_equipment
from .database import get_connection
from .schemas import Assessment, Equipment, EquipmentCreate

logger = logging.getLogger(__name__)
app = FastAPI(title='Biomedical Maintenance API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Content-Type'],
)


@app.exception_handler(psycopg.Error)
async def database_exception(request, exc):
    from fastapi.responses import JSONResponse
    # Log the category only: exception text may contain connection details or input.
    logger.error('Database operation failed: %s', type(exc).__name__)
    if isinstance(exc, psycopg.errors.UniqueViolation):
        return JSONResponse(status_code=409, content={'detail': 'Asset tag or serial number already exists. Use unique values.'})
    if isinstance(exc, psycopg.errors.ForeignKeyViolation):
        return JSONResponse(status_code=409, content={'detail': 'This equipment is referenced by other records and cannot be deleted.'})
    return JSONResponse(status_code=503, content={'detail': 'Database unavailable. Check configuration, network access, and equipment table setup.'})


@app.exception_handler(RuntimeError)
async def configuration_exception(request, exc):
    from fastapi.responses import JSONResponse
    logger.error('Database configuration is incomplete or certificate is missing.')
    return JSONResponse(status_code=503, content={'detail': 'Database configuration is incomplete. Check backend/.env and its CA certificate path.'})


@app.get('/api/health')
def health():
    return {'status': 'ok', 'message': 'Biomedical Maintenance API is running'}


@app.get('/api/ready')
def ready():
    # Verify the expected columns as well as database connectivity.
    with get_connection() as connection:
        connection.execute(f'SELECT {repository.COLUMNS} FROM equipment LIMIT 0')
    return {'status': 'ok', 'message': 'Equipment database is ready'}


@app.get('/api/equipment', response_model=list[Equipment])
def equipment():
    return repository.list_equipment()


@app.get('/api/equipment/{equipment_id}', response_model=Equipment)
def equipment_details(equipment_id: UUID):
    record = repository.get_equipment(equipment_id)
    if record is None:
        raise HTTPException(404, 'Equipment not found.')
    return record


@app.post('/api/equipment', response_model=Equipment, status_code=201)
def create_equipment(device: EquipmentCreate):
    return repository.save_equipment(device)


@app.put('/api/equipment/{equipment_id}', response_model=Equipment)
def update_equipment(equipment_id: UUID, device: EquipmentCreate):
    record = repository.save_equipment(device, equipment_id)
    if record is None:
        raise HTTPException(404, 'Equipment not found.')
    return record


@app.delete('/api/equipment/{equipment_id}', status_code=204)
def remove_equipment(equipment_id: UUID):
    if repository.delete_equipment(equipment_id) is None:
        raise HTTPException(404, 'Equipment not found.')
    return Response(status_code=204)


@app.get('/api/equipment/{equipment_id}/assessment', response_model=Assessment)
@app.post('/api/equipment/{equipment_id}/assessment', response_model=Assessment, deprecated=True)
def equipment_assessment(equipment_id: UUID, response: Response):
    # Assessments depend on the latest saved history; do not cache old results.
    response.headers['Cache-Control'] = 'no-store'
    device = Equipment.model_validate(equipment_details(equipment_id))
    return assess_equipment(device)
