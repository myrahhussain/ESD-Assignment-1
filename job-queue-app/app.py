from flask import Flask, request, jsonify
from prometheus_client import Counter, Gauge, Histogram, generate_latest
import uuid
import threading
import time
import os
from fpdf import FPDF

app = Flask(__name__)

jobs = {}

os.makedirs("invoices", exist_ok=True)

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
    return filename

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

    return jsonify({"job_id": job_id, "status": "pending"})

@app.route("/jobs/<job_id>")
def get_job(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(jobs[job_id])

@app.route("/metrics")
def metrics():
    return generate_latest()

def worker_loop():
    while True:
        for job_id, job in list(jobs.items()):
            if job["status"] == "pending":
                job["status"] = "in_progress"
                print(f"Processing job {job_id}...")

                start_time = time.time()

                time.sleep(2)

                filename = generate_invoice(job_id, job["customer"], job["items"])

                duration = time.time() - start_time
                job_processing_seconds.observe(duration)

                job["status"] = "done"
                job["file"] = filename
                jobs_in_progress.dec()
                print(f"Job {job_id} done -> {filename}")

        time.sleep(1)

if __name__ == "__main__":
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    app.run(debug=True, use_reloader=False)