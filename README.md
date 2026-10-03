# Biomedical Maintenance System

A senior engineering project for biomedical equipment maintenance and replacement decision support. This first phase proves that a React frontend can communicate with a Python FastAPI backend.

## What works now

- Backend health status and message displayed in the browser.
- A simple table of three hard-coded devices: Infusion Pump, Patient Monitor, and Defibrillator.
- Independent loading and error messages for the two API requests.

The selected stack is **React + Vite, FastAPI, PostgreSQL, and Python AI**. Only React and FastAPI are implemented. PostgreSQL, AI recommendations, scheduling, authentication, technician management, and advanced UI are future work. Sample equipment is demonstration data, not a live inventory.

## Folders

```text
frontend/             React application (JavaScript), built with Vite
backend/
  app/main.py         FastAPI application and the two API routes
  app/routes/         Placeholder for future route organization
  app/models/         Placeholder for future data models
  requirements.txt    Pinned Python dependencies
ai/                   Future Python AI work; placeholder only
scheduler/            Future scheduling work; placeholder only
database/             Future PostgreSQL work; placeholder only
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
| GET | /api/equipment | A JSON array of exactly three devices with id, name, type, location, and status |

The frontend calls these endpoints directly. CORS permits the frontend origin `http://localhost:5173`.

## Check the setup

With the backend running, use PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
Invoke-RestMethod http://localhost:8000/api/equipment
```

Open the frontend and confirm the status says `ok` and the table has three rows. Stop the backend, then reload the page: clear error messages should replace the results.

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
