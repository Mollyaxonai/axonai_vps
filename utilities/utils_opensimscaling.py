import os
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UTILS_DIR = os.path.join(BASE_DIR, "utilities")
if UTILS_DIR not in sys.path:
    sys.path.insert(0, UTILS_DIR)

from utilities.utils import importMetadata
from utilities.utilsOpenSim import getScaleTimeRange, runScaleTool


def scale_model_from_trc(
    trc_path: str,
    output_dir: str,
    session_metadata_path: str = None,
    scaling_setup: str = "upright_standing_pose",
):
    """
    Run OpenSim scaling from TRC file using metadata from sessionMetadata.yaml.
    """

    if not os.path.exists(trc_path):
        raise FileNotFoundError(f"TRC file not found: {trc_path}")

    # ---------------------------------------------------------
    # Load session metadata
    # ---------------------------------------------------------
    if session_metadata_path is None:
        session_metadata_path = os.path.join(
            BASE_DIR,
            "OpenCapData_experiment",
            "sessionMetadata.yaml"
        )

    if not os.path.exists(session_metadata_path):
        raise FileNotFoundError(
            f"sessionMetadata.yaml not found: {session_metadata_path}"
        )

    sessionMetadata = importMetadata(session_metadata_path)

    # Read required parameters
    openSimModel = sessionMetadata["openSimModel"]
    mass_kg = sessionMetadata["mass_kg"]
    height_m = sessionMetadata["height_m"]

    logging.info(f"Using OpenSim model: {openSimModel}")
    logging.info(f"Mass: {mass_kg} kg")
    logging.info(f"Height: {height_m} m")

    # ---------------------------------------------------------
    # Setup OpenSim paths
    # ---------------------------------------------------------
    openSimPipelineDir = os.path.join(BASE_DIR, "opensimPipeline")

    if scaling_setup == "any_pose":
        genericSetupFile4ScalingName = "Setup_scaling_LaiUhlrich2022_any_pose.xml"
    else:
        genericSetupFile4ScalingName = "Setup_scaling_LaiUhlrich2022.xml"

    pathGenericSetupFile4Scaling = os.path.join(
        openSimPipelineDir,
        "Scaling",
        genericSetupFile4ScalingName
    )

    pathGenericModel4Scaling = os.path.join(
        openSimPipelineDir,
        "Models",
        openSimModel + ".osim"
    )

    if not os.path.exists(pathGenericModel4Scaling):
        raise FileNotFoundError(
            f"OpenSim model not found: {pathGenericModel4Scaling}"
        )

    os.makedirs(output_dir, exist_ok=True)

    # ---------------------------------------------------------
    # Detect neutral pose time range
    # ---------------------------------------------------------
    thresholdPosition = 0.003
    maxThreshold = 0.6
    increment = 0.001

    success = False

    while thresholdPosition <= maxThreshold and not success:
        try:
            timeRange4Scaling = getScaleTimeRange(
                trc_path,
                thresholdPosition=thresholdPosition,
                thresholdTime=0.1,
                removeRoot=True,
            )
            success = True

        except Exception as e:
            logging.info(
                f"Scaling time range detection failed with threshold "
                f"{thresholdPosition}: {e}"
            )
            thresholdPosition += increment

    if not success:
        raise RuntimeError("Failed to detect neutral pose time range.")

    logging.info(f"Scaling time range: {timeRange4Scaling}")

    # ---------------------------------------------------------
    # Run OpenSim scaling
    # ---------------------------------------------------------
    pathScaledModel = runScaleTool(
        pathGenericSetupFile4Scaling,
        pathGenericModel4Scaling,
        mass_kg,
        trc_path,
        timeRange4Scaling,
        output_dir,
        subjectHeight=height_m,
        suffix_model="",
    )

    logging.info(f"Scaled model saved to: {pathScaledModel}")

    return {
        "scaled_model_path": pathScaledModel,
        "time_range": timeRange4Scaling,
        "model_used": openSimModel,
    }


# ---------------------------------------------------------
# CLI usage
# ---------------------------------------------------------
if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--trc_path",
        required=True,
        help="Path to augmented TRC file"
    )

    parser.add_argument(
        "--output_dir",
        default="./Data/OpenSimScaled",
        help="Directory to save scaled model"
    )

    args = parser.parse_args()

    result = scale_model_from_trc(
        trc_path=args.trc_path,
        output_dir=args.output_dir,
    )

    print("Scaling completed")
    print(result)