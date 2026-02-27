# api.py
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from pathlib import Path
import uuid
import json
import traceback
from typing import Optional
# ✅ Import your existing pipeline entrypoint
# Adjust this import to match how your code runs today.
# Example: if you currently run: python main.py --session ...,
# create a function in main.py like run_pipeline(...) and import it here.
from main import run_pipeline  # <-- you may need to create this function

app = FastAPI(title="OpenCap Core API")

JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(exist_ok=True)

class RunRequest(BaseModel):
    # the two inputs are what you receive from the website
    session_path: str            # e.g. "Data/my_session"
    output_dir: Optional[str] = None

def job_file(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"

def write_job(job_id: str, data: dict):
    job_file(job_id).write_text(json.dumps(data, indent=2))

def read_job(job_id: str) -> dict:
    p = job_file(job_id)
    if not p.exists():
        return {"error": "job_not_found"}
    return json.loads(p.read_text())

def run_job(job_id: str, req: RunRequest):
    try:
        write_job(job_id, {"status": "running", "request": req.model_dump()})

        out = run_pipeline(
            session_path=req.session_path,
            output_dir=req.output_dir,
        )

        # out can be a path, dict, etc. Keep it JSON-friendly.
        write_job(job_id, {"status": "done", "result": out})

    except Exception as e:
        write_job(job_id, {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        })

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/jobs")
def create_job(req: RunRequest, background: BackgroundTasks):
    job_id = str(uuid.uuid4())
    write_job(job_id, {"status": "queued", "request": req.model_dump()})
    background.add_task(run_job, job_id, req)
    return {"job_id": job_id}

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    return read_job(job_id)
