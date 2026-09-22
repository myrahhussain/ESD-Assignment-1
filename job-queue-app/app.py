from flask import Flask, request, jsonify
from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest, CONTENT_TYPE_LATEST
import uuid
import threading
import time
import os
import random
import logging
from pythonjsonlogger import jsonlogger
from fpdf import FPDF
from datetime import datetime

app = Flask(__name__)

jobs = {}

os.makedirs("invoices", exist_ok=True)
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("invoice_app")
logger.setLevel(logging.INFO)

log_handler = logging.FileHandler("logs/app.log")
formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)

SERVICE_NAME = "invoice_job_queue"

# --- Chaos / fault injection state ---
CHAOS_STATE = {
    "slow_every_nth": 0,
    "failure_rate": 0.0
}
jobs_processed_count = 0
chaos_lock = threading.Lock()

jobs_submitted_total = Counter(
    "jobs_submitted_total",
    "Total number of invoice jobs submitted"
)

jobs_in_progress = Gauge(
    "jobs_in_progress",
    "Number of jobs currently pending or being processed"
)

job_processing_seconds = Histogram(
    "job_processing_seconds",
    "Time taken to process a job, in seconds"
)

invoice_file_size_kb = Summary(
    "invoice_file_size_kb",
    "Size of generated invoice PDF files in kilobytes"
)

invoice_total_value = Histogram(
    "invoice_total_value",
    "Total dollar value of generated invoices",
    buckets=[10, 50, 100, 500, 1000, 5000, 10000]
)

jobs_failed_total = Counter(
    "jobs_failed_total",
    "Total number of jobs that failed during processing"
)

# --- Cardinality explosion demo ---
cardinality_test_counter = Counter(
    "cardinality_test_requests_total",
    "Test counter demonstrating cardinality explosion when labeled with a unique ID per call",
    ["request_id"]
)

cardinality_test_safe_counter = Counter(
    "cardinality_test_safe_requests_total",
    "Safe version - no per-request label, single series regardless of call volume"
)

def generate_invoice(job_id, customer, items):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "SHOP INVOICE", align="C", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", size=10)
    invoice_number = job_id.split("-")[0].upper()
    pdf.cell(0, 6, f"Invoice #: {invoice_number}", ln=True)
    pdf.cell(0, 6, f"Date: {datetime.now().strftime('%B %d, %Y')}", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"Customer: {customer}", ln=True)
    pdf.ln(6)

    col_widths = [80, 25, 35, 40]
    headers = ["Item", "Qty", "Price", "Total"]

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    for width, header in zip(col_widths, headers):
        align = "L" if header == "Item" else "R"
        pdf.cell(width, 8, header, border=1, align=align, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", size=10)
    total = 0
    for item in items:
        line_total = item["qty"] * item["price"]
        total += line_total
        pdf.cell(col_widths[0], 8, str(item["name"]), border=1)
        pdf.cell(col_widths[1], 8, str(item["qty"]), border=1, align="R")
        pdf.cell(col_widths[2], 8, f"${item['price']:.2f}", border=1, align="R")
        pdf.cell(col_widths[3], 8, f"${line_total:.2f}", border=1, align="R")
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(sum(col_widths[:3]), 8, "Grand Total:", align="R")
    pdf.cell(col_widths[3], 8, f"${total:.2f}", border=1, align="R")
    pdf.ln()

    filename = f"invoices/invoice_{job_id}.pdf"
    pdf.output(filename)
    return filename, total

@app.route("/")
def home():
    return "This is Myrah's invoice job queue."

@app.route("/chaos", methods=["POST"])
def set_chaos():
    data = request.get_json()
    if "slow_every_nth" in data:
        CHAOS_STATE["slow_every_nth"] = data["slow_every_nth"]
    if "failure_rate" in data:
        CHAOS_STATE["failure_rate"] = data["failure_rate"]
    return jsonify({"status": "ok", "chaos_state": CHAOS_STATE})

@app.route("/chaos", methods=["GET"])
def get_chaos():
    return jsonify(CHAOS_STATE)

@app.route("/cardinality-test")
def cardinality_test():
    request_id = str(uuid.uuid4())
    cardinality_test_counter.labels(request_id=request_id).inc()
    return jsonify({"request_id": request_id})

@app.route("/cardinality-test-safe")
def cardinality_test_safe():
    cardinality_test_safe_counter.inc()
    return jsonify({"status": "called"})

@app.route("/jobs", methods=["POST"])
def create_job():
    data = request.get_json()

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "customer": data["customer"],
        "items": data["items"]
    }

    jobs_submitted_total.inc()
    jobs_in_progress.inc()

    logger.info(
        "Job submitted",
        extra={
            "app_service": SERVICE_NAME,
            "job_id": job_id,
            "event_type": "job_submitted",
            "customer": data["customer"],
            "items": data["items"]
        }
    )

    return jsonify({"job_id": job_id, "status": "pending"})

@app.route("/jobs/<job_id>")
def get_job(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(jobs[job_id])

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

def worker_loop():
    global jobs_processed_count
    while True:
        for job_id, job in list(jobs.items()):
            if job["status"] == "pending":
                job["status"] = "in_progress"
                logger.info(
                    "Job processing started",
                    extra={"app_service": SERVICE_NAME, "job_id": job_id, "event_type": "job_started"}
                )

                start_time = time.time()

                with chaos_lock:
                    jobs_processed_count += 1
                    current_count = jobs_processed_count
                    slow_n = CHAOS_STATE["slow_every_nth"]
                    fail_rate = CHAOS_STATE["failure_rate"]

                if fail_rate > 0 and random.random() < fail_rate:
                    time.sleep(1)
                    job["status"] = "failed"
                    jobs_in_progress.dec()
                    jobs_failed_total.inc()
                    logger.error(
                        "Job failed during processing",
                        extra={
                            "app_service": SERVICE_NAME,
                            "job_id": job_id,
                            "event_type": "job_failed",
                            "reason": "simulated_failure"
                        }
                    )
                    continue

                if slow_n > 0 and current_count % slow_n == 0:
                    time.sleep(30)
                else:
                    time.sleep(8)

                filename, invoice_total = generate_invoice(job_id, job["customer"], job["items"])

                duration = time.time() - start_time
                job_processing_seconds.observe(duration)

                file_size_kb = os.path.getsize(filename) / 1024
                invoice_file_size_kb.observe(file_size_kb)

                invoice_total_value.observe(invoice_total)

                job["status"] = "done"
                job["file"] = filename
                jobs_in_progress.dec()

                logger.info(
                    "Job completed successfully",
                    extra={
                        "app_service": SERVICE_NAME,
                        "job_id": job_id,
                        "event_type": "job_completed",
                        "invoice_file": filename,
                        "duration_seconds": duration,
                        "invoice_total": invoice_total
                    }
                )

        time.sleep(1)

if __name__ == "__main__":
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    app.run(debug=True, use_reloader=False)