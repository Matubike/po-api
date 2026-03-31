from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
import io, os

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]
FONT_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]
font_path = next((p for p in FONT_PATHS if os.path.exists(p)), None)
font_bold_path = next((p for p in FONT_BOLD_PATHS if os.path.exists(p)), None)
if font_path:
    pdfmetrics.registerFont(TTFont("DejaVu", font_path))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", font_bold_path))
    F = "DejaVu"
    FB = "DejaVu-Bold"
else:
    F = "Helvetica"
    FB = "Helvetica-Bold"

# ── Mapecomm brand colors ──────────────────────────────────────────────────────
BLUE    = colors.HexColor("#2E7EC7")       # Mapecomm modrá
DARK    = colors.HexColor("#3D4555")       # tmavě šedá (text)
LGRAY   = colors.HexColor("#F4F6F9")       # světle šedé pozadí buněk
MID     = colors.HexColor("#666B7A")       # střední šedá
WHITE   = colors.white
DIVIDER = colors.HexColor("#D0D5E0")

# ── Data ───────────────────────────────────────────────────────────────────────
po_data = {
    "po_number": "OBJ-26-0010",
    "issue_date": "10.2.2026",
    "supplier": {
        "name": "Michal Čaňo",
        "ico": "17293936",
        "dic": "",
        "address": "Brodská 813",
        "city_zip": "68751 Nivnice",
        "country": "Česká republika",
        "email": "mcano@seznam.cz",
        "phone": "+420733742064",
    },
    "buyer": {
        "name": "Mapecomm s.r.o.",
        "ico": "10950672",
        "dic": "CZ10950672",
        "address": "U Stavoservisu 659/3",
        "city_zip": "10800 Praha",
        "country": "Česká republika",
        "contact": "Jakub Matuska",
        "email": "jakub@mapecomm.tech",
        "phone": "+420724941971",
    },
    "item_description": "Servisní práce na vysílačích telefonních operátorů - Švédsko - Remarks&Fixes",
    "amount": 19008,
}

def format_czk(amount):
    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)
    int_str = f"{integer_part:,}".replace(",", "\u00a0")
    return f"{int_str},{decimal_part:02d} Kč"

def s(name, **kw):
    return ParagraphStyle(name, fontName=kw.get("font", F), fontSize=kw.get("size", 9),
        textColor=kw.get("color", DARK), leading=kw.get("leading", 13),
        alignment=kw.get("align", TA_LEFT), spaceBefore=kw.get("sb", 0),
        spaceAfter=kw.get("sa", 0))

def generate_po_content(po_data):
    """Generate the PO content as a PDF buffer (no letterhead)."""
    buf = io.BytesIO()
    W, H = A4

    # Margins: top large (for letterhead header area), others normal
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=26*mm,   # logo ends at ~23mm, start just below
        bottomMargin=22*mm,
    )
    CW = W - 36*mm  # content width

    story = []

    # ── PO TITLE BLOCK ────────────────────────────────────────────────────────
    # Full-width light blue band with OBJEDNÁVKA left, PO number+date right
    # ── PO TITLE BLOCK ────────────────────────────────────────────────────────
    po_num_p = Paragraph(
        f'{po_data["po_number"]}<br/><font size="8.5" color="#C8DCF0">Vystaveno: {po_data["issue_date"]}</font>',
        s("t2", font=FB, size=11, color=WHITE, align=TA_RIGHT, leading=16)
    )
    title_band = Table(
        [[Paragraph("OBJEDNÁVKA", s("t1", font=FB, size=20, color=WHITE, leading=20)), po_num_p]],
        colWidths=[CW*0.55, CW*0.45],
        rowHeights=[20*mm],
    )
    title_band.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLUE),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 5*mm),
        ("TOPPADDING", (0,0), (0,0), 6.5*mm),   # (20mm - 7mm font) / 2
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (1,0), (1,0), 4*mm),      # two lines right side, less padding
    ]))
    story.append(title_band)
    story.append(Spacer(1, 7*mm))

    # ── PARTIES ───────────────────────────────────────────────────────────────
    def party_lines(data, is_supplier):
        d = po_data["supplier"] if is_supplier else po_data["buyer"]
        label = "Dodavatel:" if is_supplier else "Odběratel:"
        lines = [
            Paragraph(label, s("pl", font=FB, size=8, color=BLUE, sa=2)),
            Paragraph(d["name"], s("pn", font=FB, size=10.5, color=DARK, sa=1)),
        ]
        def inf(label, val):
            if val:
                lines.append(Paragraph(
                    f'<font color="#999999">{label}</font>\u00a0\u00a0{val}',
                    s("pi", size=8.5, color=DARK, leading=12)
                ))
        inf("IČO:", d.get("ico",""))
        inf("DIČ:", d.get("dic",""))
        lines.append(Spacer(1, 2))
        lines.append(Paragraph(
            f'<font color="#999999">Adresa:</font>',
            s("pal", size=8.5, color=DARK, leading=12)
        ))
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
        [[party_lines(po_data["supplier"], True), party_lines(po_data["buyer"], False)]],
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

    # ── ITEMS TABLE ───────────────────────────────────────────────────────────
    col_widths = [CW*0.42, CW*0.14, CW*0.22, CW*0.22]

    def hdr(txt, align=TA_LEFT):
        return Paragraph(txt, s("th", font=FB, size=9, color=WHITE, align=align))

    def cel(txt, bold=False, align=TA_LEFT, color=DARK, size=9):
        return Paragraph(txt, s("td", font=FB if bold else F, size=size, color=color, align=align, leading=13))

    amt = po_data["amount"]
    amt_str = format_czk(amt)

    rows = [
        [hdr("Položka"), hdr("Množství", TA_CENTER), hdr("Jednotková cena", TA_RIGHT), hdr("Celkem", TA_RIGHT)],
        [cel(po_data["item_description"]), cel("1", align=TA_CENTER), cel(amt_str, align=TA_RIGHT), cel(amt_str, align=TA_RIGHT)],
        [cel("CENA CELKEM bez DPH", bold=True, size=10), cel(""), cel(""), cel(amt_str, bold=True, align=TA_RIGHT, size=10)],
    ]

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0,0), (-1,0), BLUE),
        ("TOPPADDING",    (0,0), (-1,0), 3*mm),
        ("BOTTOMPADDING", (0,0), (-1,0), 3*mm),
        ("LEFTPADDING",   (0,0), (-1,0), 4*mm),
        ("RIGHTPADDING",  (0,0), (-1,0), 4*mm),
        # Item row
        ("BACKGROUND", (0,1), (-1,1), WHITE),
        ("TOPPADDING",    (0,1), (-1,1), 3.5*mm),
        ("BOTTOMPADDING", (0,1), (-1,1), 3.5*mm),
        ("LEFTPADDING",   (0,1), (-1,1), 4*mm),
        ("RIGHTPADDING",  (0,1), (-1,1), 4*mm),
        ("LINEBELOW", (0,1), (-1,1), 0.5, DIVIDER),
        # Total row
        ("BACKGROUND", (0,2), (-1,2), LGRAY),
        ("TOPPADDING",    (0,2), (-1,2), 3*mm),
        ("BOTTOMPADDING", (0,2), (-1,2), 3*mm),
        ("LEFTPADDING",   (0,2), (-1,2), 4*mm),
        ("RIGHTPADDING",  (0,2), (-1,2), 4*mm),
        ("LINEABOVE", (0,2), (-1,2), 1.5, BLUE),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 7*mm))

    # ── FOOTER TEXT ───────────────────────────────────────────────────────────
    story.append(Paragraph(
        f'Po obdržení této objednávky prosím zašlete fakturu ve formátu PDF na adresu <font color="#2E7EC7"><b>info@mapecomm.tech</b></font>. Na faktuře uveďte číslo této objednávky (<font color="#2E7EC7"><b>{po_data["po_number"]}</b></font>) jako referenci.',
        s("fi", font=FB, size=9, color=DARK, sa=5)
    ))
    story.append(Paragraph(
        "Dodavatel potvrzuje, že vystupuje jako nezávislý dodavatel (samostatný podnikatel nebo právnická osoba) a není zaměstnancem, zástupcem ani partnerem společnosti Mapecomm s.r.o. Touto objednávkou nevzniká žádný pracovněprávní vztah. Dodavatel nese plnou odpovědnost za splnění veškerých povinností vyplývajících z platných právních předpisů, včetně mimo jiné: odvodu daní a sociálních příspěvků v zemi svého sídla, pojištění odpovědnosti a zdravotního pojištění, dodržování pracovněprávních předpisů a zajištění případných pracovních povolení pro zemi výkonu práce. Tento výčet není vyčerpávající — dodavatel je povinen dodržovat veškeré další právní povinnosti, které se na jeho činnost vztahují. Společnost Mapecomm s.r.o. nenese odpovědnost za žádné nároky vzniklé v důsledku nesplnění těchto či jakýchkoliv jiných povinností dodavatelem.",
        s("fd", size=8, color=MID, leading=12, align=4)  # 4 = TA_JUSTIFY
    ))
    story.append(Spacer(1, 10*mm))

    # ── SIGNATURE BLOCK — both parties ────────────────────────────────────────
    sig_data = [[
        [
            Paragraph("Za dodavatele:", s("sl", font=FB, size=8.5, color=DARK, sa=2)),
            Paragraph(po_data["supplier"]["name"], s("sn", size=8.5, color=MID, sa=10)),
            HRFlowable(width="100%", thickness=0.5, color=DIVIDER, spaceAfter=2),
            Paragraph("Podpis / datum", s("sd", size=7.5, color=MID)),
        ],
        [
            Paragraph("Za odběratele:", s("sl2", font=FB, size=8.5, color=DARK, sa=2)),
            Paragraph(f"Jakub Matuska, Mapecomm s.r.o.", s("sn2", size=8.5, color=MID, sa=10)),
            HRFlowable(width="100%", thickness=0.5, color=DIVIDER, spaceAfter=2),
            Paragraph(f"Podpis / datum", s("sd2", size=7.5, color=MID)),
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

def merge_with_letterhead(content_buf, letterhead_path, output_path):
    """Merge content PDF with letterhead as background."""
    lh = PdfReader(letterhead_path)
    content = PdfReader(content_buf)
    writer = PdfWriter()

    lh_page = lh.pages[0]
    content_page = content.pages[0]

    # Merge: letterhead first, then content on top
    from copy import deepcopy
    bg = deepcopy(lh_page)
    bg.merge_page(content_page)
    writer.add_page(bg)

    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"Generated: {output_path}")

# Run
content_buf = generate_po_content(po_data)
merge_with_letterhead(content_buf, "/home/claude/letterhead.pdf", "/mnt/user-data/outputs/OBJ-26-0010_v2.pdf")
