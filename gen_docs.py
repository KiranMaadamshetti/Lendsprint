from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def make(path, lines):
    c = canvas.Canvas(path, pagesize=A4)
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 16
        if y < 60:
            c.showPage(); y = 800
    c.save()

make("/tmp/bank.pdf", [
    "HDFC BANK - CURRENT ACCOUNT STATEMENT (SYNTHETIC DEMO DATA)",
    "Account holder: Nova Precision Tools Pvt Ltd",
    "Statement period: 01-Apr-2025 to 31-Mar-2026 (12 months)",
    "Average monthly credits (inflows): INR 18,50,000",
    "Average monthly balance: INR 9,20,000",
    "Total annual bank credits (turnover): INR 2,22,00,000",
    "Existing loan EMI debits observed: INR 2,10,000 per month",
    "Total monthly obligations (EMIs + recurring debits): INR 5,60,000",
    "Cheque returns during period: 0",
    "NACH mandate failures during period: 0",
])
make("/tmp/itr.pdf", [
    "INCOME TAX RETURN - ITR (SYNTHETIC DEMO DATA)",
    "Assessee: Nova Precision Tools Pvt Ltd",
    "Assessment Year: 2025-26",
    "Declared gross annual business income: INR 2,05,00,000",
    "Nature of business: Precision Engineering / CNC Machining",
    "Business commencement: registered 84 months ago",
])
make("/tmp/gst.pdf", [
    "GST RETURNS SUMMARY GSTR-3B (SYNTHETIC DEMO DATA)",
    "Legal name: Nova Precision Tools Pvt Ltd",
    "Aggregate annual turnover declared: INR 2,15,00,000",
    "Filing status: all periods filed, no defaults",
    "CIBIL / commercial bureau score on file: 771",
])
print("generated")
