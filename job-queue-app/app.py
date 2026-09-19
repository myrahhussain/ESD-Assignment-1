from flask import Flask, request, jsonify
from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest, CONTENT_TYPE_LATEST
import uuid
import threading
import time
import os
import logging
from pythonjsonlogger import jsonlogger
from fpdf import FPDF

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

def generate_invoice(job_id, customer, items):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)
    pdf.cell(0, 10, "SHOP INVOICE", ln=True)

    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, f"Customer: {customer}", ln=True)
    pdf.ln(5)

    total = 0
    for item in items:
        line_total = item["qty"] * item["price"]
        total += line_total
        pdf.cell(0, 10, f"{item['name']} - Qty: {item['qty']} - Price: ${item['price']} - Total: ${line_total}", ln=True)

    pdf.ln(5)
    pdf.cell(0, 10, f"Grand Total: ${total}", ln=True)

    filename = f"invoices/invoice_{job_id}.pdf"
    pdf.output(filename)
    return filename, total

@app.route("/")
def home():
    return "This is Myrah's invoice job queue."

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

    logger.info("Job submitted", extra={"job_id": job_id, "event_type": "job_submitted", "customer": data["customer"]})

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
    while True:
        for job_id, job in list(jobs.items()):
            if job["status"] == "pending":
                job["status"] = "in_progress"
                logger.info("Job processing started", extra={"job_id": job_id, "event_type": "job_started"})

                start_time = time.time()

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

                logger.info("Job completed successfully", extra={"job_id": job_id, "event_type": "job_completed", "invoice_file": filename, "duration_seconds": duration, "invoice_total": invoice_total})

        time.sleep(1)

if __name__ == "__main__":
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    app.run(debug=True, use_reloader=False)