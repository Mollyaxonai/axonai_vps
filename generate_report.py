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


# -----------------------------
# CONFIG
# -----------------------------

JSON_FILE = "gait_output.json"
PLOT_DIR = "plots"
PDF_NAME = "clinical_gait_report.pdf"

os.makedirs(PLOT_DIR, exist_ok=True)

styles = getSampleStyleSheet()


# -----------------------------
# LOAD JSON
# -----------------------------

with open(JSON_FILE) as f:
    raw = json.load(f)

gait_metrics = raw["gait_analysis"]["body"]["metrics"]
datasets = raw["gait_analysis"]["body"]["datasets"]

df = pd.DataFrame(datasets)


# -----------------------------
# EVALUATE GAIT METRICS
# -----------------------------

def evaluate_metric(m):

    value = m["value"]

    if value < m["min_limit"]:
        return "Below", colors.orange

    if value > m["max_limit"]:
        return "Above", colors.red

    return "Normal", colors.green


metric_rows = [["Metric","Value","Reference","Status"]]

for key,m in gait_metrics.items():

    status,color = evaluate_metric(m)

    metric_rows.append([
        m["label"],
        round(m["value"],3),
        f'{m["min_limit"]}-{m["max_limit"]}',
        status
    ])


# -----------------------------
# RANGE OF MOTION
# -----------------------------

rom_rows = [["Joint","ROM"]]

for col in df.columns:

    if col == "time":
        continue

    rom = round(df[col].max() - df[col].min(),2)

    rom_rows.append([col,rom])


# -----------------------------
# SYMMETRY
# -----------------------------

def find_pairs(columns):

    pairs = []

    for col in columns:

        if col.endswith("_l"):

            r = col.replace("_l","_r")

            if r in columns:
                pairs.append((col,r))

    return pairs


pairs = find_pairs(df.columns)

symmetry_rows = [["Joint","Mean L-R Difference"]]

for l,r in pairs:

    diff = abs(df[l]-df[r]).mean()

    symmetry_rows.append([
        l.replace("_l",""),
        round(diff,2)
    ])


# -----------------------------
# VARIABLE GROUPING
# -----------------------------

GROUPS = {
    "Pelvis": [],
    "Right Leg": [],
    "Left Leg": [],
    "Lumbar": [],
    "Right Arm": [],
    "Left Arm": [],
    "Other": []
}

for col in df.columns:

    if col == "time":
        continue

    if "pelvis" in col:
        GROUPS["Pelvis"].append(col)

    elif col.endswith("_r") and any(x in col for x in ["hip","knee","ankle","subtalar"]):
        GROUPS["Right Leg"].append(col)

    elif col.endswith("_l") and any(x in col for x in ["hip","knee","ankle","subtalar"]):
        GROUPS["Left Leg"].append(col)

    elif "lumbar" in col:
        GROUPS["Lumbar"].append(col)

    elif col.endswith("_r") and any(x in col for x in ["arm","elbow"]):
        GROUPS["Right Arm"].append(col)

    elif col.endswith("_l") and any(x in col for x in ["arm","elbow"]):
        GROUPS["Left Arm"].append(col)

    else:
        GROUPS["Other"].append(col)


# -----------------------------
# PLOT GENERATION
# -----------------------------

def make_plot(column):

    plt.figure(figsize=(6,3))

    plt.plot(df["time"],df[column])

    plt.title(column.replace("_"," ").title())
    plt.xlabel("Time (s)")
    plt.ylabel("Value")

    plt.tight_layout()

    filename = os.path.join(PLOT_DIR,f"{column}.png")

    plt.savefig(filename)

    plt.close()

    return filename


plot_files = {}

for group in GROUPS:

    plot_files[group] = []

    for col in GROUPS[group]:

        if col in df.columns:

            plot_files[group].append(
                make_plot(col)
            )


# -----------------------------
# BUILD PDF
# -----------------------------

elements = []

# Title
elements.append(
    Paragraph("Clinical Gait Analysis Report", styles["Title"])
)

elements.append(Spacer(1,20))


# -----------------------------
# GAIT MEASURES
# -----------------------------

elements.append(
    Paragraph("Gait Measures", styles["Heading2"])
)

elements.append(Spacer(1,10))

metric_table = Table(metric_rows)

metric_table.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
    ("GRID",(0,0),(-1,-1),1,colors.grey)
]))

elements.append(metric_table)

elements.append(PageBreak())


# -----------------------------
# RANGE OF MOTION
# -----------------------------

elements.append(
    Paragraph("Range of Motion Summary", styles["Heading2"])
)

elements.append(Spacer(1,10))

rom_table = Table(rom_rows)

rom_table.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
    ("GRID",(0,0),(-1,-1),1,colors.grey)
]))

elements.append(rom_table)

elements.append(PageBreak())


# -----------------------------
# SYMMETRY
# -----------------------------

elements.append(
    Paragraph("Left–Right Symmetry", styles["Heading2"])
)

elements.append(Spacer(1,10))

sym_table = Table(symmetry_rows)

sym_table.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),
    ("GRID",(0,0),(-1,-1),1,colors.grey)
]))

elements.append(sym_table)

elements.append(PageBreak())


# -----------------------------
# PLOTS
# -----------------------------

for group in GROUPS:

    if len(plot_files[group]) == 0:
        continue

    elements.append(
        Paragraph(group + " Kinematics", styles["Heading2"])
    )

    elements.append(Spacer(1,10))

    for img in plot_files[group]:

        elements.append(
            Image(img,width=5.5*inch,height=2.5*inch)
        )

        elements.append(Spacer(1,10))

    elements.append(PageBreak())


# -----------------------------
# EXPORT
# -----------------------------

doc = SimpleDocTemplate(
    PDF_NAME,
    pagesize=A4
)

doc.build(elements)

print("Clinical report generated:",PDF_NAME)