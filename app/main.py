# app/api.py
import os
import uuid
import json
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

APP_ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = Path(os.environ.get("JOBS_DIR", "/tmp/axon_jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# ✅ Point to the CLI script you showed (the file with __main__ + argparse).
# Adjust this path to where that file actually lives in your repo.
# Common cases:
#   - if it's at repo root: APP_ROOT / "main.py"
#   - if it's in app/:      APP_ROOT / "app" / "main.py"
OPENCAP_SCRIPT = APP_ROOT / "app" / "main.py"

app = FastAPI(title="AxonAI OpenCap Runner", version="0.2.0")


class RunRequest(BaseModel):
    # Match your main.py CLI: --session_path required, --output_dir optional :contentReference[oaicite:1]{index=1}
    session_path: str = Field(..., description="Session path (as expected by main.py)")
    output_dir: Optional[str] = Field(default=None, description="Optional output directory")


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
        "pid": job_dir / "pid.txt",
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

    # Build the command that matches main.py's argparse :contentReference[oaicite:2]{index=2}
    cmd = [
        "python",
        str(OPENCAP_SCRIPT),
        "--session_path", req.session_path,
    ]
    if req.output_dir:
        cmd += ["--output_dir", req.output_dir]

    # ✅ Ensure we always record exit code.
    # We do this by running a small shell wrapper that writes exitcode.txt.
    # (Using bash -lc keeps it simple and reliable.)
    exitcode_path = str(paths["exitcode"])
    wrapped_cmd = " ".join([subprocess.list2cmdline(cmd), f"; echo $? > {subprocess.list2cmdline([exitcode_path])}"])

    with open(paths["stdout"], "wb") as out, open(paths["stderr"], "wb") as err:
        p = subprocess.Popen(
            ["bash", "-lc", wrapped_cmd],
            cwd=str(APP_ROOT),
            stdout=out,
            stderr=err,
            env=os.environ.copy(),
        )

    paths["pid"].write_text(str(p.pid))
    return {"job_id": job_id, "status_url": f"/jobs/{job_id}"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    paths = _job_paths(job_id)
    if not paths["dir"].exists():
        raise HTTPException(status_code=404, detail="job_id not found")

    # If exit code recorded, we’re done
    if paths["exitcode"].exists():
        exit_code = int(paths["exitcode"].read_text().strip())
        return {
            "job_id": job_id,
            "status": "succeeded" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "stdout_log": str(paths["stdout"]),
            "stderr_log": str(paths["stderr"]),
        }

    # Otherwise, check if PID is alive
    if paths["pid"].exists():
        pid = int(paths["pid"].read_text().strip())
        alive = Path(f"/proc/{pid}").exists()
        return {"job_id": job_id, "status": "running" if alive else "finished_pending_exitcode"}

    return {"job_id": job_id, "status": "unknown"}