"""
Mapecomm Line Items Breakdown — PDF generator.
Renders the team-reported scope of work as a dispute document for KVM.
Uses the same letterhead.pdf as PO/Quote for brand consistency, but no
gradient title band — uses a plain bold navy title (lighter, less aggressive
than PO/Quote since this is a dispute clarification document, not an invoice
or offer).

Layout (top to bottom, on letterhead):
  - Title: "Team-Reported Line Items — {site_id}" (bold navy, 16pt)
  - Metadata block (light F2 background): Bestellung-Nr / Customer / Generated
  - Disclaimer banner (light blue, English): explains team-reported nature
  - Items table: Code | Description | Customer Price | Qty | Total
  - TOTAL row at bottom (bold navy)
  - Optional Note to KVM (if note_to_customer field is set)
  (footer comes from letterhead.pdf — Mapecomm contact line at bottom)

Font and currency logic is intentionally identical to po_generator.py.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io, os

# ── Fonts (identical search order to po_generator.py / quote_generator.py) ────
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
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", font_bold_path))
    except Exception:
        pass  # already registered by another module
    F = "DejaVu"
    FB = "DejaVu-Bold"
else:
    F = "Helvetica"
    FB = "Helvetica-Bold"

# ── Colors (Mapecomm canonical) ───────────────────────────────────────────────
BLUE       = colors.HexColor("#2E7EC7")
BLUE_LIGHT = colors.HexColor("#E8F1FB")
DARK       = colors.HexColor("#3D4555")
LGRAY      = colors.HexColor("#F4F6F9")
LGRAY2     = colors.HexColor("#EDF1F7")
MID        = colors.HexColor("#666B7A")
LIGHT_TXT  = colors.HexColor("#999999")
WHITE      = colors.white
DIVIDER    = colors.HexColor("#D0D5E0")

# ── Currency formatting ───────────────────────────────────────────────────────
def format_amount(amount, currency="EUR"):
    """Czech-style number formatting with currency code suffix.
    For Line Items PDF we use the currency code (EUR / CZK etc) as suffix,
    not the symbol, because recipient is KVM and they prefer explicit codes."""
    integer_part = int(amount)
    decimal_part = round((amount - integer_part) * 100)
    int_str = f"{integer_part:,}".replace(",", "\u00a0")
    return f"{int_str},{decimal_part:02d} {currency}"

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


def generate_line_items_content(data):
    """
    Generate Line Items Breakdown content as PDF buffer (no letterhead — that's
    merged separately via merge_with_letterhead from po_generator).

    Expected data shape:
    {
        "site_id": "HY8811",
        "bestellung_nr": "202600961",
        "customer_name": "KV-Mobilfunk GmbH",   # full legal name
        "generated_date": "12.05.2026",          # already formatted
        "currency": "EUR",
        "items": [
            {
                "code": "KV-001",
                "description": "Einsatz Seilwinden Montage Stando< 67 m",
                "unit_price": 270.0,
                "quantity": 1,
                "line_total": 270.0,
            },
            ...
        ],
        "total": 2248.40,
        "note_to_customer": "Optional free text..."  # optional, shown below table
    }
    """
    buf = io.BytesIO()
    W, H = A4

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=26*mm,   # match PO/Quote so letterhead header doesn't overlap
        bottomMargin=22*mm,
    )
    CW = W - 36*mm
    story = []

    currency = data.get("currency", "EUR")
    site_id = data.get("site_id", "")

    # ── TITLE (plain bold, no gradient band) ──────────────────────────────────
    title = Paragraph(
        f"Team-Reported Line Items — {site_id}",
        s("title", font=FB, size=16, color=DARK, leading=20)
    )
    story.append(title)
    story.append(Spacer(1, 5*mm))

    # ── METADATA BLOCK (light F2 background) ──────────────────────────────────
    bestellung_nr = data.get("bestellung_nr", "—")
    customer_name = data.get("customer_name", "—")
    generated_date = data.get("generated_date", "—")

    def meta_pair(label, value):
        return Paragraph(
            f'<font color="#999999" size="8.5">{label}:</font>'
            f' <font size="9.5"><b>{value}</b></font>',
            s("meta", size=9, color=DARK, leading=13)
        )

    meta_data = [[
        meta_pair("Bestellung-Nr", bestellung_nr),
        meta_pair("Customer", customer_name),
    ], [
        meta_pair("Generated", generated_date),
        Paragraph("", s("blank")),
    ]]
    meta_tbl = Table(meta_data, colWidths=[CW*0.5, CW*0.5])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LGRAY),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 5*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 5*mm),
        ("TOPPADDING", (0,0), (-1,-1), 3*mm),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3*mm),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 4*mm))

    # ── DISCLAIMER BANNER (English, light blue) ───────────────────────────────
    disclaimer = Table(
        [[Paragraph(
            "This document is generated from on-site team reporting and serves "
            "as a basis for comparison with the customer's order.",
            s("disc", size=9, color=DARK, leading=12, align=TA_LEFT)
        )]],
        colWidths=[CW],
    )
    disclaimer.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BLUE_LIGHT),
        ("LEFTPADDING", (0,0), (-1,-1), 5*mm),
        ("RIGHTPADDING", (0,0), (-1,-1), 5*mm),
        ("TOPPADDING", (0,0), (-1,-1), 3*mm),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3*mm),
        ("LINEBEFORE", (0,0), (-1,-1), 2.5, BLUE),  # left accent bar
    ]))
    story.append(disclaimer)
    story.append(Spacer(1, 5*mm))

    # ── ITEMS TABLE ───────────────────────────────────────────────────────────
    # 5 columns: Code | Description | Customer Price | Quantity | Total
    col_widths = [CW*0.12, CW*0.38, CW*0.18, CW*0.12, CW*0.20]

    def hdr(txt, align=TA_LEFT):
        return Paragraph(txt, s("th", font=FB, size=8.5, color=WHITE, align=align, leading=11))

    def cel(txt, bold=False, align=TA_LEFT, color=DARK, size=9):
        return Paragraph(txt, s("td", font=FB if bold else F, size=size,
                                color=color, align=align, leading=13))

    rows = [[
        hdr("CODE"),
        hdr("DESCRIPTION"),
        hdr(f"CUSTOMER PRICE ({currency})", TA_RIGHT),
        hdr("QUANTITY", TA_CENTER),
        hdr(f"TOTAL ({currency})", TA_RIGHT),
    ]]

    items = data.get("items", [])
    for it in items:
        qty_val = it.get("quantity", 0)
        if isinstance(qty_val, (int, float)) and qty_val == int(qty_val):
            qty_str = str(int(qty_val))
        else:
            qty_str = f"{qty_val:.2f}".replace(".", ",")
        rows.append([
            cel(it.get("code", ""), bold=False),
            cel(it.get("description", "")),
            cel(format_amount(it.get("unit_price", 0), currency), align=TA_RIGHT),
            cel(qty_str, align=TA_CENTER),
            cel(format_amount(it.get("line_total", 0), currency), align=TA_RIGHT),
        ])

    # Grand total row
    total_str = format_amount(data.get("total", 0), currency)
    rows.append([
        cel("TOTAL", bold=True, size=10),
        cel(""), cel(""), cel(""),
        cel(total_str, bold=True, align=TA_RIGHT, size=11),
    ])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        # Header row
        ("BACKGROUND", (0,0), (-1,0), BLUE),
        ("TOPPADDING",    (0,0), (-1,0), 3*mm),
        ("BOTTOMPADDING", (0,0), (-1,0), 3*mm),
        ("LEFTPADDING",   (0,0), (-1,0), 3*mm),
        ("RIGHTPADDING",  (0,0), (-1,0), 3*mm),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]
    n_items = len(items)
    for i in range(1, n_items + 1):
        style_cmds.extend([
            ("BACKGROUND", (0,i), (-1,i), LGRAY if i % 2 == 0 else WHITE),
            ("TOPPADDING",    (0,i), (-1,i), 2.5*mm),
            ("BOTTOMPADDING", (0,i), (-1,i), 2.5*mm),
            ("LEFTPADDING",   (0,i), (-1,i), 3*mm),
            ("RIGHTPADDING",  (0,i), (-1,i), 3*mm),
            ("LINEBELOW", (0,i), (-1,i), 0.5, DIVIDER),
        ])
    # Total row
    total_row_idx = n_items + 1
    style_cmds.extend([
        ("BACKGROUND", (0,total_row_idx), (-1,total_row_idx), LGRAY),
        ("TOPPADDING",    (0,total_row_idx), (-1,total_row_idx), 3*mm),
        ("BOTTOMPADDING", (0,total_row_idx), (-1,total_row_idx), 3*mm),
        ("LEFTPADDING",   (0,total_row_idx), (-1,total_row_idx), 3*mm),
        ("RIGHTPADDING",  (0,total_row_idx), (-1,total_row_idx), 3*mm),
        ("LINEABOVE", (0,total_row_idx), (-1,total_row_idx), 1.5, BLUE),
        ("TEXTCOLOR", (0,total_row_idx), (-1,total_row_idx), BLUE),
    ])
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    # ── OPTIONAL NOTE TO CUSTOMER ─────────────────────────────────────────────
    note = data.get("note_to_customer", "").strip() if data.get("note_to_customer") else ""
    if note:
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(
            f'<b>Note:</b> {note}',
            s("note", size=9, color=DARK, leading=12, align=TA_LEFT)
        ))

    doc.build(story)
    buf.seek(0)
    return buf
