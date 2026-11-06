# Frontend

React + Vite client for the Biomedical Maintenance System.

See the repository's [main README](../README.md) for Windows setup, backend commands, API details, and troubleshooting.

From this folder, use `npm.cmd run dev` to start at http://localhost:5173, `npm.cmd run build` to build, and `npm.cmd run lint` to check the code. Start the FastAPI backend separately to load real API results.


## Scheduling prototype

Use the Scheduling prototype link at the top of the app. Select an existing saved
equipment item under Equipment for demo inputs and click Load demo scheduling
inputs. This loads three tasks, two demo technicians, split availability and one
known busy window, linked to the selected equipment UUID.

Change priorities, whole-minute durations, required qualifications, technician
qualification labels, availability or known bookings as needed. Click Generate
schedule preview. The page displays proposed assignments and separate unassigned
tasks with reasons. Changing inputs or refreshing changed equipment invalidates
an old result; regenerate to obtain a current preview.

The backend checks qualifications and technician/equipment conflicts. All displayed
times use Toronto time. The result is a draft and is not saved or booked. Equipment
comes from PostgreSQL; task/staff data is explicitly entered or labelled as demo.
No personnel credentials or clinical priority are inferred from the AI result.

npm.cmd test builds and runs both equipment/assessment and scheduling UI tests.
The live test also verifies the schedule against real saved equipment.
See backend/SCHEDULING.md in the repository for the endpoint and constraint details.
