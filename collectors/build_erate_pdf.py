from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_FILE = BASE_DIR / "data" / "erate_account_intelligence.md"
OUTPUT_FILE = BASE_DIR / "data" / "erate_account_intelligence.pdf"

NAVY = colors.HexColor("#12304A")
BLUE = colors.HexColor("#1E6F9F")
PALE_BLUE = colors.HexColor("#EAF3F8")
SLATE = colors.HexColor("#425466")
LIGHT_GRAY = colors.HexColor("#D9E2E8")


def inline_markup(text):
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def footer(canvas, document):
    canvas.saveState()
    width, _ = letter
    canvas.setStrokeColor(LIGHT_GRAY)
    canvas.line(0.65 * inch, 0.55 * inch, width - 0.65 * inch, 0.55 * inch)
    canvas.setFillColor(SLATE)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.65 * inch, 0.36 * inch, "E-Rate Account Intelligence")
    canvas.drawRightString(width - 0.65 * inch, 0.36 * inch, f"Page {document.page}")
    canvas.restoreState()


def build_pdf(source_file=SOURCE_FILE, output_file=OUTPUT_FILE):
    if not source_file.exists():
        raise FileNotFoundError(f"Report source not found: {source_file}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=29,
        alignment=TA_CENTER,
        textColor=NAVY,
        spaceAfter=14,
    ))
    styles.add(ParagraphStyle(
        name="Account",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=21,
        textColor=colors.white,
        backColor=NAVY,
        borderPadding=(8, 10, 8, 10),
        spaceBefore=12,
        spaceAfter=10,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=BLUE,
        spaceBefore=9,
        spaceAfter=5,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="BodyClean",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=SLATE,
        spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="BulletClean",
        parent=styles["BodyClean"],
        leftIndent=14,
        firstLineIndent=-8,
        bulletIndent=3,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="Signal",
        parent=styles["BodyClean"],
        backColor=PALE_BLUE,
        borderColor=LIGHT_GRAY,
        borderWidth=0.5,
        borderPadding=7,
        spaceAfter=7,
    ))

    story = []
    first_account = True
    for raw_line in source_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line == "---":
            continue
        if line.startswith("# "):
            story.append(Spacer(1, 0.25 * inch))
            story.append(Paragraph(inline_markup(line[2:]), styles["ReportTitle"]))
        elif line.startswith("## "):
            if not first_account:
                story.append(PageBreak())
            first_account = False
            story.append(Paragraph(inline_markup(line[3:]), styles["Account"]))
        elif line.startswith("### "):
            story.append(Paragraph(inline_markup(line[4:]), styles["Section"]))
        elif line.startswith("  - "):
            story.append(Paragraph(
                inline_markup(line[4:]), styles["BulletClean"], bulletText="-"
            ))
        elif line.startswith("- "):
            story.append(Paragraph(
                inline_markup(line[2:]), styles["BulletClean"], bulletText="-"
            ))
        elif line.startswith("**Priority:"):
            story.append(KeepTogether([
                Paragraph(inline_markup(line), styles["Signal"]),
            ]))
        else:
            story.append(Paragraph(inline_markup(line), styles["BodyClean"]))

    document = SimpleDocTemplate(
        str(output_file),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.75 * inch,
        title="E-Rate Account Intelligence Brief",
        author="K-12 Opportunity Command Center",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Printable E-Rate brief saved to {output_file}")


if __name__ == "__main__":
    build_pdf()
