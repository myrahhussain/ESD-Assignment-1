from flask import Flask

app = Flask(__name__)

import uuid

jobs = {}

from fpdf import FPDF
import os

os.makedirs("invoices", exist_ok=True)

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

from flask import request, jsonify

@app.route("/jobs", methods=["POST"])
def create_job():
    data = request.get_json()

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "customer": data["customer"],
        "items": data["items"]
    }

    return jsonify({"job_id": job_id, "status": "pending"})

@app.route("/jobs/<job_id>")
def get_job(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(jobs[job_id])

import threading
import time

def worker_loop():
    while True:
        for job_id, job in list(jobs.items()):
            if job["status"] == "pending":
                job["status"] = "in_progress"
                print(f"Processing job {job_id}...")

                time.sleep(2)  # simulate the work taking a couple seconds

                filename = generate_invoice(job_id, job["customer"], job["items"])
                job["status"] = "done"
                job["file"] = filename
                print(f"Job {job_id} done -> {filename}")

        time.sleep(1)  # wait a second before checking again

if __name__ == "__main__":
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()
    app.run(debug=True)