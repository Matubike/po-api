"""
Mapecomm cenové nabídky (Price Quotations) — PDF generator.
Renders the quote body and overlays it on the same letterhead.pdf used for POs.
Visually mirrors po_generator.py (gradient title band, info blocks, items table,
legal text, signature blocks), with these differences:
  - Title: "CENOVÁ NABÍDKA" (not "OBJEDNÁVKA")
  - Number format: "Q-26-0001" (not "OBJ-26-0034")
  - Dodavatel / Odběratel are REVERSED (Mapecomm = Dodavatel, customer = Odběratel)
  - Multi-currency: CZK / EUR / SEK / DKK / NOK
  - Multi-item table (PO has 1 item, quote can have many; also supports hourly + fixed modes)
  - Legal text is quote-specific (validity, non-binding offer, scope-change reservation)
  - Optional "Valid until" line below total
  - Optional notes block below legal text
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io, os

# ── Fonts (same logic as po_generator) ────────────────────────────────────────
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
    # Re-register only if not already registered (po_generator may have done it)
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", font_bold_path))
    except Exception:
        pass
    F = "DejaVu"
    FB = "DejaVu-Bold"
else:
    F = "Helvetica"
    FB = "Helvetica-Bold"

# ── Mapecomm brand colors (matching po_generator) ─────────────────────────────
BLUE    = colors.HexColor("#2E7EC7")
DARK    = colors.HexColor("#3D4555")
LGRAY   = colors.HexColor("#F4F6F9")
LGRAY2  = colors.HexColor("#EDF1F7")
MID     = colors.HexColor("#666B7A")
LIGHT_TXT = colors.HexColor("#999999")
WHITE   = colors.white
DIVIDER = colors.HexColor("#D0D5E0")

# ── Currency formatting ──────────────────────────────────────────────────────
CURRENCY_SYMBOLS = {
    "CZK": "Kč",
    "EUR": "€",
    "SEK": "kr",
    "DKK": "kr",
    "NOK": "kr",
}

def format_amount(amount, currency="CZK"):
    """Czech-style number formatting: '1\u00a0250,00 Kč'."""
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)
    int_str = f"{integer_part:,}".replace(",", "\u00a0")
    return f"{int_str},{decimal_part:02d} {symbol}"

# ── Paragraph style helper ────────────────────────────────────────────────────
def s(name, **kw):
    return ParagraphStyle(
        name,
        fontName=kw.get("font", F),
        fontSize=kw.get("size", 9),
        textColor=kw.get("color", DARK),
        leading=kw.get("leading", 13),
        alignment=kw.get("align", TA_LEFT),
        spaceBefore=kw.get("sb", 0),
        spaceAfter=kw.get("sa", 0),
    )

# ── Legal text (CZK uses Czech, others use English) ───────────────────────────
LEGAL_CZ = (
    "Tato cenová nabídka je platná do uvedeného data platnosti. Po jeho uplynutí mohou být ceny upraveny. "
    "Uvedené ceny jsou bez DPH. Není-li dohodnuto jinak, na fakturaci bude uplatněn režim přenesené daňové "
    "povinnosti dle §92e zákona č. 235/2004 Sb., o dani z přidané hodnoty, vztahuje-li se na předmět plnění. "
    "Tato cenová nabídka představuje nezávazný návrh a nezakládá smluvní vztah; ten vzniká až písemnou akceptací "
    "této nabídky nebo uzavřením samostatné smlouvy. Cena se vztahuje na rozsah prací popsaný výše. Při změně "
    "rozsahu, technické specifikace nebo materiálových požadavků si Mapecomm s.r.o. vyhrazuje právo na úpravu "
    "ceny, o které bude objednatel informován předem. Cestovní náklady, ubytování a další vedlejší výdaje, "
    "nejsou-li výslovně uvedeny v položkách výše, budou fakturovány samostatně dle skutečné spotřeby."
)

LEGAL_EN = (
    "This price quotation is valid until the date stated above. After expiry, prices may be revised. "
    "All prices are net (excluding VAT). Where applicable, reverse-charge VAT under Article 196 of the EU VAT "
    "Directive applies — VAT is to be self-accounted by the recipient in their country of registration. This "
    "quotation constitutes a non-binding offer and does not create a contractual relationship; a contract "
    "arises only through written acceptance of this quotation or by signing a separate agreement. The price "
    "covers the scope of work described above. In case of changes to scope, technical specifications or "
    "material requirements, Mapecomm s.r.o. reserves the right to adjust the price, with the client being "
    "informed in advance. Travel costs, accommodation and other ancillary expenses, unless explicitly "
    "included in the items above, will be invoiced separately based on actual consumption."
)


def generate_quote_content(quote_data):
    """
    Generate the quote content as a PDF buffer (no letterhead — that's merged separately).

    Expected quote_data shape:
    {
        "quote_number": "Q-26-0001",
        "issue_date": "12.5.2026",
        "valid_until": "30.6.2026",                       # optional, can be empty/None
        "currency": "CZK",                                 # CZK | EUR | SEK | DKK | NOK
        "description": "Optional intro paragraph...",     # optional
        "notes": "Optional case-specific notes...",       # optional, shown below legal text
        "supplier": {                                      # = Mapecomm
            "name": "Mapecomm s.r.o.",
            "ico": "10950672",
            "dic": "CZ10950672",
            "address": "U Stavoservisu 659/3",
            "city_zip": "10800 Praha",
            "country": "Česká republika",
            "contact": "Jakub Matuska",
            "email": "jakub@mapecomm.tech",
            "phone": "+420 724 941 971",
        },
        "buyer": {                                         # = customer (existing or prospect)
            "name": "Green24 Holding, a.s.",
            "ico": "...",                                  # optional
            "dic": "...",                                  # optional
            "address": "...",                              # optional
            "city_zip": "...",                             # optional
            "country": "...",                              # optional
            "contact": "...",                              # optional
            "email": "...",                                # optional
            "phone": "...",                                # optional
        },
        "pricing_mode": "per_item",                        # per_item | hourly | fixed
        "items": [                                         # one or more rows (always provided; for hourly/fixed
                                                            #   the API server constructs a single-row list)
            {
                "name": "Servisní práce - demontáž nabíječek",
                "description": "Optional second-line description",  # optional
                "quantity": 1,
                "unit": "ks",                              # optional ('ks' | 'h' | 'site' | 'km' | free text)
                "unit_price": 22675.0,
                "line_total": 22675.0,
            },
            ...
        ],
        "total": 22675.0,                                  # grand total (also = sum of line_totals)
    }
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

    currency = quote_data.get("currency", "CZK")

    # ── TITLE BAND ────────────────────────────────────────────────────────────
    qn = quote_data["quote_number"]
    issue = quote_data["issue_date"]
    num_p = Paragraph(
        f'{qn}<br/><font size="8.5" color="#C8DCF0">Vystaveno: {issue}</font>',
        s("t2", font=FB, size=11, color=WHITE, align=TA_RIGHT, leading=16)
    )
    title_band = Table(
        [[Paragraph("CENOVÁ NABÍDKA", s("t1", font=FB, size=20, color=WHITE, leading=20)), num_p]],
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

    # ── PARTIES (Mapecomm = Dodavatel left, Customer = Odběratel right) ──────
    def party_lines(d, is_supplier):
        label = "Dodavatel:" if is_supplier else "Odběratel:"
        lines = [
            Paragraph(label, s("pl", font=FB, size=8, color=BLUE, sa=2)),
            Paragraph(d.get("name", ""), s("pn", font=FB, size=10.5, color=DARK, sa=1)),
        ]
        def inf(label, val):
            if val:
                lines.append(Paragraph(
                    f'<font color="#999999">{label}</font>\u00a0\u00a0{val}',
                    s("pi", size=8.5, color=DARK, leading=12)
                ))
        inf("IČO:", d.get("ico", ""))
        inf("DIČ:", d.get("dic", ""))
        if d.get("address") or d.get("city_zip") or d.get("country"):
            lines.append(Spacer(1, 2))
            lines.append(Paragraph('<font color="#999999">Adresa:</font>',
                                   s("pal", size=8.5, color=DARK, leading=12)))
            if d.get("address"):
                lines.append(Paragraph(d["address"], s("pa", size=8.5, color=DARK, leading=12)))
            if d.get("city_zip"):
                lines.append(Paragraph(d["city_zip"], s("pa2", size=8.5, color=DARK, leading=12)))
            if d.get("country"):
                lines.append(Paragraph(d["country"], s("pa3", size=8.5, color=DARK, leading=12, sa=2)))
        inf("Kontakt:", d.get("contact", ""))
        inf("Email:", d.get("email", ""))
        inf("Tel:", d.get("phone", ""))
        return lines

    col_w = (CW - 6*mm) / 2
    parties_tbl = Table(
        [[party_lines(quote_data["supplier"], True), party_lines(quote_data["buyer"], False)]],
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
        ("BACKGROUND", (1,0), (1,-1), LGRAY2),
        ("LINEBEFORE", (1,0), (1,-1), 2, WHITE),
    ]))
    story.append(parties_tbl)
    story.append(Spacer(1, 6*mm))

    # ── OPTIONAL DESCRIPTION PARAGRAPH ────────────────────────────────────────
    if quote_data.get("description"):
        story.append(Paragraph(
            quote_data["description"],
            s("desc", size=9, color=DARK, leading=13, sa=4)
        ))
        story.append(Spacer(1, 3*mm))

    # ── ITEMS TABLE ───────────────────────────────────────────────────────────
    # 5 columns: Položka | Množství | Jednotka | Jednotková cena | Celkem
    col_widths = [CW*0.40, CW*0.10, CW*0.10, CW*0.20, CW*0.20]

    def hdr(txt, align=TA_LEFT):
        return Paragraph(txt, s("th", font=FB, size=9, color=WHITE, align=align))

    def cel(txt, bold=False, align=TA_LEFT, color=DARK, size=9):
        return Paragraph(txt, s("td", font=FB if bold else F, size=size,
                                color=color, align=align, leading=13))

    rows = [[
        hdr("Položka"),
        hdr("Množství", TA_CENTER),
        hdr("Jednotka", TA_CENTER),
        hdr("Jednotková cena", TA_RIGHT),
        hdr("Celkem", TA_RIGHT),
    ]]

    items = quote_data.get("items", [])
    for it in items:
        # Item name + optional description as 2nd line
        name = it.get("name", "")
        if it.get("description"):
            item_html = f'{name}<br/><font size="8" color="#888888">{it["description"]}</font>'
        else:
            item_html = name
        qty_val = it.get("quantity", 1)
        # Quantity formatting: integer if whole number, else 2 decimals
        if isinstance(qty_val, (int, float)) and qty_val == int(qty_val):
            qty_str = str(int(qty_val))
        else:
            qty_str = f"{qty_val:.2f}".replace(".", ",")
        unit_str = it.get("unit") or ""
        unit_price_str = format_amount(it.get("unit_price", 0), currency)
        line_total_str = format_amount(it.get("line_total", 0), currency)
        rows.append([
            cel(item_html),
            cel(qty_str, align=TA_CENTER),
            cel(unit_str, align=TA_CENTER),
            cel(unit_price_str, align=TA_RIGHT),
            cel(line_total_str, align=TA_RIGHT),
        ])

    # Grand total row
    total_str = format_amount(quote_data.get("total", 0), currency)
    rows.append([
        cel("CENA CELKEM bez DPH", bold=True, size=10),
        cel(""), cel(""), cel(""),
        cel(total_str, bold=True, align=TA_RIGHT, size=10),
    ])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)

    # Build style dynamically: header + items + total
    style_cmds = [
        # Header row
        ("BACKGROUND", (0,0), (-1,0), BLUE),
        ("TOPPADDING",    (0,0), (-1,0), 3*mm),
        ("BOTTOMPADDING", (0,0), (-1,0), 3*mm),
        ("LEFTPADDING",   (0,0), (-1,0), 4*mm),
        ("RIGHTPADDING",  (0,0), (-1,0), 4*mm),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]
    n_items = len(items)
    for i in range(1, n_items + 1):
        style_cmds.extend([
            ("BACKGROUND", (0,i), (-1,i), LGRAY if i % 2 == 0 else WHITE),
            ("TOPPADDING",    (0,i), (-1,i), 3.5*mm),
            ("BOTTOMPADDING", (0,i), (-1,i), 3.5*mm),
            ("LEFTPADDING",   (0,i), (-1,i), 4*mm),
            ("RIGHTPADDING",  (0,i), (-1,i), 4*mm),
            ("LINEBELOW", (0,i), (-1,i), 0.5, DIVIDER),
        ])
    # Total row
    total_row_idx = n_items + 1
    style_cmds.extend([
        ("BACKGROUND", (0,total_row_idx), (-1,total_row_idx), LGRAY),
        ("TOPPADDING",    (0,total_row_idx), (-1,total_row_idx), 3*mm),
        ("BOTTOMPADDING", (0,total_row_idx), (-1,total_row_idx), 3*mm),
        ("LEFTPADDING",   (0,total_row_idx), (-1,total_row_idx), 4*mm),
        ("RIGHTPADDING",  (0,total_row_idx), (-1,total_row_idx), 4*mm),
        ("LINEABOVE", (0,total_row_idx), (-1,total_row_idx), 1.5, BLUE),
    ])
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)
    story.append(Spacer(1, 4*mm))

    # ── VALID UNTIL (if set) ──────────────────────────────────────────────────
    if quote_data.get("valid_until"):
        story.append(Paragraph(
            f'<font color="#666B7A">Nabídka je platná do:</font> <b>{quote_data["valid_until"]}</b>',
            s("vu", font=F, size=9, color=DARK, sa=4)
        ))

    story.append(Spacer(1, 3*mm))

    # ── LEGAL TEXT ────────────────────────────────────────────────────────────
    legal = LEGAL_CZ if currency == "CZK" else LEGAL_EN
    story.append(Paragraph(
        legal,
        s("legal", size=7.5, color=MID, leading=11, align=TA_JUSTIFY)
    ))

    # ── OPTIONAL NOTES ────────────────────────────────────────────────────────
    if quote_data.get("notes"):
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(
            f'<b>Poznámky:</b> {quote_data["notes"]}',
            s("notes", size=8.5, color=DARK, leading=12)
        ))

    story.append(Spacer(1, 10*mm))

    # ── SIGNATURE BLOCKS ──────────────────────────────────────────────────────
    sig_data = [[
        [
            Paragraph("Za dodavatele:", s("sl", font=FB, size=8.5, color=DARK, sa=2)),
            Paragraph("Jakub Matuska, Mapecomm s.r.o.", s("sn", size=8.5, color=MID, sa=10)),
            HRFlowable(width="100%", thickness=0.5, color=DIVIDER, spaceAfter=2),
            Paragraph("Podpis / datum", s("sd", size=7.5, color=MID)),
        ],
        [
            Paragraph("Za odběratele:", s("sl2", font=FB, size=8.5, color=DARK, sa=2)),
            Paragraph(quote_data["buyer"].get("name", ""), s("sn2", size=8.5, color=MID, sa=10)),
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
