-- Apply in one transaction via python -m app.migrate (or psql -1).
-- Source values and all old snapshot columns are preserved unchanged.
SET LOCAL lock_timeout = '5s';
LOCK TABLE equipment IN ACCESS EXCLUSIVE MODE;
DO $$
DECLARE legacy_column TEXT;
BEGIN
    FOREACH legacy_column IN ARRAY ARRAY['age_years', 'avg_annual_cost',
        'device_type', 'model_number', 'department', 'firmware_version',
        'operating_status', 'component_duty_cycles'] LOOP
        IF EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name='equipment' AND column_name=legacy_column) THEN
            EXECUTE format('ALTER TABLE equipment ALTER COLUMN %I DROP NOT NULL', legacy_column);
            EXECUTE format('ALTER TABLE equipment ALTER COLUMN %I DROP DEFAULT', legacy_column);
        END IF;
    END LOOP;
END $$;
ALTER TABLE equipment ALTER COLUMN repair_events SET DEFAULT 0;
ALTER TABLE equipment ALTER COLUMN total_historical_cost SET DEFAULT 0;
-- Remove the old constraint's dependency on inactive snapshot values.
ALTER TABLE equipment DROP CONSTRAINT IF EXISTS equipment_dataset_values_check;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='equipment'::regclass AND conname='equipment_source_values_check') THEN
        ALTER TABLE equipment ADD CONSTRAINT equipment_source_values_check CHECK (
            length(trim(asset_tag)) > 0 AND length(trim(serial_number)) > 0
            AND length(trim(manufacturer)) > 0
            AND repair_events >= 0
            AND total_historical_cost >= 0 AND total_historical_cost < 'Infinity'::numeric
            AND in_service_date < (CURRENT_TIMESTAMP AT TIME ZONE 'America/Toronto')::date
        );
    END IF;
END $$;
