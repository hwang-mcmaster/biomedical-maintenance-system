"""Parameterized CRUD. API names are mapped to existing DB columns explicitly."""
from .database import get_connection

FIELD_COLUMNS = {
    'asset_tag': 'asset_tag', 'serial_number': 'serial_number', 'manufacturer': 'manufacturer',
    'in_service_date': 'in_service_date', 'repair_events': 'repair_events',
    'total_historical_cost': 'total_historical_cost', 'model_number': 'model_number',
    'model_name': 'model_name', 'device_type': 'device_type', 'firmware_version': 'firmware_version',
    'description': 'description', 'department': 'department', 'department_code': 'department_code',
    'location': 'location', 'status': 'operating_status', 'replacement_cost': 'assumed_replacement_cost',
    'expected_useful_life': 'expected_useful_life',
}
STATUS_TO_DB = {'Operational': 'operational', 'Under Maintenance': 'under_maintenance', 'Inactive': 'inactive'}
STATUS_SELECT = """CASE operating_status WHEN 'operational' THEN 'Operational'
    WHEN 'under_maintenance' THEN 'Under Maintenance' WHEN 'inactive' THEN 'Inactive'
    ELSE operating_status END AS status"""
COLUMNS = 'equipment_id AS id, ' + ', '.join(
    STATUS_SELECT if key == 'status' else f'{column} AS {key}'
    for key, column in FIELD_COLUMNS.items()
)


def values(device):
    return tuple(STATUS_TO_DB.get(device.status) if key == 'status' else getattr(device, key)
                 for key in FIELD_COLUMNS)


def list_equipment():
    with get_connection() as connection:
        return connection.execute(f'SELECT {COLUMNS} FROM equipment ORDER BY created_at, equipment_id').fetchall()


def get_equipment(equipment_id):
    with get_connection() as connection:
        return connection.execute(f'SELECT {COLUMNS} FROM equipment WHERE equipment_id=%s', (equipment_id,)).fetchone()


def save_equipment(device, equipment_id=None):
    # Identifiers are fixed program constants; all user values are parameters.
    with get_connection() as connection:
        if equipment_id is None:
            columns = ', '.join(FIELD_COLUMNS.values())
            placeholders = ', '.join(['%s'] * len(FIELD_COLUMNS))
            return connection.execute(f'INSERT INTO equipment ({columns}) VALUES ({placeholders}) RETURNING {COLUMNS}', values(device)).fetchone()
        assignments = ', '.join(f'{column}=%s' for column in FIELD_COLUMNS.values())
        return connection.execute(
            f'UPDATE equipment SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE equipment_id=%s RETURNING {COLUMNS}',
            (*values(device), equipment_id)).fetchone()


def delete_equipment(equipment_id):
    with get_connection() as connection:
        return connection.execute('DELETE FROM equipment WHERE equipment_id=%s RETURNING equipment_id', (equipment_id,)).fetchone()
