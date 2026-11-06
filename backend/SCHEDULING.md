# Scheduling prototype

The new POST /api/scheduling/preview endpoint builds a single-day draft from real
saved equipment and explicitly supplied tasks, technicians, availability and known
bookings. It does not call the AI service or write schedules to PostgreSQL. The
existing equipment CRUD and assessment endpoints remain available.

## Inputs

- schedule_date: today or a future date, interpreted in America/Toronto.
- tasks: unique ID, existing equipment UUID, title, High/Medium/Low priority,
  required qualification label and integer duration from 1 to 1440 minutes.
- technicians: unique ID, name, qualification labels, and zero to ten availability
  windows. An empty availability list means the technician is unavailable.
- existing_bookings: optional fixed busy windows with a unique ID, technician ID
  and saved equipment UUID. Include all known commitments for the preview day.

Times use local HH:MM within the same day. Overnight windows are unsupported.
Availability windows for one technician must not overlap. Conflicting supplied
bookings are rejected before generating a draft. Ambiguous/nonexistent daylight-
saving input times are rejected; elapsed durations use UTC internally. Results
include timezone offsets and are displayed in Toronto time.

The endpoint accepts at most 100 tasks, 30 technicians, 20 qualification labels
per technician, and 200 existing bookings. Unknown request properties, duplicate
IDs, invalid durations/dates and missing booking technician references return 422.
Missing saved equipment returns 404; database errors follow the existing 503 path.

## Placement policy

Tasks are considered High, Medium, then Low, with task ID as a deterministic tie
breaker. For each task, find qualified technicians and choose the earliest feasible
continuous slot, breaking ties by technician ID. Qualification comparison ignores
case and repeated spaces but requires a full matching label.

Every assignment fits one availability window and has the requested duration.
Neither a technician nor an equipment item may have overlapping assignments or
entered bookings. Adjacent tasks are allowed: an end at 10:00 does not conflict
with another task starting at 10:00. Tasks cannot be split across a break.

Unassigned tasks retain their identity and a reason code:

- NO_QUALIFIED_TECHNICIAN: no matching supplied qualification.
- INSUFFICIENT_AVAILABILITY: no qualified continuous window is long enough.
- RESOURCE_CONFLICT: no slot remains after bookings and earlier placements.

This greedy method guarantees feasibility of returned assignments, not a globally
optimal ordering or a proof that every unassigned task is impossible. A lower-
priority task may start earlier if it fits a gap left by higher-priority placement.
The response includes persisted=false and explicit draft/data-source notices.

## Data sources and limits

Equipment IDs and asset tags are checked against PostgreSQL. The frontend suggests
a qualification label from device type when adding a task; users can edit it. These
labels are prototype project requirements, not verified professional credentials.
Task priority is entered workload priority, not clinical criticality or AI failure
probability. The current equipment table has no technician, task-duration or booking
data. Those inputs remain editable or explicitly labelled demo fixtures.

No AI files or database schema were changed for this prototype. Saved schedules,
real technician/qualification records, booking persistence/concurrency, multi-day
planning, shift rules and optimization are follow-up work. Supply actual known
bookings before using a preview for review; it does not reserve resources.

## Tests and demonstration

Run from the repository root:

```powershell
backend/venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py'
npm.cmd --prefix frontend test
```

With backend and the existing AI service running, the existing frontend live test
now also creates a draft against its temporary saved RDS fixture and independently
checks qualifications, availability, durations and resource overlaps:

```powershell
npm.cmd --prefix frontend run test:live
```

For a short demo, show saving an equipment item and its assessment first. Jump to
Scheduling prototype, select that item, load the labelled demo inputs, and generate
a preview. Point to the existing booking, lunch break, technician qualifications,
assignments and the preview-only notice. Change a required qualification to a label
no technician has, regenerate, and show the unassigned reason. Do not present the
demo technicians or this draft as a saved hospital roster.
