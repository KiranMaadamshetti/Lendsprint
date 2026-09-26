from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def make(path, lines):
    c = canvas.Canvas(path, pagesize=A4)
    y = 800
    for ln in lines:
        c.drawString(50, y, ln); y -= 16
    c.save()

make("/tmp/bad_bank.pdf", [
    "ICICI BANK - CURRENT ACCOUNT STATEMENT (SYNTHETIC DEMO DATA)",
    "Account holder: Skyline Traders",
    "Statement period: 12 months",
    "Average monthly credits (inflows): INR 12,00,000",
    "Average monthly balance: INR 1,80,000",
    "Total annual bank credits (turnover): INR 1,44,00,000",
    "Existing loan EMI debits observed: INR 3,20,000 per month",
    "Total monthly obligations: INR 7,40,000",
    "Cheque returns during period: 4",
    "NACH mandate failures during period: 2",
])
make("/tmp/bad_gst.pdf", [
    "GST RETURNS SUMMARY GSTR-3B (SYNTHETIC DEMO DATA)",
    "Legal name: Skyline Traders",
    "Aggregate annual turnover declared: INR 78,00,000",
    "CIBIL / commercial bureau score on file: 648",
    "Business commencement: registered 15 months ago",
])
print("generated bad set")
