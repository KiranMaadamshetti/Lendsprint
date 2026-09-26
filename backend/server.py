from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import logging
import uuid
import hashlib
import math
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

import jwt
import bcrypt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File, Form, Body
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Config & DB
# ---------------------------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

MOCK_MODE = os.environ.get('MOCK_MODE', 'true').lower() == 'true'
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGORITHM = "HS256"
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY', '')
ANALYSIS_MODEL = "gpt-5.6-sol"
OCR_MODEL = "mistral-ocr-latest"

UPLOAD_DIR = ROOT_DIR / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("lendsprint")

app = FastAPI(title="LendSprint AI")
api_router = APIRouter(prefix="/api")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email,
               "exp": now_utc() + timedelta(hours=12), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
LoanType = Literal["business", "personal", "MSME"]


class LoginIn(BaseModel):
    email: str
    password: str


class ApplicationCreate(BaseModel):
    borrower_name: str = Field(..., min_length=2, max_length=140)
    loan_type: LoanType
    loan_amount: float = Field(..., gt=0)

    @field_validator("borrower_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Borrower name is required")
        return v


class DecisionOptions(BaseModel):
    use_ai: bool = False


class OverrideIn(BaseModel):
    decision: Literal["approve", "review", "reject"]
    reason: str = Field(..., min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Please provide a reason for the override")
        return v


class ActionIn(BaseModel):
    action: Literal["send_review", "approve", "reject", "escalate"]
    comment: str = ""


# ---------------------------------------------------------------------------
# Decision engine (mock)
# ---------------------------------------------------------------------------
LOAN_TYPE_LABEL = {"business": "Business", "personal": "Personal", "MSME": "MSME"}

# Deterministic profiles for the seeded demo borrowers.
KNOWN_PROFILES = {
    "arvind engineering pvt ltd": {"pd": 0.182, "decision": "approve", "income": 1342000,
                                    "obligations": 435000, "tat": 14, "vintage": 96, "cibil": 762,
                                    "cheque_bounces": 0, "nach_bounces": 0, "industry": "Precision Engineering"},
    "sri lakshmi components": {"pd": 0.31, "decision": "review", "income": 940000,
                               "obligations": 545000, "tat": 21, "vintage": 40, "cibil": 706,
                               "cheque_bounces": 2, "nach_bounces": 1, "industry": "Auto Components"},
    "bluepeak traders": {"pd": 0.48, "decision": "reject", "income": 360000,
                         "obligations": 245000, "tat": 19, "vintage": 14, "cibil": 636,
                         "cheque_bounces": 4, "nach_bounces": 2, "industry": "Wholesale Trading"},
}

REASON_BANK = {
    "STRONG_CF": ("Strong operating cash flow", 0.22, "positive"),
    "GOOD_COVERAGE": ("Healthy obligation coverage", 0.17, "positive"),
    "STABLE_BANKING": ("Stable banking behaviour", 0.12, "positive"),
    "MODERATE_CF": ("Moderate cash-flow buffer", 0.08, "positive"),
    "HIGH_UTIL": ("High recent credit utilisation", -0.18, "negative"),
    "REPAY_IRREG": ("Recent repayment irregularity", -0.13, "negative"),
    "SEASONAL_CF": ("Seasonal revenue concentration", -0.09, "negative"),
    "WEAK_CF": ("Weak operating cash flow", -0.24, "negative"),
    "HIGH_LEVERAGE": ("Elevated leverage profile", -0.20, "negative"),
    "NEG_TREND": ("Declining balance trend", -0.15, "negative"),
}


def _reason(code: str) -> dict:
    label, weight, direction = REASON_BANK[code]
    return {"code": code, "label": label, "weight": weight, "direction": direction}


def _seed_int(borrower: str, amount: float) -> int:
    return int(hashlib.md5(f"{borrower.lower()}|{int(amount)}".encode()).hexdigest(), 16)


def compute_decision(borrower_name: str, loan_type: str, loan_amount: float) -> dict:
    """Deterministic mock credit decision. Same input -> same output."""
    key = borrower_name.strip().lower()
    seed = _seed_int(borrower_name, loan_amount)

    if key in KNOWN_PROFILES:
        p = KNOWN_PROFILES[key]
        pd_score, decision = p["pd"], p["decision"]
        income, obligations, tat = p["income"], p["obligations"], p["tat"]
    else:
        pd_score = round(0.10 + (seed % 46) / 100.0, 3)  # 0.10 - 0.55
        decision = "approve" if pd_score < 0.25 else ("review" if pd_score < 0.42 else "reject")
        income = int(round(loan_amount * (0.34 + (seed % 8) / 100.0)))
        obligations = int(round(income * (0.30 + (seed % 15) / 100.0)))
        tat = 12 + (seed % 12)

    net = income - obligations

    if decision == "approve":
        codes = ["STRONG_CF", "GOOD_COVERAGE", "STABLE_BANKING"]
    elif decision == "review":
        codes = ["HIGH_UTIL", "REPAY_IRREG", "MODERATE_CF"]
    else:
        codes = ["WEAK_CF", "HIGH_LEVERAGE", "NEG_TREND"]
    reason_codes = [_reason(c) for c in codes]

    cash_flow_summary = {
        "income": income,
        "obligations": obligations,
        "net": net,
        "coverage": round(net / obligations, 2) if obligations else 0,
    }
    return {
        "pd_score": pd_score,
        "decision": decision,
        "reason_codes": reason_codes,
        "cash_flow_summary": cash_flow_summary,
        "tat_minutes": tat,
        "model_version": "mock-v1.0",
    }


def lakh(v: float) -> str:
    return f"{v / 100000:.2f}"


def build_memo_text(borrower: str, loan_type: str, loan_amount: float, result: dict) -> str:
    cf = result["cash_flow_summary"]
    decision = result["decision"].upper()
    pd_pct = result["pd_score"] * 100
    positives = [r["label"].lower() for r in result["reason_codes"] if r["direction"] == "positive"]
    negatives = [r["label"].lower() for r in result["reason_codes"] if r["direction"] == "negative"]
    lt = LOAN_TYPE_LABEL.get(loan_type, loan_type)

    tone = "stable operating cash generation" if result["decision"] == "approve" else (
        "variable operating cash generation that warrants closer review"
        if result["decision"] == "review" else "constrained operating cash generation")

    para1 = (f"{borrower} has been assessed for a {lt} facility of ₹{lakh(loan_amount)} lakh. "
             f"The available financial information indicates {tone} with estimated monthly income of "
             f"₹{lakh(cf['income'])} lakh and obligations of ₹{lakh(cf['obligations'])} lakh, resulting in "
             f"net monthly cash flow of approximately ₹{lakh(cf['net'])} lakh. The application reflects an "
             f"obligation coverage of {cf['coverage']}x based on the documents available for this demonstration.")

    if positives and negatives:
        para2 = (f"The model-generated probability of default is {pd_pct:.1f}%. Positive signals include "
                 f"{', '.join(positives)}. Offsetting risk signals include {', '.join(negatives)}, which "
                 f"should be validated by the analyst before final disposition.")
    elif positives:
        para2 = (f"The model-generated probability of default is {pd_pct:.1f}%. Positive decision signals include "
                 f"{', '.join(positives)}. No material adverse signal has been identified within the mock assessment.")
    else:
        para2 = (f"The model-generated probability of default is {pd_pct:.1f}%. Adverse signals include "
                 f"{', '.join(negatives)}, which materially weigh on the recommendation.")

    para3 = (f"Based on the configured demonstration decision policy, the application is classified as {decision}. "
             f"This memo is an AI-generated draft intended to support analyst review and should not be treated as a "
             f"final credit sanction.")
    return f"{para1}\n\n{para2}\n\n{para3}"


async def generate_ai_memo(borrower: str, loan_type: str, loan_amount: float, result: dict) -> str:
    """Real LLM memo generation. Only invoked when MOCK_MODE is false. Falls back to template."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        cf = result["cash_flow_summary"]
        prompt = (
            f"Write a concise ~150 word internal credit memo for an Indian NBFC.\n"
            f"Borrower: {borrower}\nLoan type: {LOAN_TYPE_LABEL.get(loan_type, loan_type)}\n"
            f"Requested amount (INR): {loan_amount}\nDecision: {result['decision'].upper()}\n"
            f"PD score: {result['pd_score']}\nMonthly income (INR): {cf['income']}\n"
            f"Monthly obligations (INR): {cf['obligations']}\nNet cash flow (INR): {cf['net']}\n"
            f"Reason codes: {[r['label'] for r in result['reason_codes']]}\n"
            f"Use INR lakh formatting. Do not overclaim certainty. End by noting it is an AI-generated draft "
            f"subject to credit policy and analyst review."
        )
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"memo-{borrower}",
            system_message="You are a senior credit analyst at an Indian NBFC writing professional, restrained credit memos.",
        ).with_model("openai", ANALYSIS_MODEL)
        resp = await chat.send_message(UserMessage(text=prompt))
        text = resp if isinstance(resp, str) else str(resp)
        text = text.strip()
        if not text:
            return build_memo_text(borrower, loan_type, loan_amount, result), "template"
        return text, "ai"
    except Exception as e:
        logger.warning(f"AI memo generation failed, using template: {e}")
        return build_memo_text(borrower, loan_type, loan_amount, result), "template"


# ---------------------------------------------------------------------------
# CREDIT BRAIN + CREDIT POLICY ENGINE
# ---------------------------------------------------------------------------
DEFAULT_POLICY = {
    "policy_name": "MSME Secured Business Loan Policy",
    "product_type": "MSME",
    "version": "v1.0",
    "status": "active",
    "effective_from": "2026-09-01",
    "created_by": "Credit Admin",
    "rules": {
        "min_avg_credits": 800000,
        "max_foir": 0.60,
        "min_dscr": 1.50,
        "min_vintage_months": 24,
        "min_cibil": 680,
        "max_cheque_bounces": 1,
        "min_annual_turnover": 10000000,
        "min_net_cashflow": 0,
    },
    "loan_amount_rules": {"absolute_max": 5000000, "turnover_multiple": 0.35, "collateral_coverage": 1.25},
    "roi_rules": [
        {"grade": "A", "pd_max": 0.15, "roi": 18.0},
        {"grade": "B", "pd_max": 0.25, "roi": 20.0},
        {"grade": "C", "pd_max": 0.40, "roi": 22.0},
    ],
    "tenure_rules": {"A": 60, "B": 48, "C": 36},
    "decision_matrix": {"approve_pd_max": 0.25, "review_pd_max": 0.40},
    "processing_fee_pct": 1.0,
    "approval_authority": [
        {"role": "credit_analyst", "label": "Credit Analyst", "min": 0, "max": 1000000},
        {"role": "credit_manager", "label": "Credit Manager", "min": 1000000, "max": 5000000},
        {"role": "admin", "label": "Senior Credit / Admin", "min": 0, "max": 1000000000},
    ],
    "required_documents": ["Bank Statement", "ITR", "GST Returns", "KYC", "Existing Loan Statement"],
    "mandatory_documents": [],
    "conditions": [
        "Completion of KYC verification for borrower and promoters.",
        "Verification of latest 6-month bank statement prior to disbursement.",
        "Registration of NACH mandate for EMI collection.",
        "Perfection of charge over offered collateral security.",
    ],
}


def _mk_policy_doc() -> dict:
    d = dict(DEFAULT_POLICY)
    d["id"] = str(uuid.uuid4())
    d["created_at"] = iso(now_utc())
    d["updated_at"] = iso(now_utc())
    return d


async def get_active_policy() -> dict:
    pol = await db.credit_policies.find_one({"status": "active"}, {"_id": 0})
    if not pol:
        pol = _mk_policy_doc()
        await db.credit_policies.insert_one(dict(pol))
    if "approval_authority" not in pol:
        pol["approval_authority"] = DEFAULT_POLICY["approval_authority"]
    return pol


ROLE_PERMS = {
    "admin": {"policy_edit", "approve", "reject", "escalate", "review", "analyse"},
    "credit_manager": {"policy_edit", "approve", "reject", "escalate", "review", "analyse"},
    "credit_analyst": {"review", "analyse"},
    "viewer": set(),
}


def authority_for_amount(amount: float, policy: dict) -> str:
    slabs = sorted(policy.get("approval_authority", []), key=lambda s: s["max"])
    for s in slabs:
        if amount <= s["max"]:
            return s.get("label", s["role"])
    return "Senior Credit / Admin"


def user_max_authority(role: str, policy: dict) -> float:
    vals = [s["max"] for s in policy.get("approval_authority", []) if s["role"] == role]
    if vals:
        return max(vals)
    return 1000000000 if role == "admin" else 0


def emi_amount(principal: float, annual_roi: float, months: int) -> float:
    if principal <= 0 or months <= 0:
        return 0.0
    r = annual_roi / 12 / 100
    if r == 0:
        return principal / months
    f = (1 + r) ** months
    return principal * r * f / (f - 1)


def principal_from_emi(emi: float, annual_roi: float, months: int) -> float:
    if emi <= 0 or months <= 0:
        return 0.0
    r = annual_roi / 12 / 100
    if r == 0:
        return emi * months
    f = (1 + r) ** months
    return emi * (f - 1) / (r * f)


def risk_grade_and_roi(pd_score: float, policy: dict):
    for slab in policy["roi_rules"]:
        if pd_score <= slab["pd_max"]:
            return slab["grade"], slab["roi"]
    last = policy["roi_rules"][-1]
    return last["grade"], last["roi"]


def _ev_conf(seed: int, salt: int) -> float:
    return round(0.90 + ((seed >> salt) % 9) / 100.0, 2)


def _ev_page(seed: int, salt: int, mx: int = 6) -> str:
    return f"p.{1 + ((seed >> salt) % mx)}"


def build_evidence(f: dict, seed: int, conf_override: float = None) -> dict:
    """Deterministic source-attribution + calculation trace for each financial figure."""
    def L(v):
        return f"₹{lakh(v)} L"

    out = {
        "annual_turnover": {
            "label": "Annual Turnover", "formula": "Avg monthly credits × 12 × 0.94 (GST-adjusted)",
            "calculation": f"{L(f['avg_monthly_credits'])} × 12 × 0.94 = {L(f['annual_turnover'])}",
            "inputs": [{"label": "Avg monthly credits", "value": L(f['avg_monthly_credits'])}, {"label": "GST adjustment", "value": "0.94"}],
            "source": "GST Returns (GSTR-3B)", "page": _ev_page(seed, 1), "confidence": _ev_conf(seed, 1)},
        "avg_monthly_credits": {
            "label": "Avg Monthly Credits", "formula": "Total credits ÷ months in statement",
            "calculation": f"Averaged over {f['banking_history_months']}-month banking window = {L(f['avg_monthly_credits'])}",
            "inputs": [{"label": "Banking window", "value": f"{f['banking_history_months']} months"}],
            "source": "Bank Statement", "page": _ev_page(seed, 2), "confidence": _ev_conf(seed, 2)},
        "avg_monthly_balance": {
            "label": "Avg Monthly Balance", "formula": "Sum of daily closing balances ÷ days",
            "calculation": f"Average maintained balance = {L(f['avg_monthly_balance'])}",
            "inputs": [{"label": "Basis", "value": "Daily closing balance"}],
            "source": "Bank Statement", "page": _ev_page(seed, 3), "confidence": _ev_conf(seed, 3)},
        "net_cash_flow": {
            "label": "Net Cash Flow", "formula": "Avg monthly credits − Monthly obligations",
            "calculation": f"{L(f['avg_monthly_credits'])} − {L(f['monthly_obligations'])} = {L(f['net_cash_flow'])}",
            "inputs": [{"label": "Avg monthly credits", "value": L(f['avg_monthly_credits'])}, {"label": "Monthly obligations", "value": L(f['monthly_obligations'])}],
            "source": "Bank Statement + Existing Loan Statement", "page": _ev_page(seed, 4), "confidence": _ev_conf(seed, 4)},
        "monthly_obligations": {
            "label": "Monthly Obligations", "formula": "Existing EMIs + recurring debits",
            "calculation": f"Aggregated obligations = {L(f['monthly_obligations'])}",
            "inputs": [{"label": "Existing EMI", "value": f"₹{f['existing_emi']:,}"}],
            "source": "Existing Loan Statement", "page": _ev_page(seed, 5), "confidence": _ev_conf(seed, 5)},
        "existing_emi": {
            "label": "Existing EMI", "formula": "Sum of active loan instalments",
            "calculation": f"Detected active EMI debits = ₹{f['existing_emi']:,}/month",
            "inputs": [{"label": "Basis", "value": "Recurring loan debits"}],
            "source": "Existing Loan Statement", "page": _ev_page(seed, 6), "confidence": _ev_conf(seed, 6)},
        "foir_before": {
            "label": "FOIR (pre-loan)", "formula": "Monthly obligations ÷ Avg monthly credits",
            "calculation": f"{L(f['monthly_obligations'])} ÷ {L(f['avg_monthly_credits'])} = {round(f['foir_before']*100,1)}%",
            "inputs": [{"label": "Monthly obligations", "value": L(f['monthly_obligations'])}, {"label": "Avg monthly credits", "value": L(f['avg_monthly_credits'])}],
            "source": "Bank Statement + Existing Loan Statement", "page": _ev_page(seed, 7), "confidence": _ev_conf(seed, 7)},
        "dscr": {
            "label": "DSCR", "formula": "Net cash flow ÷ Existing EMI",
            "calculation": f"{L(f['net_cash_flow'])} ÷ ₹{f['existing_emi']:,} = {f['dscr']}x",
            "inputs": [{"label": "Net cash flow", "value": L(f['net_cash_flow'])}, {"label": "Existing EMI", "value": f"₹{f['existing_emi']:,}"}],
            "source": "Bank Statement + Existing Loan Statement", "page": _ev_page(seed, 8), "confidence": _ev_conf(seed, 8)},
        "banking_history_months": {
            "label": "Banking History", "formula": "Span of statement period",
            "calculation": f"{f['banking_history_months']} months of continuous statements reviewed",
            "inputs": [{"label": "Statement span", "value": f"{f['banking_history_months']} months"}],
            "source": "Bank Statement", "page": _ev_page(seed, 9), "confidence": _ev_conf(seed, 9)},
        "business_vintage_months": {
            "label": "Business Vintage", "formula": "Months since business registration",
            "calculation": f"Registration date to review date = {f['business_vintage_months']} months",
            "inputs": [{"label": "Vintage", "value": f"{f['business_vintage_months']} months"}],
            "source": "GST Registration / ITR", "page": _ev_page(seed, 10), "confidence": _ev_conf(seed, 10)},
        "cibil": {
            "label": "CIBIL", "formula": "Bureau-reported consumer/commercial score",
            "calculation": f"Bureau score as pulled = {f['cibil']}",
            "inputs": [{"label": "Score", "value": str(f['cibil'])}],
            "source": "Credit Bureau Report", "page": _ev_page(seed, 11, 2), "confidence": _ev_conf(seed, 11)},
        "cheque_bounces": {
            "label": "Cheque Bounces", "formula": "Count of returned cheques in window",
            "calculation": f"{f['cheque_bounces']} cheque return(s) across {f['banking_history_months']} months",
            "inputs": [{"label": "Returns", "value": str(f['cheque_bounces'])}],
            "source": "Bank Statement", "page": _ev_page(seed, 12), "confidence": _ev_conf(seed, 12)},
        "nach_bounces": {
            "label": "NACH Bounces", "formula": "Count of failed NACH mandates in window",
            "calculation": f"{f['nach_bounces']} NACH return(s) across {f['banking_history_months']} months",
            "inputs": [{"label": "Returns", "value": str(f['nach_bounces'])}],
            "source": "Bank Statement", "page": _ev_page(seed, 13), "confidence": _ev_conf(seed, 13)},
    }
    if conf_override is not None:
        for v in out.values():
            v["confidence"] = round(float(conf_override), 2)
    return out


REQUIRED_DOC_MAP = {"Bank Statement": "bank_statement", "ITR": "itr", "GST Returns": "gst",
                    "GST": "gst", "Salary Slip": "salary_slip", "KYC": "kyc",
                    "CIBIL Report": "cibil", "Purchase Bills": "purchase_bills",
                    "Sales Bills": "sales_bills"}


def build_contradictions(banking_turnover: int, gst_turnover: int, itr_income: int, banking_income_annual: int) -> list:
    """Cross-source data-integrity checks (mock intelligence layer)."""
    out = []

    def variance(a, b):
        m = max(a, b, 1)
        return abs(a - b) / m

    v1 = variance(banking_turnover, gst_turnover)
    if v1 >= 0.20:
        out.append({
            "code": "CONTRA-TURNOVER",
            "label": "GST turnover vs banking turnover mismatch",
            "detail": f"GST-declared turnover ₹{lakh(gst_turnover)} L differs from banking-derived turnover ₹{lakh(banking_turnover)} L by {round(v1*100)}%.",
            "severity": "critical" if v1 >= 0.35 else "review",
            "variance_pct": round(v1 * 100, 1),
            "sources": ["GST Returns", "Bank Statement"],
            "values": [{"label": "GST turnover", "value": f"₹{lakh(gst_turnover)} L"},
                       {"label": "Banking turnover", "value": f"₹{lakh(banking_turnover)} L"}],
        })
    v2 = variance(banking_income_annual, itr_income)
    if v2 >= 0.20:
        out.append({
            "code": "CONTRA-INCOME",
            "label": "ITR income vs banking credits mismatch",
            "detail": f"ITR-declared annual income ₹{lakh(itr_income)} L differs from banking annual credits ₹{lakh(banking_income_annual)} L by {round(v2*100)}%.",
            "severity": "critical" if v2 >= 0.40 else "review",
            "variance_pct": round(v2 * 100, 1),
            "sources": ["ITR", "Bank Statement"],
            "values": [{"label": "ITR income", "value": f"₹{lakh(itr_income)} L"},
                       {"label": "Banking credits", "value": f"₹{lakh(banking_income_annual)} L"}],
        })
    return out


def evaluate_document_readiness(documents: list, policy: dict) -> dict:
    """Which required documents are present; blocks the decision when a mandatory one is missing."""
    present = {d.get("doc_type") for d in documents}
    required = policy.get("required_documents", [])
    mandatory = policy.get("mandatory_documents", [])
    checklist = []
    for label in required:
        dtype = REQUIRED_DOC_MAP.get(label)
        is_mand = label in mandatory
        if dtype is None:
            checklist.append({"label": label, "present": True, "verifiable": False, "mandatory": is_mand})
        else:
            checklist.append({"label": label, "present": dtype in present, "verifiable": True,
                              "mandatory": is_mand, "doc_type": dtype})
    missing = [c["label"] for c in checklist if c["mandatory"] and not c["present"]]
    missing_optional = [c["label"] for c in checklist if not c["mandatory"] and not c["present"]]
    return {"checklist": checklist, "missing": missing, "missing_optional": missing_optional,
            "ready": len(missing) == 0, "required_count": len(required),
            "present_count": len([c for c in checklist if c["present"]])}


def extract_pdf_text(path: str) -> str:
    """Fallback: extract embedded text from a PDF with pypdf (used only if OCR is unavailable)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        parts = [(page.extract_text() or "") for page in reader.pages[:15]]
        return "\n".join(parts).strip()
    except Exception as e:
        logger.warning(f"PDF text extraction failed for {path}: {e}")
        return ""


async def mistral_ocr_text(path: str) -> str:
    """Extract document text/markdown via Mistral OCR (handles scanned PDFs & images)."""
    if not MISTRAL_API_KEY:
        return ""
    try:
        import base64
        import httpx
        with open(path, "rb") as fh:
            data = fh.read()
        ext = os.path.splitext(path)[1].lower()
        encoded = base64.b64encode(data).decode("ascii")
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".avif"):
            ct = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "avif": "image/avif"}[ext.lstrip(".")]
            document = {"type": "image_url", "image_url": f"data:{ct};base64,{encoded}"}
        else:
            document = {"type": "document_url", "document_url": f"data:application/pdf;base64,{encoded}"}
        payload = {"model": OCR_MODEL, "document": document, "include_image_base64": False}
        headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
        timeout = httpx.Timeout(connect=10.0, read=180.0, write=180.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post("https://api.mistral.ai/v1/ocr", json=payload, headers=headers)
        if resp.is_error:
            logger.warning(f"Mistral OCR HTTP {resp.status_code} for {os.path.basename(path)}")
            return ""
        pages = resp.json().get("pages", [])
        return "\n\n".join(p.get("markdown", "") for p in pages).strip()
    except Exception as e:
        logger.warning(f"Mistral OCR failed for {path}: {e}")
        return ""


async def extract_document_text(path: str) -> str:
    """Primary = Mistral OCR; fall back to embedded-text extraction if OCR returns nothing."""
    text = await mistral_ocr_text(path)
    if text:
        return text
    return extract_pdf_text(path)


async def llm_extract_financials(application: dict, docs_text: list) -> Optional[dict]:
    """Use the LLM to extract structured underwriting financials + deep CIBIL & bank-statement analysis."""
    import json as _json
    combined = "\n\n".join(f"=== {d['label']} ===\n{d['text'][:9000]}" for d in docs_text if d.get("text"))
    if not combined.strip():
        return None
    schema = (
        '{'
        '"avg_monthly_credits":int,"monthly_obligations":int,"existing_emi":int,'
        '"avg_monthly_balance":int,"banking_turnover":int,"gst_turnover":int,'
        '"itr_declared_income":int,"annual_turnover":int,"business_vintage_months":int,'
        '"cibil":int,"cheque_bounces":int,"nach_bounces":int,"banking_history_months":int,'
        '"industry":str,"confidence":float,'
        '"cibil_report":{"score":int,"total_active_loans":int,"total_sanctioned":int,'
        '"total_outstanding":int,"total_overdue":int,"max_dpd":int,"enquiries_6m":int,'
        '"summary":str,"tradelines":[{"lender":str,"loan_type":str,"sanctioned":int,'
        '"outstanding":int,"emi":int,"dpd":int,"status":str,"opened":str}]},'
        '"banking_analysis":{"avg_monthly_balance":int,"total_emi_count":int,'
        '"total_emi_outflow":int,"emis":[{"beneficiary":str,"amount":int,"frequency":str}],'
        '"top_credit_sources":[{"party":str,"total_amount":int,"txn_count":int}],'
        '"top_debit_destinations":[{"party":str,"total_amount":int,"txn_count":int}],'
        '"anomalies":[{"type":str,"description":str,"amount":int,"severity":str}],'
        '"monthly_breakdown":[{"month":str,"credits":int,"debits":int,"closing_balance":int}],'
        '"cash_flow_pattern":str,"inflow_outflow_ratio":float}'
        '}'
    )
    prompt = (
        "You are a senior credit-underwriting analyst for an Indian NBFC. Read the borrower documents below "
        "(synthetic demo data) and extract a thorough, structured credit analysis. Money values in INR as plain "
        "integers (no commas/symbols). If a field is absent, estimate conservatively and lower the confidence.\n\n"
        "FROM THE CIBIL / CREDIT BUREAU REPORT populate cibil_report: the score, every loan/tradeline (lender, "
        "loan_type, sanctioned amount, current outstanding, EMI, worst DPD in days, status like Active/Closed/"
        "Overdue, and opened date), the total number of active loans, total sanctioned, total outstanding, total "
        "overdue amount, worst max_dpd across all accounts, number of hard enquiries in last 6 months, and a "
        "one-line summary of the repayment track record.\n\n"
        "FROM THE BANK STATEMENT populate banking_analysis: average monthly balance, how many distinct EMIs/loan "
        "instalments the customer pays each month (total_emi_count) and their total monthly outflow, the list of "
        "those EMIs (beneficiary, amount, frequency), the top credit sources (who pays money IN, with totals and "
        "counts), the top debit destinations (where money goes OUT), the overall cash_flow_pattern in one sentence, "
        "and the inflow_outflow_ratio. Also populate monthly_breakdown: for EACH month present in the statement, "
        "give the month label and that month's total credits, total debits and closing balance. "
        "CRITICALLY, flag any ANOMALOUS or high-risk transactions in 'anomalies' — "
        "e.g. online rummy/poker/betting/gambling/gaming apps (Rummy, Dream11, betting sites), frequent large cash "
        "withdrawals, round-tripping, unexplained large one-off credits, crypto, or other unwanted/red-flag activity. "
        "For each anomaly give type, a short description, the amount involved, and severity (critical/review/warning).\n\n"
        "banking_turnover = annualised total bank credits; gst_turnover = GST-declared turnover; "
        "itr_declared_income = ITR annual income; confidence is 0-1 overall extraction quality.\n\n"
        f"Return ONLY minified JSON matching this schema exactly: {schema}\n\nDOCUMENTS:\n{combined}"
    )
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"extract-{application['id']}",
                       system_message="You extract structured financial data and deep credit analysis from documents and reply with strict minified JSON only.").with_model("openai", ANALYSIS_MODEL)
        resp = await chat.send_message(UserMessage(text=prompt))
        text = (resp if isinstance(resp, str) else str(resp)).strip()
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        data = _json.loads(m.group(0))
        conf = data.pop("confidence", 0.85)
        cibil_report = data.pop("cibil_report", None)
        banking_analysis = data.pop("banking_analysis", None)
        out = {}
        for k, v in data.items():
            if k == "industry":
                out[k] = str(v)
            else:
                try:
                    out[k] = int(round(float(v)))
                except (TypeError, ValueError):
                    continue
        if not out.get("avg_monthly_credits"):
            return None
        if isinstance(cibil_report, dict):
            out["cibil_report"] = cibil_report
        if isinstance(banking_analysis, dict):
            out["banking_analysis"] = banking_analysis
        out["_confidence"] = round(float(conf), 2)
        out["_source"] = "ai"
        return out
    except Exception as e:
        logger.warning(f"LLM financial extraction failed: {e}")
        return None


async def refresh_extraction(app_id: str) -> Optional[dict]:
    """Read all uploaded PDFs for an application and (re)extract financials via the LLM."""
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        return None
    docs = await db.documents.find({"application_id": app_id}).to_list(100)
    texts = []
    for d in docs:
        p = d.get("file_path")
        if p and os.path.exists(p):
            t = await extract_document_text(p)
            if t:
                texts.append({"label": DOC_TYPE_LABELS.get(d.get("doc_type"), d.get("doc_type")), "text": t})
    if not texts:
        return None
    ef = await llm_extract_financials(application, texts)
    if ef:
        await db.applications.update_one({"id": app_id}, {"$set": {"extracted_financials": ef}})
    return ef


CIBIL_DPD_TOLERANCE = 7  # days; up to this is treated as clean


def classify_cibil(score, max_dpd) -> dict:
    """Rate a bureau profile by score + worst DPD. DPD is the dominant gate.
    Rules: DPD>=90 -> Danger/Bad; 7<DPD<90 -> Not a Good Customer; DPD<=7 (or none) ->
    score>=750 Excellent, score>=650 Good, else Average."""
    score = int(score or 0)
    dpd = max_dpd
    if dpd is not None and dpd >= 90:
        return {"rating": "Danger / Bad Profile", "severity": "critical",
                "reason": f"Worst DPD {dpd} days (>=90) indicates serious default risk."}
    if dpd is not None and dpd > CIBIL_DPD_TOLERANCE:
        return {"rating": "Not a Good Customer", "severity": "review",
                "reason": f"Worst DPD {dpd} days exceeds the {CIBIL_DPD_TOLERANCE}-day tolerance."}
    clean = f"clean repayment (max DPD {dpd if dpd is not None else 0}d, within {CIBIL_DPD_TOLERANCE}d tolerance)"
    if score >= 750:
        return {"rating": "Excellent", "severity": "excellent", "reason": f"CIBIL {score} (>=750) with {clean}."}
    if score >= 650:
        return {"rating": "Good", "severity": "good", "reason": f"CIBIL {score} (>=650) with {clean}."}
    return {"rating": "Average", "severity": "average", "reason": f"CIBIL {score} (<650) is below the good-customer threshold."}


def compute_risk_radar(pd_score: float, cibil_report: dict, banking_analysis: dict, fin: dict) -> dict:
    """Composite risk band combining bureau health, repayment track, banking conduct and cash flow (0-100, higher = safer)."""
    def clamp(x):
        return int(max(5, min(100, round(x))))
    cr = cibil_report or {}
    ba = banking_analysis or {}
    score = cr.get("score") or fin.get("cibil") or 0
    if score >= 780: bureau = 92
    elif score >= 750: bureau = 82
    elif score >= 720: bureau = 72
    elif score >= 700: bureau = 62
    elif score >= 680: bureau = 50
    elif score >= 650: bureau = 38
    else: bureau = 22
    mdpd = cr.get("max_dpd")
    overdue = cr.get("total_overdue") or 0
    if mdpd is None: repay = 70
    elif mdpd == 0: repay = 95
    elif mdpd < 15: repay = 80
    elif mdpd < 30: repay = 62
    elif mdpd < 60: repay = 45
    elif mdpd < 90: repay = 28
    else: repay = 15
    if overdue and overdue > 0:
        repay = max(10, repay - 12)
    conduct = 95
    anomalies = ba.get("anomalies") or []
    for a in anomalies:
        sev = (a.get("severity") or "review").lower()
        conduct -= 28 if sev == "critical" else 14 if sev == "review" else 7
    conduct -= min(fin.get("cheque_bounces", 0), 5) * 4 + min(fin.get("nach_bounces", 0), 5) * 3
    conduct = clamp(conduct)
    dscr = fin.get("dscr", 0) or 0
    foir = fin.get("foir_before", 1) or 0
    net = fin.get("net_cash_flow", 0) or 0
    cf = 50
    cf += 20 if dscr >= 1.8 else 8 if dscr >= 1.3 else -10
    cf += 18 if foir <= 0.4 else 6 if foir <= 0.55 else -12
    cf += 10 if net > 0 else -20
    cf = clamp(cf)
    bureau, repay = clamp(bureau), clamp(repay)
    overall = clamp(bureau * 0.25 + repay * 0.30 + conduct * 0.25 + cf * 0.20)
    band = "Low" if overall >= 70 else "Moderate" if overall >= 45 else "High"
    factors = [
        {"label": "Bureau Health", "score": bureau, "note": f"CIBIL {score}" if score else "No bureau score"},
        {"label": "Repayment Track", "score": repay, "note": (f"Max DPD {mdpd}d" if mdpd is not None else "No DPD data")},
        {"label": "Banking Conduct", "score": conduct, "note": f"{len(anomalies)} anomaly flag(s)"},
        {"label": "Cash Flow", "score": cf, "note": f"DSCR {dscr}x · FOIR {round(foir*100)}%"},
    ]
    return {"overall": overall, "band": band, "factors": factors}


def _pd_from_financials(fin: dict) -> float:
    """Transparent, explainable PD from real metrics (not a hardcoded lookup)."""
    score = 0.05
    score += min(max(fin["foir_before"], 0.0), 1.0) * 0.28
    score += max(0.0, (760 - fin["cibil"])) / 760 * 0.30
    score += max(0.0, (1.8 - min(fin["dscr"], 3.0))) * 0.06
    score += max(0.0, (36 - fin["business_vintage_months"])) / 36 * 0.12
    score += min(fin["cheque_bounces"], 6) * 0.025 + min(fin["nach_bounces"], 6) * 0.02
    if fin["net_cash_flow"] <= 0:
        score += 0.15
    bt = max(fin.get("banking_turnover", 0), 1)
    gt = fin.get("gst_turnover", bt)
    score += min(abs(bt - gt) / bt, 0.6) * 0.10
    return round(max(0.03, min(0.80, score)), 3)


def _raw_financials(application: dict, seed: int) -> dict:
    """Extracted (AI) financials when available, else a deterministic estimate for docs-less demo rows."""
    ef = application.get("extracted_financials")
    if ef and ef.get("avg_monthly_credits"):
        income = int(ef["avg_monthly_credits"])
        obligations = int(ef.get("monthly_obligations") or round(income * 0.35))
        existing_emi = int(ef.get("existing_emi") or round(obligations * 0.55))
        avg_balance = int(ef.get("avg_monthly_balance") or round(income * 0.5))
        annual_credits = int(ef.get("banking_turnover") or income * 12)
        banking_turnover = annual_credits
        gst_turnover = int(ef.get("gst_turnover") or annual_credits)
        itr_declared_income = int(ef.get("itr_declared_income") or annual_credits)
        revenue = int(ef.get("annual_turnover") or gst_turnover)
        vintage = int(ef.get("business_vintage_months") or 36)
        cibil = int(ef.get("cibil") or 700)
        cheque_bounces = int(ef.get("cheque_bounces") or 0)
        nach_bounces = int(ef.get("nach_bounces") or 0)
        banking_months = int(ef.get("banking_history_months") or 12)
        industry = ef.get("industry") or "Not specified"
        source, confidence = "ai", float(ef.get("_confidence") or 0.9)
    else:
        prof = KNOWN_PROFILES.get(application["borrower_name"].strip().lower(), {})
        income = prof.get("income", int(round(application["loan_amount"] * (0.34 + (seed % 8) / 100.0))))
        obligations = prof.get("obligations", int(round(income * (0.30 + (seed % 15) / 100.0))))
        existing_emi = int(round(obligations * 0.55))
        avg_balance = int(round(income * (0.45 + (seed % 20) / 100)))
        annual_credits = income * 12
        banking_turnover = annual_credits
        gst_turnover = int(round(banking_turnover * round(1 - (seed % 30) / 100.0, 2)))
        itr_declared_income = int(round(annual_credits * round(1 - ((seed >> 5) % 26) / 100.0, 2)))
        revenue = int(round(annual_credits * 0.94))
        vintage = prof.get("vintage", 24 + (seed % 96))
        cibil = prof.get("cibil", 640 + (seed % 160))
        cheque_bounces = prof.get("cheque_bounces", seed % 4)
        nach_bounces = prof.get("nach_bounces", seed % 3)
        banking_months = 12
        industry = prof.get("industry", "Manufacturing")
        source, confidence = "estimate", None
    net = income - obligations
    dscr = round(net / existing_emi, 2) if existing_emi else 2.5
    foir_before = round(obligations / income, 3) if income else 0
    return {
        "avg_monthly_credits": income, "monthly_obligations": obligations, "existing_emi": existing_emi,
        "avg_monthly_balance": avg_balance, "annual_credits": annual_credits, "banking_turnover": banking_turnover,
        "gst_turnover": gst_turnover, "itr_declared_income": itr_declared_income, "annual_turnover": revenue,
        "revenue": revenue, "business_vintage_months": vintage, "cibil": cibil, "cheque_bounces": cheque_bounces,
        "nach_bounces": nach_bounces, "banking_history_months": banking_months, "net_cash_flow": net,
        "dscr": dscr, "foir_before": foir_before, "industry": industry,
        "_source": source, "_confidence": confidence,
    }


def credit_brain(application: dict) -> dict:
    """Derive structured financial evidence + signals from AI-extracted (or estimated) data."""
    seed = _seed_int(application["borrower_name"], application["loan_amount"])
    r = _raw_financials(application, seed)
    income, obligations, net = r["avg_monthly_credits"], r["monthly_obligations"], r["net_cash_flow"]
    existing_emi, dscr, foir_before = r["existing_emi"], r["dscr"], r["foir_before"]
    cheque_bounces, nach_bounces = r["cheque_bounces"], r["nach_bounces"]
    vintage, cibil, banking_months = r["business_vintage_months"], r["cibil"], r["banking_history_months"]
    banking_turnover, gst_turnover, itr_declared_income = r["banking_turnover"], r["gst_turnover"], r["itr_declared_income"]
    revenue, avg_balance, annual_credits = r["annual_turnover"], r["avg_monthly_balance"], r["annual_credits"]

    pd_score = _pd_from_financials(r)
    contradictions = build_contradictions(banking_turnover, gst_turnover, itr_declared_income, annual_credits)

    months = ["Mar", "Apr", "May", "Jun", "Jul", "Aug"]
    trend = [{"month": m, "value": int(round(net * (1 + ((seed >> (i * 3)) % 12 - 6) / 100.0)))} for i, m in enumerate(months)]

    positive, risk = [], []
    if net > 0 and dscr >= 1.5:
        positive.append({"label": "Strong operating cash flow", "evidence": f"Average monthly net cash flow of ₹{lakh(net)} lakh.", "source": "Bank Statement", "severity": "info"})
    if dscr >= 1.5:
        positive.append({"label": "Healthy debt service capacity", "evidence": f"DSCR of {dscr}x against existing obligations.", "source": "Bank Statement + Existing Loan Statement", "severity": "info"})
    if cheque_bounces <= 1:
        positive.append({"label": "Stable banking behaviour", "evidence": f"{banking_months}-month banking history with {cheque_bounces} cheque return(s).", "source": "Bank Statement", "severity": "info"})
    if cheque_bounces > 1:
        risk.append({"label": "Recent repayment irregularity", "evidence": f"{cheque_bounces} cheque returns detected in the reviewed period.", "source": "Bank Statement", "severity": "review"})
    if foir_before > 0.45:
        risk.append({"label": "Elevated existing obligations", "evidence": f"Pre-loan FOIR at {round(foir_before*100,1)}%.", "source": "Existing Loan Statement", "severity": "warning"})
    if vintage < 24:
        risk.append({"label": "Limited business vintage", "evidence": f"Business vintage of {vintage} months.", "source": "GST / ITR", "severity": "critical"})
    if cibil < 680:
        risk.append({"label": "Sub-threshold bureau score", "evidence": f"Bureau score of {cibil}.", "source": "Credit Bureau", "severity": "critical"})

    ef = application.get("extracted_financials") or {}
    cibil_report = ef.get("cibil_report")
    banking_analysis = ef.get("banking_analysis")
    if isinstance(cibil_report, dict):
        mdpd = int(cibil_report.get("max_dpd") or 0)
        overdue = int(cibil_report.get("total_overdue") or 0)
        if mdpd >= 90:
            risk.append({"label": "Severe delinquency on bureau", "evidence": f"Worst DPD of {mdpd} days across existing tradelines.", "source": "CIBIL Report", "severity": "critical"})
        elif mdpd >= 30:
            risk.append({"label": "Recent bureau delinquency", "evidence": f"Worst DPD of {mdpd} days reported.", "source": "CIBIL Report", "severity": "review"})
        if overdue > 0:
            risk.append({"label": "Outstanding overdue on bureau", "evidence": f"₹{lakh(overdue)} L reported overdue across active loans.", "source": "CIBIL Report", "severity": "review"})
    if isinstance(banking_analysis, dict):
        for a in (banking_analysis.get("anomalies") or []):
            sev = (a.get("severity") or "review").lower()
            if sev not in ("critical", "review", "warning"):
                sev = "review"
            amt = a.get("amount")
            ev_txt = a.get("description") or a.get("type") or "Anomalous activity detected"
            if amt:
                ev_txt = f"{ev_txt} (≈₹{lakh(int(amt))} L)"
            risk.append({"label": f"Anomalous transactions: {a.get('type', 'flagged activity')}", "evidence": ev_txt, "source": "Bank Statement", "severity": sev})

    fin = {
        "revenue": revenue, "annual_credits": annual_credits, "avg_monthly_credits": income,
        "avg_monthly_balance": avg_balance, "existing_emi": existing_emi,
        "monthly_obligations": obligations, "net_cash_flow": net, "foir_before": foir_before,
        "dscr": dscr, "banking_history_months": banking_months, "cheque_bounces": cheque_bounces,
        "nach_bounces": nach_bounces, "business_vintage_months": vintage, "cibil": cibil,
        "annual_turnover": revenue, "industry": r["industry"],
        "gst_turnover": gst_turnover, "banking_turnover": banking_turnover,
        "itr_declared_income": itr_declared_income,
    }
    return {
        "pd_score": pd_score,
        "financials": fin,
        "cash_flow_trend": trend,
        "positive_signals": positive,
        "risk_signals": risk,
        "contradictions": contradictions,
        "cibil_report": cibil_report,
        "banking_analysis": banking_analysis,
        "risk_radar": compute_risk_radar(pd_score, cibil_report, banking_analysis, fin),
        "cibil_rating": classify_cibil((cibil_report or {}).get("score") or cibil, (cibil_report or {}).get("max_dpd")),
        "extraction_source": r["_source"],
        "extraction_confidence": r["_confidence"],
        "evidence": build_evidence(fin, seed, r["_confidence"]),
    }



def evaluate_policy(brain: dict, policy: dict, post_loan_foir: float) -> dict:
    f = brain["financials"]
    r = policy["rules"]

    def rule(rid, name, metric, actual, op, threshold, severity, unit=""):
        if op == ">=":
            ok = actual >= threshold
        elif op == "<=":
            ok = actual <= threshold
        elif op == ">":
            ok = actual > threshold
        else:
            ok = actual == threshold
        return {"id": rid, "name": name, "metric": metric, "actual": actual, "operator": op,
                "threshold": threshold, "unit": unit, "result": "PASS" if ok else "FAIL",
                "impact": "Positive" if ok else "Negative", "severity": severity}

    rules = [
        rule("POL-BANK-001", "Minimum average monthly credits", "Avg monthly credits", f["avg_monthly_credits"], ">=", r["min_avg_credits"], "warning", "inr"),
        rule("POL-FOIR-004", "Maximum post-loan FOIR", "Post-loan FOIR", round(post_loan_foir, 3), "<=", r["max_foir"], "critical", "pct"),
        rule("POL-DSCR-002", "Minimum DSCR", "DSCR", f["dscr"], ">=", r["min_dscr"], "review", "x"),
        rule("POL-ELIG-003", "Minimum business vintage", "Business vintage", f["business_vintage_months"], ">=", r["min_vintage_months"], "critical", "months"),
        rule("POL-BUREAU-007", "Minimum bureau score", "CIBIL", f["cibil"], ">=", r["min_cibil"], "critical", "score"),
        rule("POL-BANK-005", "Maximum cheque returns", "Cheque bounces", f["cheque_bounces"], "<=", r["max_cheque_bounces"], "review", "count"),
        rule("POL-FIN-002", "Minimum annual turnover", "Annual turnover", f["annual_turnover"], ">=", r["min_annual_turnover"], "warning", "inr"),
        rule("POL-CF-001", "Positive net cash flow", "Net cash flow", f["net_cash_flow"], ">", r["min_net_cashflow"], "critical", "inr"),
    ]
    passed = [x for x in rules if x["result"] == "PASS"]
    failed = [x for x in rules if x["result"] == "FAIL"]
    crit_fail = [x for x in failed if x["severity"] == "critical"]
    review_fail = [x for x in failed if x["severity"] in ("review", "warning")]
    overall = "FAIL" if crit_fail else ("REVIEW" if review_fail else "PASS")
    return {
        "policy_version": policy["version"], "policy_name": policy["policy_name"],
        "rules": rules, "rules_evaluated": len(rules), "passed": len(passed),
        "warnings": len([x for x in rules if x["severity"] == "warning" and x["result"] == "FAIL"]),
        "review": len([x for x in rules if x["severity"] == "review" and x["result"] == "FAIL"]),
        "critical_failures": len(crit_fail), "overall": overall,
        "triggered": [x["id"] for x in failed],
    }


def compute_full_decision(application: dict, policy: dict, force_known: bool = True) -> dict:
    brain = credit_brain(application)
    f = brain["financials"]
    pd_score = brain["pd_score"]
    requested = application["loan_amount"]
    grade, roi = risk_grade_and_roi(pd_score, policy)
    tenure = policy["tenure_rules"].get(grade, 36)

    lar = policy["loan_amount_rules"]
    rules = policy["rules"]
    existing_emi = f["existing_emi"]
    income = f["avg_monthly_credits"]

    affordable_emi = max(0.0, income * rules["max_foir"] - existing_emi)
    cashflow_eligible = principal_from_emi(affordable_emi, roi, tenure)
    policy_max = min(lar["absolute_max"], f["annual_turnover"] * lar["turnover_multiple"])
    collateral_value = requested * 1.4
    collateral_eligible = collateral_value / lar["collateral_coverage"]
    final_eligible = max(0.0, min(policy_max, cashflow_eligible, collateral_eligible))
    final_eligible = round(final_eligible / 50000) * 50000  # round to 50k
    recommended = min(requested, final_eligible)

    new_emi = emi_amount(recommended, roi, tenure)
    post_loan_foir = (existing_emi + new_emi) / income if income else 0
    total_repayment = new_emi * tenure
    total_interest = total_repayment - recommended
    processing_fee = recommended * policy["processing_fee_pct"] / 100
    net_disbursement = recommended - processing_fee

    policy_eval = evaluate_policy(brain, policy, post_loan_foir)

    # decision
    key = application["borrower_name"].strip().lower()
    dm = policy["decision_matrix"]
    if policy_eval["critical_failures"] > 0 or pd_score > dm["review_pd_max"] or recommended <= 0:
        decision = "reject"
    elif policy_eval["overall"] == "REVIEW" or pd_score > dm["approve_pd_max"]:
        decision = "review"
    else:
        decision = "approve"
    crit_contra = [c for c in brain.get("contradictions", []) if c["severity"] == "critical"]
    crit_risk = [s for s in brain.get("risk_signals", []) if s.get("severity") == "critical"]
    if (crit_contra or crit_risk) and decision == "approve":
        decision = "review"

    if decision == "approve":
        codes = ["STRONG_CF", "GOOD_COVERAGE", "STABLE_BANKING"]
    elif decision == "review":
        codes = ["HIGH_UTIL", "REPAY_IRREG", "MODERATE_CF"]
    else:
        codes = ["WEAK_CF", "HIGH_LEVERAGE", "NEG_TREND"]
    reason_codes = [_reason(c) for c in codes]
    cash_flow_summary = {
        "income": f["avg_monthly_credits"], "obligations": f["monthly_obligations"],
        "net": f["net_cash_flow"],
        "coverage": round(f["net_cash_flow"] / f["monthly_obligations"], 2) if f["monthly_obligations"] else 0,
    }
    cashflow_val = round(cashflow_eligible / 50000) * 50000
    collateral_val = round(collateral_eligible / 50000) * 50000
    _ceilings = {"Policy maximum": round(policy_max), "Cash-flow eligibility": cashflow_val, "Collateral eligibility": collateral_val}
    _binding_label = min(_ceilings, key=_ceilings.get)
    eligibility_waterfall = [
        {"label": "Requested amount", "value": requested, "kind": "input",
         "formula": "Amount applied for by the borrower",
         "calculation": f"₹{lakh(requested)} L requested for {LOAN_TYPE_LABEL.get(application['loan_type'], application['loan_type'])}",
         "inputs": [{"label": "Requested", "value": f"₹{lakh(requested)} L"}]},
        {"label": "Policy maximum", "value": round(policy_max), "kind": "ceiling",
         "binding": _binding_label == "Policy maximum",
         "formula": "min(product absolute cap, annual turnover × turnover multiple)",
         "calculation": f"min(₹{lakh(lar['absolute_max'])} L, ₹{lakh(f['annual_turnover'])} L × {lar['turnover_multiple']}) = min(₹{lakh(lar['absolute_max'])} L, ₹{lakh(f['annual_turnover'] * lar['turnover_multiple'])} L) = ₹{lakh(policy_max)} L",
         "inputs": [{"label": "Absolute cap", "value": f"₹{lakh(lar['absolute_max'])} L"},
                    {"label": "Annual turnover", "value": f"₹{lakh(f['annual_turnover'])} L"},
                    {"label": "Turnover multiple", "value": f"{lar['turnover_multiple']}×"}]},
        {"label": "Cash-flow eligibility", "value": cashflow_val, "kind": "ceiling",
         "binding": _binding_label == "Cash-flow eligibility",
         "formula": "loan supportable by (income × max FOIR − existing EMI) at offered ROI/tenure",
         "calculation": f"Affordable EMI = ₹{lakh(income)} L × {round(rules['max_foir']*100)}% − ₹{existing_emi:,} = ₹{affordable_emi:,.0f}/mo → supports ≈ ₹{lakh(cashflow_val)} L over {tenure} mo @ {roi}%",
         "inputs": [{"label": "Monthly income", "value": f"₹{lakh(income)} L"},
                    {"label": "Max FOIR (policy)", "value": f"{round(rules['max_foir']*100)}%"},
                    {"label": "Existing EMI", "value": f"₹{existing_emi:,}"},
                    {"label": "Affordable new EMI", "value": f"₹{affordable_emi:,.0f}/mo"}]},
        {"label": "Collateral eligibility", "value": collateral_val, "kind": "ceiling",
         "binding": _binding_label == "Collateral eligibility",
         "formula": "collateral value ÷ required coverage ratio",
         "calculation": f"₹{lakh(collateral_value)} L ÷ {lar['collateral_coverage']} = ₹{lakh(collateral_val)} L",
         "inputs": [{"label": "Collateral value", "value": f"₹{lakh(collateral_value)} L"},
                    {"label": "Coverage ratio", "value": f"{lar['collateral_coverage']}×"}]},
        {"label": "Final eligible", "value": final_eligible, "kind": "result",
         "formula": "min(all ceilings above), rounded to ₹50k",
         "calculation": f"min(₹{lakh(round(policy_max))} L, ₹{lakh(cashflow_val)} L, ₹{lakh(collateral_val)} L) = ₹{lakh(final_eligible)} L  ·  binding: {_binding_label}",
         "binding_label": _binding_label,
         "inputs": [{"label": "Binding constraint", "value": _binding_label}]},
        {"label": "Recommended amount", "value": recommended, "kind": "final",
         "formula": "min(requested amount, final eligible)",
         "calculation": f"min(₹{lakh(requested)} L, ₹{lakh(final_eligible)} L) = ₹{lakh(recommended)} L",
         "inputs": [{"label": "Requested", "value": f"₹{lakh(requested)} L"},
                    {"label": "Final eligible", "value": f"₹{lakh(final_eligible)} L"}]},
    ]
    return {
        "pd_score": pd_score, "risk_grade": grade, "decision": decision,
        "requested_amount": requested, "eligible_amount": final_eligible,
        "recommended_amount": recommended if decision != "reject" else max(0, min(recommended, final_eligible)),
        "roi": roi, "tenure_months": tenure, "emi": round(new_emi),
        "total_interest": round(total_interest), "total_repayment": round(total_repayment),
        "processing_fee": round(processing_fee), "net_disbursement": round(net_disbursement),
        "existing_emi": existing_emi, "post_loan_foir": round(post_loan_foir, 3),
        "binding_constraint": _binding_label,
        "eligibility_waterfall": eligibility_waterfall,
        "reason_codes": reason_codes,
        "cash_flow_summary": cash_flow_summary,
        "positive_signals": brain["positive_signals"],
        "risk_signals": brain["risk_signals"],
        "credit_brain": brain,
        "policy_evaluation": policy_eval,
        "policy_version": policy["version"],
        "conditions": policy["conditions"],
        "tat_minutes": KNOWN_PROFILES.get(key, {}).get("tat", 12 + (_seed_int(application["borrower_name"], requested) % 12)),
        "model_version": "credit-brain-v1.0",
    }


def build_detailed_memo(application: dict, policy: dict, full: dict) -> str:
    b = full["credit_brain"]["financials"]
    d = full
    decU = d["decision"].upper()
    lt = LOAN_TYPE_LABEL.get(application["loan_type"], application["loan_type"])
    pe = d["policy_evaluation"]
    pos = "; ".join(s["label"] for s in d["positive_signals"]) or "None material."
    rsk = "; ".join(s["label"] for s in d["risk_signals"]) or "None material."
    S = []
    S.append("CREDIT APPRAISAL MEMORANDUM")
    S.append(f"Application: {application['reference']}  |  Prepared by: Credit Brain  |  Model: {d['model_version']}  |  Policy: {policy['policy_name']} {d['policy_version']}")

    S.append("1. EXECUTIVE SUMMARY\n"
             f"{application['borrower_name']} has been assessed for a {lt} facility. Against a requested amount of "
             f"₹{lakh(d['requested_amount'])} lakh, the configured Credit Policy and cash-flow analysis support a "
             f"recommended sanction of ₹{lakh(d['recommended_amount'])} lakh. The application carries a model probability "
             f"of default of {round(d['pd_score']*100,1)}% (Risk Grade {d['risk_grade']}), priced at {d['roi']:.2f}% p.a. "
             f"over {d['tenure_months']} months with an indicative EMI of ₹{d['emi']:,}. Overall policy outcome: {pe['overall']}. "
             f"Recommendation: {decU}.")

    S.append("2. BORROWER PROFILE\n"
             f"Legal name: {application['borrower_name']}. Industry: {b['industry']}. Business vintage: "
             f"{b['business_vintage_months']} months. Requested facility: ₹{lakh(d['requested_amount'])} lakh. The borrower "
             f"maintains a {b['banking_history_months']}-month banking relationship reviewed for this appraisal.")

    S.append("3. LOAN REQUEST\n"
             f"Requested amount ₹{lakh(d['requested_amount'])} lakh; product {lt}. Proposed amount ₹{lakh(d['recommended_amount'])} "
             f"lakh at {d['roi']:.2f}% p.a. for {d['tenure_months']} months, monthly repayment, proposed EMI ₹{d['emi']:,}.")

    S.append("5. FINANCIAL ANALYSIS\n"
             f"Estimated annual turnover ₹{lakh(b['annual_turnover'])} lakh with average monthly banking credits of "
             f"₹{lakh(b['avg_monthly_credits'])} lakh and average monthly balance of ₹{lakh(b['avg_monthly_balance'])} lakh. "
             f"Net monthly cash flow is approximately ₹{lakh(b['net_cash_flow'])} lakh after existing obligations of "
             f"₹{lakh(b['monthly_obligations'])} lakh.")

    S.append("6. BANKING ANALYSIS\n"
             f"Banking history of {b['banking_history_months']} months reviewed. Cheque returns: {b['cheque_bounces']}; "
             f"NACH returns: {b['nach_bounces']}. Banking credit trend is assessed as broadly stable across the reviewed period.")

    S.append("7. DEBT OBLIGATION ANALYSIS\n"
             f"Existing EMI obligations of ₹{b['existing_emi']:,} per month translate to a pre-loan FOIR of "
             f"{round(b['foir_before']*100,1)}%. Inclusive of the proposed EMI of ₹{d['emi']:,}, post-loan FOIR is estimated at "
             f"{round(d['post_loan_foir']*100,1)}% against the policy maximum of {round(policy['rules']['max_foir']*100)}%. "
             f"DSCR stands at {b['dscr']}x against the policy minimum of {policy['rules']['min_dscr']}x.")

    S.append("8. CREDIT / BUREAU ANALYSIS\n"
             f"Indicative bureau score of {b['cibil']} evaluated against the configured minimum of {policy['rules']['min_cibil']}. "
             f"No settlement or write-off signal has been assumed within this demonstration dataset beyond the stated parameters.")

    S.append("9. CREDIT BRAIN ASSESSMENT\n"
             f"Positive signals: {pos}. Risk signals: {rsk}. Credit Brain provides structured evidence only and does not "
             f"override the configured Credit Policy.")

    rule_lines = "\n".join(
        f"  - {r['id']} {r['name']}: actual {r['actual']} vs {r['operator']} {r['threshold']} → {r['result']} ({r['impact']})"
        for r in pe["rules"])
    S.append("10. CREDIT POLICY EVALUATION\n"
             f"{pe['rules_evaluated']} rules evaluated — {pe['passed']} passed, {pe['review']} review, "
             f"{pe['critical_failures']} critical failure(s). Overall: {pe['overall']}.\n" + rule_lines)

    wf = "\n".join(f"  - {w['label']}: ₹{lakh(w['value'])} lakh" for w in d["eligibility_waterfall"])
    S.append("11. LOAN ELIGIBILITY\n"
             f"The eligible amount is derived through a constrained waterfall:\n{wf}\n"
             f"The recommended amount of ₹{lakh(d['recommended_amount'])} lakh reflects the binding constraint among policy "
             f"cap, cash-flow capacity and collateral coverage.")

    S.append("12. PRICING\n"
             f"Risk Grade {d['risk_grade']} (PD {round(d['pd_score']*100,1)}%) attracts an ROI of {d['roi']:.2f}% p.a. with a "
             f"processing fee of ₹{d['processing_fee']:,}. Net disbursement is estimated at ₹{d['net_disbursement']:,}.")

    S.append("13. REPAYMENT STRUCTURE\n"
             f"On a sanction of ₹{lakh(d['recommended_amount'])} lakh at {d['roi']:.2f}% for {d['tenure_months']} months, the "
             f"EMI is ₹{d['emi']:,}, total interest ₹{d['total_interest']:,} and total repayment ₹{d['total_repayment']:,}.")

    if d["decision"] == "approve":
        rationale = (f"The application satisfies the mandatory eligibility, financial and banking rules under the active policy. "
                     f"The recommended amount of ₹{lakh(d['recommended_amount'])} lakh — rather than the requested "
                     f"₹{lakh(d['requested_amount'])} lakh — is governed by the binding cash-flow / policy capacity constraint. "
                     f"Pricing of {d['roi']:.2f}% and tenure of {d['tenure_months']} months follow the configured Risk Grade "
                     f"{d['risk_grade']} slab. Residual risks are addressed through the conditions of approval.")
    elif d["decision"] == "review":
        rationale = (f"The application does not fail any mandatory rejection rule but triggers one or more review conditions "
                     f"({', '.join(pe['triggered']) or 'policy borderline'}). Analyst review is required prior to sanction; the "
                     f"indicative structure is provided for reference only.")
    else:
        rationale = (f"The application does not satisfy mandatory Credit Policy requirements. Rules triggered: "
                     f"{', '.join(pe['triggered']) or 'policy thresholds'}. Cash-flow capacity and/or bureau and eligibility "
                     f"constraints preclude a positive recommendation under the active policy.")
    S.append("14. DECISION RATIONALE\n" + rationale)

    cond = "\n".join(f"  - {c}" for c in d["conditions"])
    S.append("15. CONDITIONS OF APPROVAL\n" + cond)

    S.append("16. RISK MITIGANTS\n"
             "  - Collateral security with policy-compliant coverage.\n"
             "  - NACH mandate for disciplined repayment.\n"
             "  - Periodic monitoring of banking turnover and obligation coverage.")

    if d["decision"] == "approve":
        final = (f"Based on the available documents, the Credit Brain assessment and configured Credit Policy {d['policy_version']}, "
                 f"the application is recommended for sanction of ₹{lakh(d['recommended_amount'])} lakh at {d['roi']:.2f}% p.a. for "
                 f"{d['tenure_months']} months, subject to the conditions listed above.")
    elif d["decision"] == "review":
        final = "Credit sanction should remain pending analyst review until the identified policy exceptions are resolved."
    else:
        final = (f"The application is not recommended under the active credit policy because mandatory rules "
                 f"{', '.join(pe['triggered'][:2]) or 'were not satisfied'} were not satisfied.")
    S.append("17. FINAL RECOMMENDATION\n" + final)
    S.append("AI-generated credit decision support. Subject to applicable credit policy, analyst review and institutional "
             "approval authority.")
    return "\n\n".join(S)


async def generate_ai_memo_detailed(application: dict, policy: dict, full: dict, fallback: str):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        b = full["credit_brain"]["financials"]
        prompt = (
            "Write a detailed, professional Indian NBFC credit appraisal memorandum (800-1200 words) using the sections: "
            "Executive Summary, Borrower Profile, Loan Request, Financial Analysis, Banking Analysis, Debt Obligation "
            "Analysis, Bureau Analysis, Credit Brain Assessment, Credit Policy Evaluation, Loan Eligibility, Pricing, "
            "Repayment Structure, Decision Rationale, Conditions of Approval, Risk Mitigants, Final Recommendation. "
            "Be restrained and evidence-led; do not overclaim. Explain why the recommended amount differs from requested. "
            f"Data: borrower={application['borrower_name']}, product={LOAN_TYPE_LABEL.get(application['loan_type'])}, "
            f"requested={full['requested_amount']}, recommended={full['recommended_amount']}, decision={full['decision']}, "
            f"risk_grade={full['risk_grade']}, pd={full['pd_score']}, roi={full['roi']}, tenure_months={full['tenure_months']}, "
            f"emi={full['emi']}, post_loan_foir={full['post_loan_foir']}, dscr={b['dscr']}, cibil={b['cibil']}, "
            f"vintage_months={b['business_vintage_months']}, avg_monthly_credits={b['avg_monthly_credits']}, "
            f"net_cash_flow={b['net_cash_flow']}, policy_rules_triggered={full['policy_evaluation']['triggered']}. "
            "End with the disclaimer that it is AI-generated decision support subject to policy and analyst review."
        )
        chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"memo-{application['id']}",
                       system_message="You are a senior credit analyst at an Indian NBFC writing detailed, restrained credit appraisal memos.").with_model("openai", ANALYSIS_MODEL)
        resp = await chat.send_message(UserMessage(text=prompt))
        text = (resp if isinstance(resp, str) else str(resp)).strip()
        return (text, "ai") if len(text) > 400 else (fallback, "template")
    except Exception as e:
        logger.warning(f"AI detailed memo failed, using structured memo: {e}")
        return fallback, "template"


# ---------------------------------------------------------------------------
# Reference generation
# ---------------------------------------------------------------------------
async def next_reference() -> str:
    year = now_utc().year
    count = await db.applications.count_documents({})
    return f"LS-{year}-{str(124 + count).zfill(5)}"


async def write_audit(application_id: str, event: str, actor: str, payload: dict):
    await db.audit_log.insert_one({
        "id": str(uuid.uuid4()),
        "application_id": application_id,
        "event": event,
        "actor": actor,
        "payload": payload,
        "created_at": iso(now_utc()),
    })


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@api_router.post("/auth/login")
async def login(body: LoginIn):
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user.get("name", "Analyst")}}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ---------------------------------------------------------------------------
# Application routes
# ---------------------------------------------------------------------------
@api_router.post("/applications", status_code=201)
async def create_application(body: ApplicationCreate, user: dict = Depends(get_current_user)):
    app_id = str(uuid.uuid4())
    reference = await next_reference()
    doc = {
        "id": app_id,
        "reference": reference,
        "borrower_name": body.borrower_name,
        "loan_type": body.loan_type,
        "loan_amount": body.loan_amount,
        "status": "pending",
        "created_at": iso(now_utc()),
    }
    await db.applications.insert_one(doc)
    await write_audit(app_id, "Application Created", user.get("name", "Analyst"),
                      {"reference": reference, "loan_type": body.loan_type, "loan_amount": body.loan_amount})
    doc.pop("_id", None)
    return doc


@api_router.get("/applications")
async def list_applications(search: Optional[str] = None, status: Optional[str] = None,
                            loan_type: Optional[str] = None, user: dict = Depends(get_current_user)):
    query: dict = {}
    if status and status != "all":
        query["status"] = status
    if loan_type and loan_type != "all":
        query["loan_type"] = loan_type
    if search:
        query["$or"] = [
            {"borrower_name": {"$regex": re.escape(search), "$options": "i"}},
            {"reference": {"$regex": re.escape(search), "$options": "i"}},
        ]
    apps = await db.applications.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    # attach decision summary
    decisions = await db.decisions.find({}, {"_id": 0}).to_list(1000)
    dmap = {d["application_id"]: d for d in decisions}
    for a in apps:
        d = dmap.get(a["id"])
        a["decision"] = d["decision"] if d else None
        a["pd_score"] = d["pd_score"] if d else None
        a["tat_minutes"] = d["tat_minutes"] if d else None
        a["recommended_amount"] = d.get("recommended_amount") if d else None
        a["roi"] = d.get("roi") if d else None
        a["tenure_months"] = d.get("tenure_months") if d else None
        a["emi"] = d.get("emi") if d else None
        a["risk_grade"] = d.get("risk_grade") if d else None
    return apps


@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    total = await db.applications.count_documents({})
    pending = await db.applications.count_documents({"status": "pending"})
    apps = await db.applications.find({}, {"_id": 0}).to_list(2000)
    decisions = await db.decisions.find({}, {"_id": 0}).to_list(2000)
    decided = len(decisions)
    approved = sum(1 for d in decisions if d["decision"] == "approve")
    review = sum(1 for d in decisions if d["decision"] == "review")
    rejected = sum(1 for d in decisions if d["decision"] == "reject")
    auto = approved + rejected
    straight_through = round((auto / decided) * 100, 1) if decided else 0.0
    avg_tat = round(sum(d["tat_minutes"] for d in decisions) / decided) if decided else 0
    avg_pd = round((sum(d["pd_score"] for d in decisions) / decided) * 100, 1) if decided else 0.0
    total_requested = sum(a["loan_amount"] for a in apps)
    total_recommended = sum(d.get("recommended_amount", 0) for d in decisions)
    total_approved = sum(d.get("recommended_amount", 0) for d in decisions if d["decision"] == "approve")
    return {
        "total_applications": total,
        "straight_through_rate": straight_through,
        "avg_tat": avg_tat,
        "pending_review": pending + review,
        "approved": approved, "review": review, "rejected": rejected, "pending": pending,
        "avg_pd": avg_pd, "total_requested": total_requested,
        "total_recommended": total_recommended, "total_approved": total_approved,
    }


@api_router.get("/credit-policy")
async def get_credit_policy(user: dict = Depends(get_current_user)):
    return await get_active_policy()


@api_router.get("/credit-policy/versions")
async def list_policy_versions(user: dict = Depends(get_current_user)):
    return await db.credit_policies.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.put("/credit-policy")
async def update_credit_policy(body: dict = Body(...), user: dict = Depends(get_current_user)):
    if user.get("role") not in ("admin", "credit_manager"):
        raise HTTPException(status_code=403, detail="Only administrators can edit the credit policy")
    active = await get_active_policy()
    new = dict(active)
    new.pop("_id", None)
    for k in ("rules", "loan_amount_rules", "tenure_rules", "decision_matrix"):
        if isinstance(body.get(k), dict):
            merged = dict(active.get(k, {}))
            merged.update(body[k])
            new[k] = merged
    for k in ("roi_rules", "required_documents", "conditions", "approval_authority"):
        if body.get(k) is not None:
            new[k] = body[k]
    if body.get("policy_name"):
        new["policy_name"] = body["policy_name"]
    if body.get("product_type"):
        new["product_type"] = body["product_type"]
    if body.get("effective_from"):
        new["effective_from"] = body["effective_from"]
    # bump version
    try:
        major_minor = active["version"].lstrip("v").split(".")
        new_ver = f"v{major_minor[0]}.{int(major_minor[1]) + 1}"
    except Exception:
        new_ver = "v1.1"
    new["version"] = new_ver
    new["id"] = str(uuid.uuid4())
    new["status"] = "active"
    new["created_by"] = user.get("name", "Credit Admin")
    new["created_at"] = iso(now_utc())
    new["updated_at"] = iso(now_utc())
    await db.credit_policies.update_many({"status": "active"}, {"$set": {"status": "archived"}})
    await db.credit_policies.insert_one(dict(new))
    await write_audit("system", "Policy Updated", user.get("name", "Credit Admin"),
                      {"version": new_ver, "policy_name": new["policy_name"]})
    await write_audit("system", "Policy Activated", user.get("name", "Credit Admin"), {"version": new_ver})
    new.pop("_id", None)
    return new


@api_router.post("/credit-policy/simulate")
async def simulate_policy(body: dict = Body(...), user: dict = Depends(get_current_user)):
    active = await get_active_policy()
    proposed = dict(active)
    proposed.pop("_id", None)
    for k in ("rules", "loan_amount_rules", "tenure_rules", "decision_matrix"):
        if isinstance(body.get(k), dict):
            merged = dict(active.get(k, {}))
            merged.update(body[k])
            proposed[k] = merged
    if body.get("roi_rules") is not None:
        proposed["roi_rules"] = body["roi_rules"]

    apps = await db.applications.find({}, {"_id": 0}).to_list(2000)
    cur_mix = {"approve": 0, "review": 0, "reject": 0}
    prop_mix = {"approve": 0, "review": 0, "reject": 0}
    changes = []
    for a in apps:
        cur = compute_full_decision(a, active, force_known=False)["decision"]
        prop = compute_full_decision(a, proposed, force_known=False)["decision"]
        cur_mix[cur] += 1
        prop_mix[prop] += 1
        if cur != prop:
            changes.append({"reference": a["reference"], "borrower": a["borrower_name"], "from": cur, "to": prop})
    return {"current_mix": cur_mix, "proposed_mix": prop_mix, "changes": changes,
            "applications": len(apps)}


@api_router.get("/credit-brain/{app_id}")
async def get_credit_brain(app_id: str, user: dict = Depends(get_current_user)):
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    decision = await db.decisions.find_one({"application_id": app_id}, {"_id": 0})
    documents = await db.documents.find({"application_id": app_id}, {"_id": 0}).to_list(100)
    policy = await get_active_policy()
    readiness = evaluate_document_readiness(documents, policy)
    if decision and decision.get("credit_brain"):
        cb = decision["credit_brain"]
        seed = _seed_int(application["borrower_name"], application["loan_amount"])
        if not cb.get("evidence") and cb.get("financials"):
            cb["evidence"] = build_evidence(cb["financials"], seed)
        if not cb.get("contradictions"):
            cb["contradictions"] = credit_brain(application).get("contradictions", [])
        return {"application": application, "credit_brain": cb, "readiness": readiness, "computed": False}
    brain = credit_brain(application)
    return {"application": application, "credit_brain": brain, "readiness": readiness, "computed": True}


@api_router.get("/applications/{app_id}/policy-evaluation")
async def get_policy_evaluation(app_id: str, user: dict = Depends(get_current_user)):
    decision = await db.decisions.find_one({"application_id": app_id}, {"_id": 0})
    if not decision or not decision.get("policy_evaluation"):
        raise HTTPException(status_code=404, detail="No policy evaluation. Run the decision first.")
    return decision["policy_evaluation"]


# ---------------------------------------------------------------------------
# Demo seed


@api_router.get("/applications/{app_id}")
async def get_application(app_id: str, user: dict = Depends(get_current_user)):
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    documents = await db.documents.find({"application_id": app_id}, {"_id": 0}).sort("uploaded_at", 1).to_list(100)
    decision = await db.decisions.find_one({"application_id": app_id}, {"_id": 0})
    if decision and decision.get("credit_brain") and decision["credit_brain"].get("financials"):
        cb = decision["credit_brain"]
        seed = _seed_int(application["borrower_name"], application["loan_amount"])
        if not cb.get("evidence"):
            cb["evidence"] = build_evidence(cb["financials"], seed)
        if not cb.get("contradictions"):
            cb["contradictions"] = credit_brain(application).get("contradictions", [])
    return {"application": application, "documents": documents, "decision": decision}


@api_router.get("/applications/{app_id}/audit")
async def get_audit(app_id: str, user: dict = Depends(get_current_user)):
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    events = await db.audit_log.find({"application_id": app_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return events


DOC_TYPE_LABELS = {"bank_statement": "Bank Statement", "itr": "ITR", "gst": "GST",
                   "salary_slip": "Salary Slip", "kyc": "KYC", "cibil": "CIBIL Report",
                   "purchase_bills": "Purchase Bills", "sales_bills": "Sales Bills"}


@api_router.post("/applications/{app_id}/documents", status_code=201)
async def upload_documents(app_id: str, files: List[UploadFile] = File(...),
                           doc_types: List[str] = Form(...), user: dict = Depends(get_current_user)):
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if len(files) != len(doc_types):
        raise HTTPException(status_code=400, detail="Mismatch between files and document types")

    saved = []
    for f, dtype in zip(files, doc_types):
        if dtype not in DOC_TYPE_LABELS:
            raise HTTPException(status_code=400, detail=f"Invalid document type: {dtype}")
        content = await f.read()
        if not (f.content_type == "application/pdf" or (f.filename or "").lower().endswith(".pdf")):
            raise HTTPException(status_code=400, detail=f"Only PDF files are allowed: {f.filename}")
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large: {f.filename}")

        doc_id = str(uuid.uuid4())
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(f.filename or "document.pdf"))
        stored_name = f"{doc_id}_{safe_name}"
        file_path = UPLOAD_DIR / stored_name
        with open(file_path, "wb") as out:
            out.write(content)

        doc = {
            "id": doc_id,
            "application_id": app_id,
            "doc_type": dtype,
            "filename": safe_name,
            "file_path": str(file_path),
            "file_size": len(content),
            "status": "processed",
            "uploaded_at": iso(now_utc()),
        }
        await db.documents.insert_one(doc)
        doc.pop("_id", None)
        doc.pop("file_path", None)
        saved.append(doc)

    await write_audit(app_id, "Documents Uploaded", user.get("name", "Analyst"),
                      {"count": len(saved), "types": [s["doc_type"] for s in saved]})
    try:
        ef = await refresh_extraction(app_id)
        if ef:
            await write_audit(app_id, "Documents Analysed", "Credit Brain",
                              {"source": "ai", "confidence": ef.get("_confidence"),
                               "fields": [k for k in ef.keys() if not k.startswith("_")]})
    except Exception as e:
        logger.warning(f"Post-upload extraction failed: {e}")
    return saved


@api_router.get("/documents/{doc_id}/download")
async def download_document(doc_id: str, user: dict = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": doc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    path = doc.get("file_path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not available in demo storage")
    return FileResponse(path, media_type="application/pdf", filename=doc["filename"])


@api_router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: dict = Depends(get_current_user)):
    doc = await db.documents.find_one({"id": doc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    path = doc.get("file_path")
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    await db.documents.delete_one({"id": doc_id})
    return {"ok": True}


@api_router.post("/applications/{app_id}/decision")
async def run_decision(app_id: str, options: DecisionOptions = DecisionOptions(),
                       user: dict = Depends(get_current_user)):
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    documents = await db.documents.find({"application_id": app_id}, {"_id": 0}).to_list(100)
    if not documents:
        raise HTTPException(status_code=400, detail="Upload at least one document before running the decision")

    policy = await get_active_policy()
    readiness = evaluate_document_readiness(documents, policy)
    if not readiness["ready"]:
        await write_audit(app_id, "Decision Blocked", user.get("name", "Analyst"),
                          {"reason": "Missing mandatory documents", "missing": readiness["missing"]})
        raise HTTPException(status_code=400,
                            detail=f"Decision blocked — missing mandatory document(s): {', '.join(readiness['missing'])}. Upload and classify them to proceed.")

    if not application.get("extracted_financials"):
        await refresh_extraction(app_id)
        application = await db.applications.find_one({"id": app_id}, {"_id": 0})

    full = compute_full_decision(application, policy)
    detailed = build_detailed_memo(application, policy, full)

    use_ai = options.use_ai or (not MOCK_MODE)
    if use_ai:
        memo_text, memo_source = await generate_ai_memo_detailed(application, policy, full, detailed)
    else:
        memo_text, memo_source = detailed, "template"

    created = iso(now_utc())
    decision_doc = {
        "id": str(uuid.uuid4()),
        "application_id": app_id,
        **full,
        "model_decision": full["decision"],
        "required_authority": authority_for_amount(full["recommended_amount"], policy),
        "override": None,
        "memo_text": memo_text,
        "memo_source": memo_source,
        "readiness": readiness,
        "created_at": created,
    }
    await db.decisions.replace_one({"application_id": app_id}, decision_doc, upsert=True)
    status = {"approve": "approved", "review": "review", "reject": "rejected"}.get(full["decision"], "decided")
    await db.applications.update_one({"id": app_id}, {"$set": {"status": status}})

    await write_audit(app_id, "Credit Brain Completed", "Credit Brain",
                      {"pd_score": full["pd_score"], "risk_grade": full["risk_grade"],
                       "positive": len(full["positive_signals"]), "risk": len(full["risk_signals"])})
    await write_audit(app_id, "Policy Evaluated", "Credit Policy Engine",
                      {"policy_version": full["policy_version"], "overall": full["policy_evaluation"]["overall"],
                       "passed": full["policy_evaluation"]["passed"], "triggered": full["policy_evaluation"]["triggered"]})
    await write_audit(app_id, "Decision Generated", "Decision Engine",
                      {"model_version": full["model_version"], "pd_score": full["pd_score"],
                       "decision": full["decision"], "risk_grade": full["risk_grade"],
                       "recommended_amount": full["recommended_amount"], "roi": full["roi"],
                       "tenure_months": full["tenure_months"], "emi": full["emi"], "policy_version": full["policy_version"]})
    await write_audit(app_id, "Credit Memo Generated", "Decision Engine",
                      {"model_version": full["model_version"], "memo_source": memo_source,
                       "words": len(memo_text.split())})

    decision_doc.pop("_id", None)
    return decision_doc


@api_router.post("/applications/{app_id}/decision/override")
async def override_decision(app_id: str, body: OverrideIn, user: dict = Depends(get_current_user)):
    dec = await db.decisions.find_one({"application_id": app_id})
    if not dec:
        raise HTTPException(status_code=404, detail="No decision to override. Run the decision engine first.")
    model_decision = dec.get("model_decision") or dec["decision"]
    if body.decision == dec["decision"] and not dec.get("override"):
        raise HTTPException(status_code=400, detail="Override decision matches the current decision")
    override = {
        "model_decision": model_decision,
        "reason": body.reason,
        "by": user.get("name", "Analyst"),
        "at": iso(now_utc()),
    }
    await db.decisions.update_one({"application_id": app_id},
                                  {"$set": {"decision": body.decision, "model_decision": model_decision,
                                            "override": override}})
    await write_audit(app_id, "Decision Overridden", user.get("name", "Analyst"),
                      {"from": model_decision, "to": body.decision, "reason": body.reason})
    updated = await db.decisions.find_one({"application_id": app_id}, {"_id": 0})
    return updated


@api_router.get("/reports/summary")
async def reports_summary(user: dict = Depends(get_current_user)):
    apps = await db.applications.find({}, {"_id": 0}).to_list(2000)
    decisions = await db.decisions.find({}, {"_id": 0}).to_list(2000)

    decision_mix = {"approve": 0, "review": 0, "reject": 0}
    for d in decisions:
        decision_mix[d["decision"]] = decision_mix.get(d["decision"], 0) + 1

    loan_type_mix = {"business": 0, "personal": 0, "MSME": 0}
    for a in apps:
        loan_type_mix[a["loan_type"]] = loan_type_mix.get(a["loan_type"], 0) + 1

    pd_buckets = {"0-15%": 0, "15-25%": 0, "25-40%": 0, "40%+": 0}
    for d in decisions:
        p = d["pd_score"] * 100
        if p < 15:
            pd_buckets["0-15%"] += 1
        elif p < 25:
            pd_buckets["15-25%"] += 1
        elif p < 40:
            pd_buckets["25-40%"] += 1
        else:
            pd_buckets["40%+"] += 1

    # avg TAT and approval rate per loan type
    tat_acc, tat_cnt, appr_acc = {}, {}, {}
    dmap = {d["application_id"]: d for d in decisions}
    for a in apps:
        d = dmap.get(a["id"])
        if not d:
            continue
        lt = a["loan_type"]
        tat_acc[lt] = tat_acc.get(lt, 0) + d["tat_minutes"]
        tat_cnt[lt] = tat_cnt.get(lt, 0) + 1
        appr_acc.setdefault(lt, {"approve": 0, "total": 0})
        appr_acc[lt]["total"] += 1
        if d["decision"] == "approve":
            appr_acc[lt]["approve"] += 1

    tat_by_type = [{"type": LOAN_TYPE_LABEL[k], "avg_tat": round(tat_acc[k] / tat_cnt[k])}
                   for k in tat_acc]
    approval_by_type = [{"type": LOAN_TYPE_LABEL[k],
                         "rate": round((v["approve"] / v["total"]) * 100) if v["total"] else 0}
                        for k, v in appr_acc.items()]

    total_dec = len(decisions)
    approval_rate = round((decision_mix["approve"] / total_dec) * 100, 1) if total_dec else 0.0
    avg_pd = round((sum(d["pd_score"] for d in decisions) / total_dec) * 100, 1) if total_dec else 0.0
    avg_tat = round(sum(d["tat_minutes"] for d in decisions) / total_dec) if total_dec else 0
    overrides = sum(1 for d in decisions if d.get("override"))

    return {
        "totals": {
            "applications": len(apps),
            "decisions": total_dec,
            "approval_rate": approval_rate,
            "avg_pd": avg_pd,
            "avg_tat": avg_tat,
            "overrides": overrides,
        },
        "decision_mix": [{"name": "Approve", "key": "approve", "value": decision_mix["approve"]},
                         {"name": "Review", "key": "review", "value": decision_mix["review"]},
                         {"name": "Reject", "key": "reject", "value": decision_mix["reject"]}],
        "loan_type_mix": [{"name": LOAN_TYPE_LABEL[k], "value": v} for k, v in loan_type_mix.items()],
        "pd_distribution": [{"bucket": k, "count": v} for k, v in pd_buckets.items()],
        "tat_by_type": tat_by_type,
        "approval_by_type": approval_by_type,
    }


@api_router.get("/me/authority")
async def my_authority(user: dict = Depends(get_current_user)):
    policy = await get_active_policy()
    role = user.get("role", "viewer")
    return {"role": role, "max_authority": user_max_authority(role, policy),
            "permissions": sorted(ROLE_PERMS.get(role, set())),
            "approval_authority": policy.get("approval_authority", [])}


@api_router.post("/applications/{app_id}/action")
async def application_action(app_id: str, body: ActionIn, user: dict = Depends(get_current_user)):
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    role = user.get("role", "viewer")
    perms = ROLE_PERMS.get(role, set())
    need = {"send_review": "review", "approve": "approve", "reject": "reject", "escalate": "escalate"}[body.action]
    if need not in perms:
        raise HTTPException(status_code=403, detail=f"Your role ({role}) is not permitted to {body.action.replace('_', ' ')}")
    decision = await db.decisions.find_one({"application_id": app_id}, {"_id": 0})
    policy = await get_active_policy()
    if body.action == "approve":
        if not decision:
            raise HTTPException(status_code=400, detail="Run the decision before approving")
        amount = decision.get("recommended_amount", 0)
        if amount > user_max_authority(role, policy):
            raise HTTPException(status_code=403, detail=f"Escalation required: this amount exceeds your approval authority. Escalate to {authority_for_amount(amount, policy)}.")
    status_map = {"send_review": "review", "approve": "approved", "reject": "rejected", "escalate": "escalated"}
    new_status = status_map[body.action]
    await db.applications.update_one({"id": app_id}, {"$set": {"status": new_status}})
    event = {"send_review": "Sent For Review", "approve": "Application Approved",
             "reject": "Application Rejected", "escalate": "Application Escalated"}[body.action]
    await write_audit(app_id, event, user.get("name", role),
                      {"role": role, "status": new_status, "comment": body.comment,
                       "amount": decision.get("recommended_amount") if decision else None})
    return {"status": new_status, "event": event}



class AskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None


def build_ask_context(application: dict, full: dict) -> str:
    f = full["credit_brain"]["financials"]
    pe = full["policy_evaluation"]
    lines = [
        f"Borrower: {application['borrower_name']} | Product: {LOAN_TYPE_LABEL.get(application['loan_type'], application['loan_type'])} | Reference: {application.get('reference', '-')}",
        f"Decision: {full['decision'].upper()} | Risk grade: {full['risk_grade']} | PD: {round(full['pd_score']*100,1)}%",
        f"Requested: ₹{lakh(full['requested_amount'])}L | Eligible: ₹{lakh(full['eligible_amount'])}L | Recommended: ₹{lakh(full['recommended_amount'])}L",
        f"ROI: {full['roi']}% p.a. | Tenure: {full['tenure_months']} months | EMI: ₹{full['emi']:,} | Post-loan FOIR: {round(full['post_loan_foir']*100,1)}%",
        f"Financials: annual turnover ₹{lakh(f['annual_turnover'])}L, avg monthly credits ₹{lakh(f['avg_monthly_credits'])}L, avg balance ₹{lakh(f['avg_monthly_balance'])}L, net cash flow ₹{lakh(f['net_cash_flow'])}L, existing EMI ₹{f['existing_emi']:,}, pre-loan FOIR {round(f['foir_before']*100,1)}%, DSCR {f['dscr']}x, CIBIL {f['cibil']}, business vintage {f['business_vintage_months']} months, banking history {f['banking_history_months']} months, cheque bounces {f['cheque_bounces']}, NACH bounces {f['nach_bounces']}, industry {f.get('industry','-')}",
        "Eligibility waterfall: " + "; ".join(f"{w['label']} ₹{lakh(w['value'])}L" for w in full['eligibility_waterfall']),
        f"Policy {full['policy_version']} evaluation — overall {pe['overall']}, {pe['passed']}/{pe['rules_evaluated']} passed, triggered: {', '.join(pe['triggered']) or 'none'}.",
        "Policy rules: " + "; ".join(f"{r['id']} {r['name']}: actual {r['actual']} {r['operator']} {r['threshold']} -> {r['result']}" for r in pe['rules']),
        "Positive signals: " + ("; ".join(s['label'] for s in full['positive_signals']) or "none"),
        "Risk signals: " + ("; ".join(s['label'] for s in full['risk_signals']) or "none"),
    ]
    return "\n".join(lines)


async def run_brain_chat(session_id: str, context: str, history: list, question: str) -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    system = (
        "You are Credit Brain, an assistant for an Indian NBFC credit team. Answer ONLY using the "
        "application assessment data provided below. Be concise (2-5 sentences or short bullets) and "
        "professional. Always cite the specific figures or policy rule IDs you used, e.g. 'DSCR 1.6x', "
        "'post-loan FOIR 52%', 'POL-FOIR-004'. When asked why the recommended amount differs from the "
        "requested amount, explain the binding constraint in the eligibility waterfall. If a question "
        "cannot be answered from this data, say you can only answer questions about this application's "
        "credit assessment. Never invent numbers not present in the data.\n\n"
        "APPLICATION ASSESSMENT DATA:\n" + context
    )
    if history:
        convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-6:])
        system += "\n\nCONVERSATION SO FAR:\n" + convo
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system).with_model("openai", ANALYSIS_MODEL)
    resp = await chat.send_message(UserMessage(text=question))
    return (resp if isinstance(resp, str) else str(resp)).strip()


@api_router.get("/applications/{app_id}/chat")
async def get_brain_chat(app_id: str, user: dict = Depends(get_current_user)):
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    msgs = await db.brain_chats.find({"application_id": app_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return msgs


@api_router.post("/applications/{app_id}/ask")
async def ask_brain(app_id: str, body: AskIn, user: dict = Depends(get_current_user)):
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    decision = await db.decisions.find_one({"application_id": app_id}, {"_id": 0})
    if decision and decision.get("credit_brain"):
        full = decision
    else:
        policy = await get_active_policy()
        full = compute_full_decision(application, policy)
    context = build_ask_context(application, full)
    session_id = body.session_id or f"brain-{app_id}"
    history = await db.brain_chats.find({"application_id": app_id}, {"_id": 0}).sort("created_at", 1).to_list(50)
    question = body.question.strip()
    now = iso(now_utc())
    await db.brain_chats.insert_one({"id": str(uuid.uuid4()), "application_id": app_id, "session_id": session_id,
                                     "role": "user", "content": question, "created_at": now})
    try:
        answer = await run_brain_chat(session_id, context, history, question)
    except Exception as e:
        logger.warning(f"Ask Credit Brain failed: {e}")
        raise HTTPException(status_code=503, detail="Credit Brain assistant is unavailable right now. Please try again.")
    ans_at = iso(now_utc())
    await db.brain_chats.insert_one({"id": str(uuid.uuid4()), "application_id": app_id, "session_id": session_id,
                                     "role": "assistant", "content": answer, "created_at": ans_at})
    return {"answer": answer, "session_id": session_id, "created_at": ans_at}


# ---------------------------------------------------------------------------
# Demo seed
# ---------------------------------------------------------------------------
def _seed_render_pdf(lines: list) -> bytes:
    """Render a simple text PDF (synthetic demo document) to bytes via reportlab."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 15
        if y < 60:
            c.showPage()
            y = 800
    c.save()
    return buf.getvalue()


def _seed_portfolio() -> list:
    """Three genuine-document demo borrowers: strong (approve), risky (reject), borderline (review)."""
    nova = {
        "reference": "LS-2026-00201", "borrower_name": "Nova Precision Tools Pvt Ltd",
        "loan_type": "MSME", "loan_amount": 4000000, "target": "approve",
        "docs": [
            ("kyc", "Nova_KYC.pdf", [
                "KYC / BORROWER PROFILE (SYNTHETIC DEMO DATA)",
                "Entity: Nova Precision Tools Pvt Ltd", "Constitution: Private Limited Company",
                "PAN: AABCN1234K   GSTIN: 27AABCN1234K1Z5   CIN: U29100MH2019PTC099887",
                "Registered office: Plot 21, MIDC Bhosari, Pune, Maharashtra 411026",
                "Promoters: R. Iyer (MD), S. Iyer (Director) - both KYC verified",
                "Nature of business: Precision Engineering / CNC Machining",
                "Business commencement: registered 84 months ago (Apr-2019)",
            ]),
            ("cibil", "Nova_CIBIL.pdf", [
                "CIBIL / TRANSUNION COMMERCIAL CREDIT REPORT (SYNTHETIC DEMO DATA)",
                "Entity: Nova Precision Tools Pvt Ltd", "CIBIL Score: 771",
                "Total active loans: 3   Hard enquiries (last 6 months): 1",
                "Total sanctioned: INR 1,20,00,000   Total outstanding: INR 61,00,000",
                "Total overdue amount: INR 0   Worst DPD across accounts: 0 days",
                "Repayment track record: excellent - all accounts standard, zero delinquency.",
                "TRADELINES:",
                "  1. HDFC Bank | Equipment Loan | Sanctioned 50,00,000 | Outstanding 28,00,000 | EMI 1,25,000 | DPD 0 | Active",
                "  2. Bajaj Finserv | Machinery Loan | Sanctioned 40,00,000 | Outstanding 21,00,000 | EMI 55,000 | DPD 0 | Active",
                "  3. ICICI Bank | Business Loan | Sanctioned 30,00,000 | Outstanding 12,00,000 | EMI 30,000 | DPD 0 | Active",
            ]),
            ("bank_statement", "Nova_Bank_Statement.pdf", [
                "HDFC BANK - CURRENT ACCOUNT STATEMENT (SYNTHETIC DEMO DATA)",
                "Account holder: Nova Precision Tools Pvt Ltd    Account: XXXX4471",
                "Statement period: 01-Apr-2025 to 31-Mar-2026 (12 months)",
                "Average monthly credits (inflows): INR 18,50,000",
                "Average monthly balance: INR 9,20,000",
                "Total annual bank credits (turnover): INR 2,22,00,000",
                "Total monthly EMI outflow (existing loans): INR 2,10,000",
                "Average monthly fixed obligations (EMIs + operating fixed costs): INR 5,60,000",
                "Inflow to outflow ratio: 1.18",
                "MONTH-WISE SUMMARY (credits / debits / closing balance in INR):",
                "  Apr-2025: 19,20,000 / 17,80,000 / 8,90,000",
                "  May-2025: 17,90,000 / 16,40,000 / 9,10,000",
                "  Jun-2025: 18,60,000 / 17,10,000 / 9,40,000",
                "  Jul-2025: 20,10,000 / 18,20,000 / 9,80,000",
                "  Aug-2025: 17,40,000 / 16,90,000 / 8,70,000",
                "  Sep-2025: 18,80,000 / 17,50,000 / 9,20,000",
                "  Oct-2025: 19,60,000 / 18,00,000 / 9,60,000",
                "  Nov-2025: 18,20,000 / 16,80,000 / 9,30,000",
                "  Dec-2025: 20,40,000 / 18,60,000 / 9,90,000",
                "  Jan-2026: 17,80,000 / 16,50,000 / 8,80,000",
                "  Feb-2026: 18,10,000 / 17,00,000 / 9,10,000",
                "  Mar-2026: 19,90,000 / 18,40,000 / 9,50,000",
                "RECURRING EMI DEBITS: HDFC Equipment 1,25,000; Bajaj Machinery 55,000; ICICI Business 30,000 (3 EMIs, total 2,10,000/mo)",
                "TOP CREDIT SOURCES: Larsen & Toubro 84,00,000; Tata Motors 62,00,000; Ashok Leyland 38,00,000",
                "Cheque returns: 0   NACH failures: 0",
                "No gambling, betting or unexplained cash transactions observed.",
                "Cash flow pattern: consistent B2B receivables, healthy surplus, disciplined EMIs.",
            ]),
            ("itr", "Nova_ITR.pdf", [
                "INCOME TAX RETURN - ITR (SYNTHETIC DEMO DATA)",
                "Assessee: Nova Precision Tools Pvt Ltd   AY: 2025-26",
                "Declared gross annual business income: INR 2,05,00,000",
                "Nature of business: Precision Engineering / CNC Machining",
                "Business commencement: registered 84 months ago",
            ]),
            ("gst", "Nova_GST.pdf", [
                "GST RETURNS SUMMARY GSTR-3B (SYNTHETIC DEMO DATA)",
                "Legal name: Nova Precision Tools Pvt Ltd",
                "Aggregate annual turnover declared: INR 2,15,00,000",
                "Filing status: all periods filed, no defaults",
            ]),
            ("purchase_bills", "Nova_Purchase_Bills.pdf", [
                "PURCHASE INVOICES SUMMARY (SYNTHETIC DEMO DATA)",
                "Buyer: Nova Precision Tools Pvt Ltd   Period: FY 2025-26",
                "Total purchases (raw material + consumables): INR 96,00,000",
                "  INV-P/2025/118 | JSW Steel Ltd | Alloy steel | 42,00,000",
                "  INV-P/2025/204 | Sandvik Tools | Carbide inserts | 21,00,000",
                "  INV-P/2025/331 | Kennametal India | Tooling | 18,00,000",
                "  INV-P/2025/402 | Local consumables | 15,00,000",
                "All purchases GST-compliant with input tax credit availed.",
            ]),
            ("sales_bills", "Nova_Sales_Bills.pdf", [
                "SALES INVOICES SUMMARY (SYNTHETIC DEMO DATA)",
                "Seller: Nova Precision Tools Pvt Ltd   Period: FY 2025-26",
                "Total sales / receivables raised: INR 2,18,00,000",
                "  INV-S/2025/551 | Larsen & Toubro Ltd | Machined components | 84,00,000",
                "  INV-S/2025/612 | Tata Motors | Precision parts | 62,00,000",
                "  INV-S/2025/708 | Ashok Leyland | Assemblies | 38,00,000",
                "  INV-S/2025/766 | Assorted OEM buyers | 34,00,000",
                "Receivable ageing healthy; majority collected within 45 days.",
            ]),
        ],
    }
    skyline = {
        "reference": "LS-2026-00202", "borrower_name": "Skyline Traders",
        "loan_type": "business", "loan_amount": 3500000, "target": "reject",
        "docs": [
            ("kyc", "Skyline_KYC.pdf", [
                "KYC / BORROWER PROFILE (SYNTHETIC DEMO DATA)",
                "Entity: Skyline Traders   Constitution: Proprietorship",
                "PAN: AFGPS8899L   GSTIN: 27AFGPS8899L1Z2",
                "Proprietor: M. Khanna - KYC verified", "Address: Andheri East, Mumbai 400069",
                "Nature of business: Wholesale trading (electronics)",
                "Business commencement: registered 15 months ago",
            ]),
            ("cibil", "Skyline_CIBIL.pdf", [
                "CIBIL / TRANSUNION COMMERCIAL CREDIT REPORT (SYNTHETIC DEMO DATA)",
                "Entity: Skyline Traders", "CIBIL Score: 648",
                "Total active loans: 4   Hard enquiries (last 6 months): 6",
                "Total sanctioned: INR 95,00,000   Total outstanding: INR 72,00,000",
                "Total overdue amount: INR 3,20,000   Worst DPD across accounts: 62 days",
                "Repayment track record: multiple late payments, one account 60+ DPD.",
                "TRADELINES:",
                "  1. IIFL Finance | Business Loan | Sanctioned 45,00,000 | Outstanding 38,00,000 | EMI 1,95,000 | DPD 62 | Overdue",
                "  2. Kotak Mahindra | Personal Loan | Sanctioned 20,00,000 | Outstanding 16,00,000 | EMI 85,000 | DPD 15 | Active",
                "  3. HDFC Bank | Credit Card | Sanctioned 10,00,000 | Outstanding 9,50,000 | EMI 40,000 | DPD 30 | Active",
                "  4. Bajaj Finserv | Consumer Durable | Sanctioned 20,00,000 | Outstanding 8,50,000 | EMI 22,000 | DPD 0 | Active",
            ]),
            ("bank_statement", "Skyline_Bank_Statement.pdf", [
                "ICICI BANK - CURRENT ACCOUNT STATEMENT (SYNTHETIC DEMO DATA)",
                "Account holder: Skyline Traders    Account: XXXX9920",
                "Statement period: 12 months",
                "Average monthly credits (inflows): INR 12,00,000",
                "Average monthly balance: INR 1,80,000",
                "Total annual bank credits (turnover): INR 1,44,00,000",
                "Total monthly EMI outflow (existing loans): INR 3,20,000",
                "Average monthly fixed obligations (EMIs + operating fixed costs): INR 11,50,000",
                "Inflow to outflow ratio: 0.96",
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
                "RECURRING EMI DEBITS: Kotak Personal 85,000; HDFC Card min-due 40,000; IIFL Business 1,95,000 (3 EMIs, total 3,20,000/mo)",
                "FLAGGED / ANOMALOUS TRANSACTIONS OBSERVED:",
                "  Junglee Rummy (RummyCircle) debits: INR 6,40,000 across 52 txns",
                "  Dream11 / MPL fantasy gaming debits: INR 2,10,000 across 33 txns",
                "  Parimatch betting gateway: INR 1,80,000 across 19 txns",
                "  Frequent large cash withdrawals near month-end (structuring pattern).",
                "Cheque returns: 4   NACH failures: 2",
                "Cash flow pattern: volatile, high gambling outflow, thin surplus, EMI stress.",
            ]),
            ("itr", "Skyline_ITR.pdf", [
                "INCOME TAX RETURN - ITR (SYNTHETIC DEMO DATA)",
                "Assessee: Skyline Traders   AY: 2025-26",
                "Declared gross annual business income: INR 82,00,000",
                "Business commencement: registered 15 months ago",
            ]),
            ("gst", "Skyline_GST.pdf", [
                "GST RETURNS SUMMARY GSTR-3B (SYNTHETIC DEMO DATA)",
                "Legal name: Skyline Traders",
                "Aggregate annual turnover declared: INR 78,00,000",
                "Note: banking turnover (1.44 Cr) materially exceeds GST-declared turnover.",
            ]),
            ("purchase_bills", "Skyline_Purchase_Bills.pdf", [
                "PURCHASE INVOICES SUMMARY (SYNTHETIC DEMO DATA)",
                "Buyer: Skyline Traders   Period: FY 2025-26",
                "Total purchases: INR 52,00,000 (several cash purchases, weak documentation)",
                "  INV-P/981 | Assorted distributors | 31,00,000",
                "  INV-P/1044 | Unregistered vendors (cash) | 21,00,000",
            ]),
            ("sales_bills", "Skyline_Sales_Bills.pdf", [
                "SALES INVOICES SUMMARY (SYNTHETIC DEMO DATA)",
                "Seller: Skyline Traders   Period: FY 2025-26",
                "Total sales raised: INR 76,00,000 (mostly retail UPI, high fragmentation)",
                "  Retail UPI collections | 70,00,000 across 210 txns",
                "  Counter sales (cash) | 6,00,000",
            ]),
        ],
    }
    lakshmi = {
        "reference": "LS-2026-00203", "borrower_name": "Sri Lakshmi Components",
        "loan_type": "business", "loan_amount": 2500000, "target": "review",
        "docs": [
            ("kyc", "Lakshmi_KYC.pdf", [
                "KYC / BORROWER PROFILE (SYNTHETIC DEMO DATA)",
                "Entity: Sri Lakshmi Components   Constitution: Partnership",
                "PAN: AAEFS5566M   GSTIN: 36AAEFS5566M1Z9",
                "Partners: K. Reddy, V. Reddy - KYC verified", "Address: Balanagar, Hyderabad 500037",
                "Nature of business: Auto components sub-assembly",
                "Business commencement: registered 40 months ago",
            ]),
            ("cibil", "Lakshmi_CIBIL.pdf", [
                "CIBIL / TRANSUNION COMMERCIAL CREDIT REPORT (SYNTHETIC DEMO DATA)",
                "Entity: Sri Lakshmi Components", "CIBIL Score: 705",
                "Total active loans: 3   Hard enquiries (last 6 months): 3",
                "Total sanctioned: INR 60,00,000   Total outstanding: INR 41,00,000",
                "Total overdue amount: INR 0   Worst DPD across accounts: 22 days",
                "Repayment track record: broadly regular, one instance of 22-day delay.",
                "TRADELINES:",
                "  1. Axis Bank | Working Capital | Sanctioned 30,00,000 | Outstanding 22,00,000 | EMI 1,60,000 | DPD 22 | Active",
                "  2. Tata Capital | Machinery Loan | Sanctioned 20,00,000 | Outstanding 13,00,000 | EMI 95,000 | DPD 0 | Active",
                "  3. HDFC Bank | Overdraft | Sanctioned 10,00,000 | Outstanding 6,00,000 | EMI 45,000 | DPD 5 | Active",
            ]),
            ("bank_statement", "Lakshmi_Bank_Statement.pdf", [
                "AXIS BANK - CURRENT ACCOUNT STATEMENT (SYNTHETIC DEMO DATA)",
                "Account holder: Sri Lakshmi Components    Account: XXXX7712",
                "Statement period: 12 months",
                "Average monthly credits (inflows): INR 9,40,000",
                "Average monthly balance: INR 3,10,000",
                "Total annual bank credits (turnover): INR 1,40,00,000",
                "Total monthly EMI outflow (existing loans): INR 3,00,000",
                "Average monthly fixed obligations (EMIs + operating fixed costs): INR 5,45,000",
                "Inflow to outflow ratio: 1.03",
                "MONTH-WISE SUMMARY (credits / debits / closing balance in INR):",
                "  Apr-2025: 9,80,000 / 9,40,000 / 3,20,000",
                "  May-2025: 8,60,000 / 9,10,000 / 2,70,000",
                "  Jun-2025: 10,20,000 / 9,60,000 / 3,30,000",
                "  Jul-2025: 9,10,000 / 9,00,000 / 3,40,000",
                "  Aug-2025: 8,90,000 / 9,30,000 / 3,00,000",
                "  Sep-2025: 9,60,000 / 9,20,000 / 3,40,000",
                "  Oct-2025: 10,10,000 / 9,70,000 / 3,80,000",
                "  Nov-2025: 8,80,000 / 9,10,000 / 3,50,000",
                "  Dec-2025: 9,90,000 / 9,40,000 / 4,00,000",
                "  Jan-2026: 8,70,000 / 9,20,000 / 3,50,000",
                "  Feb-2026: 9,30,000 / 9,00,000 / 3,80,000",
                "  Mar-2026: 9,80,000 / 9,60,000 / 4,00,000",
                "RECURRING EMI DEBITS: Axis WC 1,60,000; Tata Capital 95,000; HDFC OD 45,000 (3 EMIs, total 3,00,000/mo)",
                "TOP CREDIT SOURCES: Mahindra CIE 58,00,000; Bosch India 41,00,000; assorted 41,00,000",
                "Cheque returns: 2   NACH failures: 1",
                "No gambling or betting transactions observed.",
                "Cash flow pattern: steady but thin surplus; moderate obligation load.",
            ]),
            ("itr", "Lakshmi_ITR.pdf", [
                "INCOME TAX RETURN - ITR (SYNTHETIC DEMO DATA)",
                "Assessee: Sri Lakshmi Components   AY: 2025-26",
                "Declared gross annual business income: INR 92,00,000",
                "Business commencement: registered 40 months ago",
            ]),
            ("gst", "Lakshmi_GST.pdf", [
                "GST RETURNS SUMMARY GSTR-3B (SYNTHETIC DEMO DATA)",
                "Legal name: Sri Lakshmi Components",
                "Aggregate annual turnover declared: INR 1,05,00,000",
                "Note: GST turnover 1.05 Cr vs banking turnover 1.40 Cr (~25% variance).",
            ]),
            ("purchase_bills", "Lakshmi_Purchase_Bills.pdf", [
                "PURCHASE INVOICES SUMMARY (SYNTHETIC DEMO DATA)",
                "Buyer: Sri Lakshmi Components   Period: FY 2025-26",
                "Total purchases: INR 62,00,000",
                "  INV-P/311 | Jindal Steel | 34,00,000",
                "  INV-P/377 | Fastener suppliers | 16,00,000",
                "  INV-P/430 | Consumables | 12,00,000",
            ]),
            ("sales_bills", "Lakshmi_Sales_Bills.pdf", [
                "SALES INVOICES SUMMARY (SYNTHETIC DEMO DATA)",
                "Seller: Sri Lakshmi Components   Period: FY 2025-26",
                "Total sales raised: INR 1,02,00,000",
                "  INV-S/540 | Mahindra CIE | 58,00,000",
                "  INV-S/588 | Bosch India | 41,00,000",
                "  INV-S/612 | Assorted buyers | 3,00,000",
            ]),
        ],
    }
    return [nova, skyline, lakshmi]


async def _process_seed_app(app_id: str):
    """Background: run genuine OCR + LLM extraction, then decision + memo for a seeded app."""
    try:
        await refresh_extraction(app_id)
        application = await db.applications.find_one({"id": app_id}, {"_id": 0})
        if not application:
            return
        if application.get("extracted_financials"):
            ef = application["extracted_financials"]
            await write_audit(app_id, "Documents Analysed", "Credit Brain",
                              {"source": "ai", "confidence": ef.get("_confidence")})
        policy = await get_active_policy()
        documents = await db.documents.find({"application_id": app_id}, {"_id": 0}).to_list(100)
        readiness = evaluate_document_readiness(documents, policy)
        full = compute_full_decision(application, policy)
        memo = build_detailed_memo(application, policy, full)
        decision_doc = {
            "id": str(uuid.uuid4()), "application_id": app_id, **full,
            "model_decision": full["decision"], "override": None,
            "required_authority": authority_for_amount(full["recommended_amount"], policy),
            "memo_text": memo, "memo_source": "template", "readiness": readiness,
            "created_at": iso(now_utc()),
        }
        await db.decisions.replace_one({"application_id": app_id}, decision_doc, upsert=True)
        status = {"approve": "approved", "review": "review", "reject": "rejected"}.get(full["decision"], "decided")
        await db.applications.update_one({"id": app_id}, {"$set": {"status": status}})
        await write_audit(app_id, "Credit Brain Completed", "Credit Brain",
                          {"pd_score": full["pd_score"], "risk_grade": full["risk_grade"]})
        await write_audit(app_id, "Policy Evaluated", "Credit Policy Engine",
                          {"policy_version": full["policy_version"], "overall": full["policy_evaluation"]["overall"]})
        await write_audit(app_id, "Decision Generated", "Decision Engine",
                          {"decision": full["decision"], "recommended_amount": full["recommended_amount"],
                           "roi": full["roi"], "tenure_months": full["tenure_months"], "emi": full["emi"]})
        await write_audit(app_id, "Credit Memo Generated", "Decision Engine",
                          {"model_version": full["model_version"], "memo_source": "template"})
    except Exception as e:
        logger.warning(f"Seed processing failed for {app_id}: {e}")
        await db.applications.update_one({"id": app_id}, {"$set": {"status": "pending"}})


async def _run_seed_processing(app_ids: list):
    for app_id in app_ids:
        await _process_seed_app(app_id)


@api_router.post("/demo/seed")
async def seed_demo(user: dict = Depends(get_current_user)):
    import asyncio
    created = 0
    refs = []
    new_app_ids = []
    for idx, s in enumerate(_seed_portfolio()):
        existing = await db.applications.find_one({"reference": s["reference"]})
        if existing:
            continue
        created += 1
        refs.append(s["reference"])
        app_id = str(uuid.uuid4())
        new_app_ids.append(app_id)
        base_dt = now_utc() - timedelta(minutes=6 + idx)
        await db.applications.insert_one({
            "id": app_id, "reference": s["reference"], "borrower_name": s["borrower_name"],
            "loan_type": s["loan_type"], "loan_amount": s["loan_amount"],
            "status": "pending", "created_at": iso(base_dt),
        })
        await db.audit_log.insert_one({"id": str(uuid.uuid4()), "application_id": app_id,
                                       "event": "Application Created", "actor": "System",
                                       "payload": {"reference": s["reference"]}, "created_at": iso(base_dt)})
        for dtype, fname, lines in s["docs"]:
            doc_id = str(uuid.uuid4())
            stored_name = f"{doc_id}_{fname}"
            file_path = UPLOAD_DIR / stored_name
            content = _seed_render_pdf(lines)
            with open(file_path, "wb") as out:
                out.write(content)
            await db.documents.insert_one({
                "id": doc_id, "application_id": app_id, "doc_type": dtype, "filename": fname,
                "file_path": str(file_path), "file_size": len(content), "status": "processed",
                "uploaded_at": iso(base_dt + timedelta(minutes=1)),
            })
        await db.audit_log.insert_one({"id": str(uuid.uuid4()), "application_id": app_id,
                                       "event": "Documents Uploaded", "actor": "System",
                                       "payload": {"count": len(s["docs"]),
                                                   "types": [d[0] for d in s["docs"]]},
                                       "created_at": iso(base_dt + timedelta(minutes=1))})
    if new_app_ids:
        asyncio.create_task(_run_seed_processing(new_app_ids))
    return {"created": created, "refs": refs, "processing": len(new_app_ids),
            "message": "Sample portfolio loading — AI is analysing the documents" if created
                       else "Sample portfolio already present"}


@api_router.get("/")
async def root():
    return {"service": "LendSprint AI", "mock_mode": MOCK_MODE}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "email": admin_email, "password_hash": hash_password(admin_password),
            "name": "Credit Analyst", "role": "admin", "created_at": iso(now_utc()),
        })
        logger.info("Seeded admin user")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})
    # seed additional demo roles
    demo_users = [
        ("manager@lendsprint.ai", "Manager@2026", "credit_manager", "Credit Manager"),
        ("analyst@lendsprint.ai", "Analyst@2026", "credit_analyst", "Credit Analyst"),
        ("viewer@lendsprint.ai", "Viewer@2026", "viewer", "Portfolio Viewer"),
    ]
    for email, pw, role, name in demo_users:
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({"id": str(uuid.uuid4()), "email": email,
                                       "password_hash": hash_password(pw), "name": name,
                                       "role": role, "created_at": iso(now_utc())})
    await get_active_policy()
    logger.info(f"LendSprint AI started. MOCK_MODE={MOCK_MODE}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
