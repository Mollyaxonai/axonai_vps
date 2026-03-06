"""
    @authors: Scott Uhlrich, Antoine Falisse, Łukasz Kidziński

    This script takes as inputs a video, sessionMetadata.yaml, the camera model name, and
    computes camera intrinsics. The intrinsic parameters are then saved to file in a general
    location for future use of this phone model.
"""

import os 
from utilsChecker import computeAverageIntrinsics_local
from utilsChecker import saveCameraParameters

def get_camera_instrincs(calib_videos, CheckerBoardParams):
    """
    Compute camera intrinsic parameters from checkerboard calibration videos.

    The function samples frames from the provided calibration videos, detects
    checkerboard corners, estimates the camera intrinsics using OpenCV
    calibration, averages the results across videos, and saves the final
    parameters to `CameraIntrinsics/cameraIntrinsics.pickle`.

    Parameters
    ----------
    calib_videos : list[str]
        Paths to calibration videos containing a checkerboard observed from
        different angles.

    CheckerBoardParams : dict
        Checkerboard specification with keys:
        - 'dimensions': tuple (width, height) of inner corners
        - 'squareSize': size of each square (in mm)

    session_path : str
        Directory where intermediate calibration files (frames, checkerboard
        detections, per-video intrinsics) will be stored.

    nImages : int
        Number of frames to sample from each calibration video.

    Returns
    -------
    None
        The averaged camera intrinsics are saved to
        `CameraIntrinsics/cameraIntrinsics.pickle` in the current directory.
    """
    CamParamsAverage, _, _, _ = computeAverageIntrinsics_local(
        session_path = r"D:\axon-ai\Data\IntrinsicsSession",
        calibration_videos = calib_videos,
        CheckerBoardParams = CheckerBoardParams,
        nImages=25,
    )

    permIntrinsicDir = os.path.join(os.getcwd(), 'CameraIntrinsics')
    output_path = os.path.join(permIntrinsicDir, 'cameraIntrinsics.pickle')
    saveCameraParameters(
        output_path,
        CamParamsAverage
    )
    print(f"Your camera instrincs is saved at {output_path}")

if __name__ == "__main__":

    CheckerBoardParams = {'dimensions': (11, 8), 'squareSize': 60}

    calib_videos = [
        r"D:\calib\cam0_intrinsics.mov",
        r"D:\calib\cam0_intrinsics_take2.mov",
    ]
    
    get_camera_instrincs(calib_videos, CheckerBoardParams)