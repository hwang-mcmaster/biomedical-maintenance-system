-- Fresh database: source and operational fields plus internal UUID/timestamps.
-- Existing databases use migrations 002 and 003.
CREATE TABLE IF NOT EXISTS equipment (
    equipment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_tag VARCHAR(50) NOT NULL UNIQUE,
    serial_number VARCHAR(100) NOT NULL UNIQUE,
    manufacturer VARCHAR(100) NOT NULL,
    in_service_date DATE NOT NULL,
    repair_events INTEGER NOT NULL DEFAULT 0,
    total_historical_cost NUMERIC(12,2) NOT NULL DEFAULT 0,
    model_number VARCHAR(100),
    model_name VARCHAR(100),
    device_type VARCHAR(100) CHECK (device_type IN ('Ventilator','Infusion Pump','Patient Monitor','Defibrillator','Other')),
    firmware_version VARCHAR(50),
    description TEXT CHECK (length(trim(description)) > 0 AND length(description) <= 2000),
    department VARCHAR(100),
    department_code VARCHAR(30),
    location VARCHAR(200),
    operating_status VARCHAR(30) CHECK (operating_status IN ('operational','under_maintenance','inactive')),
    assumed_replacement_cost NUMERIC(12,2) CHECK (assumed_replacement_cost >= 0 AND assumed_replacement_cost < 10000000000),
    expected_useful_life INTEGER CHECK (expected_useful_life > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT equipment_source_values_check CHECK (
        length(trim(asset_tag)) > 0 AND length(trim(serial_number)) > 0
        AND length(trim(manufacturer)) > 0 AND repair_events >= 0
        AND total_historical_cost >= 0 AND total_historical_cost < 'Infinity'::numeric
        AND in_service_date < (CURRENT_TIMESTAMP AT TIME ZONE 'America/Toronto')::date
    )
);
