from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def make(path, lines):
    c = canvas.Canvas(path, pagesize=A4)
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 15
        if y < 60:
            c.showPage(); y = 800
    c.save()

# ---------- STRONG borrower: Nova Precision Tools ----------
make("/app/synthetic_docs/bank.pdf", [
    "HDFC BANK - CURRENT ACCOUNT STATEMENT (SYNTHETIC DEMO DATA)",
    "Account holder: Nova Precision Tools Pvt Ltd    Account: XXXX4471",
    "Statement period: 01-Apr-2025 to 31-Mar-2026 (12 months)",
    "Average monthly credits (inflows): INR 18,50,000",
    "Average monthly balance: INR 9,20,000",
    "Total annual bank credits (turnover): INR 2,22,00,000",
    "Inflow to outflow ratio: 1.18",
    "",
    "RECURRING EMI / LOAN INSTALMENT DEBITS (monthly):",
    "  HDFC Bank Equipment Loan EMI ............ INR 1,25,000 (monthly)",
    "  Bajaj Finserv Machinery Loan EMI ........ INR 55,000 (monthly)",
    "  ICICI Business Loan EMI ................. INR 30,000 (monthly)",
    "  Total EMIs per month: 3  |  Total EMI outflow: INR 2,10,000",
    "",
    "TOP CREDIT SOURCES (money received):",
    "  Larsen & Toubro Ltd (customer) .......... INR 84,00,000 across 14 txns",
    "  Tata Motors Vendor Payments ............. INR 62,00,000 across 11 txns",
    "  Ashok Leyland Ltd ....................... INR 38,00,000 across 7 txns",
    "TOP DEBIT DESTINATIONS (money paid):",
    "  Steel & Raw Material Suppliers .......... INR 96,00,000 across 40 txns",
    "  Salaries / Payroll ...................... INR 48,00,000 across 12 txns",
    "  GST & Tax Payments ...................... INR 22,00,000 across 12 txns",
    "",
    "Cheque returns during period: 0",
    "NACH mandate failures during period: 0",
    "No gambling, betting or unexplained cash transactions observed.",
    "Cash flow pattern: consistent B2B receivables, healthy surplus, disciplined EMIs.",
])
make("/app/synthetic_docs/cibil.pdf", [
    "CIBIL / TRANSUNION COMMERCIAL CREDIT REPORT (SYNTHETIC DEMO DATA)",
    "Entity: Nova Precision Tools Pvt Ltd",
    "CIBIL Score: 771",
    "Total active loans: 3   Hard enquiries (last 6 months): 1",
    "Total sanctioned: INR 1,20,00,000   Total outstanding: INR 61,00,000",
    "Total overdue amount: INR 0   Worst DPD across accounts: 0 days",
    "Repayment track record: excellent - all accounts standard, zero delinquency.",
    "",
    "TRADELINES / LOAN ACCOUNTS:",
    "  1. HDFC Bank | Equipment Loan | Sanctioned 50,00,000 | Outstanding 28,00,000 | EMI 1,25,000 | DPD 0 | Status Active | Opened Jan-2023",
    "  2. Bajaj Finserv | Machinery Loan | Sanctioned 40,00,000 | Outstanding 21,00,000 | EMI 55,000 | DPD 0 | Status Active | Opened Jun-2023",
    "  3. ICICI Bank | Business Loan | Sanctioned 30,00,000 | Outstanding 12,00,000 | EMI 30,000 | DPD 0 | Status Active | Opened Mar-2024",
])
make("/app/synthetic_docs/itr.pdf", [
    "INCOME TAX RETURN - ITR (SYNTHETIC DEMO DATA)",
    "Assessee: Nova Precision Tools Pvt Ltd   AY: 2025-26",
    "Declared gross annual business income: INR 2,05,00,000",
    "Nature of business: Precision Engineering / CNC Machining",
    "Business commencement: registered 84 months ago",
])
make("/app/synthetic_docs/gst.pdf", [
    "GST RETURNS SUMMARY GSTR-3B (SYNTHETIC DEMO DATA)",
    "Legal name: Nova Precision Tools Pvt Ltd",
    "Aggregate annual turnover declared: INR 2,15,00,000",
    "Filing status: all periods filed, no defaults",
])
print("generated strong set + CIBIL")
