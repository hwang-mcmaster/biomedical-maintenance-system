-- Additive operational metadata; existing source records and snapshots remain intact.
SET LOCAL lock_timeout = '5s';
LOCK TABLE equipment IN ACCESS EXCLUSIVE MODE;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS model_number VARCHAR(100);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS model_name VARCHAR(100);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS device_type VARCHAR(100);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS firmware_version VARCHAR(50);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS department VARCHAR(100);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS department_code VARCHAR(30);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS location VARCHAR(200);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS operating_status VARCHAR(30);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS assumed_replacement_cost NUMERIC(12,2);
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS expected_useful_life INTEGER;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='equipment'::regclass AND conname='equipment_operational_values_check') THEN
        ALTER TABLE equipment ADD CONSTRAINT equipment_operational_values_check CHECK (
            (device_type IS NULL OR device_type IN ('Ventilator','Infusion Pump','Patient Monitor','Defibrillator','Other'))
            AND (operating_status IS NULL OR operating_status IN ('operational','under_maintenance','inactive'))
            AND (assumed_replacement_cost IS NULL OR (assumed_replacement_cost >= 0 AND assumed_replacement_cost < 10000000000))
            AND (expected_useful_life IS NULL OR expected_useful_life > 0)
            AND (description IS NULL OR (length(trim(description)) > 0 AND length(description) <= 2000))
        );
    END IF;
END $$;
