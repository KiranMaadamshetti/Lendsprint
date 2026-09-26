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

# ---------- RISKY borrower: Skyline Traders (anomalies + DPD) ----------
make("/app/synthetic_docs/bad_bank.pdf", [
    "ICICI BANK - CURRENT ACCOUNT STATEMENT (SYNTHETIC DEMO DATA)",
    "Account holder: Skyline Traders    Account: XXXX9920",
    "Statement period: 12 months",
    "Average monthly credits (inflows): INR 12,00,000",
    "Average monthly balance: INR 1,80,000",
    "Total annual bank credits (turnover): INR 1,44,00,000",
    "Inflow to outflow ratio: 0.96",
    "",
    "MONTH-WISE SUMMARY (credits / debits / closing balance in INR):",
    "  Apr-2025: 13,40,000 / 13,90,000 / 1,60,000",
    "  May-2025: 10,80,000 / 11,50,000 / 1,20,000",
    "  Jun-2025: 14,20,000 / 13,10,000 / 2,10,000",
    "  Jul-2025: 9,60,000 / 10,80,000 / 90,000",
    "  Aug-2025: 12,90,000 / 12,40,000 / 1,80,000",
    "  Sep-2025: 11,20,000 / 12,10,000 / 1,10,000",
    "  Oct-2025: 13,80,000 / 13,20,000 / 2,20,000",
    "  Nov-2025: 10,40,000 / 11,90,000 / 80,000",
    "  Dec-2025: 14,60,000 / 13,70,000 / 2,40,000",
    "  Jan-2026: 9,90,000 / 11,20,000 / 70,000",
    "  Feb-2026: 12,10,000 / 12,00,000 / 1,50,000",
    "  Mar-2026: 11,10,000 / 12,80,000 / 60,000",
    "",
    "RECURRING EMI / LOAN INSTALMENT DEBITS (monthly):",
    "  Kotak Personal Loan EMI ................. INR 85,000 (monthly)",
    "  HDFC Credit Card minimum due ............ INR 40,000 (monthly)",
    "  IIFL Business Loan EMI .................. INR 1,95,000 (monthly)",
    "  Total EMIs per month: 3  |  Total EMI outflow: INR 3,20,000",
    "",
    "TOP CREDIT SOURCES (money received):",
    "  Assorted retail UPI collections ......... INR 70,00,000 across 210 txns",
    "  Cash deposits (self) .................... INR 34,00,000 across 26 txns",
    "TOP DEBIT DESTINATIONS (money paid):",
    "  Supplier payments ....................... INR 52,00,000 across 60 txns",
    "  ATM / cash withdrawals .................. INR 41,00,000 across 88 txns",
    "",
    "FLAGGED / ANOMALOUS TRANSACTIONS OBSERVED:",
    "  Junglee Rummy (RummyCircle) debits ...... INR 6,40,000 across 52 txns",
    "  Dream11 / MPL fantasy gaming debits ..... INR 2,10,000 across 33 txns",
    "  Parimatch betting gateway ............... INR 1,80,000 across 19 txns",
    "  Frequent large cash withdrawals near month-end (structuring pattern).",
    "",
    "Cheque returns during period: 4",
    "NACH mandate failures during period: 2",
    "Cash flow pattern: volatile, high gambling outflow, thin surplus, EMI stress.",
])
make("/app/synthetic_docs/bad_cibil.pdf", [
    "CIBIL / TRANSUNION COMMERCIAL CREDIT REPORT (SYNTHETIC DEMO DATA)",
    "Entity: Skyline Traders",
    "CIBIL Score: 648",
    "Total active loans: 4   Hard enquiries (last 6 months): 6",
    "Total sanctioned: INR 95,00,000   Total outstanding: INR 72,00,000",
    "Total overdue amount: INR 3,20,000   Worst DPD across accounts: 62 days",
    "Repayment track record: multiple late payments, one account 60+ DPD.",
    "",
    "TRADELINES / LOAN ACCOUNTS:",
    "  1. IIFL Finance | Business Loan | Sanctioned 45,00,000 | Outstanding 38,00,000 | EMI 1,95,000 | DPD 62 | Status Overdue | Opened Feb-2023",
    "  2. Kotak Mahindra | Personal Loan | Sanctioned 20,00,000 | Outstanding 16,00,000 | EMI 85,000 | DPD 15 | Status Active | Opened Aug-2023",
    "  3. HDFC Bank | Credit Card | Sanctioned 10,00,000 | Outstanding 9,50,000 | EMI 40,000 | DPD 30 | Status Active | Opened May-2022",
    "  4. Bajaj Finserv | Consumer Durable | Sanctioned 20,00,000 | Outstanding 8,50,000 | EMI 22,000 | DPD 0 | Status Active | Opened Jan-2024",
])
make("/app/synthetic_docs/bad_gst.pdf", [
    "GST RETURNS SUMMARY GSTR-3B (SYNTHETIC DEMO DATA)",
    "Legal name: Skyline Traders",
    "Aggregate annual turnover declared: INR 78,00,000",
    "Business commencement: registered 15 months ago",
])
print("generated risky set + CIBIL + month-wise")
