# app/api.py
import os
import uuid
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

APP_ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = Path(os.environ.get("JOBS_DIR", "/tmp/axon_jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)

OPENCAP_SCRIPT = APP_ROOT / "opencap-main.py"   # adjust if your file lives elsewhere

app = FastAPI(title="AxonAI OpenCap Runner", version="0.1.0")


class RunRequest(BaseModel):
    # Put whatever your opencap-main.py expects
    # Example placeholders:
    subject_id: str = Field(..., description="Patient / subject identifier")
    trial_name: str = Field(..., description="Trial name")
    input_video_path: str = Field(..., description="Path inside container (or mounted volume)")
    extra_args: Optional[Dict[str, Any]] = Field(default=None, description="Extra script args")


@app.get("/health")
def health():
    return {"status": "ok"}


def _job_paths(job_id: str):
    job_dir = JOBS_DIR / job_id
    return {
        "dir": job_dir,
        "stdout": job_dir / "stdout.log",
        "stderr": job_dir / "stderr.log",
        "meta": job_dir / "meta.json",
        "exitcode": job_dir / "exitcode.txt",
    }


@app.post("/jobs")
def create_job(req: RunRequest):
    if not OPENCAP_SCRIPT.exists():
        raise HTTPException(status_code=500, detail=f"Missing script: {OPENCAP_SCRIPT}")

    job_id = uuid.uuid4().hex
    paths = _job_paths(job_id)
    paths["dir"].mkdir(parents=True, exist_ok=True)

    # Save request for traceability
    paths["meta"].write_text(json.dumps(req.model_dump(), indent=2))

    # Build command line for your script.
    # IMPORTANT: adapt these flags to match your opencap-main.py CLI.
    cmd = [
        "python",
        str(OPENCAP_SCRIPT),
        "--subject-id", req.subject_id,
        "--trial-name", req.trial_name,
        "--input-video", req.input_video_path,
    ]

    # Optional: pass extra args (key->value) as --key value
    if req.extra_args:
        for k, v in req.extra_args.items():
            cmd += [f"--{k}", str(v)]

    # Start in background (non-blocking).
    # We redirect logs to files.
    with open(paths["stdout"], "wb") as out, open(paths["stderr"], "wb") as err:
        p = subprocess.Popen(
            cmd,
            cwd=str(APP_ROOT),
            stdout=out,
            stderr=err,
            env=os.environ.copy(),
        )

    # Save PID so we can query status later
    (paths["dir"] / "pid.txt").write_text(str(p.pid))

    return {"job_id": job_id, "status_url": f"/jobs/{job_id}"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    paths = _job_paths(job_id)
    if not paths["dir"].exists():
        raise HTTPException(status_code=404, detail="job_id not found")

    pid_file = paths["dir"] / "pid.txt"
    exitcode_file = paths["exitcode"]

    # If exit code recorded, we’re done
    if exitcode_file.exists():
        exit_code = int(exitcode_file.read_text().strip())
        status = "succeeded" if exit_code == 0 else "failed"
        return {
            "job_id": job_id,
            "status": status,
            "exit_code": exit_code,
            "stdout_log": str(paths["stdout"]),
            "stderr_log": str(paths["stderr"]),
        }

    # Otherwise, check if PID is alive
    if pid_file.exists():
        pid = int(pid_file.read_text().strip())
        alive = Path(f"/proc/{pid}").exists()
        if alive:
            return {"job_id": job_id, "status": "running"}
        else:
            # Process ended but we didn't capture exit code yet (best-effort)
            # Mark unknown as failed-ish and ask user to check logs
            return {
                "job_id": job_id,
                "status": "finished_unknown",
                "message": "Process ended; check logs. Consider adding an exit-code writer.",
                "stdout_log": str(paths["stdout"]),
                "stderr_log": str(paths["stderr"]),
            }

    return {"job_id": job_id, "status": "unknown"}