from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
from copy import deepcopy
import io, os

# ── Fonts ──────────────────────────────────────────────────────────────────────
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

# ── Colors ─────────────────────────────────────────────────────────────────────
BLUE    = colors.HexColor("#2E7EC7")
DARK    = colors.HexColor("#3D4555")
LGRAY   = colors.HexColor("#F4F6F9")
MID     = colors.HexColor("#666B7A")
WHITE   = colors.white
DIVIDER = colors.HexColor("#D0D5E0")

CURRENCY_SYMBOLS = {
    "CZK": "Kč",
    "SEK": "kr",
    "EUR": "€",
    "NOK": "kr",
    "DKK": "kr",
    "CHF": "CHF",
}

def format_amount(amount, currency="CZK"):
    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)
    int_str = f"{integer_part:,}".replace(",", "\u00a0")
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    # EUR symbol goes before the number
    if currency == "EUR":
        return f"{symbol} {int_str},{decimal_part:02d}"
    elif currency == "CHF":
        return f"CHF {int_str},{decimal_part:02d}"
    else:
        return f"{int_str},{decimal_part:02d} {symbol}"

def s(name, **kw):
    return ParagraphStyle(name, fontName=kw.get("font", F), fontSize=kw.get("size", 9),
        textColor=kw.get("color", DARK), leading=kw.get("leading", 13),
        alignment=kw.get("align", TA_LEFT), spaceBefore=kw.get("sb", 0),
        spaceAfter=kw.get("sa", 0))

def generate_po_content(po_data):
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

    # ── TITLE BAND ────────────────────────────────────────────────────────────
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
        ("TOPPADDING", (0,0), (0,0), 6.5*mm),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (1,0), (1,0), 4*mm),
    ]))
    story.append(title_band)
    story.append(Spacer(1, 7*mm))

    # ── PARTIES ───────────────────────────────────────────────────────────────
    def party_lines(is_supplier):
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
        inf("IČO:", d.get("ico", ""))
        inf("DIČ:", d.get("dic", ""))
        lines.append(Spacer(1, 2))
        lines.append(Paragraph('<font color="#999999">Adresa:</font>', s("pal", size=8.5, color=DARK, leading=12)))
        lines.append(Paragraph(d.get("address", ""), s("pa", size=8.5, color=DARK, leading=12)))
        lines.append(Paragraph(d.get("city_zip", ""), s("pa2", size=8.5, color=DARK, leading=12)))
        lines.append(Paragraph(d.get("country", ""), s("pa3", size=8.5, color=DARK, leading=12, sa=2)))
        if d.get("contact"):
            inf("Kontakt:", d["contact"])
        inf("Email:", d.get("email", ""))
        inf("Tel:", d.get("phone", ""))
        return lines

    col_w = (CW - 6*mm) / 2
    parties_tbl = Table(
        [[party_lines(True), party_lines(False)]],
        colWidths=[col_w, col_w],
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
    currency = po_data.get("currency", "CZK")
    amt_str = format_amount(amt, currency)

    rows = [
        [hdr("Položka"), hdr("Množství", TA_CENTER), hdr("Jednotková cena", TA_RIGHT), hdr("Celkem", TA_RIGHT)],
        [cel(po_data["item_description"]), cel("1", align=TA_CENTER), cel(amt_str, align=TA_RIGHT), cel(amt_str, align=TA_RIGHT)],
        [cel("CENA CELKEM bez DPH", bold=True, size=10), cel(""), cel(""), cel(amt_str, bold=True, align=TA_RIGHT, size=10)],
    ]

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BLUE),
        ("TOPPADDING",    (0,0), (-1,0), 3*mm),
        ("BOTTOMPADDING", (0,0), (-1,0), 3*mm),
        ("LEFTPADDING",   (0,0), (-1,0), 4*mm),
        ("RIGHTPADDING",  (0,0), (-1,0), 4*mm),
        ("BACKGROUND", (0,1), (-1,1), WHITE),
        ("TOPPADDING",    (0,1), (-1,1), 3.5*mm),
        ("BOTTOMPADDING", (0,1), (-1,1), 3.5*mm),
        ("LEFTPADDING",   (0,1), (-1,1), 4*mm),
        ("RIGHTPADDING",  (0,1), (-1,1), 4*mm),
        ("LINEBELOW", (0,1), (-1,1), 0.5, DIVIDER),
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
        "Dodavatel potvrzuje, že vystupuje jako nezávislý dodavatel (samostatný podnikatel nebo právnická osoba) a není zaměstnancem, zástupcem ani partnerem společnosti Mapecomm s.r.o. Touto objednávkou nevzniká žádný pracovněprávní vztah. Dodavatel nese plnou odpovědnost za splnění veškerých povinností vyplývajících z platných právních předpisů, včetně mimo jiné: odvodu daní a sociálních příspěvků v zemi svého sídla, pojištění odpovědnosti a zdravotního pojištění, dodržování pracovněprávních předpisů a zajištění případných pracovních povolení pro zemi výkonu práce. Uvedený výčet je pouze demonstrativní. Dodavatel odpovídá za dodržování veškerých právních povinností vyplývajících z jeho podnikatelské činnosti, a to bez ohledu na to, zda jsou výše výslovně uvedeny. Společnost Mapecomm s.r.o. nenese odpovědnost za žádné nároky vzniklé v důsledku nesplnění těchto či jakýchkoliv jiných povinností dodavatelem.",
        s("fd", size=8, color=MID, leading=12, align=4)
    ))
    story.append(Spacer(1, 10*mm))

    # ── SIGNATURES ────────────────────────────────────────────────────────────
    sig_data = [[
        [
            Paragraph("Za dodavatele:", s("sl", font=FB, size=8.5, color=DARK, sa=2)),
            Paragraph(po_data["supplier"]["name"], s("sn", size=8.5, color=MID, sa=10)),
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
    sig_tbl = Table(sig_data, colWidths=[CW/2, CW/2])
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

def merge_with_letterhead(content_buf, letterhead_path, output):
    lh = PdfReader(letterhead_path)
    content = PdfReader(content_buf)
    writer = PdfWriter()

    bg = deepcopy(lh.pages[0])
    bg.merge_page(content.pages[0])
    writer.add_page(bg)

    if hasattr(output, 'write'):
        writer.write(output)
    else:
        with open(output, "wb") as f:
            writer.write(f)
