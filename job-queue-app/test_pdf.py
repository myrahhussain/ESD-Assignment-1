from fpdf import FPDF

def generate_invoice(customer, items):
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

    pdf.output("test_invoice.pdf")

generate_invoice("John Smith", [
    {"name": "Laptop", "qty": 2, "price": 1000},
    {"name": "Mouse", "qty": 3, "price": 25}
])