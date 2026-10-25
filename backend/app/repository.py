"""SQL mapping for the existing RDS equipment table (UUID primary key)."""
from .database import get_connection

# Explicit aliases preserve the frontend's name/type/location/status contract.
COLUMNS = '''equipment_id AS id, model_number AS name, device_type AS type,
    department AS location,
    CASE operating_status WHEN 'operational' THEN 'Operational'
        WHEN 'under_maintenance' THEN 'Under Maintenance'
        WHEN 'inactive' THEN 'Inactive' ELSE operating_status END AS status,
    asset_tag, serial_number, manufacturer, firmware_version, in_service_date,
    repair_events, total_historical_cost, assumed_replacement_cost'''
STATUS_TO_DB = {'Operational': 'operational', 'Under Maintenance': 'under_maintenance', 'Inactive': 'inactive'}


def values(device):
    return (device.name, device.type, device.location, STATUS_TO_DB[device.status],
            device.asset_tag, device.serial_number, device.manufacturer,
            device.firmware_version, device.in_service_date, device.repair_events,
            device.total_historical_cost, device.assumed_replacement_cost)


def list_equipment():
    with get_connection() as connection:
        return connection.execute(f'SELECT {COLUMNS} FROM equipment ORDER BY created_at, equipment_id').fetchall()


def get_equipment(equipment_id):
    with get_connection() as connection:
        return connection.execute(f'SELECT {COLUMNS} FROM equipment WHERE equipment_id = %s', (equipment_id,)).fetchone()


def save_equipment(device, equipment_id=None):
    with get_connection() as connection:
        if equipment_id is None:
            return connection.execute(
                f'''INSERT INTO equipment (model_number, device_type, department, operating_status,
                    asset_tag, serial_number, manufacturer, firmware_version, in_service_date,
                    repair_events, total_historical_cost, assumed_replacement_cost)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING {COLUMNS}''', values(device)).fetchone()
        return connection.execute(
            f'''UPDATE equipment SET model_number=%s, device_type=%s, department=%s,
                operating_status=%s, asset_tag=%s, serial_number=%s, manufacturer=%s,
                firmware_version=%s, in_service_date=%s, repair_events=%s,
                total_historical_cost=%s, assumed_replacement_cost=%s, updated_at=CURRENT_TIMESTAMP
                WHERE equipment_id=%s RETURNING {COLUMNS}''',
            (*values(device), equipment_id)).fetchone()


def delete_equipment(equipment_id):
    with get_connection() as connection:
        return connection.execute('DELETE FROM equipment WHERE equipment_id=%s RETURNING equipment_id', (equipment_id,)).fetchone()
