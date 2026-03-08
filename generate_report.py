import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak
)

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors


styles = getSampleStyleSheet()


# -----------------------------
# HELPERS
# -----------------------------

def evaluate_metric(m):

    value = m["value"]

    if value < m["min_limit"]:
        return "Below", colors.orange

    if value > m["max_limit"]:
        return "Above", colors.red

    return "Normal", colors.green


def find_pairs(columns):

    pairs = []

    for col in columns:

        if col.endswith("_l"):

            r = col.replace("_l", "_r")

            if r in columns:
                pairs.append((col, r))

    return pairs


def make_plot(df, column, plot_dir):

    plt.figure(figsize=(6, 3))

    plt.plot(df["time"], df[column])

    plt.title(column.replace("_", " ").title())
    plt.xlabel("Time (s)")
    plt.ylabel("Value")

    plt.tight_layout()

    filename = os.path.join(plot_dir, f"{column}.png")

    plt.savefig(filename)
    plt.close()

    return filename


def group_variables(columns):

    groups = {
        "Pelvis": [],
        "Right Leg": [],
        "Left Leg": [],
        "Lumbar": [],
        "Right Arm": [],
        "Left Arm": [],
        "Other": []
    }

    for col in columns:

        if col == "time":
            continue

        if "pelvis" in col:
            groups["Pelvis"].append(col)

        elif col.endswith("_r") and any(x in col for x in ["hip", "knee", "ankle", "subtalar"]):
            groups["Right Leg"].append(col)

        elif col.endswith("_l") and any(x in col for x in ["hip", "knee", "ankle", "subtalar"]):
            groups["Left Leg"].append(col)

        elif "lumbar" in col:
            groups["Lumbar"].append(col)

        elif col.endswith("_r") and any(x in col for x in ["arm", "elbow"]):
            groups["Right Arm"].append(col)

        elif col.endswith("_l") and any(x in col for x in ["arm", "elbow"]):
            groups["Left Arm"].append(col)

        else:
            groups["Other"].append(col)

    return groups


# -----------------------------
# MAIN REPORT FUNCTION
# -----------------------------

def generate_clinical_report(
    json_file,
    output_pdf="clinical_gait_report.pdf",
    plot_dir="plots"
):
    """
    Generate a clinical gait PDF report from gait JSON output.

    Parameters
    ----------
    json_file : str
        Path to gait_output.json
    output_pdf : str
        Output PDF file name
    plot_dir : str
        Directory to store generated plots
    """

    os.makedirs(plot_dir, exist_ok=True)

    # -----------------------------
    # LOAD JSON
    # -----------------------------

    with open(json_file) as f:
        raw = json.load(f)

    gait_metrics = raw["gait_analysis"]["body"]["metrics"]
    datasets = raw["gait_analysis"]["body"]["datasets"]

    df = pd.DataFrame(datasets)

    # -----------------------------
    # GAIT METRICS TABLE
    # -----------------------------

    metric_rows = [["Metric", "Value", "Reference", "Status"]]

    for key, m in gait_metrics.items():

        status, color = evaluate_metric(m)

        metric_rows.append([
            m["label"],
            round(m["value"], 3),
            f'{m["min_limit"]}-{m["max_limit"]}',
            status
        ])

    # -----------------------------
    # RANGE OF MOTION
    # -----------------------------

    rom_rows = [["Joint", "ROM"]]

    for col in df.columns:

        if col == "time":
            continue

        rom = round(df[col].max() - df[col].min(), 2)

        rom_rows.append([col, rom])

    # -----------------------------
    # SYMMETRY
    # -----------------------------

    pairs = find_pairs(df.columns)

    symmetry_rows = [["Joint", "Mean L-R Difference"]]

    for l, r in pairs:

        diff = abs(df[l] - df[r]).mean()

        symmetry_rows.append([
            l.replace("_l", ""),
            round(diff, 2)
        ])

    # -----------------------------
    # VARIABLE GROUPING
    # -----------------------------

    groups = group_variables(df.columns)

    # -----------------------------
    # PLOT GENERATION
    # -----------------------------

    plot_files = {}

    for group in groups:

        plot_files[group] = []

        for col in groups[group]:

            if col in df.columns:

                plot_files[group].append(
                    make_plot(df, col, plot_dir)
                )

    # -----------------------------
    # BUILD PDF
    # -----------------------------

    elements = []

    elements.append(
        Paragraph("Clinical Gait Analysis Report", styles["Title"])
    )

    elements.append(Spacer(1, 20))

    # Gait measures

    elements.append(
        Paragraph("Gait Measures", styles["Heading2"])
    )

    elements.append(Spacer(1, 10))

    metric_table = Table(metric_rows)

    metric_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey)
    ]))

    elements.append(metric_table)
    elements.append(PageBreak())

    # ROM

    elements.append(
        Paragraph("Range of Motion Summary", styles["Heading2"])
    )

    elements.append(Spacer(1, 10))

    rom_table = Table(rom_rows)

    rom_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey)
    ]))

    elements.append(rom_table)
    elements.append(PageBreak())

    # Symmetry

    elements.append(
        Paragraph("Left–Right Symmetry", styles["Heading2"])
    )

    elements.append(Spacer(1, 10))

    sym_table = Table(symmetry_rows)

    sym_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey)
    ]))

    elements.append(sym_table)
    elements.append(PageBreak())

    # Plots

    for group in groups:

        if len(plot_files[group]) == 0:
            continue

        elements.append(
            Paragraph(group + " Kinematics", styles["Heading2"])
        )

        elements.append(Spacer(1, 10))

        for img in plot_files[group]:

            elements.append(
                Image(img, width=5.5 * inch, height=2.5 * inch)
            )

            elements.append(Spacer(1, 10))

        elements.append(PageBreak())

    # -----------------------------
    # EXPORT
    # -----------------------------

    doc = SimpleDocTemplate(
        output_pdf,
        pagesize=A4
    )

    doc.build(elements)

    print("Clinical report generated:", output_pdf)