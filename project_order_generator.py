from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io, os

# ── Fonts (identical search order to po_generator — Liberation + DejaVu) ────────
FONT_PATHS = [
    os.environ.get("DEJAVU_FONT_PATH", ""),
    "/tmp/fonts/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/tmp/fonts/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_BOLD_PATHS = [
    os.environ.get("DEJAVU_FONT_BOLD_PATH", ""),
    "/tmp/fonts/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/tmp/fonts/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
font_path = next((p for p in FONT_PATHS if p and os.path.exists(p)), None)
font_bold_path = next((p for p in FONT_BOLD_PATHS if p and os.path.exists(p)), None)
if font_path and font_bold_path:
    pdfmetrics.registerFont(TTFont("DejaVu", font_path))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", font_bold_path))
    F = "DejaVu"
    FB = "DejaVu-Bold"
else:
    F = "Helvetica"
    FB = "Helvetica-Bold"

# ── Mapecomm brand colors (identical to po_generator) ───────────────────────────
BLUE    = colors.HexColor("#2E7EC7")
DARK    = colors.HexColor("#3D4555")
LGRAY   = colors.HexColor("#F4F6F9")
MID     = colors.HexColor("#666B7A")
WHITE   = colors.white
DIVIDER = colors.HexColor("#D0D5E0")


def s(name, **kw):
    return ParagraphStyle(name, fontName=kw.get("font", F), fontSize=kw.get("size", 9),
        textColor=kw.get("color", DARK), leading=kw.get("leading", 13),
        alignment=kw.get("align", TA_LEFT), spaceBefore=kw.get("sb", 0),
        spaceAfter=kw.get("sa", 0))


def generate_project_order_content(po_data):
    """Generate the project-order content as a PDF buffer (no letterhead).

    Expected po_data shape:
    {
      "po_number": "OBJ-26-0056",
      "issue_date": "23.6.2026",
      "supplier": { name, ico, dic, address, city_zip, country, email, phone },
      "buyer": { ... } (optional; defaults to Mapecomm),
      "items": [
         { "project": "NEMO DT", "location": "Německo",
           "end_date": "31.12.2026", "price": "Bude specifikována v jednotlivých objednávkách" }
      ]
    }
    Each item's "price" may be free text OR a number string.
    """
    buf = io.BytesIO()
    W, H = A4

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=26*mm,
        bottomMargin=22*mm,
    )
    CW = W - 36*mm

    story = []

    # ── TITLE BLOCK — "OBJEDNÁVKA – Projekt" ───────────────────────────────────
    po_num_p = Paragraph(
        f'{po_data["po_number"]}<br/><font size="8.5" color="#C8DCF0">Vystaveno: {po_data["issue_date"]}</font>',
        s("t2", font=FB, size=11, color=WHITE, align=TA_RIGHT, leading=16)
    )
    title_band = Table(
        [[Paragraph("OBJEDNÁVKA – Projekt", s("t1", font=FB, size=20, color=WHITE, leading=20)), po_num_p]],
        colWidths=[CW*0.60, CW*0.40],
        rowHeights=[20*mm],
    )
    title_band.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLUE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 5*mm),
        ("TOPPADDING", (0,0), (0,0), 6.5*mm),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (1,0), (1,0), 4*mm),
    ]))
    story.append(title_band)
    story.append(Spacer(1, 7*mm))

    # ── PARTIES (identical styling to po_generator) ────────────────────────────
    buyer = po_data.get("buyer") or {
        "name": "Mapecomm s.r.o.", "ico": "10950672", "dic": "CZ10950672",
        "address": "U Stavoservisu 659/3", "city_zip": "10800 Praha",
        "country": "Česká republika", "contact": "Jakub Matuska",
        "email": "jakub@mapecomm.tech", "phone": "+420724941971",
    }

    def party_lines(d, is_supplier):
        label = "Dodavatel:" if is_supplier else "Odběratel:"
        lines = [
            Paragraph(label, s("pl", font=FB, size=8, color=BLUE, sa=2)),
            Paragraph(d.get("name",""), s("pn", font=FB, size=10.5, color=DARK, sa=1)),
        ]
        def inf(lbl, val):
            if val:
                lines.append(Paragraph(
                    f'<font color="#999999">{lbl}</font>\u00a0\u00a0{val}',
                    s("pi", size=8.5, color=DARK, leading=12)
                ))
        inf("IČO:", d.get("ico",""))
        inf("DIČ:", d.get("dic",""))
        lines.append(Spacer(1, 2))
        lines.append(Paragraph('<font color="#999999">Adresa:</font>',
                               s("pal", size=8.5, color=DARK, leading=12)))
        lines.append(Paragraph(d.get("address",""), s("pa", size=8.5, color=DARK, leading=12)))
        lines.append(Paragraph(d.get("city_zip",""), s("pa2", size=8.5, color=DARK, leading=12)))
        lines.append(Paragraph(d.get("country",""), s("pa3", size=8.5, color=DARK, leading=12, sa=2)))
        if d.get("contact"):
            inf("Kontakt:", d["contact"])
        inf("Email:", d.get("email",""))
        inf("Tel:", d.get("phone",""))
        return lines

    col_w = (CW - 6*mm) / 2
    parties_tbl = Table(
        [[party_lines(po_data["supplier"], True), party_lines(buyer, False)]],
        colWidths=[col_w, col_w],
        hAlign="LEFT",
    )
    parties_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 4*mm),
        ("TOPPADDING", (0,0), (-1,-1), 4*mm),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5*mm),
        ("BACKGROUND", (0,0), (0,-1), LGRAY),
        ("BACKGROUND", (1,0), (1,-1), colors.HexColor("#EDF1F7")),
        ("LINEBEFORE", (1,0), (1,-1), 2, WHITE),
    ]))
    story.append(parties_tbl)
    story.append(Spacer(1, 6*mm))

    # ── ITEMS TABLE — 4 columns: Projekt / Místo plnění / Konec / Cena ─────────
    col_widths = [CW*0.30, CW*0.22, CW*0.24, CW*0.24]

    def hdr(txt, align=TA_LEFT):
        return Paragraph(txt, s("th", font=FB, size=9, color=WHITE, align=align))

    def cel(txt, bold=False, align=TA_LEFT, color=DARK, size=9):
        return Paragraph(txt, s("td", font=FB if bold else F, size=size, color=color, align=align, leading=13))

    rows = [[
        hdr("Položka / Projekt"),
        hdr("Místo plnění", TA_CENTER),
        hdr("Předpokládaný konec realizace", TA_CENTER),
        hdr("Cena", TA_RIGHT),
    ]]
    for it in po_data["items"]:
        rows.append([
            cel(it.get("project",""), bold=True),
            cel(it.get("location",""), align=TA_CENTER),
            cel(it.get("end_date",""), align=TA_CENTER),
            cel(str(it.get("price","")), align=TA_RIGHT),
        ])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0,0), (-1,0), BLUE),
        ("TOPPADDING",    (0,0), (-1,0), 3*mm),
        ("BOTTOMPADDING", (0,0), (-1,0), 3*mm),
        ("LEFTPADDING",   (0,0), (-1,0), 4*mm),
        ("RIGHTPADDING",  (0,0), (-1,0), 4*mm),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]
    # body rows
    for r in range(1, len(rows)):
        style += [
            ("BACKGROUND", (0,r), (-1,r), WHITE),
            ("TOPPADDING",    (0,r), (-1,r), 3.5*mm),
            ("BOTTOMPADDING", (0,r), (-1,r), 3.5*mm),
            ("LEFTPADDING",   (0,r), (-1,r), 4*mm),
            ("RIGHTPADDING",  (0,r), (-1,r), 4*mm),
            ("LINEBELOW", (0,r), (-1,r), 0.5, DIVIDER),
        ]
    tbl.setStyle(TableStyle(style))
    story.append(tbl)
    story.append(Spacer(1, 7*mm))

    # ── DISCLAIMER (identical text/style to po_generator, no info-line/total) ──
    story.append(Paragraph(
        "Dodavatel potvrzuje, že vystupuje jako nezávislý dodavatel (samostatný podnikatel nebo právnická osoba) a není zaměstnancem, zástupcem ani partnerem společnosti Mapecomm s.r.o. Touto objednávkou nevzniká žádný pracovněprávní vztah. Dodavatel nese plnou odpovědnost za splnění veškerých povinností vyplývajících z platných právních předpisů, včetně mimo jiné: odvodu daní a sociálních příspěvků v zemi svého sídla, pojištění odpovědnosti a zdravotního pojištění, dodržování pracovněprávních předpisů a zajištění případných pracovních povolení pro zemi výkonu práce. Tento výčet není vyčerpávající — dodavatel je povinen dodržovat veškeré další právní povinnosti, které se na jeho činnost vztahují. Společnost Mapecomm s.r.o. nenese odpovědnost za žádné nároky vzniklé v důsledku nesplnění těchto či jakýchkoliv jiných povinností dodavatelem.",
        s("fd", size=8, color=MID, leading=12, align=4)
    ))
    story.append(Spacer(1, 10*mm))

    # ── SIGNATURE BLOCK (identical to po_generator) ───────────────────────────
    sig_data = [[
        [
            Paragraph("Za dodavatele:", s("sl", font=FB, size=8.5, color=DARK, sa=2)),
            Paragraph(po_data["supplier"].get("name",""), s("sn", size=8.5, color=MID, sa=10)),
            HRFlowable(width="100%", thickness=0.5, color=DIVIDER, spaceAfter=2),
            Paragraph("Podpis / datum", s("sd", size=7.5, color=MID)),
        ],
        [
            Paragraph("Za odběratele:", s("sl2", font=FB, size=8.5, color=DARK, sa=2)),
            Paragraph("Jakub Matuska, Mapecomm s.r.o.", s("sn2", size=8.5, color=MID, sa=10)),
            HRFlowable(width="100%", thickness=0.5, color=DIVIDER, spaceAfter=2),
            Paragraph("Podpis / datum", s("sd2", size=7.5, color=MID)),
        ],
    ]]
    sig_tbl = Table(sig_data, colWidths=[CW/2, CW/2], hAlign="LEFT")
    sig_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (0,-1), 8*mm),
        ("RIGHTPADDING", (1,0), (1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(sig_tbl)

    doc.build(story)
    buf.seek(0)
    return buf
