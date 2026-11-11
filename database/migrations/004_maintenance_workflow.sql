-- Additive Week 10 workflow. Legacy maintenance_schedules stays intact.
CREATE TABLE IF NOT EXISTS workflow_assessments (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), equipment_id UUID NOT NULL REFERENCES equipment(equipment_id),
 equipment_version TIMESTAMPTZ NOT NULL, snapshot JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workflow_technicians (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), name VARCHAR(100) NOT NULL CHECK(length(trim(name))>0), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workflow_qualifications (name VARCHAR(100) PRIMARY KEY CHECK(length(trim(name))>0));
CREATE TABLE IF NOT EXISTS workflow_technician_qualifications (
 technician_id UUID REFERENCES workflow_technicians(id) ON DELETE CASCADE, qualification VARCHAR(100) REFERENCES workflow_qualifications(name), PRIMARY KEY(technician_id,qualification)
);
CREATE TABLE IF NOT EXISTS workflow_availability (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), technician_id UUID NOT NULL REFERENCES workflow_technicians(id) ON DELETE CASCADE,
 starts_at TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL, CHECK(ends_at>starts_at)
);
CREATE TABLE IF NOT EXISTS workflow_tasks (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), equipment_id UUID NOT NULL REFERENCES equipment(equipment_id),
 assessment_id UUID REFERENCES workflow_assessments(id), equipment_version TIMESTAMPTZ NOT NULL,
 title VARCHAR(150) NOT NULL CHECK(length(trim(title))>0), duration_minutes INTEGER NOT NULL CHECK(duration_minutes BETWEEN 1 AND 1440),
 required_qualification VARCHAR(100) NOT NULL REFERENCES workflow_qualifications(name),
 priority VARCHAR(10) NOT NULL CHECK(priority IN ('High','Medium','Low')), priority_reason TEXT NOT NULL,
 due_date DATE NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','scheduled','in_progress','completed','cancelled')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workflow_schedules (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), schedule_date DATE NOT NULL, task_ids JSONB NOT NULL, result JSONB NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','confirmed')), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), confirmed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS workflow_assignments (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), schedule_id UUID NOT NULL REFERENCES workflow_schedules(id),
 task_id UUID NOT NULL UNIQUE REFERENCES workflow_tasks(id), equipment_id UUID NOT NULL REFERENCES equipment(equipment_id),
 technician_id UUID NOT NULL REFERENCES workflow_technicians(id), starts_at TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL,
 status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled','in_progress','completed','cancelled')), CHECK(ends_at>starts_at)
);
CREATE TABLE IF NOT EXISTS workflow_history (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), task_id UUID NOT NULL UNIQUE REFERENCES workflow_tasks(id), equipment_id UUID NOT NULL REFERENCES equipment(equipment_id),
 notes TEXT NOT NULL CHECK(length(trim(notes))>0), actual_cost NUMERIC(12,2) NOT NULL CHECK(actual_cost>=0), completed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS workflow_events (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(), task_id UUID NOT NULL REFERENCES workflow_tasks(id), from_status VARCHAR(20), to_status VARCHAR(20) NOT NULL,
 note TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS workflow_tasks_equipment_idx ON workflow_tasks(equipment_id);
CREATE INDEX IF NOT EXISTS workflow_assignment_times_idx ON workflow_assignments(starts_at,ends_at);
-- Protect workflow assignments even if another SQL client inserts directly.
CREATE OR REPLACE FUNCTION workflow_check_booking() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(74102026);
 IF NEW.status IN ('scheduled','in_progress') THEN
  IF NOT EXISTS(SELECT 1 FROM workflow_tasks t WHERE t.id=NEW.task_id AND t.equipment_id=NEW.equipment_id) THEN
   RAISE EXCEPTION 'Assignment equipment must match its task' USING ERRCODE='23514';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM workflow_tasks t JOIN workflow_technician_qualifications q ON q.qualification=t.required_qualification
    WHERE t.id=NEW.task_id AND q.technician_id=NEW.technician_id) OR NOT EXISTS(
    SELECT 1 FROM workflow_availability v WHERE v.technician_id=NEW.technician_id AND v.starts_at<=NEW.starts_at AND NEW.ends_at<=v.ends_at) THEN
   RAISE EXCEPTION 'Assignment requires qualification and continuous availability' USING ERRCODE='23514';
  END IF;
  IF to_regclass('maintenance_schedules') IS NOT NULL THEN
   IF EXISTS(SELECT 1 FROM maintenance_schedules m WHERE m.equipment_id=NEW.equipment_id AND m.status IN ('scheduled','pending','in_progress')
      AND m.scheduled_start_time<NEW.ends_at AND NEW.starts_at<m.scheduled_end_time) THEN
    RAISE EXCEPTION 'Equipment has a legacy booking' USING ERRCODE='23P01';
   END IF;
  END IF;
  IF EXISTS(SELECT 1 FROM workflow_assignments a WHERE a.id<>NEW.id AND a.status IN ('scheduled','in_progress')
    AND (a.technician_id=NEW.technician_id OR a.equipment_id=NEW.equipment_id) AND a.starts_at<NEW.ends_at AND NEW.starts_at<a.ends_at) THEN
   RAISE EXCEPTION 'Technician or equipment booking conflict' USING ERRCODE='23P01';
  END IF;
 END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS workflow_booking_guard ON workflow_assignments;
CREATE TRIGGER workflow_booking_guard BEFORE INSERT OR UPDATE ON workflow_assignments FOR EACH ROW EXECUTE FUNCTION workflow_check_booking();

-- Shared lock also serializes the team's legacy automatic writer.
CREATE OR REPLACE FUNCTION workflow_check_legacy_booking() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(74102026);
 IF NEW.status IN ('scheduled','pending','in_progress') AND EXISTS(
   SELECT 1 FROM workflow_assignments a WHERE a.status IN ('scheduled','in_progress') AND a.equipment_id=NEW.equipment_id
   AND a.starts_at<NEW.scheduled_end_time AND NEW.scheduled_start_time<a.ends_at) THEN
  RAISE EXCEPTION 'Legacy scheduling conflicts with confirmed maintenance' USING ERRCODE='23P01';
 END IF;
 RETURN NEW;
END $$;
DO $$ BEGIN
 IF to_regclass('maintenance_schedules') IS NOT NULL THEN
  DROP TRIGGER IF EXISTS workflow_legacy_booking_guard ON maintenance_schedules;
  CREATE TRIGGER workflow_legacy_booking_guard BEFORE INSERT OR UPDATE ON maintenance_schedules FOR EACH ROW EXECUTE FUNCTION workflow_check_legacy_booking();
 END IF;
END $$;

ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS request_id UUID NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE workflow_tasks ADD COLUMN IF NOT EXISTS request_payload JSONB NOT NULL DEFAULT '{}';
CREATE UNIQUE INDEX IF NOT EXISTS workflow_task_request_key ON workflow_tasks(request_id);
