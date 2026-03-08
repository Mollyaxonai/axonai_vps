# app.py
import os
from pathlib import Path

import reflex as rx


UPLOAD_DIR = Path("uploaded_files")
UPLOAD_DIR.mkdir(exist_ok=True)


class State(rx.State):
    """App state."""

    # Checkerboard settings
    cols: int = 6
    rows: int = 9
    square_size_mm: float = 25.0

    # Calibration settings
    n_images: int = 25

    # Uploaded file names / saved paths
    calib_video_left_name: str = ""
    calib_video_right_name: str = ""
    calib_video_left_path: str = ""
    calib_video_right_path: str = ""

    # UI state
    status_message: str = ""
    configured: bool = False

    @rx.var
    def can_configure(self) -> bool:
        return bool(self.calib_video_left_name and self.calib_video_right_name)

    async def handle_left_upload(self, files: list[rx.UploadFile]):
        """Save the uploaded left calibration video."""
        if not files:
            return

        file = files[0]
        upload_data = await file.read()

        save_path = UPLOAD_DIR / f"left_{file.filename}"
        save_path.write_bytes(upload_data)

        self.calib_video_left_name = file.filename
        self.calib_video_left_path = str(save_path)
        self.status_message = f"Uploaded LEFT calibration video: {file.filename}"
        self.configured = False

    async def handle_right_upload(self, files: list[rx.UploadFile]):
        """Save the uploaded right calibration video."""
        if not files:
            return

        file = files[0]
        upload_data = await file.read()

        save_path = UPLOAD_DIR / f"right_{file.filename}"
        save_path.write_bytes(upload_data)

        self.calib_video_right_name = file.filename
        self.calib_video_right_path = str(save_path)
        self.status_message = f"Uploaded RIGHT calibration video: {file.filename}"
        self.configured = False

    def set_cols(self, value):
        self.cols = int(value)

    def set_rows(self, value):
        self.rows = int(value)

    def set_square_size_mm(self, value):
        self.square_size_mm = float(value)

    def set_n_images(self, value):
        self.n_images = int(value)

    def configure_camera(self):
        """Placeholder for your camera-intrinsics configuration logic."""
        if not self.can_configure:
            self.status_message = "Please upload both LEFT and RIGHT calibration videos first."
            self.configured = False
            return

        # Put your real backend/API logic here.
        # For example, call your FastAPI endpoint with:
        # - self.cols
        # - self.rows
        # - self.square_size_mm
        # - self.n_images
        # - self.calib_video_left_path
        # - self.calib_video_right_path

        self.configured = True
        self.status_message = (
            "Camera configured successfully.\n"
            f"Cols={self.cols}, Rows={self.rows}, Square size={self.square_size_mm} mm, "
            f"Sampled frames={self.n_images}\n"
            f"LEFT={self.calib_video_left_name}, RIGHT={self.calib_video_right_name}"
        )


def number_input_card() -> rx.Component:
    return rx.box(
        rx.heading("Step 1 — Configure camera intrinsics", size="6", margin_bottom="1rem"),
        rx.box(
            rx.heading("Checkerboard settings", size="4", margin_bottom="0.75rem"),
            rx.hstack(
                rx.box(
                    rx.text("Cols (internal corners)", margin_bottom="0.35rem"),
                    rx.input(
                        type="number",
                        value=State.cols,
                        min=3,
                        max=25,
                        step=1,
                        on_change=State.set_cols,
                        width="100%",
                    ),
                    width="100%",
                ),
                rx.box(
                    rx.text("Rows (internal corners)", margin_bottom="0.35rem"),
                    rx.input(
                        type="number",
                        value=State.rows,
                        min=3,
                        max=25,
                        step=1,
                        on_change=State.set_rows,
                        width="100%",
                    ),
                    width="100%",
                ),
                rx.box(
                    rx.text("Square size (mm)", margin_bottom="0.35rem"),
                    rx.input(
                        type="number",
                        value=State.square_size_mm,
                        min=1,
                        max=200,
                        step=1,
                        on_change=State.set_square_size_mm,
                        width="100%",
                    ),
                    width="100%",
                ),
                spacing="4",
                width="100%",
                align="end",
            ),
            padding="1.25rem",
            border="1px solid #e5e7eb",
            border_radius="12px",
            margin_bottom="1.25rem",
            width="100%",
        ),
        width="100%",
    )


def upload_box(
    title: str,
    upload_id: str,
    button_label: str,
    filename_var,
    upload_handler,
) -> rx.Component:
    return rx.box(
        rx.text(title, weight="medium", margin_bottom="0.5rem"),
        rx.upload(
            rx.vstack(
                rx.button(button_label),
                rx.text("Accepted formats: .mov, .mp4, .avi, .mkv", size="2", color="gray"),
                spacing="2",
                align="start",
            ),
            id=upload_id,
            multiple=False,
            accept={
                "video/*": [".mov", ".mp4", ".avi", ".mkv"],
            },
            border="1px dashed #cbd5e1",
            padding="1rem",
            border_radius="12px",
            width="100%",
        ),
        rx.cond(
            filename_var != "",
            rx.text(f"Selected file: ", rx.code(filename_var), margin_top="0.5rem"),
            rx.text("No file uploaded yet.", margin_top="0.5rem", color="gray"),
        ),
        rx.button(
            "Upload",
            on_click=upload_handler(rx.upload_files(upload_id=upload_id)),
            margin_top="0.75rem",
            width="100%",
        ),
        padding="1rem",
        border="1px solid #e5e7eb",
        border_radius="12px",
        width="100%",
    )


def calibration_page() -> rx.Component:
    return rx.container(
        rx.vstack(
            number_input_card(),
            rx.hstack(
                upload_box(
                    title="Upload LEFT calibration video",
                    upload_id="left_upload",
                    button_label="Choose LEFT video",
                    filename_var=State.calib_video_left_name,
                    upload_handler=State.handle_left_upload,
                ),
                upload_box(
                    title="Upload RIGHT calibration video",
                    upload_id="right_upload",
                    button_label="Choose RIGHT video",
                    filename_var=State.calib_video_right_name,
                    upload_handler=State.handle_right_upload,
                ),
                spacing="4",
                width="100%",
                flex_wrap="wrap",
            ),
            rx.box(
                rx.text("Number of sampled frames per calibration video", margin_bottom="0.35rem"),
                rx.input(
                    type="number",
                    value=State.n_images,
                    min=5,
                    max=100,
                    step=1,
                    on_change=State.set_n_images,
                    width="220px",
                ),
                margin_top="1rem",
                width="100%",
            ),
            rx.text(
                "Each calibration video should show the checkerboard from multiple positions and angles.",
                color="gray",
                size="2",
                width="100%",
            ),
            rx.button(
                "⚙️ Configure camera",
                on_click=State.configure_camera,
                disabled=~State.can_configure,
                size="3",
                margin_top="0.75rem",
            ),
            rx.cond(
                State.status_message != "",
                rx.callout(
                    State.status_message,
                    icon="info",
                    width="100%",
                ),
            ),
            rx.cond(
                State.configured,
                rx.badge("Configured", color_scheme="green", size="2"),
            ),
            spacing="4",
            width="100%",
            max_width="900px",
            align="start",
        ),
        padding_y="2rem",
    )


app = rx.App()
app.add_page(calibration_page, route="/")