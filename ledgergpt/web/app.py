"""
Flask Web Application & REST API for LedgerGPT.
"""

import os
import io
import csv
from flask import Flask, render_template, request, jsonify, send_file, Response
from ledgergpt.config import DB_PATH, SAMPLE_DATA_DIR, WEB_HOST, WEB_PORT, WEB_DEBUG
from ledgergpt.db import FinancialDB
from ledgergpt.query_engine import QueryEngine
from ledgergpt.ingestor import DataIngestor
from ledgergpt.forensic import ForensicScanner
from ledgergpt.formatters import format_inr
from ledgergpt.tally_sync import TallySyncEngine
from ledgergpt.dashboard_service import DashboardService

template_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# Initialize Core Services
db = FinancialDB(DB_PATH)
engine = QueryEngine(db=db)
scanner = ForensicScanner(db=db)
dashboard_service = DashboardService(db=db)

# Ensure sample data is loaded if DB is empty
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vouchers")
    count = cursor.fetchone()[0]
    if count == 0 and os.path.exists(SAMPLE_DATA_DIR):
        print("[AUTO-INIT] Empty database detected. Ingesting verified sample dataset...")
        ingestor = DataIngestor(db=db)
        ingestor.ingest_sample_dataset(SAMPLE_DATA_DIR)

@app.route("/")
def index():
    kpis = db.get_kpis()
    return render_template("index.html", kpis=kpis, format_inr=format_inr)

@app.route("/api/kpis", methods=["GET"])
def get_kpis():
    kpis = db.get_kpis()
    # Add human formatted values
    kpis["sales_formatted"] = format_inr(kpis.get("total_sales_gross", 0))
    kpis["purchase_formatted"] = format_inr(kpis.get("total_purchase_gross", 0))
    kpis["debit_formatted"] = format_inr(kpis.get("total_debit_notes_gross", 0))
    kpis["credit_formatted"] = format_inr(kpis.get("total_credit_notes_gross", 0))
    return jsonify(kpis)

# --- DASHBOARD ANALYTICS ENDPOINTS ---
@app.route("/api/dashboard/summary", methods=["GET"])
def get_dashboard_summary():
    return jsonify(dashboard_service.get_executive_summary())

@app.route("/api/dashboard/monthly-trend", methods=["GET"])
def get_dashboard_monthly_trend():
    return jsonify(dashboard_service.get_monthly_trend())

@app.route("/api/dashboard/rankings", methods=["GET"])
def get_dashboard_rankings():
    top_n = request.args.get("top_n", 10, type=int)
    return jsonify(dashboard_service.get_rankings(top_n=top_n))

@app.route("/api/dashboard/vouchers-grid", methods=["GET"])
def get_dashboard_vouchers_grid():
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    vtype = request.args.get("type", None, type=str)
    fy = request.args.get("fy", None, type=str)
    search = request.args.get("search", None, type=str)
    return jsonify(dashboard_service.get_vouchers_grid(
        page=page, page_size=page_size, vtype=vtype, search=search, fy=fy
    ))

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "Query cannot be empty"}), 400

    res = engine.process_query(query)
    return jsonify(res)

@app.route("/api/export", methods=["POST"])
def export_csv():
    data = request.get_json() or {}
    rows = data.get("data", [])
    columns = data.get("columns", [])
    filename = data.get("filename", "LedgerGPT_Query_Export.csv")

    if not rows:
        return jsonify({"error": "No data to export"}), 400

    if not columns and rows:
        columns = list(rows[0].keys())

    output = io.StringIO()
    # Write UTF-8 BOM
    output.write("\ufeff")
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)

    return send_file(
        mem,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )

@app.route("/api/forensic", methods=["GET"])
def run_forensic():
    report = scanner.run_full_forensic_suite()
    return jsonify(report)

@app.route("/api/tally-companies", methods=["GET"])
def get_tally_companies():
    sync_engine = TallySyncEngine(db=db)
    ok, msg = sync_engine.check_connection()
    if not ok:
        return jsonify({"connected": False, "error": msg, "companies": []})
    comps = sync_engine.get_open_companies()
    return jsonify({"connected": True, "companies": comps})

@app.route("/api/sync-tally", methods=["POST"])
def sync_tally():
    data = request.get_json() or {}
    company_name = data.get("company_name")
    clear_existing = data.get("clear_existing", False)
    
    sync_engine = TallySyncEngine(db=db)
    result = sync_engine.sync(company_name=company_name, clear_existing=clear_existing)
    
    if result.get("success"):
        # Enrich with formatted KPIs
        kpis = result.get("kpis", {})
        kpis["sales_formatted"] = format_inr(kpis.get("total_sales_gross", 0))
        kpis["purchase_formatted"] = format_inr(kpis.get("total_purchase_gross", 0))
        kpis["debit_formatted"] = format_inr(kpis.get("total_debit_notes_gross", 0))
        kpis["credit_formatted"] = format_inr(kpis.get("total_credit_notes_gross", 0))
        result["kpis"] = kpis
        return jsonify(result)
    else:
        return jsonify(result), 400

@app.route("/api/ingest_sample", methods=["POST"])
def ingest_sample():
    ingestor = DataIngestor(db=db)
    cnt = ingestor.ingest_sample_dataset(SAMPLE_DATA_DIR)
    return jsonify({"status": "success", "vouchers_ingested": cnt})

def run():
    print(f"\n=======================================================")
    print(f"  LedgerGPT Server Running at http://{WEB_HOST}:{WEB_PORT}")
    print(f"=======================================================\n")
    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG)

if __name__ == "__main__":
    run()
