import csv
import io
import logging
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router, access_control, origins
from . import repository
from .scheduling import router as scheduling_router
from .workflow import router as workflow_router
from .assessment import assess_equipment
from .database import get_connection
from .calculations import reference_date
from .schemas import Assessment, Equipment, EquipmentCreate, MaintenanceSchedules, DEVICE_TYPES, STATUSES, SCHEDULED_MAINTENANCE_STATUSES

logger = logging.getLogger(__name__)
app = FastAPI(title='Biomedical Maintenance API')
app.include_router(scheduling_router)
app.include_router(workflow_router)
app.include_router(auth_router)
app.middleware("http")(access_control)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(origins()),
    allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Content-Type','X-CSRF-Token'], allow_credentials=True,
)


@app.exception_handler(psycopg.Error)
async def database_exception(request, exc):
    from fastapi.responses import JSONResponse
    # Log the category only: exception text may contain connection details or input.
    logger.error('Database operation failed: %s', type(exc).__name__)
    if isinstance(exc, psycopg.errors.UniqueViolation) and request.url.path.startswith('/api/auth'):
        return JSONResponse(status_code=409, content={'detail':'Account or technician link already exists.'})
    if isinstance(exc, psycopg.errors.ExclusionViolation):
        return JSONResponse(status_code=409, content={'detail': 'Booking conflict. Refresh and generate a new preview.'})
    if isinstance(exc, psycopg.errors.CheckViolation) and request.url.path.startswith('/api/workflow'):
        return JSONResponse(status_code=422, content={'detail': 'Invalid maintenance record or assignment. Check qualification, availability and task requirements.'})
    if isinstance(exc, psycopg.errors.UniqueViolation) and request.url.path.startswith('/api/workflow'):
        return JSONResponse(status_code=409, content={'detail': 'This task or record is already assigned. Refresh before retrying.'})
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


@app.get('/api/equipment/options')
def equipment_options():
    return {'device_types': DEVICE_TYPES, 'statuses': STATUSES, 'useful_life_unit': 'years', 'currency': 'CAD'}


@app.get('/api/equipment', response_model=list[Equipment])
def equipment():
    return repository.list_equipment()


@app.get('/api/equipment/export')
def export_equipment():
    # One reference date for the whole export; derived values are frozen in CSV.
    as_of = reference_date()
    fields = ['asset_tag', 'serial_number', 'manufacturer', 'in_service_date',
              'age_years', 'repair_events', 'total_historical_cost', 'avg_annual_cost']
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in repository.list_equipment():
        record = Equipment.model_validate({**row, 'calculated_as_of': as_of})
        writer.writerow(record.model_dump(include=set(fields)))
    return Response(output.getvalue(), media_type='text/csv', headers={
        'Content-Disposition': f'attachment; filename="equipment-training-{as_of}.csv"',
        'X-Calculated-As-Of': as_of.isoformat(), 'Cache-Control': 'no-store',
    })


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

@app.get('/api/maintenance-schedules', response_model=list[MaintenanceSchedules])
def maintenance_schedules():
    schedule = repository.get_maintenance_schedules()
    if schedule is None:
        raise HTTPException(404, 'No maintenance schedules found.')
    return schedule

@app.get('/api/maintenance-schedules/{status}/status', response_model=list[MaintenanceSchedules])
def maintenance_schedule_from_status(status: SCHEDULED_MAINTENANCE_STATUSES):
    schedule = repository.get_maintenance_schedules_from_status(status)
    if schedule is None:
        raise HTTPException(404, f'No maintenance schedules with status {status} found.')
    return schedule

@app.get('/api/equipment/{equipment_id}/maintenance-schedule', response_model=MaintenanceSchedules)
def equipment_maintenance_schedule(equipment_id: UUID, response: Response):
    schedule = repository.get_equipment_maintenance_schedule(equipment_id)
    if schedule is None:
        raise HTTPException(404, f'Maintenance schedule for equipment not found.')
    return schedule