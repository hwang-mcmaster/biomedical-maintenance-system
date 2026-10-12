from fastapi import FastAPI

app = FastAPI(title="Biomedical Maintenance AI Service")


@app.get("/api/ai/health")
def health():
    return {"status": "ok", "message": "AI service is running"}
