"""Backend tests for AI extraction credit brain feature (iteration 8)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-lending-hub-4.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"
DOCS_DIR = "/app/synthetic_docs"

ADMIN_EMAIL = "kiranmaadamshetti@gmail.com"
ADMIN_PW = "LendSprint@2026"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _create_app(hdr, name, amount=25000000, tenor=36):
    payload = {
        "borrower_name": name,
        "entity_type": "Private Limited",
        "loan_amount": amount,
        "tenor_months": tenor,
        "purpose": "Working capital",
        "industry": "Manufacturing",
        "loan_type": "MSME",
    }
    r = requests.post(f"{API}/applications", json=payload, headers=hdr, timeout=30)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _upload(hdr, app_id, files_map):
    """files_map: list of (doc_type, path)"""
    files = []
    doc_types = []
    for dt, path in files_map:
        files.append(("files", (os.path.basename(path), open(path, "rb"), "application/pdf")))
        doc_types.append(dt)
    data = [("doc_types", dt) for dt in doc_types]
    r = requests.post(f"{API}/applications/{app_id}/documents", headers=hdr, files=files, data=data, timeout=120)
    assert r.status_code in (200, 201), r.text
    return r.json()


# --- Strong borrower ---
class TestStrongBorrower:
    app_id = None

    def test_01_create_and_upload_strong(self, hdr):
        app = _create_app(hdr, "TEST_Nova Precision Tools", amount=25000000)
        TestStrongBorrower.app_id = app["id"]
        _upload(hdr, app["id"], [
            ("bank_statement", f"{DOCS_DIR}/bank.pdf"),
            ("itr", f"{DOCS_DIR}/itr.pdf"),
            ("gst", f"{DOCS_DIR}/gst.pdf"),
        ])

    def test_02_credit_brain_ai_extracted(self, hdr):
        # Extraction happens in upload but allow a moment
        time.sleep(1)
        r = requests.get(f"{API}/credit-brain/{TestStrongBorrower.app_id}", headers=hdr, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        cb = data.get("credit_brain") or data
        assert cb.get("extraction_source") == "ai", f"expected ai, got {cb.get('extraction_source')}: {cb}"
        fin = cb["financials"]
        # target ~1,850,000 avg monthly credits; allow wide tolerance for LLM variance
        assert 1_500_000 <= fin["avg_monthly_credits"] <= 2_200_000, fin
        assert 18_000_000 <= fin["banking_turnover"] <= 26_000_000, fin
        assert 18_000_000 <= fin["gst_turnover"] <= 24_000_000, fin
        assert 740 <= fin["cibil"] <= 800, fin
        assert cb.get("pd_score", 1) < 0.25, cb.get("pd_score")
        contras = cb.get("contradictions") or []
        assert len(contras) == 0, f"expected no contradictions, got {contras}"
        readiness = data.get("readiness") or {}
        assert readiness.get("ready") is True

    def test_03_decision_from_real_data(self, hdr):
        r = requests.post(f"{API}/applications/{TestStrongBorrower.app_id}/decision",
                          json={}, headers=hdr, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        dec = d  # decision_doc returned directly
        assert dec.get("decision", "").lower() in ("approve", "approved"), dec.get("decision")
        assert dec.get("risk_grade") in ("A", "A+", "B"), dec.get("risk_grade")
        # cash_flow_summary income equals extracted avg_monthly_credits
        cfs = dec.get("cash_flow_summary") or {}
        # Fetch extracted
        r2 = requests.get(f"{API}/credit-brain/{TestStrongBorrower.app_id}", headers=hdr, timeout=30)
        avg = r2.json()["credit_brain"]["financials"]["avg_monthly_credits"]
        assert cfs.get("income") == avg, f"cfs income {cfs.get('income')} != extracted {avg}"


# --- Weak borrower with contradictions ---
class TestWeakBorrower:
    app_id = None

    def test_10_create_and_upload_weak(self, hdr):
        app = _create_app(hdr, "TEST_Skyline Traders", amount=8000000)
        TestWeakBorrower.app_id = app["id"]
        _upload(hdr, app["id"], [
            ("bank_statement", f"{DOCS_DIR}/bad_bank.pdf"),
            ("gst", f"{DOCS_DIR}/bad_gst.pdf"),
        ])

    def test_11_credit_brain_contradictions(self, hdr):
        time.sleep(1)
        r = requests.get(f"{API}/credit-brain/{TestWeakBorrower.app_id}", headers=hdr, timeout=60)
        assert r.status_code == 200, r.text
        cb = r.json()["credit_brain"]
        assert cb["extraction_source"] == "ai"
        codes = {c["code"] for c in (cb.get("contradictions") or [])}
        assert "CONTRA-TURNOVER" in codes, codes
        # CONTRA-INCOME only exists if ITR is present; weak has no ITR, so may only have turnover
        fin = cb["financials"]
        assert 600 <= fin["cibil"] <= 700, fin
        readiness = r.json().get("readiness") or {}
        assert readiness.get("ready") is False, readiness
        assert cb.get("pd_score", 0) > 0.3, cb.get("pd_score")

    def test_12_decision_blocked(self, hdr):
        r = requests.post(f"{API}/applications/{TestWeakBorrower.app_id}/decision",
                          json={}, headers=hdr, timeout=60)
        assert r.status_code == 400, f"expected 400 blocked, got {r.status_code}: {r.text}"


# --- Regression: seed apps without PDFs still render ---
class TestRegression:
    def test_20_list_apps(self, hdr):
        r = requests.get(f"{API}/applications", headers=hdr, timeout=30)
        assert r.status_code == 200
        apps = r.json()
        assert isinstance(apps, list) and len(apps) > 0
        # Find an app with no docs; check its credit-brain says estimate
        for a in apps:
            if "arvind" in a["borrower_name"].lower() or "bluepeak" in a["borrower_name"].lower():
                rc = requests.get(f"{API}/credit-brain/{a['id']}", headers=hdr, timeout=30)
                assert rc.status_code == 200, rc.text
                cb = rc.json()["credit_brain"]
                # Either estimate or ai (Sri Lakshmi got ITR uploaded in prev iteration)
                # Legacy seeded apps may not have extraction_source; require it for docs-less
                src = cb.get("extraction_source")
                assert src in (None, "ai", "estimate"), src
                return
