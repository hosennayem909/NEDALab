"""Excel export with multiple sheets."""
import io
import json
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows


EMERALD = "047857"
CREAM = "FAF8F3"
GRAY_HEADER = "F4F1EA"


def _style_header(cell):
    cell.font = Font(bold=True, color="FFFFFF", size=11, name="Calibri")
    cell.fill = PatternFill("solid", fgColor=EMERALD)
    cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    cell.border = Border(bottom=Side(style="thin", color="FFFFFF"))


def _style_title(cell):
    cell.font = Font(bold=True, size=14, color=EMERALD, name="Calibri")
    cell.alignment = Alignment(vertical="center")


def export_dataset_excel(
    df: pd.DataFrame,
    dataset_name: str,
    cleaning_report: dict | None = None,
    stats: dict | None = None,
    model_result: dict | None = None,
) -> bytes:
    """Export dataset + optional analysis to Excel with multiple sheets."""
    wb = Workbook()

    # ===== Sheet 1: Data =====
    ws_data = wb.active
    ws_data.title = "Data"

    # Header row
    for col_idx, col_name in enumerate(df.columns, 1):
        c = ws_data.cell(row=1, column=col_idx, value=str(col_name))
        _style_header(c)

    # Data rows
    for r_idx, row in enumerate(df.itertuples(index=False), 2):
        for c_idx, val in enumerate(row, 1):
            # Handle NaN
            if pd.isna(val):
                val = ""
            ws_data.cell(row=r_idx, column=c_idx, value=val)

    # Auto-width columns (limited)
    for col_idx, col_name in enumerate(df.columns, 1):
        max_len = max(len(str(col_name)), 10)
        sample_vals = df[col_name].head(100).astype(str)
        if len(sample_vals):
            max_len = max(max_len, int(sample_vals.str.len().max()) + 2)
        col_letter = ws_data.cell(row=1, column=col_idx).column_letter
        ws_data.column_dimensions[col_letter].width = min(max_len, 40)

    ws_data.freeze_panes = "A2"

    # ===== Sheet 2: Summary =====
    ws_summary = wb.create_sheet("Summary")
    row = 1

    c = ws_summary.cell(row=row, column=1, value="Dataset Overview")
    _style_title(c)
    row += 2

    info = [
        ("Dataset name", dataset_name),
        ("Total rows", len(df)),
        ("Total columns", len(df.columns)),
        ("Columns", ", ".join(str(c) for c in df.columns)),
    ]
    for label, val in info:
        ws_summary.cell(row=row, column=1, value=label).font = Font(bold=True)
        ws_summary.cell(row=row, column=2, value=str(val))
        row += 1

    # Stats
    if stats and stats.get("numeric"):
        row += 2
        c = ws_summary.cell(row=row, column=1, value="Numeric Column Statistics")
        _style_title(c)
        row += 1

        headers = ["Column", "Count", "Mean", "Std", "Min", "Q1", "Median", "Q3", "Max"]
        for i, h in enumerate(headers, 1):
            _style_header(ws_summary.cell(row=row, column=i, value=h))
        row += 1

        for col, s in stats["numeric"].items():
            if not isinstance(s, dict):
                continue
            vals = [
                col,
                s.get("count", ""),
                s.get("mean", ""),
                s.get("std", ""),
                s.get("min", ""),
                s.get("q1", ""),
                s.get("median", ""),
                s.get("q3", ""),
                s.get("max", ""),
            ]
            for i, v in enumerate(vals, 1):
                ws_summary.cell(row=row, column=i, value=v)
            row += 1

    # Cleaning report
    if cleaning_report:
        row += 2
        c = ws_summary.cell(row=row, column=1, value="Cleaning Report")
        _style_title(c)
        row += 1

        preset = cleaning_report.get("preset", "")
        ws_summary.cell(row=row, column=1, value="Preset").font = Font(bold=True)
        ws_summary.cell(row=row, column=2, value=preset)
        row += 1

        log = cleaning_report.get("log", [])
        if log:
            ws_summary.cell(row=row, column=1, value="Actions").font = Font(bold=True)
            row += 1
            for entry in log:
                ws_summary.cell(row=row, column=2, value="• " + str(entry))
                row += 1

        sb = cleaning_report.get("stats_before", {})
        sa = cleaning_report.get("stats_after", {})
        if sb or sa:
            row += 1
            for i, h in enumerate(["Metric", "Before", "After"], 1):
                _style_header(ws_summary.cell(row=row, column=i, value=h))
            row += 1
            for k in ["rows", "columns", "missing", "duplicates"]:
                ws_summary.cell(row=row, column=1, value=k.capitalize())
                ws_summary.cell(row=row, column=2, value=sb.get(k, ""))
                ws_summary.cell(row=row, column=3, value=sa.get(k, ""))
                row += 1

    # Model result
    if model_result:
        row += 2
        c = ws_summary.cell(row=row, column=1, value="Model Results")
        _style_title(c)
        row += 1

        for k in ["model_type", "dependent_var", "n_obs", "r_squared", "adj_r_squared", "f_statistic", "durbin_watson"]:
            if k in model_result:
                ws_summary.cell(row=row, column=1, value=k.replace("_", " ").title()).font = Font(bold=True)
                ws_summary.cell(row=row, column=2, value=str(model_result[k]))
                row += 1

        coeffs = model_result.get("coefficients", [])
        if coeffs:
            row += 1
            headers = ["Variable", "Coef", "Std Err", "t", "p-value", "CI Lower", "CI Upper", "Sig"]
            for i, h in enumerate(headers, 1):
                _style_header(ws_summary.cell(row=row, column=i, value=h))
            row += 1
            for c2 in coeffs:
                vals = [
                    c2.get("variable", ""),
                    c2.get("coef", ""),
                    c2.get("std_err", ""),
                    c2.get("t_stat", ""),
                    c2.get("p_value", ""),
                    c2.get("ci_lower", ""),
                    c2.get("ci_upper", ""),
                    c2.get("significance", ""),
                ]
                for i, v in enumerate(vals, 1):
                    ws_summary.cell(row=row, column=i, value=v)
                row += 1

    # Column widths for summary
    for col_letter, width in [("A", 22), ("B", 18), ("C", 18), ("D", 12), ("E", 14), ("F", 14), ("G", 14), ("H", 10), ("I", 14)]:
        ws_summary.column_dimensions[col_letter].width = width

    # Save to bytes
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
