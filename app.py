from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import io
import sys
import os
import urllib.request

# ── Download DejaVu fonts if not present ──────────────────────────────────────
FONT_DIR = "/tmp/fonts"
FONT_URL = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2"

def ensure_fonts():
    font_path = "/tmp/fonts/LiberationSans-Regular.ttf"
    # First check if Liberation Sans is already on the system
    system_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    if os.path.exists(system_path):
        print("Using system Liberation Sans fonts")
        return system_path
    if not os.path.exists(font_path):
        os.makedirs(FONT_DIR, exist_ok=True)
        print("Downloading Liberation fonts...")
        import tarfile
        tmp_tar = "/tmp/liberation.tar.gz"
        urllib.request.urlretrieve(
            "https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz",
            tmp_tar
        )
        with tarfile.open(tmp_tar, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".ttf"):
                    member.name = os.path.basename(member.name)
                    tar.extract(member, FONT_DIR)
        print(f"Fonts ready: {os.listdir(FONT_DIR)}")
    return font_path

ensure_fonts()

# Set font paths for po_generator
os.environ["DEJAVU_FONT_PATH"] = "/tmp/fonts/DejaVuSans.ttf"
os.environ["DEJAVU_FONT_BOLD_PATH"] = "/tmp/fonts/DejaVuSans-Bold.ttf"

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from po_generator import generate_po_content, merge_with_letterhead
from quote_generator import generate_quote_content

app = Flask(__name__)
CORS(app)

LETTERHEAD_PATH = os.path.join(os.path.dirname(__file__), "letterhead.pdf")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/generate-po", methods=["POST"])
def generate_po():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate required fields
        required = ["po_number", "issue_date", "supplier", "item_description", "amount"]
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        po_data = {
            "po_number": data["po_number"],
            "issue_date": data["issue_date"],
            "supplier": {
                "name": data["supplier"].get("name", ""),
                "ico": data["supplier"].get("ico", ""),
                "dic": data["supplier"].get("dic", ""),
                "address": data["supplier"].get("address", ""),
                "city_zip": data["supplier"].get("city_zip", ""),
                "country": data["supplier"].get("country", "Česká republika"),
                "email": data["supplier"].get("email", ""),
                "phone": data["supplier"].get("phone", ""),
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
            "item_description": data["item_description"],
            "amount": float(data["amount"]),
            "currency": data.get("currency", "CZK"),
        }

        # Generate PDF
        content_buf = generate_po_content(po_data)
        output_buf = io.BytesIO()
        merge_with_letterhead(content_buf, LETTERHEAD_PATH, output_buf)
        output_buf.seek(0)

        filename = f"{po_data['po_number']} {po_data['supplier']['name']}.pdf"
        return send_file(
            output_buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route("/generate-quote", methods=["POST"])
def generate_quote():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate required fields
        required = ["quote_number", "issue_date", "buyer", "items", "total", "currency"]
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing field: {field}"}), 400

        # Build quote payload with Mapecomm as supplier (always us) and customer as buyer
        quote_data = {
            "quote_number": data["quote_number"],
            "issue_date": data["issue_date"],
            "valid_until": data.get("valid_until", ""),
            "currency": data.get("currency", "CZK"),
            "description": data.get("description", ""),
            "notes": data.get("notes", ""),
            "pricing_mode": data.get("pricing_mode", "per_item"),
            "supplier": {
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
            "buyer": {
                "name": data["buyer"].get("name", ""),
                "ico": data["buyer"].get("ico", ""),
                "dic": data["buyer"].get("dic", ""),
                "address": data["buyer"].get("address", ""),
                "city_zip": data["buyer"].get("city_zip", ""),
                "country": data["buyer"].get("country", ""),
                "contact": data["buyer"].get("contact", ""),
                "email": data["buyer"].get("email", ""),
                "phone": data["buyer"].get("phone", ""),
            },
            "items": [
                {
                    "name": it.get("name", ""),
                    "description": it.get("description", ""),
                    "quantity": float(it.get("quantity", 1)),
                    "unit": it.get("unit", ""),
                    "unit_price": float(it.get("unit_price", 0)),
                    "line_total": float(it.get("line_total", 0)),
                }
                for it in data["items"]
            ],
            "total": float(data["total"]),
        }

        # Generate content PDF, then merge with letterhead (reusing PO module's merger)
        content_buf = generate_quote_content(quote_data)
        output_buf = io.BytesIO()
        merge_with_letterhead(content_buf, LETTERHEAD_PATH, output_buf)
        output_buf.seek(0)

        # Sanitize customer name for filename
        customer_slug = "".join(
            c if c.isalnum() or c in (" ", "_", "-") else "_"
            for c in quote_data["buyer"]["name"]
        ).strip().replace(" ", "_")
        filename = f"{quote_data['quote_number']}_{customer_slug}.pdf"

        return send_file(
            output_buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
