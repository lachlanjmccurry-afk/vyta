"""
VYTA - PDF report
------------------
Builds the PDF version of the Vyta report from the results of score.compute().
Used by the dashboard's "Export report as PDF" button. To make one from the command line:

    py report_pdf.py                  (scores data\\ and saves data\\model\\vyta_report.pdf)
    py report_pdf.py data_stressed    (same for another data folder)

All wording comes from wording.json / scorecard.json - nothing here needs editing to change text.
"""

import io
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import score

# (background, text) colours shared with the dashboard
RATING_STYLE = {
    "Red": ("#F8D0D0", "#9C0006"),
    "Amber": ("#FFE9A8", "#7A5A00"),
    "Green": ("#D5EBC5", "#2F5A1B"),
    "Not assessed": ("#ECECEC", "#555555"),
}
BAND_RATING = {"Low": "Green", "Moderate": "Amber", "High": "Red",
               "Strong": "Green", "Uncertain": "Amber", "Weak": "Red"}
KINDS = (("distress", "Distress indicators", "How much financial trouble is the business in right now?"),
         ("viability", "Viability indicators", "If the cash problem were fixed, would the business make money?"))


def rating_key(rating):
    return rating if rating in ("Red", "Amber", "Green") else "Not assessed"


def esc(text):
    return escape(str(text or ""))


# ---------- styles ----------

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#222222"))
SMALL = ParagraphStyle("small", parent=BASE, fontSize=8, leading=10.5, textColor=colors.HexColor("#555555"))
H1 = ParagraphStyle("h1", parent=BASE, fontName="Helvetica-Bold", fontSize=18, leading=22, spaceAfter=2)
H2 = ParagraphStyle("h2", parent=BASE, fontName="Helvetica-Bold", fontSize=12.5, leading=16, spaceBefore=10,
                    spaceAfter=2, keepWithNext=1)
H3 = ParagraphStyle("h3", parent=BASE, fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=6,
                    spaceAfter=3, keepWithNext=1)
BOLD = ParagraphStyle("bold", parent=BASE, fontName="Helvetica-Bold")
CELL = ParagraphStyle("cell", parent=BASE, fontSize=8.5, leading=11)
CELL_BOLD = ParagraphStyle("cellbold", parent=CELL, fontName="Helvetica-Bold")
HEAD_CELL = ParagraphStyle("headcell", parent=CELL, textColor=colors.white)


# ---------- building blocks ----------

def score_card(label, kind, run):
    s, weight, possible, _ = run["scores"][kind]
    band = run["bands"][kind]
    bg, fg = RATING_STYLE[BAND_RATING.get(band, "Not assessed")]
    direction = "higher = worse" if kind == "distress" else "higher = better"
    content = [
        Paragraph(label.upper(), ParagraphStyle("cl", parent=SMALL, textColor=colors.HexColor(fg))),
        Paragraph(f"<font size=24><b>{'n/a' if s is None else f'{s:.0f}'}</b></font>"
                  f"<font size=10> / 100</font>",
                  ParagraphStyle("cv", parent=BASE, leading=28, textColor=colors.HexColor(fg))),
        Paragraph(f"<b>{esc(band)}</b>", ParagraphStyle("cb", parent=BASE, fontSize=11,
                                                       textColor=colors.HexColor(fg))),
        Paragraph(f"0-100, {direction}. Based on {weight:g} of {possible:g} weight points.", SMALL),
    ]
    return content, bg


def boxed(flowables, bg, width, border=None):
    t = Table([[flowables]], colWidths=[width])
    style = [("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
             ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
             ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]
    if border:
        style.append(("LINEBEFORE", (0, 0), (0, -1), 4, colors.HexColor(border)))
    t.setStyle(TableStyle(style))
    return t


def indicator_table(results, kind, width):
    header = ["Result", "ID", "Indicator", "Value", "Amber at", "Red at", "Weight"]
    rows = [[Paragraph(f"<b>{h}</b>", HEAD_CELL) for h in header]]
    fills = []
    for i, r in enumerate((r for r in results if r["ind"]["score"] == kind), start=1):
        ind, unit = r["ind"], r["ind"].get("unit", "ratio")
        key = rating_key(r["rating"])
        bg, fg = RATING_STYLE[key]
        label = r["rating"] if key != "Not assessed" else "Not assessed"
        rows.append([
            Paragraph(f"<b>{esc(label)}</b>", ParagraphStyle("rc", parent=CELL, textColor=colors.HexColor(fg))),
            Paragraph(esc(ind["id"]), CELL_BOLD),
            Paragraph(esc(ind.get("name", "")), CELL),
            Paragraph(esc(r.get("display", "")) or "-", CELL),
            Paragraph(esc(score.fmt(ind["amber"], unit)), CELL),
            Paragraph(esc(score.fmt(ind["red"], unit)), CELL),
            Paragraph(f"{ind['weight']:g}", CELL),
        ])
        fills.append(("BACKGROUND", (0, i), (0, i), colors.HexColor(bg)))
    widths = [w * mm for w in (27, 10, 55, 29, 18, 17, 18)]
    scale = width / sum(widths)
    t = Table(rows, colWidths=[w * scale for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D9D9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ] + fills))
    return t


def explanation_item(r, width):
    bg, fg = RATING_STYLE[rating_key(r["rating"])]
    ind = r["ind"]
    text = (f"<b>{esc(ind['id'])}  {esc(ind.get('name', ''))}</b>"
            f"<font color='{fg}'>  <b>{esc(r['rating'])}</b> · {esc(r.get('display', ''))}</font><br/>"
            f"{esc(r.get('explanation') or r.get('note', ''))}")
    return KeepTogether([boxed([Paragraph(text, BASE)], "#FAFAFA", width, border=fg), Spacer(1, 4)])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#777777"))
    canvas.drawString(doc.leftMargin, 10 * mm,
                      "Vyta - indicative early-warning signals only, not an insolvency determination "
                      "or professional advice.")
    canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


# ---------- the report ----------

def build_pdf(run):
    """Returns the PDF as bytes."""
    d, results = run["d"], run["results"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=20 * mm, title=f"Vyta report - {d['org']}", author="Vyta")
    width = doc.width
    active = len(score.active_months(d))
    story = [
        Paragraph(f"Vyta report: {esc(d['org'])}", H1),
        Paragraph(f"12 months ending {d['months'][-1]['month']:%d %B %Y} · {active} of "
                  f"{len(d['months'][-12:])} months with trading activity · scored {date.today():%d %B %Y}",
                  SMALL),
        Spacer(1, 8),
    ]

    # Scores
    cards = [score_card("Distress score", "distress", run), score_card("Viability score", "viability", run)]
    gap = 6 * mm
    t = Table([[cards[0][0], "", cards[1][0]]], colWidths=[(width - gap) / 2, gap, (width - gap) / 2])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(cards[0][1])),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor(cards[1][1])),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story += [t, Spacer(1, 8)]

    # Pathway + summary
    pathway_parts = [Paragraph("OUTCOME PATHWAY", SMALL), Paragraph(esc(run["pathway"]), BOLD)]
    if run["summary"]:
        pathway_parts += [Spacer(1, 3), Paragraph(esc(run["summary"]), BASE)]
    applied = [n for n in run["override_notes"] if n.startswith("APPLIED")]
    pathway_parts += [Spacer(1, 3), Paragraph("Statutory demand override: "
                                              + esc(" ".join(applied or run["override_notes"]) or "none set up"),
                                              SMALL)]
    story += [boxed(pathway_parts, "#EEF2F8", width, border="#1F3864"), Spacer(1, 4)]

    # Traffic-light tables
    for kind, title, question in KINDS:
        story.append(KeepTogether([Paragraph(title, H2), Paragraph(esc(question), SMALL), Spacer(1, 4),
                                   indicator_table(results, kind, width)]))

    # Plain-English summary
    story.append(Paragraph("What the results mean", H2))
    for kind, title, _ in KINDS:
        mine = [r for r in results if r["ind"]["score"] == kind]
        flagged = [r for rating in ("Red", "Amber") for r in mine if r["rating"] == rating]
        greens = [r for r in mine if r["rating"] == "Green"]
        story.append(Paragraph(f"{title.split()[0]}: needs attention", H3))
        story += [explanation_item(r, width) for r in flagged] or [Paragraph("Nothing flagged Red or Amber.", BASE)]
        story.append(Paragraph(f"{title.split()[0]}: going well", H3))
        story += [explanation_item(r, width) for r in greens] or [Paragraph("Nothing rated Green yet.", BASE)]

    skipped = [r for r in results if r["points"] is None]
    if skipped:
        story.append(Paragraph("Not assessed (left out of the scores)", H3))
        story += [Paragraph(f"<b>{esc(r['ind']['id'])}</b> {esc(r['ind'].get('name', ''))}: "
                            f"{esc(r.get('note', ''))}", SMALL) for r in skipped]

    story += [Spacer(1, 10), Paragraph(esc(run["cfg"].get("disclaimer", "")), SMALL)]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    run = score.compute(base)
    out = base / "model" / "vyta_report.pdf"
    try:
        out.write_bytes(build_pdf(run))
    except PermissionError:
        score.stop("vyta_report.pdf is open in another program. Close it and run again.")
    print(f"[DONE] Saved:\n  {out.resolve()}")


if __name__ == "__main__":
    main()
