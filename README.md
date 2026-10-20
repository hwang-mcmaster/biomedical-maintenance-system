# Biomedical Maintenance System

A senior engineering project for biomedical equipment maintenance and replacement decision support. This first phase proves that a React frontend can communicate with a Python FastAPI backend.

## What works now

- React equipment form with required-field validation, saving state, and errors.
- Database-backed GET /api/equipment and POST /api/equipment.
- PostgreSQL generates IDs; the table refreshes after a successful save.
- Status values: Operational, Under Maintenance, Inactive.

## Week 4 database setup

From backend/ in PowerShell:

```powershell
Copy-Item .env.example .env
Invoke-WebRequest https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -OutFile global-bundle.pem
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Edit backend/.env and enter DB_PASSWORD locally. Do not commit this file.
DB_SSLROOTCERT comes from the environment; relative paths resolve from backend/.
Connections always use sslmode=verify-full. The example contains the supplied RDS
host, port, database and username; the password is deliberately blank.

Have the database member inspect the existing equipment table before running
`database/equipment.sql`. It creates a missing table and leaves an existing table
unchanged. Existing tables must have id (generated integer), name, type, location,
and status columns matching the API. Existing `Maintenance Due` values must be
reviewed and mapped to the agreed statuses before use.

With psql installed, from backend/ (password is prompted, never placed in a command):

```powershell
psql "host=biomedical-maintenance-db.c9o8kaiim0dv.ca-central-1.rds.amazonaws.com port=5432 dbname=biomedical_maintenance user=postgres sslmode=verify-full sslrootcert=./global-bundle.pem" -W -f ../database/equipment.sql
```

Allow your computer's public IP in the RDS security group on port 5432 and ensure
RDS is reachable from your network. No database setup runs automatically on API startup.

## Folders

```text
frontend/             React application (JavaScript), built with Vite
backend/
  app/main.py         FastAPI application and API routes
  app/database.py     Environment configuration and verified TLS connection
  app/schemas.py      Request and response validation
  app/routes/         Placeholder for future route organization
  app/models/         Placeholder for future data models
  requirements.txt    Pinned Python dependencies
ai/                   Future Python AI work; placeholder only
scheduler/            Future scheduling work; placeholder only
database/             Equipment table SQL setup
docs/                 Future project documentation; placeholder only
```

## Prerequisites

- Node.js 22.12+ (or a newer supported LTS release) with npm.
- Python 3.10+ with pip and venv (this project was verified with Python 3.12).
- Two terminal windows. The commands below use Windows PowerShell.

Check installation with `node --version`, `npm.cmd --version`, and `python --version`. If Python is available only through the Windows launcher, replace `python` with `py` when creating the environment.

## Initial setup and run on Windows

### Terminal 1: backend

```powershell
Set-Location "C:\Users\Gordon\Desktop\Class Material\fall 2026\Senior Eng Project\Git repo\biomedical-maintenance-system\backend"
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If `python` and `py` are unavailable on this computer, Codex's bundled interpreter used during setup is an alternative while installed:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv venv
```

For a portable setup on another computer, install Python and use the normal commands above. Virtual environments depend on their original Python installation; recreate venv if that installation moves or is removed.

Activation is optional: `.\venv\Scripts\Activate.ps1` in PowerShell or `venv\Scripts\activate.bat` in Command Prompt. The direct interpreter commands above work without activation or changing PowerShell execution policy.

### Terminal 2: frontend

```powershell
Set-Location "C:\Users\Gordon\Desktop\Class Material\fall 2026\Senior Eng Project\Git repo\biomedical-maintenance-system\frontend"
npm.cmd install
npm.cmd run dev
```

Open **http://localhost:5173**. Keep both terminals running. Press Ctrl+C in each to stop its server. `npm.cmd` works in PowerShell even if script execution policy blocks `npm.ps1`; plain `npm` also works where permitted.

### Later runs

From backend/, run only:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

From frontend/, run only:

```powershell
npm.cmd run dev
```

Create the environment once. Install dependencies on initial setup or when dependency files change. For a fresh frontend installation using the lockfile, `npm.cmd ci` is also available.

## API

Backend base URL: http://localhost:8000. Interactive documentation: http://localhost:8000/docs.

| Method | Path | Result |
| --- | --- | --- |
| GET | /api/health | `{"status":"ok","message":"Biomedical Maintenance API is running"}` |
| GET | /api/equipment | Database records with id, name, type, location, and status |

| POST | /api/equipment | Saves name/type/location/status; returns HTTP 201 and the record with generated ID |

The frontend calls these endpoints directly. CORS permits the frontend origin `http://localhost:5173`.

## Check the setup

With the backend running, use PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod http://localhost:8000/api/equipment
```

Open the frontend and confirm the status says `ok`. Add a device and check the generated ID and refreshed table. Reload to confirm persistence. Submit blank fields to check validation. A database failure returns HTTP 503; health reports only that the API process is running. Stop the backend, then reload the page: clear error messages should replace the results.

From frontend/, check the code and production build:

```powershell
npm.cmd run lint
npm.cmd run build
```

## Troubleshooting

- **Missing Node or Python:** install the prerequisite, reopen your terminal, and check its version. Try `py` if `python` is missing, or use the bundled interpreter described above.
- **Port already in use:** stop the other program using port 8000 or 5173. Vite intentionally exits instead of silently changing ports.
- **Backend unavailable:** start it from backend/, confirm http://localhost:8000/api/health opens, then reload the frontend.
- **Browser blocks requests:** use http://localhost:5173, matching the allowed CORS origin. The frontend URL http://127.0.0.1:5173 is a different origin.
- **Cannot import app.main:** run the backend start command from backend/, not the repository root.

Reference documentation: [Vite](https://vite.dev/guide/) and [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/).

## Automated Week 4 checks

From the repository root:

```powershell
backend/venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/venv/Scripts/python.exe -m unittest discover -s backend -p test_equipment.py
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

API tests use a simulated database connection. The React DOM test uses simulated API
responses to check blank fields, saving state, duplicate prevention, successful save,
form reset, table refresh, and connection errors. These do not prove RDS persistence.
For a live check, start both servers, add equipment, then reload and confirm it remains.
A TCP timeout to RDS requires checking its security group, public accessibility or VPN,
and network routing before database authentication can be verified.
