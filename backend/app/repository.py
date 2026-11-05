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

def get_maintenance_schedules():
    with get_connection() as connection:
        return connection.execute(
            '''SELECT asset_tag, scheduled_start_time, scheduled_end_time, status, priority_score
               FROM maintenance_schedules'''
        ).fetchall()

def get_equipment_due_for_maintenance():
  with get_connection() as connection:
      return connection.execute("""
                SELECT e.equipment_id AS id, e.asset_tag, e.serial_number, e.manufacturer,
                        e.in_service_date, e.repair_events, e.total_historical_cost FROM equipment e
                LEFT JOIN maintenance_schedules ms ON e.equipment_id = ms.equipment_id
                WHERE ms.scheduled_end_time <= CURRENT_TIMESTAMP + INTERVAL '14 days'
                   OR ms.id IS NULL
                ORDER BY e.created_at, e.equipment_id;
            """).fetchall()

def get_equipment_maintenance_schedule(equipment_id):
    with get_connection() as connection:
        return connection.execute(
            '''SELECT asset_tag, scheduled_start_time, scheduled_end_time, status, priority_score
               FROM maintenance_schedules WHERE equipment_id = %s''',
            (equipment_id,)
        ).fetchone()

def sweep_overdue_schedules():
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE maintenance_schedules
            SET status = 'incomplete', 
                updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('pending', 'scheduled')
              AND scheduled_end_time < CURRENT_TIMESTAMP;
        """
        )
        updated_count = connection.rowcount
        connection.commit()
        print(f"Sweep complete: {updated_count} past-due equipment maintenance tasks marked 'incomplete'.")

def save_optimized_maintenance_schedule(optimized_work_orders):
    with get_connection() as connection:
        try:
            #Clear out 'pending' tasks inside the maintenance_schedules table
            connection.execute(
                """
                    DELETE FROM maintenance_schedules 
                    WHERE status IN ('scheduled', 'pending')
                    AND scheduled_start_time >= CURRENT_TIMESTAMP
                    AND scheduled_start_time <= CURRENT_TIMESTAMP + INTERVAL '14 days';
                """
            )

            # Insert the new optimized equipment maintenance schedule entries.
            for slot in optimized_work_orders.values():
                connection.execute(
                    """
                        INSERT INTO maintenance_schedules 
                        (equipment_id, asset_tag, scheduled_start_time, scheduled_end_time, status, priority_score)
                        VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        slot["equipment_id"],
                        slot["asset_tag"],
                        slot["scheduled_start_time"],
                        slot["scheduled_end_time"],
                        slot["status"],
                        slot["priority_score"],
                    ),
                )

            connection.commit()

        except Exception as e:
            connection.rollback()
            print(f"Failed to save optimized maintenance schedule, rolled back changes: {e}")
            raise e