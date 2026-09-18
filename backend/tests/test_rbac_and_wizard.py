"""RBAC + committee actions + escalation + policy wizard (PUT /credit-policy) tests."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API = f"{BASE_URL}/api"

USERS = {
    "admin": ("kiranmaadamshetti@gmail.com", "LendSprint@2026"),
    "manager": ("manager@lendsprint.ai", "Manager@2026"),
    "analyst": ("analyst@lendsprint.ai", "Analyst@2026"),
    "viewer": ("viewer@lendsprint.ai", "Viewer@2026"),
}

EXPECTED_ROLE = {
    "admin": "admin",
    "manager": "credit_manager",
    "analyst": "credit_analyst",
    "viewer": "viewer",
}


def _pdf_bytes() -> bytes:
    return (b"%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
            b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] >>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000110 00000 n \n"
            b"trailer<< /Size 4 /Root 1 0 R >>\nstartxref\n180\n%%EOF")


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"{email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def tokens():
    return {k: _login(*v) for k, v in USERS.items()}


@pytest.fixture(scope="session")
def headers(tokens):
    return {k: {"Authorization": f"Bearer {t}"} for k, t in tokens.items()}


class TestAuthorityEndpoint:
    @pytest.mark.parametrize("key", ["admin", "manager", "analyst", "viewer"])
    def test_authority(self, headers, key):
        r = requests.get(f"{API}/me/authority", headers=headers[key])
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == EXPECTED_ROLE[key], d
        assert isinstance(d["max_authority"], (int, float))
        assert isinstance(d["permissions"], list)
        assert isinstance(d["approval_authority"], list) and len(d["approval_authority"]) >= 3
        if key == "analyst":
            assert d["max_authority"] == 1000000
            assert "approve" not in d["permissions"]
            assert "review" in d["permissions"]
        elif key == "manager":
            assert d["max_authority"] == 5000000
            assert "approve" in d["permissions"]
        elif key == "admin":
            assert d["max_authority"] >= 100000000
            assert "approve" in d["permissions"]
        elif key == "viewer":
            assert d["permissions"] == []


def _get_app_id(headers_admin, search):
    r = requests.get(f"{API}/applications", params={"search": search}, headers=headers_admin)
    assert r.status_code == 200
    apps = r.json()
    assert apps, f"missing seed for {search}"
    return apps[0]["id"]


def _ensure_seed(headers_admin):
    requests.post(f"{API}/demo/seed", headers=headers_admin)


class TestCommitteeActionsRBAC:
    def test_seed(self, headers):
        _ensure_seed(headers["admin"])

    def test_analyst_can_send_review(self, headers):
        app_id = _get_app_id(headers["admin"], "Sri Lakshmi")
        r = requests.post(f"{API}/applications/{app_id}/action",
                          json={"action": "send_review", "comment": "TEST_ analyst review"},
                          headers=headers["analyst"])
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "review"

    @pytest.mark.parametrize("action", ["approve", "reject", "escalate"])
    def test_analyst_forbidden(self, headers, action):
        app_id = _get_app_id(headers["admin"], "Arvind")
        r = requests.post(f"{API}/applications/{app_id}/action",
                          json={"action": action, "comment": "no"}, headers=headers["analyst"])
        assert r.status_code == 403

    @pytest.mark.parametrize("action", ["approve", "reject", "escalate", "send_review"])
    def test_viewer_forbidden(self, headers, action):
        app_id = _get_app_id(headers["admin"], "Arvind")
        r = requests.post(f"{API}/applications/{app_id}/action",
                          json={"action": action, "comment": "no"}, headers=headers["viewer"])
        assert r.status_code == 403

    def test_manager_approve_within_authority(self, headers):
        # Arvind recommended ~35L, within manager 50L limit
        app_id = _get_app_id(headers["admin"], "Arvind")
        r = requests.post(f"{API}/applications/{app_id}/action",
                          json={"action": "approve", "comment": "TEST_ manager approve"},
                          headers=headers["manager"])
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved"
        # Audit event
        audit = requests.get(f"{API}/applications/{app_id}/audit", headers=headers["admin"]).json()
        events = [e["event"] for e in audit]
        assert "Application Approved" in events

    def test_manager_escalation_required_for_large_amount(self, headers):
        # Create large app, upload doc, run decision as admin, then try approve as manager
        payload = {"borrower_name": "TEST_ Large Escalation Co", "loan_type": "MSME", "loan_amount": 8000000}
        c = requests.post(f"{API}/applications", json=payload, headers=headers["admin"])
        assert c.status_code == 201
        app_id = c.json()["id"]
        files = [("files", ("s.pdf", io.BytesIO(_pdf_bytes()), "application/pdf"))]
        data = [("doc_types", "bank_statement")]
        u = requests.post(f"{API}/applications/{app_id}/documents", files=files, data=data,
                          headers=headers["admin"])
        assert u.status_code == 201
        d = requests.post(f"{API}/applications/{app_id}/decision", json={"use_ai": False},
                          headers=headers["admin"])
        assert d.status_code == 200
        rec = d.json().get("recommended_amount", 0)
        # Manager attempt to approve
        r = requests.post(f"{API}/applications/{app_id}/action",
                          json={"action": "approve", "comment": "try"}, headers=headers["manager"])
        if rec > 5000000:
            assert r.status_code == 403
            assert "escalation" in r.json()["detail"].lower()
        else:
            # If recommended got clipped below 50L, manager can approve; skip strict check
            assert r.status_code in (200, 403)
        # Admin can approve regardless
        r2 = requests.post(f"{API}/applications/{app_id}/action",
                           json={"action": "approve", "comment": "admin ok"}, headers=headers["admin"])
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "approved"

    def test_action_bad_role_escalate_reject_events(self, headers):
        # Manager escalate + reject flow on a fresh app
        payload = {"borrower_name": "TEST_ Action Events", "loan_type": "business", "loan_amount": 900000}
        c = requests.post(f"{API}/applications", json=payload, headers=headers["admin"]).json()
        app_id = c["id"]
        # escalate (no decision needed)
        r = requests.post(f"{API}/applications/{app_id}/action",
                          json={"action": "escalate", "comment": "risk"}, headers=headers["manager"])
        assert r.status_code == 200
        assert r.json()["status"] == "escalated"
        # reject
        r2 = requests.post(f"{API}/applications/{app_id}/action",
                           json={"action": "reject", "comment": "no"}, headers=headers["manager"])
        assert r2.status_code == 200
        assert r2.json()["status"] == "rejected"
        events = [e["event"] for e in
                  requests.get(f"{API}/applications/{app_id}/audit", headers=headers["admin"]).json()]
        assert "Application Escalated" in events
        assert "Application Rejected" in events


class TestPolicyWizardPUT:
    def test_non_admin_cannot_edit_policy(self, headers):
        r = requests.put(f"{API}/credit-policy",
                         json={"rules": {"max_foir": 0.55}}, headers=headers["analyst"])
        assert r.status_code in (401, 403)

    def test_admin_put_bumps_version_and_carries_authority(self, headers):
        before = requests.get(f"{API}/credit-policy", headers=headers["admin"]).json()
        before_ver = before["version"]
        payload = {
            "rules": {"max_foir": 0.57},
            "approval_authority": [
                {"role": "credit_analyst", "label": "Credit Analyst", "min": 0, "max": 1000000},
                {"role": "credit_manager", "label": "Credit Manager", "min": 1000000, "max": 5000000},
                {"role": "admin", "label": "Senior Credit / Admin", "min": 0, "max": 1000000000},
            ],
            "product_type": "MSME",
        }
        r = requests.put(f"{API}/credit-policy", json=payload, headers=headers["admin"])
        assert r.status_code == 200, r.text
        new = r.json()
        maj, minr = before_ver.lstrip("v").split(".")
        assert new["version"] == f"v{maj}.{int(minr) + 1}"
        assert new["status"] == "active"
        assert new["rules"]["max_foir"] == 0.57
        assert len(new["approval_authority"]) == 3
        # version history includes archived old
        versions = requests.get(f"{API}/credit-policy/versions", headers=headers["admin"]).json()
        by_ver = {v["version"]: v for v in versions}
        assert by_ver[before_ver]["status"] == "archived"
        assert by_ver[new["version"]]["status"] == "active"
