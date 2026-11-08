"""PDF report generation using reportlab with proper text wrapping."""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.lib.enums import TA_LEFT


EMERALD = colors.HexColor("#047857")
DARK = colors.HexColor("#1c1917")
GRAY = colors.HexColor("#78716c")
LIGHT_BG = colors.HexColor("#faf8f3")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(
        name="TitleBig", parent=ss["Title"], fontSize=22, textColor=EMERALD,
        spaceAfter=6, fontName="Helvetica-Bold", alignment=TA_LEFT,
    ))
    ss.add(ParagraphStyle(
        name="Section", parent=ss["Heading1"], fontSize=14, textColor=EMERALD,
        spaceBefore=14, spaceAfter=8, fontName="Helvetica-Bold",
    ))
    ss.add(ParagraphStyle(
        name="SubSection", parent=ss["Heading2"], fontSize=11, textColor=DARK,
        spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold",
    ))
    ss.add(ParagraphStyle(
        name="Small", parent=ss["Normal"], fontSize=9, textColor=GRAY,
        spaceAfter=4,
    ))
    ss.add(ParagraphStyle(
        name="Body2", parent=ss["Normal"], fontSize=10, textColor=DARK,
        spaceAfter=6,
    ))
    ss.add(ParagraphStyle(
        name="TableCell", parent=ss["Normal"], fontSize=9, textColor=DARK,
        leading=11, wordWrap="CJK",
    ))
    ss.add(ParagraphStyle(
        name="TableHeader", parent=ss["Normal"], fontSize=10, textColor=colors.white,
        fontName="Helvetica-Bold", leading=12,
    ))
    return ss


def _P(text, style_name="TableCell"):
    """Wrap text in Paragraph for auto-wrapping inside table cells."""
    styles = _styles()
    return Paragraph(str(text), styles[style_name])


def _table(data, col_widths=None, header=True):
    """Build styled table with auto-wrapping text cells."""
    styles = _styles()

    # Convert all string cells to Paragraphs
    converted = []
    for row_idx, row in enumerate(data):
        new_row = []
        for cell in row:
            if row_idx == 0 and header:
                new_row.append(Paragraph(str(cell), styles["TableHeader"]))
            else:
                new_row.append(Paragraph(str(cell) if cell != "" else "", styles["TableCell"]))
        converted.append(new_row)

    t = Table(converted, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, EMERALD),
    ]
    if header:
        style += [
            ("BACKGROUND", (0, 0), (-1, 0), EMERALD),
        ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), LIGHT_BG))
    t.setStyle(TableStyle(style))
    return t


def export_dataset_pdf(
    dataset_name: str,
    df_shape: tuple,
    columns: list,
    stats: dict | None = None,
    cleaning_report: dict | None = None,
    model_result: dict | None = None,
    tests: list | None = None,
) -> bytes:
    """Generate PDF report."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"NEDA LAB Report - {dataset_name}",
    )
    ss = _styles()
    story = []

    # ---- Header ----
    story.append(Paragraph("NEDA LAB", ss["TitleBig"]))
    story.append(Paragraph(f"<b>Report:</b> {dataset_name}", ss["Body2"]))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}",
        ss["Small"],
    ))
    story.append(Spacer(1, 10))

    # ---- Dataset Overview ----
    story.append(Paragraph("Dataset Overview", ss["Section"]))
    cols_str = ", ".join(str(c) for c in columns)
    overview = [
        ["Metric", "Value"],
        ["Total rows", f"{df_shape[0]:,}"],
        ["Total columns", str(df_shape[1])],
        ["Columns", cols_str],
    ]
    story.append(_table(overview, col_widths=[4.5 * cm, 12 * cm]))
    story.append(Spacer(1, 6))

    # ---- Descriptive Stats ----
    if stats and stats.get("numeric"):
        story.append(Paragraph("Descriptive Statistics", ss["Section"]))
        headers = ["Column", "N", "Mean", "Std", "Min", "Median", "Max"]
        rows = [headers]
        for col, s in stats["numeric"].items():
            if not isinstance(s, dict):
                continue
            rows.append([
                str(col),
                f"{s.get('count', '')}",
                f"{s.get('mean', '')}",
                f"{s.get('std', '')}",
                f"{s.get('min', '')}",
                f"{s.get('median', '')}",
                f"{s.get('max', '')}",
            ])
        story.append(_table(rows))
        story.append(Spacer(1, 6))

    # ---- Cleaning Report ----
    if cleaning_report:
        story.append(Paragraph("Cleaning Report", ss["Section"]))
        preset = cleaning_report.get("preset", "standard")
        story.append(Paragraph(f"Preset: <b>{preset}</b>", ss["Body2"]))

        log = cleaning_report.get("log", [])
        if log:
            story.append(Paragraph("Actions applied:", ss["SubSection"]))
            log_data = [["#", "Action"]]
            for i, entry in enumerate(log, 1):
                log_data.append([str(i), str(entry)])
            story.append(_table(log_data, col_widths=[1.5 * cm, 15 * cm]))
            story.append(Spacer(1, 6))

        sb = cleaning_report.get("stats_before", {})
        sa = cleaning_report.get("stats_after", {})
        if sb or sa:
            ba_data = [["Metric", "Before", "After", "Change"]]
            for k in ["rows", "columns", "missing", "duplicates"]:
                b = sb.get(k, 0) or 0
                a = sa.get(k, 0) or 0
                ch = a - b
                ba_data.append([k.capitalize(), str(b), str(a), f"{ch:+d}"])
            story.append(_table(ba_data, col_widths=[4 * cm, 4 * cm, 4 * cm, 4.5 * cm]))
        story.append(Spacer(1, 6))

    # ---- Model Results ----
    if model_result:
        story.append(Paragraph("Model Results", ss["Section"]))
        meta = [
            ["Metric", "Value"],
            ["Model type", str(model_result.get("model_type", ""))],
            ["Dependent variable", str(model_result.get("dependent_var", ""))],
            ["N observations", str(model_result.get("n_obs", ""))],
            ["R²", str(model_result.get("r_squared", ""))],
            ["Adj R²", str(model_result.get("adj_r_squared", ""))],
            ["F statistic", str(model_result.get("f_statistic", ""))],
            ["Durbin-Watson", str(model_result.get("durbin_watson", ""))],
        ]
        story.append(_table(meta, col_widths=[5 * cm, 11.5 * cm]))
        story.append(Spacer(1, 6))

        coeffs = model_result.get("coefficients", [])
        if coeffs:
            story.append(Paragraph("Coefficients", ss["SubSection"]))
            rows = [["Variable", "Coef", "Std Err", "t", "p-value", "CI Lower", "CI Upper", "Sig"]]
            for c in coeffs:
                rows.append([
                    str(c.get("variable", "")),
                    str(c.get("coef", "")),
                    str(c.get("std_err", "")),
                    str(c.get("t_stat", "")),
                    str(c.get("p_value", "")),
                    str(c.get("ci_lower", "")),
                    str(c.get("ci_upper", "")),
                    str(c.get("significance", "")),
                ])
            story.append(_table(rows))

        interp = model_result.get("interpretation", {})
        if interp:
            story.append(Paragraph("Interpretation", ss["SubSection"]))
            for k, v in interp.items():
                if isinstance(v, list):
                    v = ", ".join(map(str, v))
                story.append(Paragraph(
                    f"<b>{k.replace('_', ' ').title()}:</b> {v}",
                    ss["Body2"],
                ))
        story.append(Spacer(1, 6))

    # ---- Extra Tests ----
    if tests:
        story.append(Paragraph("Additional Tests", ss["Section"]))
        for t in tests:
            title = t.get("title", "Test")
            body = t.get("body", "")
            story.append(Paragraph(title, ss["SubSection"]))
            story.append(Paragraph(body, ss["Body2"]))

    # ---- Footer ----
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Generated by NEDA LAB - Research Data Platform",
        ss["Small"],
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
