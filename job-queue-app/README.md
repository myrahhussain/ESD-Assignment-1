# Invoice Job Queue

A small job queue system for a shop that needs to generate customer invoices without making anyone wait. Built for Assignment 1 (Observability), Enterprise Software Development, Fall 2026.

## Problem

Small shops need to generate invoices for customer orders, but doing this manually for each order wastes the owner's time and forces them to stop other work to create one. If many orders arrive at the same time, the owner would have to handle them one by one instead of running the shop.

## Users

- **Shop owners (primary user)** — save time by not manually creating each invoice themselves
- **Customers (secondary/indirect user)** — receive their invoice without waiting on the owner to stop and create it

## Solution

A job queue system where the shop owner submits order details through a simple API. Initially, the job is stored with a "pending" status. A background worker continuously checks for pending jobs and processes them in first-come-first-serve order, generating a real, itemized PDF invoice. The owner and customer can check a job's status at any time: pending, in progress, or done.

## What Works

- Submitting a new invoice job via the API, with one or more items per order
- Jobs are processed in the order they were received (first-come-first-serve)
- A background worker automatically picks up pending jobs and generates a real, itemized PDF invoice
- Job status can be checked at any time: `pending`, `in_progress`, or `done`
- Once done, the response includes the generated PDF's file path
- Application metrics (counters, a gauge, histograms, a summary) exposed at `/metrics` and visualized in Grafana
- Machine metrics (CPU, memory, disk, network) collected two ways: via Node Exporter (reflecting the WSL2/Docker virtualization layer) and via windows_exporter (reflecting the real Windows host directly) — kept as separate panels so both views can be compared
- Structured JSON logs shipped through Filebeat into Elasticsearch, searchable in Kibana, with a retention policy
- A `/chaos` endpoint to deliberately inject processing delays or random failures, used to test whether the observability setup actually catches problems

## Tech Stack

- **Backend:** Python, Flask
- **PDF generation:** fpdf2
- **Metrics:** prometheus_client, Prometheus, Grafana, Node Exporter, windows_exporter
- **Logging:** Python logging + python-json-logger, Filebeat, Elasticsearch, Kibana
- **Infrastructure:** Docker

## Project Structure

```
job-queue-app/
├── app.py              (the entire application: API, worker, metrics, logging, chaos endpoint)
├── filebeat.yml         (Filebeat config: where to read logs, where to send them)
├── prometheus.yml       (Prometheus config: what to monitor, how often)
├── requirements.txt
├── invoices/            (generated PDF invoices)
└── logs/
    └── app.log          (structured JSON application logs)
```

## How to Try It

**1. Install dependencies**

`pip install -r requirements.txt`

**2. Run the app**

`python app.py`

**3. Submit a job**

Send a POST request to `http://127.0.0.1:5000/jobs` with a JSON body like:

```
{
  "customer": "Hira Naveed",
  "items": [
    {"name": "Chocolate Eclairs", "qty": 4, "price": 6},
    {"name": "Blueberry Macarons", "qty": 6, "price": 3},
    {"name": "Tiramisu Slice", "qty": 1, "price": 15},
    {"name": "Red Velvet Cupcake", "qty": 4, "price": 4}
  ]
}
```

You'll get back:

```
{
  "customer": "Hira Naveed",
  "items": [...],
  "status": "pending"
}
```

**4. Check the job's status**

Send a GET request to `http://127.0.0.1:5000/jobs/<job_id>`. Checking this at different times shows the job move through pending, then in_progress, then:

```
{
  "status": "done",
  "file": "invoices/invoice_<job_id>.pdf"
}
```

**5. View the invoice**

Open the file listed in `"file"`, inside the `invoices/` folder, to see the generated PDF.

**6. View metrics**

Raw metrics: `http://127.0.0.1:5000/metrics`. Dashboards: Grafana, once Prometheus is running.

**7. Search logs**

Once Filebeat, Elasticsearch, and Kibana are running, search logs in Kibana Discover, for example: `event_type: "job_completed"`.

**8. Test fault injection**

```
GET  http://127.0.0.1:5000/chaos
POST http://127.0.0.1:5000/chaos   body: {"slow_every_nth": 3}
POST http://127.0.0.1:5000/chaos   body: {"failure_rate": 0.3}
```

## Machine Metrics: Virtualization vs. Real Host

CPU, memory, disk, and network are each collected two separate ways:

- **Node Exporter**, running in Docker, reports on the WSL2 virtualization layer Docker Desktop uses on Windows. CPU and memory figures from this source are reasonably representative of the real machine, since WSL2 shares actual hardware directly. Disk figures from this source are not representative of the real machine — they reflect WSL2's own small internal virtual disk, not the real Windows drive.
- **windows_exporter**, running natively on Windows (not in Docker), reports directly on the real host machine, with no virtualization layer involved. This is the accurate source for disk usage, and is also collected for CPU, memory, and network for direct comparison against the Node Exporter figures.

Total physical memory for the windows_exporter memory calculation was obtained once via `Get-CimInstance Win32_ComputerSystem` in PowerShell and used as a fixed value in the Grafana query, since this windows_exporter build does not expose total memory as its own metric with the default collectors enabled.

## Known Limitations

- All application data (jobs, in-progress status) lives in memory and resets on restart. This is intentional, per the assignment's instruction not to build a database management system.
- Grafana dashboards are not persisted outside the running container; if the Grafana container is removed, its saved panels must be rebuilt (the exact queries used are documented in the project report).
