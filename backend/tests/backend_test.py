"""LendSprint AI backend integration tests."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-lending-hub-4.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "kiranmaadamshetti@gmail.com"
ADMIN_PASSWORD = "LendSprint@2026"


def _pdf_bytes(text: str = "Hello") -> bytes:
    # Minimal valid PDF
    return (b"%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
            b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] >>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000110 00000 n \n"
            b"trailer<< /Size 4 /Root 1 0 R >>\nstartxref\n180\n%%EOF")


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- Auth ---
class TestAuth:
    def test_login_success(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and data["user"]["email"] == ADMIN_EMAIL.lower()

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "bad"})
        assert r.status_code == 401

    def test_me_requires_auth(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_me_success(self, auth):
        r = requests.get(f"{API}/auth/me", headers=auth)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL.lower()


# --- Seed idempotency ---
class TestSeed:
    def test_seed_idempotent(self, auth):
        r1 = requests.post(f"{API}/demo/seed", headers=auth)
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/demo/seed", headers=auth)
        assert r2.status_code == 200
        assert r2.json()["created"] == 0
        # Verify 3 seeded apps exist
        apps = requests.get(f"{API}/applications", headers=auth).json()
        refs = {a["reference"] for a in apps}
        for ref in ["LS-2026-00124", "LS-2026-00125", "LS-2026-00126"]:
            assert ref in refs


# --- Dashboard stats ---
class TestDashboard:
    def test_stats(self, auth):
        r = requests.get(f"{API}/dashboard/stats", headers=auth)
        assert r.status_code == 200
        d = r.json()
        for k in ["total_applications", "straight_through_rate", "avg_tat", "pending_review"]:
            assert k in d
            assert isinstance(d[k], (int, float))


# --- Filters ---
class TestListFilters:
    def test_search_by_borrower(self, auth):
        r = requests.get(f"{API}/applications", params={"search": "BluePeak"}, headers=auth)
        assert r.status_code == 200
        apps = r.json()
        assert any("BluePeak" in a["borrower_name"] for a in apps)

    def test_status_filter(self, auth):
        r = requests.get(f"{API}/applications", params={"status": "pending"}, headers=auth)
        assert r.status_code == 200
        for a in r.json():
            assert a["status"] == "pending"

    def test_loan_type_filter(self, auth):
        r = requests.get(f"{API}/applications", params={"loan_type": "MSME"}, headers=auth)
        assert r.status_code == 200
        for a in r.json():
            assert a["loan_type"] == "MSME"


# --- Full application lifecycle ---
class TestApplicationFlow:
    def test_create_upload_decision_and_persist(self, auth):
        # Create
        payload = {"borrower_name": "TEST_ Borrower QA", "loan_type": "business", "loan_amount": 1200000}
        r = requests.post(f"{API}/applications", json=payload, headers=auth)
        assert r.status_code == 201, r.text
        app = r.json()
        app_id = app["id"]
        assert app["reference"].startswith("LS-")
        assert app["status"] == "pending"

        # Decision without documents -> 400
        r_nodoc = requests.post(f"{API}/applications/{app_id}/decision", headers=auth)
        assert r_nodoc.status_code == 400
        assert "document" in r_nodoc.json()["detail"].lower()

        # Non-PDF upload rejected
        files = [("files", ("bad.txt", io.BytesIO(b"hello"), "text/plain"))]
        data = [("doc_types", "bank_statement")]
        r_bad = requests.post(f"{API}/applications/{app_id}/documents", files=files, data=data, headers=auth)
        assert r_bad.status_code == 400

        # PDF upload OK
        files = [("files", ("statement.pdf", io.BytesIO(_pdf_bytes()), "application/pdf"))]
        data = [("doc_types", "bank_statement")]
        r_ok = requests.post(f"{API}/applications/{app_id}/documents", files=files, data=data, headers=auth)
        assert r_ok.status_code == 201, r_ok.text
        assert len(r_ok.json()) == 1

        # Verify document persisted
        detail = requests.get(f"{API}/applications/{app_id}", headers=auth).json()
        assert len(detail["documents"]) == 1

        # Run decision
        r_dec = requests.post(f"{API}/applications/{app_id}/decision", headers=auth)
        assert r_dec.status_code == 200, r_dec.text
        dec = r_dec.json()
        assert dec["decision"] in ("approve", "review", "reject")
        assert 0 < dec["pd_score"] < 1
        assert len(dec["reason_codes"]) >= 3
        assert dec["model_version"] == "mock-v1.0"
        assert dec["memo_text"] and len(dec["memo_text"].split()) > 50

        # Verify persisted after refresh
        detail2 = requests.get(f"{API}/applications/{app_id}", headers=auth).json()
        assert detail2["decision"]["pd_score"] == dec["pd_score"]
        assert detail2["application"]["status"] == "decided"

        # Audit trail contains all events
        audit = requests.get(f"{API}/applications/{app_id}/audit", headers=auth).json()
        events = [e["event"] for e in audit]
        for req in ["Application Created", "Documents Uploaded", "Decision Generated", "Credit Memo Generated"]:
            assert req in events, f"missing: {req}"

    def test_known_borrower_deterministic(self, auth):
        # BluePeak Traders (seeded, no docs) -> upload a doc then decide
        apps = requests.get(f"{API}/applications", params={"search": "BluePeak"}, headers=auth).json()
        assert apps, "seed missing"
        app_id = apps[0]["id"]
        detail = requests.get(f"{API}/applications/{app_id}", headers=auth).json()
        if not detail["documents"]:
            files = [("files", ("bs.pdf", io.BytesIO(_pdf_bytes()), "application/pdf"))]
            data = [("doc_types", "bank_statement")]
            r = requests.post(f"{API}/applications/{app_id}/documents", files=files, data=data, headers=auth)
            assert r.status_code == 201
        r_dec = requests.post(f"{API}/applications/{app_id}/decision", headers=auth)
        assert r_dec.status_code == 200
        dec = r_dec.json()
        # Known profile: bluepeak -> approve pd 0.214
        assert dec["decision"] == "approve"
        assert dec["pd_score"] == 0.214

    def test_not_found(self, auth):
        r = requests.get(f"{API}/applications/does-not-exist", headers=auth)
        assert r.status_code == 404


# --- Reports summary (new) ---
class TestReports:
    def test_summary_structure(self, auth):
        r = requests.get(f"{API}/reports/summary", headers=auth)
        assert r.status_code == 200, r.text
        s = r.json()
        for k in ["totals", "decision_mix", "loan_type_mix", "pd_distribution", "tat_by_type", "approval_by_type"]:
            assert k in s
        t = s["totals"]
        for k in ["applications", "decisions", "approval_rate", "avg_pd", "avg_tat", "overrides"]:
            assert k in t
        # decision_mix must include approve/review/reject keys
        keys = {d["key"] for d in s["decision_mix"]}
        assert {"approve", "review", "reject"}.issubset(keys)
        # pd buckets present
        buckets = {b["bucket"] for b in s["pd_distribution"]}
        assert {"0-15%", "15-25%", "25-40%", "40%+"}.issubset(buckets)


# --- Decision override (new) ---
class TestOverride:
    def _ensure_decided_app(self, auth):
        # Use seeded Sri Lakshmi Components (review) as target
        apps = requests.get(f"{API}/applications", params={"search": "Sri Lakshmi"}, headers=auth).json()
        assert apps, "seed missing"
        return apps[0]["id"]

    def test_override_empty_reason_rejected(self, auth):
        app_id = self._ensure_decided_app(auth)
        r = requests.post(f"{API}/applications/{app_id}/decision/override",
                          json={"decision": "approve", "reason": ""}, headers=auth)
        assert r.status_code == 422  # pydantic validation

    def test_override_success_and_audit(self, auth):
        app_id = self._ensure_decided_app(auth)
        # Fetch current decision
        det = requests.get(f"{API}/applications/{app_id}", headers=auth).json()
        current = det["decision"]["decision"]
        target = "approve" if current != "approve" else "reject"

        r = requests.post(f"{API}/applications/{app_id}/decision/override",
                          json={"decision": target, "reason": "TEST_override rationale from analyst"},
                          headers=auth)
        assert r.status_code == 200, r.text
        dec = r.json()
        assert dec["decision"] == target
        assert dec["override"] is not None
        assert dec["override"]["reason"] == "TEST_override rationale from analyst"
        assert dec["model_decision"] in ("approve", "review", "reject")

        # Verify persistence via GET
        det2 = requests.get(f"{API}/applications/{app_id}", headers=auth).json()
        assert det2["decision"]["decision"] == target
        assert det2["decision"]["override"]["reason"] == "TEST_override rationale from analyst"

        # Audit trail contains override event with from/to/reason
        audit = requests.get(f"{API}/applications/{app_id}/audit", headers=auth).json()
        ov_events = [e for e in audit if e["event"] == "Decision Overridden"]
        assert ov_events, "override audit event missing"
        p = ov_events[-1]["payload"]
        assert p["to"] == target
        assert p["reason"] == "TEST_override rationale from analyst"
        assert "from" in p

    def test_rerun_clears_override(self, auth):
        app_id = self._ensure_decided_app(auth)
        # Re-run decision
        r = requests.post(f"{API}/applications/{app_id}/decision", headers=auth)
        assert r.status_code == 200
        dec = r.json()
        assert dec["override"] is None
        assert dec["decision"] == dec["model_decision"]


# --- use_ai flag on decision (new) ---
class TestDecisionUseAi:
    def test_template_memo_source(self, auth):
        # Use BluePeak (must have docs after prior test); ensure a doc uploaded
        apps = requests.get(f"{API}/applications", params={"search": "BluePeak"}, headers=auth).json()
        app_id = apps[0]["id"]
        detail = requests.get(f"{API}/applications/{app_id}", headers=auth).json()
        if not detail["documents"]:
            files = [("files", ("bs.pdf", io.BytesIO(_pdf_bytes()), "application/pdf"))]
            data = [("doc_types", "bank_statement")]
            requests.post(f"{API}/applications/{app_id}/documents", files=files, data=data, headers=auth)
        r = requests.post(f"{API}/applications/{app_id}/decision", json={"use_ai": False}, headers=auth)
        assert r.status_code == 200
        assert r.json()["memo_source"] == "template"
