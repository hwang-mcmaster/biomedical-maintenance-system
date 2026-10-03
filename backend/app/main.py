from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Biomedical Maintenance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "message": "Biomedical Maintenance API is running",
    }


@app.get("/api/equipment")
def equipment():
    return [
        {"id": 1, "name": "Infusion Pump", "type": "Infusion", "location": "ICU", "status": "Operational"},
        {"id": 2, "name": "Patient Monitor", "type": "Monitoring", "location": "Emergency Department", "status": "Maintenance Due"},
        {"id": 3, "name": "Defibrillator", "type": "Emergency", "location": "Operating Room", "status": "Operational"},
    ]
