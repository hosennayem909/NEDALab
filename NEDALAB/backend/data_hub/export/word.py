"""Word (.docx) export."""
import io
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


EMERALD = RGBColor(0x04, 0x78, 0x57)
DARK = RGBColor(0x1c, 0x19, 0x17)
GRAY = RGBColor(0x78, 0x71, 0x6c)


def _add_heading_styled(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = EMERALD
        run.font.name = "Calibri"
    return h


def _add_para(doc, text, bold=False, color=None, size=10):
    p = doc.add_paragraph()
    run = p.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = "Calibri"
    if color:
        run.font.color.rgb = color
    return p


def _add_table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = str(h)
        for p in hdr_cells[i].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(9)

    for row in rows:
        cells = table.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v) if v is not None else ""
            for p in cells[i].paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    return table


def export_word_report(
    dataset_name: str,
    df_shape: tuple,
    columns: list,
    quality_report: dict = None,
    stats: dict = None,
    cleaning_report: dict = None,
    model_result: dict = None,
) -> bytes:
    """Generate Word report."""
    doc = Document()

    # Title
    title = doc.add_heading("NEDA LAB", level=0)
    for run in title.runs:
        run.font.color.rgb = EMERALD

    _add_para(doc, f"Report: {dataset_name}", bold=True, color=DARK, size=14)
    _add_para(doc, f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}", color=GRAY, size=9)
    doc.add_paragraph()

    # Dataset Overview
    _add_heading_styled(doc, "Dataset Overview", level=1)
    _add_table(doc, ["Metric", "Value"], [
        ["Total rows", f"{df_shape[0]:,}"],
        ["Total columns", str(df_shape[1])],
        ["Columns", ", ".join(str(c) for c in columns[:15]) + (f" (+{len(columns)-15} more)" if len(columns) > 15 else "")],
    ])

    # Quality Report
    if quality_report:
        doc.add_paragraph()
        _add_heading_styled(doc, "Data Quality Report", level=1)
        _add_para(doc, f"Health Score: {quality_report.get('health_score', '—')} (Grade {quality_report.get('grade', '—')})", bold=True, color=EMERALD, size=12)
        _add_table(doc, ["Metric", "Value"], [
            ["Total cells", quality_report.get("total_cells", "—")],
            ["Missing cells", quality_report.get("total_missing", "—")],
            ["Missing %", f"{quality_report.get('missing_pct', '—')}%"],
            ["Duplicate rows", quality_report.get("duplicate_rows", "—")],
            ["Issues found", quality_report.get("n_issues", "—")],
        ])

        # Issues
        issues = quality_report.get("issues", [])
        if issues:
            _add_para(doc, "Issues Detected:", bold=True, color=DARK, size=11)
            for iss in issues[:20]:
                _add_para(doc, f"  • [{iss['severity'].upper()}] {iss['column']}: {iss['issue']}", color=GRAY, size=9)

    # Descriptive Stats
    if stats and stats.get("numeric"):
        doc.add_paragraph()
        _add_heading_styled(doc, "Descriptive Statistics", level=1)
        headers = ["Column", "N", "Mean", "Std", "Min", "Median", "Max"]
        rows = []
        for col, s in stats["numeric"].items():
            if not isinstance(s, dict):
                continue
            rows.append([
                str(col)[:25],
                s.get("count", ""),
                s.get("mean", ""),
                s.get("std", ""),
                s.get("min", ""),
                s.get("median", ""),
                s.get("max", ""),
            ])
        if rows:
            _add_table(doc, headers, rows)

    # Cleaning Report
    if cleaning_report:
        doc.add_paragraph()
        _add_heading_styled(doc, "Cleaning Report", level=1)
        _add_para(doc, f"Preset: {cleaning_report.get('preset', '—')}", bold=True, color=DARK)
        log = cleaning_report.get("log", [])
        if log:
            _add_para(doc, "Actions applied:", bold=True, color=DARK, size=11)
            for entry in log:
                _add_para(doc, f"  • {entry}", color=GRAY, size=9)

    # Model Results
    if model_result:
        doc.add_paragraph()
        _add_heading_styled(doc, "Model Results", level=1)
        _add_table(doc, ["Metric", "Value"], [
            ["Model type", str(model_result.get("model_type", ""))],
            ["Dependent variable", str(model_result.get("dependent_var", ""))],
            ["N observations", str(model_result.get("n_obs", ""))],
            ["R²", str(model_result.get("r_squared", ""))],
            ["Adj R²", str(model_result.get("adj_r_squared", ""))],
            ["F statistic", str(model_result.get("f_statistic", ""))],
            ["Durbin-Watson", str(model_result.get("durbin_watson", ""))],
        ])
        coeffs = model_result.get("coefficients", [])
        if coeffs:
            _add_para(doc, "Coefficients:", bold=True, color=DARK, size=11)
            _add_table(doc,
                ["Variable", "Coef", "Std Err", "t", "p-value", "Sig"],
                [[str(c.get("variable", "")), str(c.get("coef", "")), str(c.get("std_err", "")),
                  str(c.get("t_stat", "")), str(c.get("p_value", "")), str(c.get("significance", ""))]
                 for c in coeffs])

    # Footer
    doc.add_paragraph()
    p = doc.add_paragraph()
    run = p.add_run("Generated by NEDA LAB - Research Data Platform")
    run.font.size = Pt(8)
    run.font.color.rgb = GRAY
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()
