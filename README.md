# Biomedical Maintenance System

React + FastAPI + PostgreSQL equipment management with the team's existing
AI maintenance-cost service. The dataset has eight displayed columns: six
entered source fields and two calculated values.

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

Create/update bodies accept only the six source fields. Requests containing
age_years, avg_annual_cost, calculated_as_of, or old name/type/location/status
fields are rejected. Missing repair count or historical cost defaults to zero;
explicit null or invalid values are rejected. The form starts both at zero and
also treats a cleared optional count/cost as zero when submitting.

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
Set-Location ai
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
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

## Database setup and migration

For an existing RDS database, from backend/:

```powershell
.\venv\Scripts\python.exe -m app.migrate
```

The runner now applies `database/migrations/002_calculated_metrics.sql` in one
transaction. It makes old age/annual-cost snapshot columns optional, restores zero
defaults for repairs/cost, and checks source values/date. It never deletes or
rewrites existing source data or snapshot values. Application queries ignore the
old snapshots, so they cannot override calculated results. Legacy equipment fields
are also preserved as optional columns and are not collected by the app.

Migration 002 is re-runnable and works on both the previous dataset schema and a
fresh source-only schema. It does not rerun historical migration 001, which required
manual snapshots. A failing constraint rolls the migration back; correct invalid
source data through a reviewed change before retrying. Migration never runs
automatically on API startup. It has already been applied to the configured RDS.

For a fresh PostgreSQL database, run `database/equipment.sql` using psql. It creates
only the six source fields plus UUID/timestamps. The existing shared RDS table
must not be dropped/recreated to change the application schema.

## API

| Method | Path | Result |
| --- | --- | --- |
| GET | /api/health | API process responds |
| GET | /api/ready | Checks database connectivity and source columns |
| GET | /api/equipment | Records with calculated metrics and reference date |
| GET | /api/equipment/export | Dated training CSV containing all eight dataset columns |
| GET | /api/equipment/{uuid} | One record, or 404 |
| POST | /api/equipment | Creates equipment; returns 201 and generated UUID/calculations |
| PUT | /api/equipment/{uuid} | Updates source fields; returns recalculated record |
| DELETE | /api/equipment/{uuid} | Deletes equipment; returns 204 |
| GET | /api/equipment/{uuid}/assessment | Current AI-assisted assessment |

Example creation body:

```json
{
  "asset_tag": "CED-DEMO-001",
  "serial_number": "006412",
  "manufacturer": "Getinge SERVOi",
  "in_service_date": "2003-03-03",
  "repair_events": 19,
  "total_historical_cost": "9678.12"
}
```

The response adds id, calculated_as_of, age_years and avg_annual_cost. A full PUT
requires all four identifying/date fields; omitted repair count/cost reset to the
agreed zero defaults. Duplicates return 409; invalid input returns 422; missing
records return 404; database/AI connection failures return 503. Database errors
log categories without raw credentials. Assessment disables caching and retains
the old POST route as a deprecated compatibility alias.

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

Assessment loads saved source fields and calculates unrounded age using the same
reference date. It sends that age, manufacturer, repair count and historical total
to the existing AI service with a five-year projection horizon. Historical annual
average is the training target, not a prediction input. Recommendations are
transparent low/medium/high engineering-review rules layered on model output.

The model remains trained on 24 synthetic ventilators, with manufacturer/model
family categories Getinge SERVOi and Draeger V500. Unknown labels produce warnings;
there is no silent category mapping or retraining. This dataset does not include
device type, so the screen and response ask users to confirm ventilator scope.
Risk means relative repair intensity, not failure probability or clinical safety.
MAE is typical validation error, not a confidence interval. Five-year cost is a
simple annual estimate times five. Results are on demand, not saved to equipment.
CRUD works when the AI service is offline.

## Code map

```text
frontend/src/
  App.jsx                         Page layout and refresh coordination
  api.js                          Requests, timeouts and error parsing
  useApi.js                       Cancellable GET requests and refresh state
  equipmentFields.js              Eight display fields, six source fields, previews
  components/EquipmentForm.jsx    Six inputs, two read-only calculated previews
  components/EquipmentTable.jsx   Inventory, export, retry and delete confirmation
  components/EquipmentDetails.jsx Recorded values, calculation date and assessment
backend/app/
  main.py                         Routes, CSV export and safe error responses
  schemas.py                      Source-only requests and computed response fields
  calculations.py                 Toronto date, unrounded age, annual average
  database.py                     Environment settings and verified TLS connection
  repository.py                   Parameterized SQL for source values only
  assessment.py                   AI client and recommendation mapping
  migrate.py                      Explicit current database migration
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
- Schema mismatch: apply migration 002; readiness never changes the database.
- AI unavailable: start its server on port 8001 with its own environment.
- Port in use: stop the old server before starting another on that port.
- A lost save response: refresh inventory before retrying. Unique asset tags and
  serial numbers protect inserts from duplicate identifiers.
