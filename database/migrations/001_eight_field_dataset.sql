-- Apply inside one transaction (python -m app.migrate, or psql -1 -f this-file).
-- Re-runnable; never deletes columns, records, or invents historical values.
SET LOCAL lock_timeout = '5s';
LOCK TABLE equipment IN ACCESS EXCLUSIVE MODE;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS age_years NUMERIC(8,3);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS avg_annual_cost NUMERIC(12,2);

-- A populated legacy database needs approved source values first. Abort the whole
-- transaction rather than calculating ages from today or fabricating annual costs.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM equipment WHERE age_years IS NULL OR avg_annual_cost IS NULL) THEN
        RAISE EXCEPTION 'Migration needs verified age_years and avg_annual_cost for existing records. Backfill from the approved dataset before retrying; no values were invented.';
    END IF;
END $$;

-- Keep legacy columns and their data, but make them optional and remove defaults.
DO $$
DECLARE legacy_column TEXT;
BEGIN
    FOREACH legacy_column IN ARRAY ARRAY['device_type', 'model_number', 'department',
        'firmware_version', 'operating_status', 'component_duty_cycles'] LOOP
        IF EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema=current_schema() AND table_name='equipment'
                     AND column_name=legacy_column) THEN
            EXECUTE format('ALTER TABLE equipment ALTER COLUMN %I DROP NOT NULL', legacy_column);
            EXECUTE format('ALTER TABLE equipment ALTER COLUMN %I DROP DEFAULT', legacy_column);
        END IF;
    END LOOP;
END $$;

ALTER TABLE equipment ALTER COLUMN age_years SET NOT NULL;
ALTER TABLE equipment ALTER COLUMN avg_annual_cost SET NOT NULL;
ALTER TABLE equipment ALTER COLUMN repair_events DROP DEFAULT;
ALTER TABLE equipment ALTER COLUMN total_historical_cost DROP DEFAULT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='equipment'::regclass AND conname='equipment_dataset_values_check') THEN
        ALTER TABLE equipment ADD CONSTRAINT equipment_dataset_values_check CHECK (
            length(trim(asset_tag)) > 0 AND length(trim(serial_number)) > 0
            AND length(trim(manufacturer)) > 0
            AND age_years >= 0 AND age_years <> 'NaN'::numeric
            AND repair_events >= 0
            AND total_historical_cost >= 0 AND total_historical_cost <> 'NaN'::numeric
            AND avg_annual_cost >= 0 AND avg_annual_cost <> 'NaN'::numeric
        );
    END IF;
END $$;
