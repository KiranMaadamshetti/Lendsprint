"""Backend tests for Ask Credit Brain + Evidence Chain (iteration 5)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-lending-hub-4.preview.emergentagent.com").rstrip("/")
ADMIN = ("kiranmaadamshetti@gmail.com", "LendSprint@2026")

EVIDENCE_KEYS_REQUIRED = [
    "foir_before", "dscr", "annual_turnover", "avg_monthly_credits",
    "net_cash_flow", "existing_emi", "cibil",
]


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def arvind_id(headers):
    apps = requests.get(f"{BASE_URL}/api/applications", headers=headers, timeout=30).json()
    arvind = next((a for a in apps if "Arvind" in a.get("borrower_name", "")), None)
    assert arvind, "Arvind Engineering seed application not found"
    return arvind["id"]


# ---- Credit Brain Evidence ----

def test_credit_brain_returns_evidence(headers, arvind_id):
    r = requests.get(f"{BASE_URL}/api/credit-brain/{arvind_id}", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    cb = r.json()
    assert "credit_brain" in cb, cb.keys()
    assert "evidence" in cb["credit_brain"], list(cb["credit_brain"].keys())
    ev = cb["credit_brain"]["evidence"]
    for k in EVIDENCE_KEYS_REQUIRED:
        assert k in ev, f"missing evidence key {k}"
        item = ev[k]
        for field in ("source", "page", "calculation", "confidence", "formula", "inputs"):
            assert field in item, f"evidence[{k}] missing {field}"
        assert 0 <= item["confidence"] <= 1
        assert isinstance(item["inputs"], list)


# ---- Chat history ----

def test_get_brain_chat_initial(headers, arvind_id):
    r = requests.get(f"{BASE_URL}/api/applications/{arvind_id}/chat", headers=headers, timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_brain_chat_404(headers):
    r = requests.get(f"{BASE_URL}/api/applications/does-not-exist/chat", headers=headers, timeout=30)
    assert r.status_code == 404


# ---- Live Ask Brain (calls LLM, allow long timeout) ----

def test_ask_brain_grounded_question(headers, arvind_id):
    r = requests.post(f"{BASE_URL}/api/applications/{arvind_id}/ask",
                      headers=headers, json={"question": "Why was this application approved?"}, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "answer" in data and isinstance(data["answer"], str) and len(data["answer"]) > 10
    assert "session_id" in data
    # persisted to chat history
    hist = requests.get(f"{BASE_URL}/api/applications/{arvind_id}/chat", headers=headers, timeout=30).json()
    assert any(m["role"] == "user" and "approved" in m["content"].lower() for m in hist)
    assert any(m["role"] == "assistant" for m in hist)


def test_ask_brain_refuses_unrelated(headers, arvind_id):
    r = requests.post(f"{BASE_URL}/api/applications/{arvind_id}/ask",
                      headers=headers, json={"question": "What is the capital of France?"}, timeout=90)
    assert r.status_code == 200, r.text
    ans = r.json()["answer"].lower()
    # refusal indicators
    assert any(k in ans for k in ("only answer", "application", "cannot", "can't", "not able", "unable")), ans


def test_ask_brain_404(headers):
    r = requests.post(f"{BASE_URL}/api/applications/bogus/ask", headers=headers,
                      json={"question": "hi"}, timeout=30)
    assert r.status_code == 404
