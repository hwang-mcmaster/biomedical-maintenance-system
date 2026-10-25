-- Matches the existing team RDS schema. This script only creates a missing table;
-- it never renames or replaces existing columns. IDs are database-generated UUIDs.
CREATE TABLE IF NOT EXISTS equipment (
    equipment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_tag VARCHAR(50) NOT NULL UNIQUE,
    serial_number VARCHAR(100) NOT NULL UNIQUE,
    device_type VARCHAR(100) NOT NULL,
    manufacturer VARCHAR(100) NOT NULL,
    model_number VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    firmware_version VARCHAR(50) NOT NULL,
    in_service_date DATE NOT NULL,
    repair_events INTEGER NOT NULL DEFAULT 0,
    component_duty_cycles JSONB NOT NULL DEFAULT '{}',
    last_serviced_at TIMESTAMPTZ,
    operating_status VARCHAR(30) NOT NULL DEFAULT 'operational',
    total_historical_cost NUMERIC(12,2) NOT NULL DEFAULT 0,
    assumed_replacement_cost NUMERIC(12,2),
    health_score NUMERIC,
    anomaly_risk_score NUMERIC,
    predicted_next_failure TIMESTAMPTZ,
    recommended_maintenance_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
