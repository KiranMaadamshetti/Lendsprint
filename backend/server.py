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
        ).with_model("openai", "gpt-5.4")
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
    "required_documents": ["Bank Statement", "ITR", "GST Returns", "KYC", "Existing Loan Statement"],
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
    return pol


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


def credit_brain(application: dict) -> dict:
    """Derive structured financial evidence + signals (mock intelligence layer)."""
    borrower = application["borrower_name"]
    amount = application["loan_amount"]
    key = borrower.strip().lower()
    seed = _seed_int(borrower, amount)
    base = compute_decision(borrower, application["loan_type"], amount)
    prof = KNOWN_PROFILES.get(key, {})

    income = base["cash_flow_summary"]["income"]
    obligations = base["cash_flow_summary"]["obligations"]
    net = income - obligations
    existing_emi = int(round(obligations * 0.55))
    annual_credits = income * 12
    revenue = int(round(annual_credits * 0.94))
    avg_balance = int(round(income * (0.45 + (seed % 20) / 100)))
    vintage = prof.get("vintage", 24 + (seed % 96))
    cibil = prof.get("cibil", 640 + (seed % 160))
    cheque_bounces = prof.get("cheque_bounces", seed % 4)
    nach_bounces = prof.get("nach_bounces", seed % 3)
    dscr = round(net / existing_emi, 2) if existing_emi else 2.5
    foir_before = round(obligations / income, 3) if income else 0
    banking_months = 12

    # monthly cash-flow trend (last 6 months)
    months = ["Mar", "Apr", "May", "Jun", "Jul", "Aug"]
    trend = []
    for i, m in enumerate(months):
        wobble = ((seed >> (i * 3)) % 12 - 6) / 100.0
        trend.append({"month": m, "value": int(round(net * (1 + wobble)))})

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

    return {
        "pd_score": base["pd_score"],
        "financials": {
            "revenue": revenue, "annual_credits": annual_credits, "avg_monthly_credits": income,
            "avg_monthly_balance": avg_balance, "existing_emi": existing_emi,
            "monthly_obligations": obligations, "net_cash_flow": net, "foir_before": foir_before,
            "dscr": dscr, "banking_history_months": banking_months, "cheque_bounces": cheque_bounces,
            "nach_bounces": nach_bounces, "business_vintage_months": vintage, "cibil": cibil,
            "annual_turnover": revenue, "industry": prof.get("industry", "Manufacturing"),
        },
        "cash_flow_trend": trend,
        "positive_signals": positive,
        "risk_signals": risk,
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
    if key in KNOWN_PROFILES and force_known:
        decision = KNOWN_PROFILES[key]["decision"]

    base = compute_decision(application["borrower_name"], application["loan_type"], requested)
    return {
        "pd_score": pd_score, "risk_grade": grade, "decision": decision,
        "requested_amount": requested, "eligible_amount": final_eligible,
        "recommended_amount": recommended if decision != "reject" else max(0, min(recommended, final_eligible)),
        "roi": roi, "tenure_months": tenure, "emi": round(new_emi),
        "total_interest": round(total_interest), "total_repayment": round(total_repayment),
        "processing_fee": round(processing_fee), "net_disbursement": round(net_disbursement),
        "existing_emi": existing_emi, "post_loan_foir": round(post_loan_foir, 3),
        "eligibility_waterfall": [
            {"label": "Requested amount", "value": requested},
            {"label": "Policy maximum", "value": round(policy_max)},
            {"label": "Cash-flow eligibility", "value": round(cashflow_eligible / 50000) * 50000},
            {"label": "Collateral eligibility", "value": round(collateral_eligible / 50000) * 50000},
            {"label": "Final eligible", "value": final_eligible},
            {"label": "Recommended amount", "value": recommended},
        ],
        "reason_codes": base["reason_codes"],
        "cash_flow_summary": base["cash_flow_summary"],
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
                       system_message="You are a senior credit analyst at an Indian NBFC writing detailed, restrained credit appraisal memos.").with_model("openai", "gpt-5.4")
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
    for k in ("roi_rules", "required_documents", "conditions"):
        if body.get(k) is not None:
            new[k] = body[k]
    if body.get("policy_name"):
        new["policy_name"] = body["policy_name"]
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
    if decision and decision.get("credit_brain"):
        return {"application": application, "credit_brain": decision["credit_brain"],
                "computed": False}
    brain = credit_brain(application)
    return {"application": application, "credit_brain": brain, "computed": True}


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
    return {"application": application, "documents": documents, "decision": decision}


@api_router.get("/applications/{app_id}/audit")
async def get_audit(app_id: str, user: dict = Depends(get_current_user)):
    application = await db.applications.find_one({"id": app_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    events = await db.audit_log.find({"application_id": app_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return events


DOC_TYPE_LABELS = {"bank_statement": "Bank Statement", "itr": "ITR", "gst": "GST", "salary_slip": "Salary Slip"}


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

    result = compute_decision(application["borrower_name"], application["loan_type"], application["loan_amount"])
    policy = await get_active_policy()
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
        "override": None,
        "memo_text": memo_text,
        "memo_source": memo_source,
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


# ---------------------------------------------------------------------------
# Demo seed
# ---------------------------------------------------------------------------
SEED_APPS = [
    {"reference": "LS-2026-00124", "borrower_name": "Arvind Engineering Pvt Ltd", "loan_type": "MSME",
     "loan_amount": 3500000, "decide": True,
     "docs": [("bank_statement", "HDFC_Bank_Statement_FY25.pdf"), ("itr", "ITR_FY25.pdf"),
              ("gst", "GST_Returns_FY25.pdf"), ("salary_slip", "Promoter_Remuneration.pdf")]},
    {"reference": "LS-2026-00125", "borrower_name": "Sri Lakshmi Components", "loan_type": "business",
     "loan_amount": 2250000, "decide": True,
     "docs": [("bank_statement", "ICICI_Bank_Statement.pdf"), ("gst", "GST_Returns.pdf")]},
    {"reference": "LS-2026-00126", "borrower_name": "BluePeak Traders", "loan_type": "business",
     "loan_amount": 1500000, "decide": False, "docs": []},
]


@api_router.post("/demo/seed")
async def seed_demo(user: dict = Depends(get_current_user)):
    created = 0
    for s in SEED_APPS:
        existing = await db.applications.find_one({"reference": s["reference"]})
        if existing:
            continue
        created += 1
        app_id = str(uuid.uuid4())
        base_dt = now_utc() - timedelta(days=created, minutes=6)
        app_doc = {
            "id": app_id,
            "reference": s["reference"],
            "borrower_name": s["borrower_name"],
            "loan_type": s["loan_type"],
            "loan_amount": s["loan_amount"],
            "status": "pending",
            "created_at": iso(base_dt),
        }
        await db.applications.insert_one(app_doc)
        await db.audit_log.insert_one({"id": str(uuid.uuid4()), "application_id": app_id,
                                       "event": "Application Created", "actor": "System",
                                       "payload": {"reference": s["reference"]},
                                       "created_at": iso(base_dt)})
        for dtype, fname in s["docs"]:
            await db.documents.insert_one({
                "id": str(uuid.uuid4()), "application_id": app_id, "doc_type": dtype,
                "filename": fname, "file_path": None, "file_size": 240000 + len(fname) * 91,
                "status": "processed", "uploaded_at": iso(base_dt + timedelta(minutes=1)),
            })
        if s["docs"]:
            await db.audit_log.insert_one({"id": str(uuid.uuid4()), "application_id": app_id,
                                           "event": "Documents Uploaded", "actor": "System",
                                           "payload": {"count": len(s["docs"])},
                                           "created_at": iso(base_dt + timedelta(minutes=1))})
        if s["decide"]:
            application_obj = {"id": app_id, "reference": s["reference"], "borrower_name": s["borrower_name"],
                               "loan_type": s["loan_type"], "loan_amount": s["loan_amount"]}
            policy = await get_active_policy()
            full = compute_full_decision(application_obj, policy)
            memo = build_detailed_memo(application_obj, policy, full)
            dec_dt = base_dt + timedelta(minutes=full["tat_minutes"])
            await db.decisions.insert_one({
                "id": str(uuid.uuid4()), "application_id": app_id, **full,
                "model_decision": full["decision"], "override": None,
                "memo_text": memo, "memo_source": "template", "created_at": iso(dec_dt),
            })
            new_status = {"approve": "approved", "review": "review", "reject": "rejected"}.get(full["decision"], "decided")
            await db.applications.update_one({"id": app_id}, {"$set": {"status": new_status}})
            for ev, actor, pl in [
                ("Credit Brain Completed", "Credit Brain", {"pd_score": full["pd_score"], "risk_grade": full["risk_grade"]}),
                ("Policy Evaluated", "Credit Policy Engine", {"policy_version": full["policy_version"], "overall": full["policy_evaluation"]["overall"]}),
                ("Decision Generated", "Decision Engine", {"decision": full["decision"], "recommended_amount": full["recommended_amount"], "roi": full["roi"], "tenure_months": full["tenure_months"], "emi": full["emi"]}),
                ("Credit Memo Generated", "Decision Engine", {"model_version": full["model_version"]}),
            ]:
                await db.audit_log.insert_one({"id": str(uuid.uuid4()), "application_id": app_id, "event": ev,
                                               "actor": actor, "payload": pl, "created_at": iso(dec_dt)})
    return {"created": created, "message": "Sample portfolio loaded" if created else "Sample portfolio already present"}


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
    await get_active_policy()
    logger.info(f"LendSprint AI started. MOCK_MODE={MOCK_MODE}")


@app.on_event("shutdown")
async def shutdown():
    client.close()
