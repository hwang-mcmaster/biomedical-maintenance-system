# Saved maintenance workflow

Week 10 adds a persistent path from equipment assessment to reviewed task priority,
qualified technician assignment, confirmed schedule and recorded maintenance.
Existing equipment CRUD and the independent manual scheduling preview still work.

## Setup

Apply the additive migration using the existing backend environment:

```powershell
Set-Location backend
venv/Scripts/python.exe -m app.migrate
```

Migration 004 creates workflow_* tables and preserves existing equipment and
legacy maintenance_schedules rows. If the optional legacy schedule table exists,
it installs a guard against overlaps with confirmed workflow assignments. Reapply
004 if that legacy table is created later. Do not run migrations automatically on
web requests. Use a development database for normal write testing.

Run the backend on port 8000, the AI service on 8001 and React on 5173. From the
repository root the AI command is:

```powershell
$env:SCHEDULER_ENABLED = "false"
ai/.venv/Scripts/python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
```

The legacy hourly scheduler remains off by default. The new user-driven workflow
does not depend on enabling it and never silently confirms generated drafts.

## User flow

1. Add/select equipment and open its details.
2. Create a task with title, duration, required qualification and optional target.
   For a ventilator the backend requests a fresh assessment. Unsupported or
   unavailable AI requires the user to select manual mode and give a priority
   and explanation. The system never guesses an unsupported device type.
3. Add a technician with qualification labels and dated Toronto availability.
   Multiple windows represent breaks or different dates. Edit updates the saved
   technician, but cannot invalidate confirmed work.
4. Select pending tasks, or use all pending tasks, and generate a dated preview.
5. Review priority explanations, target dates, assignments and unassigned reasons.
   Confirm to reserve the returned assignments. Refresh/reload to see saved work.
6. Start scheduled work at/after its start, then record completion notes and CAD
   cost. Cancel pending/scheduled/in-progress tasks with a reason when needed.

## API contract

All new routes use /api/workflow:

- GET/POST /technicians and PUT /technicians/{id}: saved skills/availability.
- GET/POST /tasks: saved tasks and assessment snapshots. Send request_id (UUID)
  when creating a task to safely retry the same payload after a lost response.
  The React form retains its key until inputs change or the save succeeds.
- POST /tasks/{id}/status: in_progress, completed or cancelled plus notes and
  optional actual_cost. Only pending→cancelled, scheduled→in_progress/cancelled,
  and in_progress→completed/cancelled are valid. Terminal states cannot reopen.
- POST /schedules/preview: schedule_date and 1–100 unique task_ids. Reads saved
  technician data and existing commitments, stores a draft and returns results.
- POST /schedules/{id}/confirm: rechecks current data before booking. Repeating
  confirmation of the same confirmed schedule creates no duplicate bookings.
- GET /schedules and /assignments: saved previews/confirmed assignments.
- GET /equipment/{id}: tasks, historical assessment snapshot, assignments,
  completed service records and task transition events.
- GET /metrics: recorded task/completion counts, including high-priority target
  compliance. Empty history yields counts, not an invented completion rate.

Validation rejects missing references, unknown statuses, blank inputs, invalid
amounts, overlapping availability, past dates, impossible transitions and stale
equipment. Changed equipment requires cancellation/recreation of an outdated
pending task. Booking changes return 409 so the user can regenerate and review.

## Priority and model provenance

The versioned prototype policy maps existing repair-intensity bands directly:
High→High, Medium→Medium, Low→Low, with optional explained override. Defaults of
7/30/90 calendar days are engineering-review targets for demonstration, not
manufacturer service intervals, clinical criticality or a prediction of failure.
The numeric percentile and recommendation remain in the assessment snapshot.
The existing AI service exposes a SHA-256 fingerprint of the loaded model artifact
as model_version. This does not retrain or establish the validity of the model.

Task completion stores an individual service record. It does not silently
increment repair_events or rewrite the aggregate training-cost fields. Update
those source totals only from verified service records and an agreed aggregation
policy. The latest stored task assessment is historical; a standalone on-demand
assessment remains read-only and is not automatically persisted.

## Scheduling and consistency

Reuse the tested deterministic priority-first earliest-slot engine. Qualification
labels match after whitespace/case normalization. Tasks must fit one continuous
availability window; shared equipment and technicians cannot overlap. Existing
legacy bookings reserve equipment but do not imply a qualified technician.
Tie-breaking uses task ID/technician ID. This is feasible placement, not proof of
a globally optimal schedule or that every unassigned task is impossible.

Workflow mutations serialize with transaction-level advisory lock 74102026.
Confirmation also locks task/equipment rows and compares regenerated assignments
with the stored preview. Database triggers protect active workflow bookings and
legacy inserts/updates with the same lock. Confirmed bookings cannot be replaced
by the legacy automatic writer. This intentionally simple lock limits concurrent
write throughput; larger deployments should revisit locking and pagination.

The backend stores priority explanations and transition notes, but there is no
user authentication yet, so these events do not establish who performed an action.
Qualification labels are entered requirements, not validated professional credentials.
The prototype supports up to 30 technicians and 100 tasks per planning run, one
Toronto day, and no overnight availability windows. Schedule confirmation and
technician edits require the latest constraints; drafts do not reserve resources.

## Verification and measurements

```powershell
backend/venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py'
$env:RUN_POSTGRES_TESTS = "1"
$env:RUN_WORKFLOW_TESTS = "1"
$env:RUN_AI_TESTS = "1"
backend/venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py'
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run test:live
npm.cmd --prefix frontend run test:workflow:live
backend/venv/Scripts/python.exe backend/benchmark_workflow.py
```

Live tests use unique fixtures and remove only those generated records, not the
team's equipment. The browser check covers real model assessment, task priority,
technician entry, preview, confirmation and persistence after a reload. Backend
checks include actual concurrent confirmations, changed availability, terminal
states, status/history, task retries, and the legacy overlap guard.

validation/week10-synthetic-results.json records reproducible 20/50-equipment,
five-technician scenarios. Engine timing excludes DB, model and network work.
Stored previews separately capture end-to-end planning-function time, requested/
scheduled/unassigned counts, independently checked overlaps, high-priority tasks
scheduled within target, and each technician's available/assigned minutes.
Utilization measures selected tasks in that run, not observed staff productivity.
Completion compliance comes from completed history, not simulated assignments.
No downtime reduction, clinical benefit or real-world model accuracy is claimed.
