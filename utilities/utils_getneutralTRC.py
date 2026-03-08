"""
Simplified OpenCap neutral-video -> augmented TRC pipeline.

Outputs:
    ./Data/neutral_raw.trc
    ./Data/neutral_augmented.trc

Expected input video layout:
    <project_root>/
        main.py
        Data/
            Videos/
                Cam0/
                    InputMedia/
                        neutral/
                            neutral.mp4
                Cam1/
                    InputMedia/
                        neutral/
                            neutral.mp4
                ...

Notes
-----
1. This script only runs:
       videos -> pose detection -> synchronization -> triangulation
       -> raw TRC -> marker augmentation
   It does NOT run OpenSim scaling / IK.

2. Camera intrinsics/extrinsics are loaded from:
       Data/Videos/Cam*/cameraIntrinsicsExtrinsics.pickle
   If missing, extrinsics are computed from the neutral trial video using the
   checkerboard settings in sessionMetadata.yaml, while intrinsics are loaded
   from:
       <project_root>/CameraIntrinsics/<iphone model>/Deployed/cameraIntrinsics.pickle

3. sessionMetadata.yaml is loaded from:
       <project_root>/OpenCapData_experiment/sessionMetadata.yaml
"""

import os
import sys
import glob
import yaml
import traceback
import logging
from typing import Dict, List, Optional

import numpy as np

logging.basicConfig(level=logging.INFO)

UTILS_DIR = os.path.join(os.path.dirname(__file__), "utilities")
if UTILS_DIR not in sys.path:
    sys.path.insert(0, UTILS_DIR)

from utilities.utils import (
    importMetadata,
    loadCameraParameters,
    getVideoExtension,
    getOpenPoseDirectory,
    getMMposeDirectory,
)
from utilities.utilsChecker import (
    saveCameraParameters,
    calcExtrinsicsFromVideo,
    isCheckerboardUpsideDown,
    rotateIntrinsics,
    triangulateMultiviewVideo,
    writeTRCfrom3DKeypoints,
)
from utilities.utilsSync import synchronizeVideos
from utilities.utilsDetector import runPoseDetector
from utilities.utilsAugmenter import augmentTRC


def neutral_videos_to_augmented_trc(
    trial_name: str = "neutral",
    trial_id: str = "neutral",
    cameras_to_use: Optional[List[str]] = None,
    intrinsics_final_folder: str = "Deployed",
    pose_detector: str = "OpenPose",
    resolution_pose_detection: str = "default",
    bbox_thr: float = 0.8,
    image_upsample_factor: int = 4,
    augmenter_model: str = "v0.3",
    filter_frequency: str = "default",
    sync_ver: Optional[str] = None,
    default_sync_ver: str = "1.0",
    generate_video: bool = True,
    offset: bool = True,
    overwrite_augmenter_model: bool = False,
    overwrite_filter_frequency: bool = False,
    overwrite_cameras_to_use: bool = False,
    alternate_extrinsics: Optional[List[str]] = None,
) -> Dict[str, object]:
    """
    Process neutral videos and output raw + augmented TRC under ./Data.

    Parameters
    ----------
    trial_name : str
        Trial folder name under InputMedia. Default is "neutral".
    trial_id : str
        Video basename without extension. Default is "neutral".
    cameras_to_use : list[str]
        Examples: ["all"], ["all_available"], ["Cam0", "Cam1"].
    intrinsics_final_folder : str
        Folder under CameraIntrinsics/<iphone model>/ containing cameraIntrinsics.pickle.
    pose_detector : str
        "OpenPose", "openpose", "mmpose", or "hrnet".
    resolution_pose_detection : str
        OpenPose resolution setting.
    bbox_thr : float
        MMPose bbox threshold.
    image_upsample_factor : int
        Used when computing extrinsics from checkerboard video.
    augmenter_model : str
        Marker augmenter version if not overwritten by metadata.
    filter_frequency : str or number-like
        Keypoint filter frequency if not overwritten by metadata.
    sync_ver : str, optional
        Synchronization version.
    default_sync_ver : str
        Default sync version.
    generate_video : bool
        Whether pose detector should generate output videos.
    offset : bool
        Whether augmentTRC should apply vertical offset.
    overwrite_augmenter_model : bool
        If True, use augmenter_model argument instead of metadata.
    overwrite_filter_frequency : bool
        If True, use filter_frequency argument instead of metadata.
    overwrite_cameras_to_use : bool
        If True, use cameras_to_use argument instead of metadata.
    alternate_extrinsics : list[str], optional
        Cameras for which to use second extrinsics solution.

    Returns
    -------
    dict
        {
            "raw_trc_path": ...,
            "augmented_trc_path": ...,
            "settings_path": ...,
            "cameras_used": ...,
            "frame_rate": ...,
            "keypoint_names": ...
        }
    """
    if cameras_to_use is None:
        cameras_to_use = ["all"]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "Data")
    os.makedirs(data_dir, exist_ok=True)

    videos_root = os.path.join(data_dir, "Videos")
    if not os.path.exists(videos_root):
        raise FileNotFoundError(
            f"Videos folder not found: {videos_root}\n"
            "Expected layout: ./Data/Videos/Cam*/InputMedia/neutral/neutral.mp4"
        )

    session_metadata_path = os.path.join(
        base_dir, "OpenCapData_experiment", "sessionMetadata.yaml"
    )
    if not os.path.exists(session_metadata_path):
        raise FileNotFoundError(f"sessionMetadata.yaml not found: {session_metadata_path}")

    session_metadata = importMetadata(session_metadata_path)

    # ------------------------------------------------------------------
    # Metadata-driven settings
    # ------------------------------------------------------------------
    if "augmentermodel" in session_metadata and not overwrite_augmenter_model:
        augmenter_model_used = session_metadata["augmentermodel"]
    else:
        augmenter_model_used = augmenter_model

    if "filterfrequency" in session_metadata and not overwrite_filter_frequency:
        filterfrequency = session_metadata["filterfrequency"]
    else:
        filterfrequency = filter_frequency

    if filterfrequency == "default":
        filt_freqs = {"gait": 12, "default": 500}
    else:
        filt_freqs = {"gait": filterfrequency, "default": filterfrequency}

    if "camerastouse" in session_metadata and not overwrite_cameras_to_use:
        cameras_to_use_cfg = session_metadata["camerastouse"]
    else:
        cameras_to_use_cfg = cameras_to_use

    sync_ver = sync_ver or session_metadata.get("sync_ver", default_sync_ver)

    # ------------------------------------------------------------------
    # Pose detector normalization
    # ------------------------------------------------------------------
    if pose_detector == "hrnet":
        pose_detector = "mmpose"
    elif pose_detector == "openpose":
        pose_detector = "OpenPose"

    if pose_detector == "mmpose":
        pose_detector_directory = getMMposeDirectory(False)
        output_media_folder = "OutputMedia_mmpose" + str(bbox_thr)
        detector_suffix = "_" + str(bbox_thr)
    elif pose_detector == "OpenPose":
        pose_detector_directory = getOpenPoseDirectory(False)
        output_media_folder = "OutputMedia_" + resolution_pose_detection
        detector_suffix = "_" + resolution_pose_detection
    else:
        raise ValueError(f"Unsupported pose detector: {pose_detector}")

    # ------------------------------------------------------------------
    # Simple output paths
    # ------------------------------------------------------------------
    raw_trc_path = os.path.join(data_dir, "neutral_raw.trc")
    augmented_trc_path = os.path.join(data_dir, "neutral_augmented.trc")
    settings_path = os.path.join(data_dir, "neutral_settings.yaml")

    settings = {
        "poseDetector": pose_detector,
        "augmenter_model": augmenter_model_used,
        "imageUpsampleFactor": image_upsample_factor,
        "openSimModel": session_metadata["openSimModel"],
        "filterFrequency": filterfrequency,
    }
    if pose_detector == "OpenPose":
        settings["resolutionPoseDetection"] = resolution_pose_detection
    elif pose_detector == "mmpose":
        settings["bbox_thr"] = bbox_thr

    with open(settings_path, "w") as f:
        yaml.dump(settings, f)

    # ------------------------------------------------------------------
    # Camera folders and phone models
    # ------------------------------------------------------------------
    camera_directories: Dict[str, str] = {}
    camera_models: Dict[str, str] = {}

    for path_cam in glob.glob(os.path.join(videos_root, "Cam*")):
        cam_name = os.path.basename(path_cam)
        camera_directories[cam_name] = path_cam
        if "iphoneModel" not in session_metadata or cam_name not in session_metadata["iphoneModel"]:
            raise ValueError(f"Missing iphoneModel entry for {cam_name} in session metadata.")
        camera_models[cam_name] = session_metadata["iphoneModel"][cam_name]

    if len(camera_directories) < 2:
        raise ValueError("At least two camera folders are required under ./Data/Videos/")

    # ------------------------------------------------------------------
    # Checkerboard parameters for extrinsics
    # ------------------------------------------------------------------
    checkerboard_params = {
        "dimensions": (
            session_metadata["checkerBoard"]["black2BlackCornersWidth_n"],
            session_metadata["checkerBoard"]["black2BlackCornersHeight_n"],
        ),
        "squareSize": session_metadata["checkerBoard"]["squareSideLength_mm"],
    }

    # ------------------------------------------------------------------
    # Load or compute intrinsics/extrinsics
    # ------------------------------------------------------------------
    cam_param_dict = {}
    loaded_cam_params = {}

    for cam_name, cam_dir in camera_directories.items():
        intrinsics_extrinsics_path = os.path.join(
            cam_dir, "cameraIntrinsicsExtrinsics.pickle"
        )

        if os.path.exists(intrinsics_extrinsics_path):
            logging.info(f"Loading existing camera parameters for {cam_name}")
            cam_params = loadCameraParameters(intrinsics_extrinsics_path)
            loaded_cam_params[cam_name] = True
        else:
            logging.info(f"Computing camera parameters for {cam_name}")

            intrinsic_dir = os.path.join(
                base_dir, "CameraIntrinsics", camera_models[cam_name]
            )
            perm_intrinsic_dir = os.path.join(intrinsic_dir, intrinsics_final_folder)

            if not os.path.exists(perm_intrinsic_dir):
                raise FileNotFoundError(
                    f"Intrinsics not found for camera model {camera_models[cam_name]}.\n"
                    f"Expected folder: {perm_intrinsic_dir}"
                )

            cam_params = loadCameraParameters(
                os.path.join(perm_intrinsic_dir, "cameraIntrinsics.pickle")
            )

            path_video_without_extension = os.path.join(
                cam_dir, "InputMedia", trial_name, trial_id
            )
            extension = getVideoExtension(path_video_without_extension)
            extrinsic_path = os.path.join(
                cam_dir, "InputMedia", trial_name, trial_id + extension
            )

            if not os.path.exists(extrinsic_path):
                raise FileNotFoundError(
                    f"Neutral video not found for {cam_name}: {extrinsic_path}"
                )

            cam_params = rotateIntrinsics(cam_params, extrinsic_path)

            use_second_extrinsics_solution = (
                alternate_extrinsics is not None and cam_name in alternate_extrinsics
            )

            try:
                cam_params = calcExtrinsicsFromVideo(
                    extrinsic_path,
                    cam_params,
                    checkerboard_params,
                    visualize=False,
                    imageUpsampleFactor=image_upsample_factor,
                    useSecondExtrinsicsSolution=use_second_extrinsics_solution,
                )
            except Exception as e:
                raise RuntimeError(
                    f"Camera calibration failed for {cam_name}: {e}"
                ) from e

            loaded_cam_params[cam_name] = False

        cam_param_dict[cam_name] = cam_params.copy() if cam_params is not None else None

    # Save newly computed parameters
    if not all(loaded_cam_params.values()):
        for cam_name, cam_params in cam_param_dict.items():
            saveCameraParameters(
                os.path.join(
                    camera_directories[cam_name], "cameraIntrinsicsExtrinsics.pickle"
                ),
                cam_params,
            )

    # ------------------------------------------------------------------
    # Rotation angles for TRC export
    # ------------------------------------------------------------------
    checkerboard_mount = session_metadata["checkerBoard"]["placement"]
    if checkerboard_mount in ["backWall", "Perpendicular"]:
        upside_down_checker = isCheckerboardUpsideDown(cam_param_dict)
        if upside_down_checker:
            rotation_angles = {"y": -90}
        else:
            rotation_angles = {"y": 90, "z": 180}
    elif checkerboard_mount in ["ground", "Lying"]:
        rotation_angles = {"x": 90, "y": 90}
    else:
        raise ValueError(
            f"Unsupported checkerBoard placement: {checkerboard_mount}"
        )

    # ------------------------------------------------------------------
    # Determine available cameras
    # ------------------------------------------------------------------
    cameras_available = []
    for cam_name, cam_dir in camera_directories.items():
        path_video_without_extension = os.path.join(
            cam_dir, "InputMedia", trial_name, trial_id
        )
        matches = glob.glob(path_video_without_extension + "*")
        if len(matches) == 0:
            logging.warning(f"Camera {cam_name} has no video for trial {trial_id}")
            continue

        ext = getVideoExtension(path_video_without_extension)
        full_video_path = path_video_without_extension + ext
        if os.path.exists(full_video_path):
            cameras_available.append(cam_name)

    if len(cameras_available) < 2:
        raise ValueError("Fewer than two cameras have valid neutral videos.")

    if cameras_to_use_cfg[0] == "all":
        cameras_all = list(camera_directories.keys())
        if not all(cam in cameras_available for cam in cameras_all):
            raise ValueError(
                "Not all cameras have uploaded neutral videos. "
                'Use cameras_to_use=["all_available"] if that is intended.'
            )
        cameras_to_use_final = cameras_to_use_cfg
    elif cameras_to_use_cfg[0] == "all_available":
        cameras_to_use_final = cameras_available
    else:
        if not all(cam in cameras_available for cam in cameras_to_use_cfg):
            raise ValueError("Some requested cameras do not have neutral videos.")
        cameras_to_use_final = cameras_to_use_cfg

    if cameras_to_use_final[0] != "all" and len(cameras_to_use_final) < 2:
        raise ValueError("At least two videos are required for 3D reconstruction.")

    settings["camerasToUse"] = cameras_to_use_final
    with open(settings_path, "w") as f:
        yaml.dump(settings, f)

    # ------------------------------------------------------------------
    # Trial relative path used by detector/sync code
    # ------------------------------------------------------------------
    trial_relative_path = os.path.join("InputMedia", trial_name, trial_id)

    # ------------------------------------------------------------------
    # 1) Pose detection
    # ------------------------------------------------------------------
    try:
        video_extension = runPoseDetector(
            camera_directories,
            trial_relative_path,
            pose_detector_directory,
            trial_name,
            CamParamDict=cam_param_dict,
            resolutionPoseDetection=resolution_pose_detection,
            generateVideo=generate_video,
            cams2Use=cameras_to_use_final,
            poseDetector=pose_detector,
            bbox_thr=bbox_thr,
        )
        trial_relative_path += video_extension
    except Exception as e:
        raise RuntimeError(
            f"Pose detection failed.\n{traceback.format_exc()}"
        ) from e

    # ------------------------------------------------------------------
    # 2) Synchronization
    # ------------------------------------------------------------------
    try:
        (
            keypoints2D,
            confidence,
            keypoint_names,
            frame_rate,
            nans_in_out,
            start_end_frames,
            cameras2Use,
        ) = synchronizeVideos(
            camera_directories,
            trial_relative_path,
            pose_detector_directory,
            undistortPoints=True,
            CamParamDict=cam_param_dict,
            filtFreqs=filt_freqs,
            confidenceThreshold=0.4,
            imageBasedTracker=False,
            cams2Use=cameras_to_use_final,
            poseDetector=pose_detector,
            trialName=trial_name,
            resolutionPoseDetection=resolution_pose_detection,
            syncVer=sync_ver,
        )
    except Exception as e:
        raise RuntimeError(
            f"Video synchronization failed.\n{traceback.format_exc()}"
        ) from e

    # ------------------------------------------------------------------
    # 3) Triangulation
    # ------------------------------------------------------------------
    try:
        keypoints3D, confidence3D = triangulateMultiviewVideo(
            cam_param_dict,
            keypoints2D,
            ignoreMissingMarkers=False,
            cams2Use=cameras2Use,
            confidenceDict=confidence,
            spline3dZeros=True,
            splineMaxFrames=int(frame_rate / 5),
            nansInOut=nans_in_out,
            CameraDirectories=camera_directories,
            trialName=trial_name,
            startEndFrames=start_end_frames,
            trialID=trial_id,
            outputMediaFolder=output_media_folder,
        )
    except Exception as e:
        raise RuntimeError(
            f"Triangulation failed.\n{traceback.format_exc()}"
        ) from e

    if keypoints3D.shape[2] < 10:
        raise ValueError("Error - less than 10 good frames of triangulated data.")

    # ------------------------------------------------------------------
    # 4) Write raw TRC
    # ------------------------------------------------------------------
    writeTRCfrom3DKeypoints(
        keypoints3D,
        raw_trc_path,
        keypoint_names,
        frameRate=frame_rate,
        rotationAngles=rotation_angles,
    )

    # ------------------------------------------------------------------
    # 5) Marker augmentation -> augmented TRC
    # ------------------------------------------------------------------
    augmenter_dir = os.path.join(base_dir, "MarkerAugmenter")
    augmenter_model_name = session_metadata["markerAugmentationSettings"][
        "markerAugmenterModel"
    ]

    try:
        vertical_offset = augmentTRC(
            raw_trc_path,
            session_metadata["mass_kg"],
            session_metadata["height_m"],
            augmented_trc_path,
            augmenter_dir,
            augmenterModelName=augmenter_model_name,
            augmenter_model=augmenter_model_used,
            offset=offset,
        )
    except Exception as e:
        raise RuntimeError(
            f"Marker augmentation failed.\n{traceback.format_exc()}"
        ) from e

    if offset:
        settings["verticalOffset"] = float(np.copy(vertical_offset) - 0.01)

    with open(settings_path, "w") as f:
        yaml.dump(settings, f)

    return {
        "raw_trc_path": raw_trc_path,
        "augmented_trc_path": augmented_trc_path,
        "settings_path": settings_path,
        "cameras_used": cameras2Use,
        "frame_rate": frame_rate,
        "keypoint_names": keypoint_names,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate raw and augmented TRC from neutral videos."
    )
    parser.add_argument("--trial_name", default="neutral")
    parser.add_argument("--trial_id", default="neutral")
    parser.add_argument(
        "--cameras_to_use",
        nargs="+",
        default=["all"],
        help='Examples: --cameras_to_use all   OR   --cameras_to_use all_available   OR   --cameras_to_use Cam0 Cam1',
    )
    parser.add_argument("--pose_detector", default="OpenPose")
    parser.add_argument("--resolution_pose_detection", default="default")
    parser.add_argument("--bbox_thr", type=float, default=0.8)
    args = parser.parse_args()

    result = neutral_videos_to_augmented_trc(
        trial_name=args.trial_name,
        trial_id=args.trial_id,
        cameras_to_use=args.cameras_to_use,
        pose_detector=args.pose_detector,
        resolution_pose_detection=args.resolution_pose_detection,
        bbox_thr=args.bbox_thr,
    )

    print("\nPipeline completed.")
    print(f"Raw TRC:       {result['raw_trc_path']}")
    print(f"Augmented TRC: {result['augmented_trc_path']}")
    print(f"Settings:      {result['settings_path']}")
    print(f"Cameras used:  {result['cameras_used']}")