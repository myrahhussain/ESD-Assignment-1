Problem

Small shops need to generate invoices for customer orders, but doing this manually (for each order) wastes the owner's time and they have to stop their other work to type one. If many orders arrive at the same time, the owner will have to handle them one by one instead of running the shop.

Users
Shop owners (primary user) — save time by not manually creating each invoice themselves
Customers (secondary/indirect user) — receive their invoice without waiting on the owner to stop and type it up
Solution

A job queue system where the shop owner submits order details through a simple API. Initially, the job is stored with a "pending" status. A background worker continuously checks for pending jobs and processes them in first-come-first-serve order, generating an invoice as a PDF. The owner and customer can check the job's status at different times: pending, in progress, or done. The request is stored as a job and handled in the background, so the shop owner doesn't have to spend their time creating it manually.

What Works
Submitting a new invoice job via the API
Jobs are processed in the order they were received (first-come-first-serve)
A background worker automatically picks up pending jobs and generates a real PDF invoice
Job status can be checked at any time: pending, in_progress, or done
Once done, the generated PDF file path is included in the response
How to Try It

1. Install dependencies

pip install -r requirements.txt

2. Run the app

python app.py

3. Submit a job

Send a POST request to http://127.0.0.1:5000/jobs with a JSON body like:

{
  "customer": "Sarah Malik",
  "items": [
    {"name": "Notebook", "qty": 4, "price": 5},
    {"name": "Pen Set", "qty": 2, "price": 10}
  ]
}

You'll get back a job with status:

{
  "customer": "Sarah Malik",
  "items": [...],
  "status": "pending"
}

4. Check the job's status

Send a GET request to http://127.0.0.1:5000/jobs/<job_id> (replace <job_id> with the ID from the previous step). Sending this at different times shows the job moving through its lifecycle:

Right after submitting:

{ "status": "pending" }

A moment later:

{ "status": "in_progress" }

After a couple seconds:

{
  "status": "done",
  "file": "invoices/invoice_b2bd8c08-a084-4758-96e5-accf665931ac.pdf"
}

5. View the invoice

Open the file listed in the "file" field, found inside the invoices/ folder, to see the generated PDF.