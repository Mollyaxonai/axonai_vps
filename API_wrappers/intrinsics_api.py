from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Tuple
from utilities.utils_calcIntrinsics import get_camera_instrincs

from utilities.utilsChecker import computeAverageIntrinsics_local, saveCameraParameters

app = FastAPI(title="Camera Intrinsics API")


class CheckerBoardParamsModel(BaseModel):
    dimensions: Tuple[int, int] = Field(..., description="Checkerboard inner corners as (width, height)")
    squareSize: float = Field(..., description="Checkerboard square size in mm")


class CameraIntrinsicsRequest(BaseModel):
    calib_videos: List[str] = Field(..., description="List of local paths to calibration videos")
    CheckerBoardParams: CheckerBoardParamsModel


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/camera/intrinsics")
def create_camera_intrinsics(request: CameraIntrinsicsRequest):
    try:
        output_path = get_camera_instrincs(
            calib_videos=request.calib_videos,
            CheckerBoardParams=request.CheckerBoardParams.model_dump()
        )
        return {
            "message": "Camera intrinsics computed successfully.",
            "output_path": output_path,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))