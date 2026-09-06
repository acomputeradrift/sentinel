"""Pure-Python PDF renderer for Management reports (reportlab)."""

from __future__ import annotations

import io
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def report_download_filename(document: dict[str, Any], *, as_of: str | None = None) -> str:
    cover = document.get("cover") if isinstance(document.get("cover"), dict) else {}
    preset = str(document.get("preset") or "report").strip() or "report"
    generated = str(as_of or document.get("generatedAtUtc") or "")
    date = generated[:10] if len(generated) >= 10 else "undated"
    client = _filename_part(cover.get("clientName") or "client")
    project = _filename_part(cover.get("projectName") or "project")
    return f"{client}-{project}-{preset}-{date}.pdf"


def _filename_part(raw: Any) -> str:
    s = str(raw or "").strip() or "report"
    s = re.sub(r"[\\/:\x00-\x1f\"']+", "-", s)
    return s


def extract_pdf_text(data: bytes) -> str:
    """Parse visible PDF string literals. Not a pixel assertion."""
    chunks: list[str] = []
    for match in re.finditer(rb"\(((?:\\.|[^\\)])*)\)", data):
        raw = match.group(1).decode("latin-1", errors="replace")
        raw = (
            raw.replace("\\n", "\n")
            .replace("\\r", "")
            .replace("\\t", " ")
            .replace("\\(", "(")
            .replace("\\)", ")")
            .replace("\\\\", "\\")
        )
        if raw.strip():
            chunks.append(raw)
    return "\n".join(chunks)


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    s = str(text if text is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(s, style)


def render_report_pdf(document: dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="Sentinel report",
        pageCompression=0,
    )
    styles = getSampleStyleSheet()
    heading = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        spaceBefore=12,
        spaceAfter=6,
    )
    body = ParagraphStyle("ReportBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12)
    small = ParagraphStyle("ReportSmall", parent=body, fontSize=8, leading=10)
    story: list[Any] = []

    story.append(_p("Sentinel report", styles["Title"]))
    if document.get("preset"):
        story.append(_p(f"Preset: {document.get('preset')}", body))
    story.append(Spacer(1, 8))

    if "cover" in document:
        story.append(_p("Cover", heading))
        cover = document.get("cover") if isinstance(document.get("cover"), dict) else {}
        for label, key in (
            ("Client", "clientName"),
            ("Project", "projectName"),
            ("Project ID", "projectId"),
            ("File", "originalFilename"),
            ("Uploaded", "uploadedAtUtc"),
            ("Status", "status"),
            ("Report time", "generatedAtUtc"),
        ):
            if cover.get(key):
                story.append(_p(f"{label}: {cover.get(key)}", body))

    if "progressSummary" in document:
        story.append(_p("Progress summary", heading))
        counts = (document.get("progressSummary") or {}).get("counts") or {}
        story.append(_p(_counts_line(counts), body))
        last = (document.get("progressSummary") or {}).get("lastTestedAtUtc")
        if last:
            story.append(_p(f"Last tested: {last}", small))

    if "eventSectionCounts" in document:
        story.append(_p("Event section counts", heading))
        sections = document.get("eventSectionCounts") or {}
        for name in ("system", "driver"):
            row = sections.get(name) if isinstance(sections, dict) else None
            if isinstance(row, dict):
                story.append(_p(f"{name}: {_counts_line(row.get('counts') or {})}", body))

    if "deviceCounts" in document:
        story.append(_p("Device counts", heading))
        rows = document.get("deviceCounts") if isinstance(document.get("deviceCounts"), list) else []
        if rows:
            table_data = [[_p("Device", small), _p("Counts", small)]]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                table_data.append(
                    [
                        _p(row.get("displayName") or row.get("deviceId") or "", small),
                        _p(_counts_line(row.get("counts") or {}), small),
                    ]
                )
            story.append(_styled_table(table_data))
        else:
            story.append(_p("No devices in scope.", body))

    if "currentTargets" in document:
        story.append(_p("Current targets", heading))
        rows = document.get("currentTargets") if isinstance(document.get("currentTargets"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            story.append(
                _p(
                    f"{row.get('currentOutcome') or ''} · {row.get('targetName') or row.get('targetKey') or ''} · {row.get('techName') or ''}",
                    body,
                )
            )

    if "failDetail" in document:
        story.append(_p("Fail detail", heading))
        rows = document.get("failDetail") if isinstance(document.get("failDetail"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            bits = [
                row.get("targetName") or row.get("buttonName") or row.get("targetKey"),
                row.get("lastFailNote"),
                row.get("deviceName"),
                row.get("pageName"),
                row.get("buttonName"),
                row.get("effectiveRoomName"),
                row.get("techName"),
            ]
            if row.get("tag"):
                bits.append(str(row.get("tag")))
            story.append(_p(" · ".join(str(b) for b in bits if b), body))

    if "history" in document:
        story.append(_p("History", heading))
        rows = document.get("history") if isinstance(document.get("history"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            story.append(
                _p(
                    f"{row.get('recordedAtUtc') or ''} · {row.get('outcome') or ''} · {row.get('source') or ''} · "
                    f"{row.get('targetKey') or ''} · {row.get('techName') or ''} · {row.get('failNote') or ''}",
                    body,
                )
            )

    if "testingTypeLegend" in document:
        story.append(_p("Testing-type legend", heading))
        types = (document.get("testingTypeLegend") or {}).get("types") if isinstance(document.get("testingTypeLegend"), dict) else []
        if isinstance(types, list):
            for row in types:
                if not isinstance(row, dict):
                    continue
                enabled = "required" if row.get("enabled") else "off"
                story.append(_p(f"{row.get('label') or row.get('id')}: {enabled}", small))

    if "operatorAppendix" in document:
        story.append(_p("Operator appendix", heading))
        names = (document.get("operatorAppendix") or {}).get("technicianNames") or []
        if names:
            story.append(_p(", ".join(str(n) for n in names), body))
        else:
            story.append(_p("No active technician names.", body))

    doc.build(story)
    return buf.getvalue()


def _counts_line(counts: dict[str, Any]) -> str:
    return (
        f"total {counts.get('totalTargets', 0)} · tested {counts.get('testedTargets', 0)} · "
        f"pass {counts.get('pass', 0)} · fail {counts.get('fail', 0)} · untested {counts.get('untested', 0)}"
    )


def _styled_table(data: list[list[Any]]) -> Table:
    table = Table(data, colWidths=[2.4 * inch, 4.4 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.91, 0.94, 0.97)),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.Color(0.78, 0.82, 0.86)),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table
