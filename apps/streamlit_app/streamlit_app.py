# app.py
# Streamlit MVP: (1) upload 2 checkerboard images -> "Configure camera"
#               (2) upload 2 walking videos (left/right) -> "Generate gait report"
#
# Run:
#   pip install streamlit opencv-python numpy requests
#   streamlit run app.py
#
# Optional: set your cloud endpoint(s)
#   export GAIT_API_BASE="https://your-cloud-api.com"
#   export GAIT_API_KEY="..."
#
# Notes:
# - This is an MVP UI scaffold. The "configure camera" step runs basic checkerboard
#   detection and stores the results in session state.
# - The "generate gait report" step demonstrates how to upload videos + metadata
#   to a cloud endpoint (placeholder). Replace with your real API.

import os
import json
import time
import tempfile
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

import numpy as np
import cv2
import requests
import streamlit as st


# ---------------------------
# Configuration
# ---------------------------
API_BASE = os.getenv("GAIT_API_BASE", "").rstrip("/")
API_KEY = os.getenv("GAIT_API_KEY", "")

DEFAULT_CHECKERBOARD_COLS = 9  # internal corners along width
DEFAULT_CHECKERBOARD_ROWS = 6  # internal corners along height
DEFAULT_SQUARE_SIZE_MM = 25.0  # used for metric scale later (optional for MVP)


# ---------------------------
# Helpers
# ---------------------------
@dataclass
class CheckerboardConfig:
    cols: int
    rows: int
    square_size_mm: float


def read_image_from_upload(uploaded_file) -> np.ndarray:
    """Read an uploaded image file into BGR OpenCV image."""
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image. Please upload a valid image file.")
    return img


def detect_checkerboard(
    bgr: np.ndarray, cfg: CheckerboardConfig
) -> Tuple[bool, Optional[np.ndarray], np.ndarray]:
    """
    Detect checkerboard corners. Returns:
      found (bool), corners (Nx1x2 float32) or None, annotated RGB image for display
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    pattern_size = (cfg.cols, cfg.rows)
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE

    found, corners = cv2.findChessboardCorners(gray, pattern_size, flags)

    annotated = bgr.copy()
    if found and corners is not None:
        # Refine corners for better accuracy
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        cv2.drawChessboardCorners(annotated, pattern_size, corners, found)

    annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
    return found, corners, annotated_rgb


def save_upload_to_temp(uploaded_file, suffix: str) -> str:
    """Persist an uploaded file to a temp path and return the path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


def cloud_generate_report(
    left_video_path: str,
    right_video_path: str,
    metadata: Dict[str, Any],
    calibration: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Example cloud call (multipart upload). Replace with your real API contract.

    Expected endpoints (example):
      POST {API_BASE}/jobs
        multipart fields:
          left_video, right_video, metadata_json, calibration_json
      returns JSON: { "job_id": "...", ... }

      GET {API_BASE}/jobs/{job_id}
        returns JSON: { "status": "processing|done|failed", "report_url": "...", ... }
    """
    if not API_BASE:
        # No API configured: return a mock response
        return {
            "mode": "mock",
            "status": "done",
            "message": "GAIT_API_BASE not set; returning mock report.",
            "report": {
                "summary": "Mock gait report (replace with cloud integration).",
                "metrics": {"cadence": 110, "stride_length_m": 1.15},
            },
        }

    url = f"{API_BASE}/jobs"
    headers = {}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    files = {
        "left_video": ("left.mp4", open(left_video_path, "rb"), "video/mp4"),
        "right_video": ("right.mp4", open(right_video_path, "rb"), "video/mp4"),
        "metadata_json": ("metadata.json", json.dumps(metadata).encode("utf-8"), "application/json"),
        "calibration_json": ("calibration.json", json.dumps(calibration).encode("utf-8"), "application/json"),
    }

    resp = requests.post(url, headers=headers, files=files, timeout=300)
    resp.raise_for_status()
    job = resp.json()

    # If your API is async, poll status
    job_id = job.get("job_id")
    if not job_id:
        return {"mode": "cloud", "status": "done", "job": job}

    status_url = f"{API_BASE}/jobs/{job_id}"
    for _ in range(60):  # ~60 polls max; adjust as needed
        time.sleep(2)
        s = requests.get(status_url, headers=headers, timeout=60)
        s.raise_for_status()
        payload = s.json()
        if payload.get("status") in ("done", "failed"):
            return {"mode": "cloud", **payload}

    return {"mode": "cloud", "status": "processing", "job_id": job_id}



# ---------------------------
# Streamlit App
# ---------------------------
st.set_page_config(page_title="Gait Report MVP", page_icon="🦿", layout="centered")

st.title("AxonAI: Gait Report Instructions")
# st.caption("Phase-1 UI: upload checkerboard images → configure → upload walking videos → generate report")

# Initialize session state
if "calibration_ready" not in st.session_state:
    st.session_state.calibration_ready = False
if "calibration" not in st.session_state:
    st.session_state.calibration = {}
if "checkerboard_cfg" not in st.session_state:
    st.session_state.checkerboard_cfg = {
        "cols": DEFAULT_CHECKERBOARD_COLS,
        "rows": DEFAULT_CHECKERBOARD_ROWS,
        "square_size_mm": DEFAULT_SQUARE_SIZE_MM,
    }

# ---------------------------
# Step 1: Upload checkerboard images
# ---------------------------
API_BASE_URL = "http://127.0.0.1:8000"  # change if your FastAPI server runs elsewhere


def save_uploaded_file(uploaded_file, save_dir: str) -> str:
    """Save a Streamlit UploadedFile to disk and return the saved path."""
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, uploaded_file.name)
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return save_path


st.header("Step 1 — Configure camera intrinsics")

with st.expander("Checkerboard settings", expanded=True):
    c1, c2, c3 = st.columns(3)
    cols = c1.number_input(
        "Cols (internal corners)",
        min_value=3,
        max_value=25,
        value=int(st.session_state.checkerboard_cfg["cols"]),
        step=1,
    )
    rows = c2.number_input(
        "Rows (internal corners)",
        min_value=3,
        max_value=25,
        value=int(st.session_state.checkerboard_cfg["rows"]),
        step=1,
    )
    square_mm = c3.number_input(
        "Square size (mm)",
        min_value=1.0,
        max_value=200.0,
        value=float(st.session_state.checkerboard_cfg["square_size_mm"]),
        step=1.0,
    )

    st.session_state.checkerboard_cfg = {
        "cols": int(cols),
        "rows": int(rows),
        "square_size_mm": float(square_mm),
    }

c1, c2 = st.columns(2)
calib_video_left = c1.file_uploader(
    "Upload LEFT calibration video",
    type=["mov", "mp4", "avi", "mkv"],
    key="calib_video_left",
)
calib_video_right = c2.file_uploader(
    "Upload RIGHT calibration video",
    type=["mov", "mp4", "avi", "mkv"],
    key="calib_video_right",
)

n_images = st.number_input(
    "Number of sampled frames per calibration video",
    min_value=5,
    max_value=100,
    value=25,
    step=1,
)

st.caption(
    "Each calibration video should show the checkerboard from multiple positions and angles."
)

configure_clicked = st.button(
    "⚙️ Configure camera",
    disabled=(calib_video_left is None or calib_video_right is None),
)

if configure_clicked:
    try:
        # Create a unique local folder for this Streamlit calibration request
        run_id = f"intrinsics_{int(time.time())}"
        upload_root = os.path.join(os.getcwd(), "uploaded_calibration_videos", run_id)
        session_path = os.path.join(os.getcwd(), "IntrinsicsSession", run_id)
        os.makedirs(upload_root, exist_ok=True)
        os.makedirs(session_path, exist_ok=True)

        # Save uploaded videos locally
        left_video_path = save_uploaded_file(calib_video_left, upload_root)
        right_video_path = save_uploaded_file(calib_video_right, upload_root)

        # Build API request body
        payload = {
            "calib_videos": [left_video_path, right_video_path],
            "CheckerBoardParams": {
                "dimensions": [int(cols), int(rows)],
                "squareSize": float(square_mm),
            },
            "session_path": session_path,
            "nImages": int(n_images),
        }

        with st.spinner("Computing camera intrinsics..."):
            resp = requests.post(
                f"{API_BASE_URL}/camera/intrinsics",
                json=payload,
                timeout=600,
            )

        if resp.status_code == 200:
            result = resp.json()
            st.session_state.calibration = {
                "calibration_id": run_id,
                "checkerboard": {
                    "cols": int(cols),
                    "rows": int(rows),
                    "square_size_mm": float(square_mm),
                },
                "calib_videos": [left_video_path, right_video_path],
                "session_path": session_path,
                "nImages": int(n_images),
                "output_path": result.get("output_path"),
            }
            st.session_state.calibration_ready = True
            st.success("Camera configured ✅")
            st.write(f"Intrinsics saved at: `{result.get('output_path')}`")
        else:
            st.session_state.calibration_ready = False
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            st.error(f"API error ({resp.status_code}): {err}")

    except requests.exceptions.RequestException as e:
        st.session_state.calibration_ready = False
        st.error(f"Failed to connect to calibration API: {e}")
    except Exception as e:
        st.session_state.calibration_ready = False
        st.error(f"Configuration failed: {e}")

if st.session_state.get("calibration_ready", False):
    with st.expander("View saved calibration profile", expanded=False):
        st.json(st.session_state.calibration)

st.divider()

# ---------------------------
# Step 2: Upload neutral images
# ---------------------------

st.header("Step 2 — Upload neutral videos")
st.caption(
    "Upload the neutral-pose videos from the same calibrated cameras. "
    "These will be sent to the backend to generate the augmented TRC."
)

c1, c2 = st.columns(2)
neutral_video_left = c1.file_uploader(
    "Upload LEFT neutral video",
    type=["mov", "mp4", "avi", "mkv"],
    key="neutral_video_left",
)
neutral_video_right = c2.file_uploader(
    "Upload RIGHT neutral video",
    type=["mov", "mp4", "avi", "mkv"],
    key="neutral_video_right",
)

run_neutral_clicked = st.button(
    "🦴 Generate augmented TRC",
    disabled=(neutral_video_left is None or neutral_video_right is None),
)

if run_neutral_clicked:
    try:
        # Create a unique local folder for this neutral-pose request
        run_id = f"neutral_{int(time.time())}"
        upload_root = os.path.join(os.getcwd(), "uploaded_neutral_videos", run_id)
        os.makedirs(upload_root, exist_ok=True)

        # Save uploaded videos locally (optional, but useful for debugging)
        left_neutral_path = save_uploaded_file(neutral_video_left, upload_root)
        right_neutral_path = save_uploaded_file(neutral_video_right, upload_root)

        # Build multipart form-data request
        files = [
            (
                "videos",
                (
                    os.path.basename(left_neutral_path),
                    open(left_neutral_path, "rb"),
                    "video/mp4",
                ),
            ),
            (
                "videos",
                (
                    os.path.basename(right_neutral_path),
                    open(right_neutral_path, "rb"),
                    "video/mp4",
                ),
            ),
        ]

        data = [
            ("trial_name", "neutral"),
            ("trial_id", "neutral"),
            ("cam_names", "Cam0"),
            ("cam_names", "Cam1"),
            ("cameras_to_use", "all_available"),
            ("pose_detector", "OpenPose"),
            ("resolution_pose_detection", "default"),
            ("bbox_thr", "0.8"),
        ]

        with st.spinner("Processing neutral videos and generating augmented TRC..."):
            resp = requests.post(
                f"{API_BASE_URL}/process-neutral",
                files=files,
                data=data,
                timeout=1800,
            )

        # Close file handles
        for _, file_tuple in files:
            file_tuple[1].close()

        if resp.status_code == 200:
            result = resp.json()

            st.success("Neutral videos processed successfully ✅")

            st.session_state["neutral_processing"] = {
                "run_id": run_id,
                "uploaded_videos": [left_neutral_path, right_neutral_path],
                "raw_trc_path": result.get("raw_trc_path"),
                "augmented_trc_path": result.get("augmented_trc_path"),
                "settings_path": result.get("settings_path"),
                "cameras_used": result.get("cameras_used"),
            }

            st.write(f"Raw TRC: `{result.get('raw_trc_path')}`")
            st.write(f"Augmented TRC: `{result.get('augmented_trc_path')}`")
            st.write(f"Settings: `{result.get('settings_path')}`")
            st.write(f"Cameras used: `{result.get('cameras_used')}`")

            # Optional: direct download from backend if you have a download endpoint
            try:
                download_resp = requests.get(
                    f"{API_BASE_URL}/download-augmented-trc",
                    timeout=120,
                )
                if download_resp.status_code == 200:
                    st.download_button(
                        label="Download augmented TRC",
                        data=download_resp.content,
                        file_name="neutral_augmented.trc",
                        mime="text/plain",
                    )
            except Exception:
                pass

        else:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            st.error(f"API error ({resp.status_code}): {err}")

    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to neutral processing API: {e}")
    except Exception as e:
        st.error(f"Neutral processing failed: {e}")

if "neutral_processing" in st.session_state:
    with st.expander("View neutral processing result", expanded=False):
        st.json(st.session_state["neutral_processing"])


# ---------------------------
# Step 2: Upload walking videos
# ---------------------------
st.header("Step 2 — Upload walking videos (Left & Right)")

if not st.session_state.calibration_ready:
    st.info("Please complete Step 1 (Configure camera) before generating a gait report.")
else:
    patient_code = st.text_input("Patient code (avoid real names)", value="P001")
    trial_name = st.text_input("Trial name", value="walk_1")

    vid_left_up = st.file_uploader("Upload LEFT walking video", type=["mp4", "mov", "m4v"], key="vid_left")
    vid_right_up = st.file_uploader("Upload RIGHT walking video", type=["mp4", "mov", "m4v"], key="vid_right")

    if vid_left_up is not None:
        st.video(vid_left_up)

    if vid_right_up is not None:
        st.video(vid_right_up)

    st.markdown("### Generate gait report")
    gen_clicked = st.button(
        "🧪 Generate gait report",
        disabled=(vid_left_up is None or vid_right_up is None),
    )

    if gen_clicked:
        with st.spinner("Uploading videos & generating report..."):
            # Save uploads to temp files
            left_path = save_upload_to_temp(vid_left_up, suffix=".mp4")
            right_path = save_upload_to_temp(vid_right_up, suffix=".mp4")

            metadata = {
                "patient_code": patient_code,
                "trial_name": trial_name,
                "created_at_unix": int(time.time()),
                "camera_pair": {"left": "left", "right": "right"},
            }

            try:
                result = cloud_generate_report(
                    left_video_path=left_path,
                    right_video_path=right_path,
                    metadata=metadata,
                    calibration=st.session_state.calibration,
                )
                st.success("Done ✅")
                st.json(result)

                # If your API returns a report URL, show it nicely:
                report_url = result.get("report_url") or result.get("report", {}).get("url")
                if report_url:
                    st.link_button("Open report", report_url)

            except requests.HTTPError as e:
                st.error(f"Cloud API error: {e}")
                try:
                    st.code(e.response.text)
                except Exception:
                    pass
            except Exception as e:
                st.error(f"Unexpected error: {e}")

            finally:
                # Best-effort cleanup
                for p in [left_path, right_path]:
                    try:
                        os.remove(p)
                    except Exception:
                        pass

st.divider()
st.caption(
    "Phase-1 MVP scaffold. Next steps for a real calibration: capture 15–25 checkerboard image pairs and run OpenCV "
    "calibrateCamera + stereoCalibrate to compute intrinsics/extrinsics."
)