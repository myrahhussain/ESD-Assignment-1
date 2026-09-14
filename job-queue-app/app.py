from flask import Flask

app = Flask(__name__)

import uuid

jobs = {}

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

if __name__ == "__main__":
    app.run(debug=True)