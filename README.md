# Biomedical Maintenance System

**Account setup required:** this version requires the manual authentication database tasks and first administrator described in [backend/ACCESS_SETUP.md](backend/ACCESS_SETUP.md). Those changes have not been applied to RDS.

React + FastAPI + PostgreSQL equipment management with the team's existing
AI maintenance-cost service. The application now stores equipment identity, location/status and lifecycle
metadata. The training export retains the original eight lifecycle dataset columns.

## Data contract

| Column | API / database name | Behavior |
| --- | --- | --- |
| Asset Tag | asset_tag | Entered; required, unique text, max 50 |
| Serial No. | serial_number | Entered; required, unique text, max 100; leading zeros preserved |
| Manufacturer | manufacturer | Entered; required text, max 100; use consistent spelling |
| In-Service Date | in_service_date | Entered date; strictly before today in Toronto |
| Age (years) | age_years | Calculated, read-only, displayed to 2 decimals |
| Repair Events (n) | repair_events | Entered non-negative integer; defaults to 0 |
| Total Historical Cost (CAD $) | total_historical_cost | Entered non-negative NUMERIC(12,2); defaults to 0 |
| Avg. Annual Cost (CAD $) | avg_annual_cost | Calculated, read-only, displayed to 2 decimals; null/N/A for zero age |

PostgreSQL generates an internal UUID (`equipment_id`, exposed as `id`) and
maintains creation/update timestamps. The API also returns `calculated_as_of`,
the reference date used for its calculated values. These are metadata, not extra
user-entered dataset fields.

Create/update requests accept the six lifecycle source fields and optional
operational metadata. Required fields remain asset_tag, serial_number, manufacturer
and in_service_date. Repair count and historical cost default to zero. Calculated
age/annual average, reference remaining life and calculated_as_of are read-only.

## Expanded operational contract

The reviewed data definition is implemented with these documented choices:

| Field | Decision |
| --- | --- |
| id | Stable public UUID; maps to existing equipment_id in PostgreSQL |
| model_number / model_name | Separate optional text fields, max 100 each |
| device_type | Optional controlled value: Ventilator, Infusion Pump, Patient Monitor, Defibrillator, Other |
| firmware_version | Optional text, max 50 |
| description | Optional text, max 2000 |
| department / department_code | Optional department name (100) and code (30); codes remain text |
| location | Separate optional physical location/room (200), avoiding ambiguity with department |
| status | Optional Operational, Under Maintenance or Inactive; unknown stays null |
| replacement_cost | Optional non-negative CAD amount, maps to assumed_replacement_cost in RDS |
| expected_useful_life | Optional positive integer reference lifespan in years |

The form loads dropdowns from GET /api/equipment/options, so the API is the source
of allowed values. Blank optional text is normalized to null, not invented. The
compact table shows identification/type/department/status; details show all fields.
A full PUT replaces the editable record: omitted optional metadata is reset to null.

Reference remaining life is max(expected useful life minus unrounded age, 0), shown
to two decimals. It is explicitly a supplied-life arithmetic reference, not an AI
remaining-life prediction or a clinical clearance. Zero replacement cost is valid
recorded data, but a maintenance/replacement ratio requires a positive denominator.

Scheduling tasks, priority, qualifications, durations and technician availability
remain separate operational requirements; this metadata change does not implement
the scheduling prototype.

## Calculations

`backend/app/calculations.py` is the authoritative calculation logic:

```text
reference date = today's calendar date in America/Toronto
unrounded age = elapsed calendar days / 365.25
age_years = unrounded age rounded to 2 decimal places
avg_annual_cost = total historical cost / unrounded age, rounded to 2 decimals
```

No division uses rounded age. A one-day-old device can display 0.00 years while
still having a valid annual average. If elapsed age is truly zero, annual average
is null (N/A in the UI), and assessment returns a clear 422 error. New requests
must use an in-service date before today; zero handling also protects legacy data.

The frontend provides immediate read-only previews when date/cost changes. Saved
responses, inventory rows, details, exports and assessments use backend results.
Refreshing records recalculates them using the current reference date. Historical
average annual cost is separate from the AI-estimated annual maintenance cost.
Currency is CAD; money is stored using Decimal/NUMERIC, never a floating-point DB
column. API decimal outputs are strings to retain exact decimal values.

## Run the app

Use three PowerShell terminals. Existing local environments are already set up.
Commands below start from the repository root unless noted.

### Backend: port 8000

```powershell
Set-Location backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### AI service: port 8001

```powershell
.\ai.\venv\Scripts\python.exe -m uvicorn ai.app.main:app --reload --host 127.0.0.1 --port 8001
```

### Frontend: port 5173

```powershell
Set-Location frontend
npm.cmd run dev
```

Open http://localhost:5173. Stop each server with Ctrl+C. Backend API documentation
is at http://localhost:8000/docs. The AI model is already in ai/models/; retraining
is not required to run the app.

## Initial setup on another machine

Prerequisites: Python 3.10+ and a Node version supported by the locked Vite release
(22.12+ or a newer supported LTS). From the repository root:

```powershell
python -m venv backend/venv
backend/venv/Scripts/python.exe -m pip install -r backend/requirements.txt
python -m venv ai/.venv
ai/.venv/Scripts/python.exe -m pip install -r ai/requirements.txt
npm.cmd --prefix frontend ci
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
Invoke-WebRequest https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -OutFile backend/global-bundle.pem
```

Enter the database password locally in backend/.env. Never commit it. Required
settings: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD and DB_SSLROOTCERT. The
example contains the supplied RDS endpoint, port 5432 and database/user names.
Connections always use verify-full TLS. Relative CA paths resolve from backend/.
AI_SERVICE_URL defaults to http://127.0.0.1:8001. Optional frontend/.env can set
VITE_API_URL; restart Vite after changing it. Both localhost and 127.0.0.1 frontend
origins on port 5173 are allowed by CORS.

### Background scheduling switch

The AI service reads `SCHEDULER_ENABLED` from the process environment or
`backend/.env`, which its database module loads. Process environment values take
precedence. The setting defaults to `false`; use `true` or `false` and restart the
AI service after changing it.

With `false` (or no setting), startup performs no overdue-schedule sweep and
registers no hourly job. Health, predictions and fleet summaries remain available.
With `true`, startup sweeps overdue schedules and registers optimization every
60 minutes. Shutdown stops the scheduler only when it was enabled.

This switch controls background work, not database permissions. Manual
`POST /api/ai/optimize-schedule` still sweeps and saves schedules, and equipment
CRUD can still write. Use a development database for local write tests. Enable
background scheduling in only one service process to avoid duplicate jobs.

From the repository root, disable background scheduling explicitly with:

```powershell
$env:SCHEDULER_ENABLED = "false"
```

Scheduler lifecycle tests mock database writes and the background scheduler:

```powershell
ai/.venv/Scripts/python.exe -m unittest discover -s ai -p test_scheduler_lifecycle.py
```

## Database setup and migration

For an existing RDS database, from backend/:

```powershell
.\venv\Scripts\python.exe -m app.migrate
```

The runner applies migration 002 (calculated metrics) and migration 003 (equipment
metadata) in one transaction. Migration 003 adds missing optional columns and enum,
replacement-cost and reference-life checks. Existing columns and records are
preserved, including prior manual snapshots. It does not add fake type, status,
location or lifespan values to existing records. Both migrations are re-runnable.
The historical snapshot-required migration 001 is not rerun.

The configured RDS has been migrated and the existing record was checked unchanged.
An unrecognized legacy enum or invalid cost/life value causes rollback; resolve the
source data explicitly before retrying. Migration does not run on API startup.
For a fresh database, run database/equipment.sql, then the migration runner if
needed. Do not drop the shared table to change the application schema.

## API

| Method | Path | Result |
| --- | --- | --- |
| GET | /api/health | API process responds |
| GET | /api/ready | Checks database connectivity and source columns |
| GET | /api/equipment/options | Shared device types, statuses, years and CAD units |
| GET | /api/equipment | Records with calculated metrics and reference date |
| GET | /api/equipment/export | Dated training CSV containing all eight dataset columns |
| GET | /api/equipment/{uuid} | One record, or 404 |
| POST | /api/equipment | Creates equipment; returns 201 and generated UUID/calculations |
| PUT | /api/equipment/{uuid} | Updates source fields; returns recalculated record |
| DELETE | /api/equipment/{uuid} | Deletes equipment; returns 204 |
| GET | /api/equipment/{uuid}/assessment | Current AI-assisted assessment |
| GET | /api/maintenance-schedules | Fetches all equipment entries in the maintenance scheduler |
| GET | /api/ai/optimize-schedule | Triggers the maintenance scheduler to calculate dates for new equipment and 
                                    optimize dates for existing equipment that will be serviced within 14 days |
| POST | /api/ai/predict | Predicts annual cost and repair intensity for one ventilator; see below |

Example creation body:

```json
{
  "asset_tag": "CED-DEMO-001",
  "serial_number": "006412",
  "manufacturer": "Getinge",
  "model_number": "SERVOi",
  "model_name": "SERVOi",
  "device_type": "Ventilator",
  "department": "ICU",
  "department_code": "001",
  "location": "Room 12",
  "status": "Operational",
  "replacement_cost": "20000.00",
  "expected_useful_life": 25,
  "in_service_date": "2003-03-03",
  "repair_events": 19,
  "total_historical_cost": "9678.12"
}
```

The response adds id, calculated_as_of, age_years, avg_annual_cost and
reference_remaining_life_years. A full PUT
requires all four identifying/date fields; omitted repair count/cost reset to the
agreed zero defaults. Duplicates return 409; invalid input returns 422; missing
records return 404; database/AI connection failures return 503. Database errors
log categories without raw credentials. Assessment disables caching and retains
the old POST route as a deprecated compatibility alias.

### POST /api/ai/predict

Predicts cost and repair intensity for one ventilator. `device_type` is
required and must be `"Ventilator"`. Unknown fields are rejected with 422.

Request:

```json
{
  "device_type": "Ventilator",
  "manufacturer": "Getinge SERVOi",
  "age_years": 23.38,
  "repair_events": 19
}
```

Other optional fields are listed in `AssetIn` in `ai/app/main.py`.

## Training exports

Use Export training CSV beside Refresh table. The backend calculates every row
using one reference date and returns exactly eight CSV columns. The date is in the
filename and X-Calculated-As-Of response header. Keep the original dated file when
training: its derived values stay frozen even as live records age. A later export
may have different metrics and updated source history; it is not a reconstruction
of a previous dataset. CSV serial numbers should be imported as text in spreadsheet
software to preserve leading zeros. Zero-age annual average exports as a blank
numeric value rather than a false zero.

## AI assessment

Assessment requires a recorded device_type of Ventilator. Missing type and all
other types return clear 422 responses before the AI call; equipment CRUD supports
all allowed types. The details screen disables assessment and explains why. For an
existing record, use Edit to supply its verified type; no automatic type guesses
were made during migration.

FastAPI sends manufacturer/model, explicit type, unrounded calculated age, repair
count, historical cost, optional replacement cost and reference useful life to the
AI service. The service also enforces ventilator scope and finite numeric inputs.
Historical annual average remains the training target, not a model input.

The trained cost model and metadata were not changed or retrained. Its existing
categories are Getinge SERVOi and Draeger V500. An explicit, case-insensitive match
combines recorded manufacturer with model name/number when appropriate (including
Draeger/Dräger spelling). Legacy combined labels still work. model_input_category
reports the selected label in the response and UI. Unknown labels retain the
model's existing ignored-manufacturer warning rather than being mapped arbitrarily.
Future retraining can use the dated eight-column export and its recorded vocabulary.

The teammate's replacement-reference dictionary is preserved; currently its costs
are unconfirmed/null. A supplied replacement cost takes precedence. Zero never
triggers a substitute assumption and yields no ratio. Confirmed reference fallbacks
retain their provenance warning. The API maps replacement_cost to the AI client's
assumed_replacement_cost, avoiding duplicate database columns. Expected useful life
produces reference arithmetic/context only; reaching it gives a review notice, not
a predicted failure date or automatic replacement decision.

The existing model estimates annual maintenance cost from synthetic ventilator
history. Risk means relative repair intensity, not failure probability or clinical
safety. MAE is typical validation error, not a confidence interval. Cost projections
remain annual estimate times five. Results are on demand, not saved to equipment.
CRUD works when the AI service is offline. The prior unresolved merge markers in
the AI service were resolved by retaining both ratio logic and cent rounding.

### Assessment presentation and range checks

The screen distinguishes recorded historical average cost from model-estimated
annual cost. `repair_rate_percentile` is the clearer response alias for the legacy
`risk_score` (both remain 0 to 1); the UI displays it as a percentage. A percentile
of 0% means below the observed fleet repair rates, not zero failure risk.

The AI prediction response includes training_repair_rate_min/max from the loaded
model metadata. The backend compares the actual repair rate against these bounds
at the metadata's six-decimal precision and adds a notice for extrapolation. An
older AI response without these fields gets an explicit range-unavailable notice.
No thresholds are hardcoded and no model weights or training data were changed.

Annual cost is rounded to cents first; the projection is that same annual amount
multiplied by the horizon. Thus CAD $299.50/year over five years displays CAD
$1,497.50 consistently. This is a presentation policy, not a new forecasting model.

Assessment has explicit not-assessed/loading/complete/error states, Reassess and
Retry controls, one scope note, and deduplicated neutral informational notices.
Only actual request errors use error styling. Restart backend and AI service after
updating to ensure the range metadata is available.

## Code map

```text
frontend/src/
  App.jsx                                     Page layout and refresh coordination
  api.js                                      Requests, timeouts and error parsing
  useApi.js                                   Cancellable GET requests and refresh state
  equipmentFields.js                          Eight display fields, six source fields, previews
  components/EquipmentForm.jsx                Six inputs, two read-only calculated previews
  components/EquipmentTable.jsx               Inventory, export, retry and delete confirmation
  components/EquipmentDetails.jsx             Recorded values, calculation date and assessment
  components/MaintenanceScheduleCalender.jsx  Calendar that displays all equipment scheduled for maintenance
backend/app/
  main.py                                     Routes, CSV export and safe error responses
  schemas.py                                  Source-only requests and computed response fields
  calculations.py                             Toronto date, unrounded age, annual average
  database.py                                 Environment settings and verified TLS connection
  repository.py                               Parameterized SQL for source values only
  assessment.py                               AI client and recommendation mapping
  migrate.py                                  Explicit current database migration
```

## Tests

From the repository root:

```powershell
backend/venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py'
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend test
```

With RDS configured and the AI server running, enable live backend tests:

```powershell
$env:RUN_POSTGRES_TESTS='1'
$env:RUN_AI_TESTS='1'
backend/venv/Scripts/python.exe -m unittest discover -s backend -p 'test_*.py'
Remove-Item Env:RUN_POSTGRES_TESTS, Env:RUN_AI_TESTS
```

With backend/AI servers running, `npm.cmd --prefix frontend run test:live` tests
React entry through real HTTP, persistence, calculations, export, AI, editing and
deletion. Live tests create isolated records and remove only their own fixtures.
Tests cover defaults, strict dates, zero age, unrounded division, recalculation,
leading-zero identifiers, safe errors and ignoring old snapshot columns.

## Troubleshooting

- RDS timeout: check public-IP security-group access, routing or VPN.
- Missing configuration or CA: check backend/.env and DB_SSLROOTCERT.
- Schema mismatch: apply migrations 002 and 003; readiness never changes the database.
- AI unavailable: start its server on port 8001 with its own environment.
- Port in use: stop the old server before starting another on that port.
- A lost save response: refresh inventory before retrying. Unique asset tags and
  serial numbers protect inserts from duplicate identifiers.

The AI response contract/rounding test can be run from ai/ with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p test_prediction.py
```

## Week 10 saved maintenance workflow

Equipment details can create a maintenance task from a fresh assessment with an
explained priority, or an explicit manual priority when AI is unavailable. Add
technicians and dated availability in **Saved maintenance workflow**, generate a
preview from saved tasks and confirm it to reserve resources. Saved assignments
survive reloads. Start/complete/cancel actions retain status notes and service history.

Apply migration 004 with the normal backend migration command before using these
views. See [backend/WORKFLOW.md](backend/WORKFLOW.md) for setup, routes, priority
policy, concurrency rules, live tests and measurement limits. The legacy automatic
calendar and advanced unsaved preview remain separate views.

## Authorized service workspace

The UI now requires sign-in and uses separate sidebar pages. Complete the manual
account database tasks in [backend/ACCESS_SETUP.md](backend/ACCESS_SETUP.md) before
running it. No default accounts exist. The prepared auth SQL is not applied by
the regular migration runner. Backend access fails closed until account storage
is ready. Use the same-origin Vite /api proxy and local cookie settings described
in that guide.
