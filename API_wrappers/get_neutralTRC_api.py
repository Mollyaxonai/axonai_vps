import os
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from utilities.utils_getneutralTRC import neutral_videos_to_augmented_trc

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "Data"


def save_uploaded_video(file: UploadFile, cam_name: str, trial_name: str, trial_id: str) -> Path:
    """
    Save uploaded video to:
    ./Data/Videos/<cam_name>/InputMedia/<trial_name>/<trial_id>.<ext>
    """
    suffix = Path(file.filename).suffix or ".mp4"
    out_dir = DATA_DIR / "Videos" / cam_name / "InputMedia" / trial_name
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{trial_id}{suffix}"

    with out_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return out_path


@app.post("/process-neutral")
async def process_neutral(
    trial_name: str = Form("neutral"),
    trial_id: str = Form("neutral"),
    cam_names: List[str] = Form(...),
    videos: List[UploadFile] = File(...),
    cameras_to_use: Optional[str] = Form("all_available"),
    pose_detector: str = Form("OpenPose"),
    resolution_pose_detection: str = Form("default"),
    bbox_thr: float = Form(0.8),
):
    """
    Receives uploaded neutral videos and runs neutral_videos_to_augmented_trc().
    """
    if len(cam_names) != len(videos):
        raise HTTPException(
            status_code=400,
            detail="cam_names and videos must have the same length.",
        )

    try:
        # Save uploaded videos into OpenCap-style folder structure
        saved_paths = []
        for cam_name, video in zip(cam_names, videos):
            saved_path = save_uploaded_video(video, cam_name, trial_name, trial_id)
            saved_paths.append(str(saved_path))

        # Normalize cameras_to_use
        if cameras_to_use in ("all", "all_available"):
            cameras_to_use_list = [cameras_to_use]
        else:
            cameras_to_use_list = [x.strip() for x in cameras_to_use.split(",") if x.strip()]

        result = neutral_videos_to_augmented_trc(
            trial_name=trial_name,
            trial_id=trial_id,
            cameras_to_use=cameras_to_use_list,
            pose_detector=pose_detector,
            resolution_pose_detection=resolution_pose_detection,
            bbox_thr=bbox_thr,
        )

        return JSONResponse(
            {
                "message": "Neutral videos processed successfully.",
                "saved_videos": saved_paths,
                "raw_trc_path": result["raw_trc_path"],
                "augmented_trc_path": result["augmented_trc_path"],
                "settings_path": result["settings_path"],
                "cameras_used": result["cameras_used"],
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download-augmented-trc")
def download_augmented_trc():
    """
    Download the generated augmented TRC file.
    """
    trc_path = DATA_DIR / "neutral_augmented.trc"
    if not trc_path.exists():
        raise HTTPException(status_code=404, detail="Augmented TRC not found.")

    return FileResponse(
        path=str(trc_path),
        media_type="text/plain",
        filename="neutral_augmented.trc",
    )