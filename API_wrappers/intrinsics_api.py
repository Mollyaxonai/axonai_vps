from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Tuple
import os

from utilities.utilsChecker import computeAverageIntrinsics_local, saveCameraParameters

app = FastAPI(title="Camera Intrinsics API")


class CheckerBoardParamsModel(BaseModel):
    dimensions: Tuple[int, int] = Field(..., description="Checkerboard inner corners as (width, height)")
    squareSize: float = Field(..., description="Checkerboard square size in mm")


class CameraIntrinsicsRequest(BaseModel):
    calib_videos: List[str] = Field(..., description="List of local paths to calibration videos")
    CheckerBoardParams: CheckerBoardParamsModel


def get_camera_intrinsics(calib_videos, CheckerBoardParams, session_path, nImages):
    """
    Compute camera intrinsic parameters from checkerboard calibration videos.

    The function samples frames from the provided calibration videos, detects
    checkerboard corners, estimates the camera intrinsics using OpenCV
    calibration, averages the results across videos, and saves the final
    parameters to `CameraIntrinsics/cameraIntrinsics.pickle`.

    Returns the saved output path.
    """
    CamParamsAverage, _, _, _ = computeAverageIntrinsics_local(
        session_path=session_path,
        calibration_videos=calib_videos,
        CheckerBoardParams=CheckerBoardParams,
        nImages=nImages,
    )

    permIntrinsicDir = os.path.join(os.getcwd(), "CameraIntrinsics")
    output_path = os.path.join(permIntrinsicDir, "cameraIntrinsics.pickle")
    saveCameraParameters(output_path, CamParamsAverage)
    return output_path


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/camera/intrinsics")
def create_camera_intrinsics(request: CameraIntrinsicsRequest):
    try:
        output_path = get_camera_intrinsics(
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