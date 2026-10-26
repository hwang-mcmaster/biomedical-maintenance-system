-- Fresh database: six source fields plus internal UUID/timestamps.
-- Existing databases use migrations/002_calculated_metrics.sql.
CREATE TABLE IF NOT EXISTS equipment (
    equipment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_tag VARCHAR(50) NOT NULL UNIQUE,
    serial_number VARCHAR(100) NOT NULL UNIQUE,
    manufacturer VARCHAR(100) NOT NULL,
    in_service_date DATE NOT NULL,
    repair_events INTEGER NOT NULL DEFAULT 0,
    total_historical_cost NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT equipment_source_values_check CHECK (
        length(trim(asset_tag)) > 0 AND length(trim(serial_number)) > 0
        AND length(trim(manufacturer)) > 0 AND repair_events >= 0
        AND total_historical_cost >= 0 AND total_historical_cost < 'Infinity'::numeric
        AND in_service_date < (CURRENT_TIMESTAMP AT TIME ZONE 'America/Toronto')::date
    )
);
