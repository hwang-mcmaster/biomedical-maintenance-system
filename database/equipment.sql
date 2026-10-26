-- Fresh database setup. Existing databases must also run the versioned migration.
-- The eight dataset fields plus internal UUID/timestamps are the active contract.
CREATE TABLE IF NOT EXISTS equipment (
    equipment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_tag VARCHAR(50) NOT NULL UNIQUE,
    serial_number VARCHAR(100) NOT NULL UNIQUE,
    manufacturer VARCHAR(100) NOT NULL,
    in_service_date DATE NOT NULL,
    age_years NUMERIC(8,3) NOT NULL,
    repair_events INTEGER NOT NULL,
    total_historical_cost NUMERIC(12,2) NOT NULL,
    avg_annual_cost NUMERIC(12,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT equipment_dataset_values_check CHECK (
        length(trim(asset_tag)) > 0 AND length(trim(serial_number)) > 0
        AND length(trim(manufacturer)) > 0
        AND age_years >= 0 AND age_years <> 'NaN'::numeric
        AND repair_events >= 0
        AND total_historical_cost >= 0 AND total_historical_cost <> 'NaN'::numeric
        AND avg_annual_cost >= 0 AND avg_annual_cost <> 'NaN'::numeric
    )
);
