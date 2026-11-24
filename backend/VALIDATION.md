# Validation week: frontend and backend

Implemented on 2026-11-19. No database migrations or AI source/model changes are
part of this update. Existing PostgreSQL account/workflow tables are required.

## What changed

- Saved previews compare risk-priority order with due-date order using identical
  tasks, durations, technician availability, qualifications and known bookings.
  Both outputs are stored in the existing `workflow_schedules.result` JSON.
- An independent output checker verifies task coverage/identity, elapsed duration,
  qualification, availability and technician/equipment conflicts against existing
  bookings. Invalid output cannot be saved or confirmed.
- A task may include `last_service_date` and `service_interval_days` together.
  The date cannot precede equipment commissioning or be in the future. Interval
  length is a whole number from 1 to 3650 days. Inputs use the existing task
  `request_payload` JSON; the API derives `service_due_date` on reads.
- A recorded service interval determines the default target. An optional earlier
  review target is allowed; a later target cannot postpone service. Overdue work
  remains schedulable but is counted and displayed as late. Unknown intervals
  remain unknown; the 7/30/90-day review defaults are not manufacturer intervals.
- Within each risk priority, earlier targets win ties. In-progress work keeps
  reserving its technician/equipment until completion or cancellation is recorded,
  even if its original planned end has passed.
- The Scheduling page includes task selection, an explicit 100-task run limit,
  baseline measurements and a JSON download. Both draft and confirmed run results
  can be reopened. Unselected work stays pending.
- Inventory pagination clamps after refresh/deletion, filtered empty states give
  useful guidance, and API/session errors explain what happened.

## Measurements and interpretation

The comparison is a single-day placement experiment on the same task cohort, not
a complete comparison between recurring maintenance policies. With complete
interval inputs it orders the baseline by fixed-interval due date. Otherwise it
is labelled **Due-date order (incomplete service intervals)** and missing intervals
fall back to review targets. The baseline never orders tasks using risk.

| Measure | Definition / limit |
| --- | --- |
| High priority within target | Scheduled end date <= recorded target; not completed work |
| Recorded completion within target | Separate history-based metric from actual completion records |
| Selected-task utilization | Selected assigned minutes / supplied availability; other bookings consume capacity but are not included in the numerator |
| Planned equipment downtime | Reserved task minutes, assuming equipment is unavailable throughout maintenance |
| Service interval on time/late | Assignment end date compared with entered interval deadline; unassigned tasks remain separately counted |
| Conflict count | Independent pairwise check against assignments and existing bookings |
| Engine time | Placement and result serialization only |
| Preview computation time | Includes DB reads, both placements, validation and evidence construction; excludes HTTP/authentication overhead |
| HTTP timing | Separately captured by the React integration script, including the backend request |
| Cost / avoided failure downtime | Not measured without approved rates, parts costs and real outcomes |

The current AI service estimates annual maintenance cost and derives repair
intensity. Report MAE, RMSE and R² for the cost model. Recall, F1 and false-negative
rate are **not applicable** until there are labelled outcomes and a defined
classification task. Do not call repair-intensity categories failure labels.

`validate_prototype.py` copies the existing AI metadata and model fingerprint into
the evidence with an explicit **not independently recomputed** label. That small
synthetic cross-validation is not new independent clinical/model validation.
This update tests the backend's model contract, scope, range warnings, priority
mapping and real HTTP integration; it does not retrain or change the AI.

## Repeat the checks

Start the existing AI service on port 8001 from the repository root with
`SCHEDULER_ENABLED=false`. For local HTTP authentication set
`AUTH_COOKIE_SECURE=false` in the backend process/environment. Use an intended
development database for repeat write tests; schema setup is manual.

From `backend`:

```powershell
# Unit tests: no live database writes by default.
venv/Scripts/python.exe -m unittest discover -p "test_*.py" -v

# Synthetic engine comparisons: no DB writes or AI service required.
venv/Scripts/python.exe validate_prototype.py

# Opt-in isolated real PostgreSQL and AI integration checks.
$env:RUN_POSTGRES_TESTS = "1"
$env:RUN_WORKFLOW_TESTS = "1"
$env:RUN_AI_TESTS = "1"
$env:RUN_SCALE_TESTS = "1"
$env:AUTH_COOKIE_SECURE = "false"
venv/Scripts/python.exe -m unittest discover -p "test_*.py" -v
```

The live suites create unique temporary accounts and fixture records. They sign
in through the real login endpoint, carry the session and CSRF token, and clean up
only their own IDs. Existing administrator credentials are never requested or
changed. Do not interrupt a live test during cleanup. If interrupted, identify
that run's exact IDs before removing anything; never delete all project records.

Start the backend on port 8000. From `frontend`:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run test:live
```

The live React test renders the production bundle in JSDOM, sends real HTTP
requests, creates equipment through the form, assesses it, creates a reviewed
task and technician, compares/ confirms a schedule, and checks persistence after
reload. It uses a generated temporary coordinator rather than an auth bypass.
`test:workflow:live` is an alias. The pre-authentication scripts (`test-flow`,
`test-scheduling`, `test-live`, `test-workflow-live`) were removed; they remain in
git history.

## Saved evidence

All files below are under `backend/validation`:

- `backend-test-results.txt`: named backend checks and actual test summary.
- `frontend-test-results.txt`, `frontend-lint-results.txt`: build/tests/lint.
- `prototype-results.json`: full 50/100/200-record synthetic scenario inputs,
  outputs, baseline, independent checks and reported model metadata.
- `prototype-summary.csv`: compact measured comparison table.
- `scale-api-results.json`: real PostgreSQL inventory retrieval at 50/100/200
  fixture records, API timings, response sizes and cleanup verification.
- `authenticated-ui-results.json`: real React/HTTP/DB/AI workflow, model version,
  sample recommendation, request timings and scheduling results.
- `ui-comparison-preview.jpg`: layout screenshot from the explicitly labelled
  read-only sample page. Its illustrative numbers are not validation evidence.

The 200-record engine case uses two **independent** 100-task cohorts because the
validated run cap remains 100. Their availability is reused for independent
experiments; the outputs must not be combined as a single conflict-free day.
The database scale test really stores/retrieves up to 200 fixture records. It
does not claim 200 simultaneous model assessments or bookings.

## Short final-demo scenario

1. Sign in as a coordinator. Show the equipment list and create a clearly named
   demo ventilator, such as `DEMO-FINAL-VENT-01`, with a unique serial number.
2. Use Getinge / SERVOi, in-service date 2020-01-01, 20 repairs and CAD 10000
   historical cost as an illustrative test input. Explain that it is synthetic.
3. Open Assessment. Show repair intensity, percentile meaning, recommendation,
   model version/history snapshot and limitations. Replacement remains a reviewed
   recommendation, never an automatic decision.
4. In Maintenance create a 60-minute task with qualification `Demo Ventilator`.
   Keep AI assessment enabled. If demonstrating interval checks, enter an agreed
   last-service date and interval; otherwise explain the missing interval label.
5. Create a demo technician with that qualification and tomorrow's Toronto
   availability 09:00–12:00. Scheduling: select only the demo task and that date.
6. Generate and review assignment, priority explanation, baseline, independent
   checks and any late/unassigned work. Download the JSON before confirming.
7. Confirm, reload and show the same assignment in equipment maintenance details.
   Show recorded maintenance history separately from pending/scheduled work.
8. Show a missing-qualification or insufficient-availability case and its clear
   unassigned reason. Finish with the measured CSV and known limitations.

Capture screenshots of the equipment record, assessment, baseline comparison,
unassigned reason and confirmed assignment from this prepared demo. Do not present
the read-only sample screenshot as a real operational test result.

## Remaining external work

- The database team may later normalize recurring service policies and approved
  interval sources. No schema edit is required for the per-task interval inputs
  implemented here. This does not automatically generate recurring tasks.
- The AI team still needs independent representative outcome data and valid model
  evaluation. Classifier metrics cannot be supplied by frontend/backend changes.
- Validate multi-day policy outcomes, approved labour/parts costs, measured downtime
  and actual completed work before claiming operational improvements.
