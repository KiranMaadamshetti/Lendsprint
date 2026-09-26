"""Backend tests for Contradiction Flags + Document Readiness feature."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-lending-hub-4.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = "kiranmaadamshetti@gmail.com"
ADMIN_PASS = "LendSprint@2026"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def apps(client):
    r = client.get(f"{BASE_URL}/api/applications", timeout=30)
    assert r.status_code == 200
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", [])
    mapping = {}
    for a in items:
        name = (a.get("borrower_name") or a.get("applicant_name") or a.get("business_name") or "").lower()
        if "arvind" in name:
            mapping["arvind"] = a.get("id") or a.get("_id")
        elif "sri lakshmi" in name or "lakshmi" in name:
            mapping["lakshmi"] = a.get("id") or a.get("_id")
        elif "bluepeak" in name:
            mapping["bluepeak"] = a.get("id") or a.get("_id")
    return mapping


def _cb(data):
    return data.get("credit_brain") or data


def test_arvind_ready_no_contradictions(client, apps):
    aid = apps.get("arvind")
    assert aid, "Arvind app not seeded"
    r = client.get(f"{BASE_URL}/api/credit-brain/{aid}", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "readiness" in data
    assert data["readiness"].get("ready") is True
    assert not data["readiness"].get("missing")
    contradictions = _cb(data).get("contradictions") or []
    assert len(contradictions) == 0


def test_lakshmi_blocked_contra_turnover(client, apps):
    aid = apps.get("lakshmi")
    assert aid
    r = client.get(f"{BASE_URL}/api/credit-brain/{aid}", timeout=30)
    assert r.status_code == 200
    data = r.json()
    readiness = data["readiness"]
    assert readiness["ready"] is False
    missing_codes = " ".join(readiness.get("missing", [])).lower()
    assert "itr" in missing_codes
    codes = [c.get("code") for c in _cb(data).get("contradictions") or []]
    assert "CONTRA-TURNOVER" in codes


def test_bluepeak_two_contradictions(client, apps):
    aid = apps.get("bluepeak")
    assert aid
    r = client.get(f"{BASE_URL}/api/credit-brain/{aid}", timeout=30)
    assert r.status_code == 200
    data = r.json()
    codes = [c.get("code") for c in _cb(data).get("contradictions") or []]
    assert "CONTRA-TURNOVER" in codes
    assert "CONTRA-INCOME" in codes
    missing = " ".join(data["readiness"].get("missing", [])).lower()
    assert "itr" in missing
    assert "gst" in missing


def test_run_decision_blocked_for_lakshmi(client, apps):
    aid = apps.get("lakshmi")
    r = client.post(f"{BASE_URL}/api/applications/{aid}/decision", json={}, timeout=60)
    assert r.status_code == 400, f"Expected 400 got {r.status_code}: {r.text}"
    body = r.json()
    msg = (body.get("detail") or body.get("message") or str(body)).lower()
    assert "blocked" in msg or "mandatory" in msg or "missing" in msg
    assert "itr" in msg


def test_run_decision_success_for_arvind(client, apps):
    aid = apps.get("arvind")
    r = client.post(f"{BASE_URL}/api/applications/{aid}/decision", json={}, timeout=90)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "decision" in body or "outcome" in body or "recommendation" in body or body


def test_contradiction_shape(client, apps):
    aid = apps.get("bluepeak")
    r = client.get(f"{BASE_URL}/api/credit-brain/{aid}", timeout=30)
    data = r.json()
    for c in _cb(data).get("contradictions") or []:
        for k in ["code", "label", "severity", "sources", "values"]:
            assert k in c, f"missing {k} in {c}"
