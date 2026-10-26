"""Parameterized SQL for the six source fields; derived values are calculated by the API."""
from .database import get_connection

COLUMNS = '''equipment_id AS id, asset_tag, serial_number, manufacturer,
    in_service_date, repair_events, total_historical_cost'''


def values(device):
    return (device.asset_tag, device.serial_number, device.manufacturer,
            device.in_service_date, device.repair_events, device.total_historical_cost)


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
                f"""INSERT INTO equipment (asset_tag, serial_number, manufacturer, in_service_date,
                    repair_events, total_historical_cost)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING {COLUMNS}""", values(device)).fetchone()
        return connection.execute(
            f"""UPDATE equipment SET asset_tag=%s, serial_number=%s, manufacturer=%s,
                in_service_date=%s, repair_events=%s,
                total_historical_cost=%s, updated_at=CURRENT_TIMESTAMP
                WHERE equipment_id=%s RETURNING {COLUMNS}""",
            (*values(device), equipment_id)).fetchone()


def delete_equipment(equipment_id):
    with get_connection() as connection:
        return connection.execute('DELETE FROM equipment WHERE equipment_id=%s RETURNING equipment_id', (equipment_id,)).fetchone()
