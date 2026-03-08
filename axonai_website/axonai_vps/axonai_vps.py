from pathlib import Path
import reflex as rx


UPLOAD_DIR = Path("uploaded_files")
UPLOAD_DIR.mkdir(exist_ok=True)

REPORTS_DIR = Path("generated_reports")
REPORTS_DIR.mkdir(exist_ok=True)


class State(rx.State):
    """App state."""

    # -------------------------
    # Camera configuration page
    # -------------------------
    cols: int = 6
    rows: int = 9
    square_size_mm: float = 25.0
    n_images: int = 25

    calib_video_left_name: str = ""
    calib_video_right_name: str = ""
    calib_video_left_path: str = ""
    calib_video_right_path: str = ""

    configured: bool = False

    # -------------------------
    # Report page
    # -------------------------
    patient_left_video_name: str = ""
    patient_right_video_name: str = ""
    patient_left_video_path: str = ""
    patient_right_video_path: str = ""

    report_status: str = ""
    status_message: str = ""

    @rx.var
    def can_configure(self) -> bool:
        return bool(self.calib_video_left_name and self.calib_video_right_name)

    @rx.var
    def can_generate_report(self) -> bool:
        return bool(self.patient_left_video_name and self.patient_right_video_name)

    # -------------------------
    # Camera uploads
    # -------------------------
    async def handle_left_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        file = files[0]
        data = await file.read()
        save_path = UPLOAD_DIR / f"calib_left_{file.filename}"
        save_path.write_bytes(data)

        self.calib_video_left_name = file.filename
        self.calib_video_left_path = str(save_path)
        self.status_message = f"Uploaded LEFT calibration video: {file.filename}"
        self.configured = False

    async def handle_right_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        file = files[0]
        data = await file.read()
        save_path = UPLOAD_DIR / f"calib_right_{file.filename}"
        save_path.write_bytes(data)

        self.calib_video_right_name = file.filename
        self.calib_video_right_path = str(save_path)
        self.status_message = f"Uploaded RIGHT calibration video: {file.filename}"
        self.configured = False

    # -------------------------
    # Patient walking video uploads
    # -------------------------
    async def handle_patient_left_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        file = files[0]
        data = await file.read()
        save_path = UPLOAD_DIR / f"patient_left_{file.filename}"
        save_path.write_bytes(data)

        self.patient_left_video_name = file.filename
        self.patient_left_video_path = str(save_path)
        self.report_status = f"Uploaded patient LEFT walking video: {file.filename}"

    async def handle_patient_right_upload(self, files: list[rx.UploadFile]):
        if not files:
            return
        file = files[0]
        data = await file.read()
        save_path = UPLOAD_DIR / f"patient_right_{file.filename}"
        save_path.write_bytes(data)

        self.patient_right_video_name = file.filename
        self.patient_right_video_path = str(save_path)
        self.report_status = f"Uploaded patient RIGHT walking video: {file.filename}"

    # -------------------------
    # Field setters
    # -------------------------
    def set_cols(self, value):
        self.cols = int(value)

    def set_rows(self, value):
        self.rows = int(value)

    def set_square_size_mm(self, value):
        self.square_size_mm = float(value)

    def set_n_images(self, value):
        self.n_images = int(value)

    # -------------------------
    # Navigation / actions
    # -------------------------
    def configure_camera(self):
        """For now, just validate and redirect to the report page."""
        if not self.can_configure:
            self.status_message = "Please upload both LEFT and RIGHT calibration videos first."
            self.configured = False
            return

        self.configured = True
        self.status_message = (
            f"Camera configured successfully. "
            f"Cols={self.cols}, Rows={self.rows}, "
            f"Square size={self.square_size_mm} mm, "
            f"Frames={self.n_images}."
        )
        return rx.redirect("/report")

    def generate_empty_pdf_and_download(self):
        """Create a placeholder PDF and download it."""
        if not self.can_generate_report:
            self.report_status = "Please upload both LEFT and RIGHT patient walking videos first."
            return

        pdf_path = REPORTS_DIR / "axonai_report_placeholder.pdf"

        # Minimal valid PDF bytes.
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj<<>>endobj\n"
            b"2 0 obj<< /Type /Catalog /Pages 3 0 R >>endobj\n"
            b"3 0 obj<< /Type /Pages /Kids [4 0 R] /Count 1 >>endobj\n"
            b"4 0 obj<< /Type /Page /Parent 3 0 R /MediaBox [0 0 595 842] "
            b"/Contents 5 0 R /Resources <<>> >>endobj\n"
            b"5 0 obj<< /Length 0 >>stream\n"
            b"\n"
            b"endstream\n"
            b"endobj\n"
            b"xref\n"
            b"0 6\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000028 00000 n \n"
            b"0000000077 00000 n \n"
            b"0000000136 00000 n \n"
            b"0000000240 00000 n \n"
            b"trailer<< /Root 2 0 R /Size 6 >>\n"
            b"startxref\n"
            b"289\n"
            b"%%EOF"
        )
        pdf_path.write_bytes(pdf_bytes)

        self.report_status = "Placeholder PDF generated. Download should start automatically."
        return rx.download(
            url=f"/{pdf_path.as_posix()}",
            filename="axonai_report.pdf",
        )


def animated_background_wave() -> rx.Component:
    return rx.box(
        rx.box(
            position="absolute",
            top="-10%",
            left="-10%",
            width="28rem",
            height="28rem",
            border_radius="9999px",
            background="radial-gradient(circle, rgba(59,130,246,0.28) 0%, rgba(59,130,246,0.00) 70%)",
            filter="blur(20px)",
            animation="float1 12s ease-in-out infinite",
        ),
        rx.box(
            position="absolute",
            bottom="-15%",
            right="-10%",
            width="30rem",
            height="30rem",
            border_radius="9999px",
            background="radial-gradient(circle, rgba(16,185,129,0.22) 0%, rgba(16,185,129,0.00) 70%)",
            filter="blur(28px)",
            animation="float2 14s ease-in-out infinite",
        ),
        rx.box(
            position="absolute",
            top="18%",
            right="18%",
            width="16rem",
            height="16rem",
            border_radius="9999px",
            background="radial-gradient(circle, rgba(255,255,255,0.16) 0%, rgba(255,255,255,0.00) 70%)",
            filter="blur(18px)",
            animation="float3 10s ease-in-out infinite",
        ),
        position="absolute",
        inset="0",
        overflow="hidden",
        z_index="0",
        pointer_events="none",
    )


def landing_page() -> rx.Component:
    return rx.box(
        rx.el.style(
            """
            @keyframes waveDrift1 {
                0% { transform: translateX(0px) translateY(0px); }
                50% { transform: translateX(-30px) translateY(10px); }
                100% { transform: translateX(0px) translateY(0px); }
            }

            @keyframes waveDrift2 {
                0% { transform: translateX(0px) translateY(0px); }
                50% { transform: translateX(35px) translateY(-12px); }
                100% { transform: translateX(0px) translateY(0px); }
            }

            @keyframes waveDrift3 {
                0% { transform: translateX(0px) translateY(0px); }
                50% { transform: translateX(-22px) translateY(8px); }
                100% { transform: translateX(0px) translateY(0px); }
            }

            @keyframes hueShift1 {
                0% { fill: rgba(180, 120, 255, 0.78); }
                33% { fill: rgba(80, 210, 255, 0.74); }
                66% { fill: rgba(120, 120, 255, 0.72); }
                100% { fill: rgba(180, 120, 255, 0.78); }
            }

            @keyframes hueShift2 {
                0% { fill: rgba(60, 210, 255, 0.72); }
                33% { fill: rgba(170, 120, 255, 0.70); }
                66% { fill: rgba(70, 160, 255, 0.72); }
                100% { fill: rgba(60, 210, 255, 0.72); }
            }

            @keyframes hueShift3 {
                0% { fill: rgba(95, 74, 255, 0.62); }
                33% { fill: rgba(40, 180, 255, 0.58); }
                66% { fill: rgba(160, 110, 255, 0.60); }
                100% { fill: rgba(95, 74, 255, 0.62); }
            }

            @keyframes glowPulse {
                0% { opacity: 0.28; transform: scale(1); }
                50% { opacity: 0.48; transform: scale(1.05); }
                100% { opacity: 0.28; transform: scale(1); }
            }

            @keyframes grainMove {
                0% { transform: translate(0, 0); }
                25% { transform: translate(-1%, 1%); }
                50% { transform: translate(1%, -1%); }
                75% { transform: translate(1%, 1%); }
                100% { transform: translate(0, 0); }
            }
            """
        ),

        # base background
        rx.box(
            position="absolute",
            inset="0",
            background="""
                radial-gradient(circle at 20% 20%, rgba(140,90,255,0.10) 0%, rgba(140,90,255,0.00) 24%),
                radial-gradient(circle at 80% 75%, rgba(0,210,220,0.08) 0%, rgba(0,210,220,0.00) 20%),
                linear-gradient(180deg, #05070c 0%, #070b14 34%, #07111c 68%, #06090f 100%)
            """,
            z_index="0",
        ),

        # soft glows
        rx.box(
            position="absolute",
            left="10%",
            top="16%",
            width="24rem",
            height="24rem",
            border_radius="9999px",
            background="radial-gradient(circle, rgba(193,139,255,0.18) 0%, rgba(193,139,255,0.00) 72%)",
            filter="blur(56px)",
            style={"animation": "glowPulse 9s ease-in-out infinite"},
            z_index="0",
            pointer_events="none",
        ),
        rx.box(
            position="absolute",
            right="8%",
            bottom="10%",
            width="26rem",
            height="26rem",
            border_radius="9999px",
            background="radial-gradient(circle, rgba(60,220,255,0.14) 0%, rgba(60,220,255,0.00) 72%)",
            filter="blur(60px)",
            style={"animation": "glowPulse 11s ease-in-out infinite"},
            z_index="0",
            pointer_events="none",
        ),

        # moving color-changing waves
        rx.el.svg(
            rx.el.path(
                d="M 0 620 C 140 560, 260 300, 430 260 C 620 215, 760 470, 980 500 C 1180 528, 1320 430, 1510 450 C 1700 470, 1860 610, 2000 650 L 2000 900 L 0 900 Z",
                style={
                    "animation": "waveDrift1 11s ease-in-out infinite, hueShift1 14s ease-in-out infinite"
                },
            ),
            rx.el.path(
                d="M 0 700 C 180 660, 300 430, 500 380 C 700 330, 840 560, 1060 610 C 1260 656, 1440 610, 1630 560 C 1810 512, 1910 520, 2000 540 L 2000 900 L 0 900 Z",
                style={
                    "animation": "waveDrift2 13s ease-in-out infinite, hueShift2 16s ease-in-out infinite"
                },
            ),
            rx.el.path(
                d="M 0 790 C 180 730, 360 600, 560 590 C 760 580, 930 700, 1140 740 C 1340 778, 1540 720, 1760 690 C 1880 674, 1940 680, 2000 700 L 2000 900 L 0 900 Z",
                style={
                    "animation": "waveDrift3 15s ease-in-out infinite, hueShift3 18s ease-in-out infinite"
                },
            ),
            viewBox="0 0 2000 900",
            preserveAspectRatio="none",
            width="100%",
            height="100%",
            position="absolute",
            inset="0",
            z_index="1",
            pointer_events="none",
        ),

        # vignette
        rx.box(
            position="absolute",
            inset="0",
            background="""
                radial-gradient(circle at center, rgba(0,0,0,0.00) 0%, rgba(0,0,0,0.14) 58%, rgba(0,0,0,0.34) 100%)
            """,
            z_index="2",
            pointer_events="none",
        ),

        # grain
        rx.box(
            position="absolute",
            inset="-10%",
            opacity="0.08",
            background="""
                radial-gradient(circle at 20% 20%, rgba(255,255,255,0.22) 0 0.6px, transparent 0.8px),
                radial-gradient(circle at 80% 30%, rgba(255,255,255,0.18) 0 0.7px, transparent 0.9px),
                radial-gradient(circle at 40% 80%, rgba(255,255,255,0.14) 0 0.7px, transparent 0.9px),
                radial-gradient(circle at 70% 70%, rgba(255,255,255,0.12) 0 0.6px, transparent 0.8px)
            """,
            background_size="20px 20px, 24px 24px, 28px 28px, 18px 18px",
            animation="grainMove 7s steps(6) infinite",
            pointer_events="none",
            z_index="3",
        ),
        # Content
        rx.vstack(
            rx.heading(
                "AxonAI is the first computer vision AI technology that understands human gait.",
                size="9",
                text_align="center",
                color="white",
                max_width="1200px",
                line_height="1.05",
                letter_spacing="-0.03em",
                text_shadow="0 2px 24px rgba(0,0,0,0.35)",
            ),
            rx.text(
                "Built by AI researchers and industry experts from",
                font_size="1.05rem",
                text_align="center",
                color="rgba(255,255,255,0.82)",
                max_width="980px",
                line_height="1.5",
            ),
        rx.hstack(
            rx.text(
                "Google DeepMind",
                color="rgba(255,255,255,0.78)",
                font_size="1.15rem",
                font_weight="500",
            ),

            rx.text(
                "IMPERIAL",
                color="rgba(255,255,255,0.92)",
                font_size="1.5rem",
                font_weight="700",
                letter_spacing="0.18em",
            ),

            rx.vstack(
                rx.text(
                    "BOSTON",
                    color="rgba(255,255,255,0.78)",
                    font_size="1.7rem",
                    font_weight="500",
                    letter_spacing="0.18em",
                    font_family="Georgia, 'Times New Roman', serif",
                    line_height="1",
                ),
                rx.text(
                    "UNIVERSITY",
                    color="rgba(255,255,255,0.78)",
                    font_size="1.1rem",
                    font_weight="500",
                    letter_spacing="0.20em",
                    font_family="Georgia, 'Times New Roman', serif",
                    line_height="1",
                ),
                spacing="0",
                align="center",
            ),

            rx.text(
                "Xifeng People's Hospital",
                color="rgba(255,255,255,0.7)",
                font_size="1.1rem",
            ),

            spacing="8",
            justify="center",
            align="center",
            flex_wrap="wrap",
            margin_top="0.25rem",
        ),
            spacing="7",
            align="center",
            width="100%",
            position="relative",
            z_index="2",
            padding_x="1.5rem",
        ),
        min_height="100vh",
        width="100%",
        position="relative",
        display="flex",
        align_items="center",
        justify_content="center",
        overflow="hidden",
    )

def setting_input(label: str, value, on_change, min_v, max_v, step) -> rx.Component:
    return rx.box(
        rx.text(label, margin_bottom="0.45rem", font_weight="500"),
        rx.input(
            type="number",
            value=value,
            min=min_v,
            max=max_v,
            step=step,
            on_change=on_change,
            width="100%",
            size="3",
            background="white",
            border="1px solid #d1d5db",
        ),
        width="100%",
    )


def upload_panel(title: str, upload_id: str, button_text: str, filename_var, handler) -> rx.Component:
    return rx.box(
        rx.text(title, font_weight="600", font_size="1.1rem", margin_bottom="0.8rem"),
        rx.upload(
            rx.vstack(
                rx.button(button_text, variant="soft", color_scheme="blue"),
                rx.text(
                    "Accepted formats: .mov, .mp4, .avi, .mkv",
                    color="#6b7280",
                    size="2",
                ),
                align="start",
                spacing="2",
            ),
            id=upload_id,
            multiple=False,
            accept={"video/*": [".mov", ".mp4", ".avi", ".mkv"]},
            border="1px dashed #cbd5e1",
            border_radius="16px",
            padding="1.25rem",
            width="100%",
            background="#fafafa",
        ),
        rx.cond(
            filename_var != "",
            rx.text("Selected file: ", rx.code(filename_var), margin_top="0.8rem"),
            rx.text("No file uploaded yet.", margin_top="0.8rem", color="#6b7280"),
        ),
        rx.button(
            "Upload",
            on_click=handler(rx.upload_files(upload_id=upload_id)),
            width="100%",
            margin_top="0.9rem",
            size="3",
            border_radius="12px",
        ),
        background="white",
        border="1px solid #e5e7eb",
        border_radius="20px",
        padding="1.2rem",
        box_shadow="0 10px 30px rgba(2, 6, 23, 0.05)",
        width="100%",
    )


def configure_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.link(
                    rx.text("← Back", color="#2563eb", font_weight="600"),
                    href="/",
                ),
                width="100%",
            ),
            rx.heading("Step 1 — Configure camera intrinsics", size="8", color="#0f172a"),
            rx.text(
                "Set checkerboard parameters and upload stereo calibration videos.",
                color="#475569",
                size="4",
            ),
            rx.box(
                rx.heading("Checkerboard settings", size="5", margin_bottom="1rem"),
                rx.hstack(
                    setting_input("Cols (internal corners)", State.cols, State.set_cols, 3, 25, 1),
                    setting_input("Rows (internal corners)", State.rows, State.set_rows, 3, 25, 1),
                    setting_input("Square size (mm)", State.square_size_mm, State.set_square_size_mm, 1, 200, 1),
                    spacing="4",
                    width="100%",
                    flex_wrap="wrap",
                ),
                background="rgba(255,255,255,0.9)",
                border="1px solid #e5e7eb",
                border_radius="22px",
                padding="1.5rem",
                box_shadow="0 12px 35px rgba(15, 23, 42, 0.06)",
                width="100%",
            ),
            rx.hstack(
                upload_panel(
                    "Upload LEFT calibration video",
                    "left_upload",
                    "Choose LEFT video",
                    State.calib_video_left_name,
                    State.handle_left_upload,
                ),
                upload_panel(
                    "Upload RIGHT calibration video",
                    "right_upload",
                    "Choose RIGHT video",
                    State.calib_video_right_name,
                    State.handle_right_upload,
                ),
                spacing="4",
                width="100%",
                flex_wrap="wrap",
                align="start",
            ),
            rx.box(
                rx.text(
                    "Number of sampled frames per calibration video",
                    margin_bottom="0.45rem",
                    font_weight="500",
                ),
                rx.input(
                    type="number",
                    value=State.n_images,
                    min=5,
                    max=100,
                    step=1,
                    on_change=State.set_n_images,
                    width="240px",
                    background="white",
                ),
                width="100%",
            ),
            rx.text(
                "Each calibration video should show the checkerboard from multiple positions and angles.",
                color="#64748b",
                size="3",
            ),
            rx.button(
                "⚙️ Configure camera",
                on_click=State.configure_camera,
                size="4",
                border_radius="9999px",
                padding_x="1.5rem",
            ),
            rx.cond(
                State.status_message != "",
                rx.callout(State.status_message, icon="info", width="100%"),
            ),
            rx.cond(
                State.configured,
                rx.badge("Configured", color_scheme="green", size="3"),
            ),
            spacing="5",
            align="start",
            width="100%",
            max_width="1200px",
        ),
        min_height="100vh",
        width="100%",
        padding="2.5rem",
        background="""
            radial-gradient(circle at top left, rgba(59,130,246,0.10), transparent 30%),
            linear-gradient(180deg, #f8fbff 0%, #f3f6fb 100%)
        """,
    )


def report_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.link(
                    rx.text("← Back to configuration", color="#2563eb", font_weight="600"),
                    href="/configure",
                ),
                width="100%",
            ),
            rx.heading("Step 2 — Generate patient report", size="8", color="#0f172a"),
            rx.text(
                "Upload the patient's walking videos from the left and right cameras, then generate a report.",
                color="#475569",
                size="4",
            ),
            rx.hstack(
                upload_panel(
                    "Upload patient LEFT walking video",
                    "patient_left_upload",
                    "Choose LEFT walking video",
                    State.patient_left_video_name,
                    State.handle_patient_left_upload,
                ),
                upload_panel(
                    "Upload patient RIGHT walking video",
                    "patient_right_upload",
                    "Choose RIGHT walking video",
                    State.patient_right_video_name,
                    State.handle_patient_right_upload,
                ),
                spacing="4",
                width="100%",
                flex_wrap="wrap",
                align="start",
            ),
            rx.button(
                "Generate report",
                on_click=State.generate_empty_pdf_and_download,
                disabled=~State.can_generate_report,
                size="4",
                border_radius="9999px",
                padding_x="1.5rem",
            ),
            rx.cond(
                State.report_status != "",
                rx.callout(State.report_status, icon="info", width="100%"),
            ),
            spacing="5",
            align="start",
            width="100%",
            max_width="1200px",
        ),
        min_height="100vh",
        width="100%",
        padding="2.5rem",
        background="""
            radial-gradient(circle at top left, rgba(16,185,129,0.08), transparent 30%),
            linear-gradient(180deg, #f8fbff 0%, #f3f6fb 100%)
        """,
    )


app = rx.App(
    theme=rx.theme(
        appearance="light",
        has_background=True,
        radius="large",
        accent_color="blue",
    ),
)

app.add_page(landing_page, route="/", title="AxonAI")
app.add_page(configure_page, route="/configure", title="Configure Camera")
app.add_page(report_page, route="/report", title="Generate Report")