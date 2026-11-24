-- Apply explicitly after equipment/workflow and authentication setup. No data is deleted.
ALTER TABLE equipment ADD COLUMN IF NOT EXISTS criticality VARCHAR(20)
 CHECK (criticality IN ('Routine','Important','Critical'));
CREATE TABLE IF NOT EXISTS workflow_reviews (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), equipment_id UUID NOT NULL REFERENCES equipment(equipment_id),
 equipment_version TIMESTAMPTZ NOT NULL, snapshot JSONB NOT NULL,
 decision VARCHAR(20) NOT NULL CHECK(decision IN ('accepted','rejected','deferred')),
 rationale TEXT NOT NULL CHECK(length(trim(rationale))>=3), actor_id UUID NOT NULL REFERENCES auth_users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workflow_service_policies (
 equipment_id UUID PRIMARY KEY REFERENCES equipment(equipment_id), title VARCHAR(150) NOT NULL,
 interval_days INTEGER NOT NULL CHECK(interval_days BETWEEN 1 AND 3650),
 last_service_date DATE NOT NULL, duration_minutes INTEGER NOT NULL CHECK(duration_minutes BETWEEN 1 AND 1440),
 required_qualification VARCHAR(100) NOT NULL, priority VARCHAR(10) NOT NULL CHECK(priority IN ('Low','Medium','High')),
 source TEXT NOT NULL CHECK(length(trim(source))>=3), active BOOLEAN NOT NULL DEFAULT true,
 actor_id UUID NOT NULL REFERENCES auth_users(id), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE workflow_history ADD COLUMN IF NOT EXISTS aggregates_applied BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS workflow_reviews_equipment_idx ON workflow_reviews(equipment_id,created_at);

ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS recurring_due DATE;
