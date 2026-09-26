# LendSprint AI

**Explainable, genuinely AI-driven credit decisioning for mid-market Indian NBFCs.**

LendSprint AI takes a borrower application from raw document intake to an auditable, explainable credit decision. Unlike a rules-only prototype, it **reads the actual uploaded documents** — bank statements, CIBIL reports, GST returns, ITRs — using real OCR and an LLM, then runs the extracted numbers through a deterministic underwriting engine.

> Borrower application → Upload financial documents → **Mistral OCR** text/markdown → **GPT-5.6-sol** structured extraction (CIBIL, banking, GST, anomalies) → Credit Brain analysis → Configurable Credit Policy evaluation → Loan structuring (eligibility waterfall, ROI/tenure/EMI) → Explainable decision & reason codes → AI credit memo → Complete audit trail.

> ⚠️ This is **not** a mock/demo engine. There is no hardcoded borrower table driving outcomes. Every decision is derived from data extracted from the documents you upload.

---

## What makes it "genuinely AI"

- **Real OCR:** Every uploaded PDF/image is sent to **Mistral OCR** (`mistral-ocr-latest`) to produce text + markdown — handles scanned statements and images, not just digital PDFs. `pypdf` is retained only as a silent fallback.
- **Real extraction:** **GPT-5.6-sol** (via the Emergent LLM key) reads the OCR output and returns strict structured JSON: turnover, monthly credits/debits/closing balances, FOIR, DSCR, vintage, bounces, a full **CIBIL report** (score, tradelines, worst DPD, enquiries) and a **bank-statement analysis** (avg balance, EMI count, top credit/debit sources, cash-flow pattern).
- **Anomaly detection:** Flags online rummy/gambling, fantasy gaming, betting, large cash withdrawals, unexplained deposits and payment returns — with amount and severity. High-severity anomalies and DPD/overdue events become risk signals that can downgrade a decision.
- **Deterministic decisioning on real data:** The PD score is a transparent function of the extracted metrics; the final decision comes from the configurable policy engine — so it stays defensible and reproducible.

---

## Key features

- **Credit Brain analysis** — derived financials, cash-flow trend, positive/risk signals, each backed by an **evidence chain** (value → formula → source document/page → confidence).
- **Risk Radar** — a 0–100 composite (Bureau Health, Repayment Track, Banking Conduct, Cash Flow) with a Low/Moderate/High band.
- **CIBIL classification** — DPD-dominant rating: max DPD ≥90 → Danger; 7 < DPD < 90 → Not a Good Customer; else score ≥750 Excellent, ≥650 Good, otherwise Average.
- **Contradiction flags** — cross-source integrity checks (GST turnover vs banking, ITR income vs banking credits) with severity and % variance.
- **Loan eligibility waterfall** — fully expandable step-by-step structuring (Requested → Policy max → Cash-flow → Collateral → Final eligible → Recommended) showing exact formulas, inputs and the binding constraint, plus reducing-balance EMI, ROI/tenure slabs and post-loan FOIR.
- **Configurable Credit Policy** — versioned rules, ROI/tenure slabs and decision matrix, a 10-step no-code Policy Wizard, and a Policy Simulator (preview decision-mix impact before activating).
- **RBAC** — admin, credit_manager, credit_analyst, viewer roles; approval-authority slabs with escalation; committee actions gated and audited.
- **Ask Credit Brain** — an application-grounded LLM assistant that cites figures and policy rule IDs.
- **Decision Trace** — interactive Documents → Extraction → Credit Brain → Policy → Structuring → Decision flow.
- **AI credit memo** — detailed multi-section appraisal memo with PDF/print export.
- **Full audit trail** — every stage (Documents Analysed, Credit Brain Completed, Policy Evaluated, Decision Generated, Memo Generated, Policy Updated/Activated) is recorded with expandable JSON payloads.

---

## Architecture

- **Frontend:** React (CRA + CRACO), Tailwind CSS, shadcn/ui, lucide-react, sonner.
- **Backend:** FastAPI (Python), Motor (async MongoDB driver), PyJWT + bcrypt auth.
- **Database:** MongoDB.
- **AI:** Mistral OCR (document text/markdown) + GPT-5.6-sol via the Emergent integrations layer (extraction, credit memo, Ask Brain).
- **Auth:** JWT (Bearer token in `Authorization` header; stored in `localStorage`) with role-based access control.

```
/app
├── backend/
│   ├── server.py          # FastAPI app: auth, applications, documents, OCR + LLM extraction,
│   │                      #   Credit Brain, policy engine, decisions, Ask Brain, audit
│   ├── requirements.txt
│   └── .env               # server-side secrets (never committed) — see .env.example
└── frontend/
    └── src/
        ├── pages/         # Login, Dashboard, NewApplication, ApplicationDetail, CreditPolicy, PolicyWizard
        ├── components/
        │   ├── layout/    # AppShell, Sidebar, Header
        │   ├── common/    # StatusBadge, PdGauge, etc.
        │   └── application/  # CreditBrainTab, DecisionTab, AskBrainTab, EvidencePanel,
        │                     #   DecisionTraceTab, MemoTab, AuditTab
        ├── context/       # AuthContext
        └── lib/           # api.js (API layer), format.js
```

> Note: `backend/server.py` is intentionally the current single module and is scheduled to be split into routers/services/models (see Roadmap).

---

## Environment variables (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and fill in your own values. **Never commit real secrets.**

| Variable           | Purpose                                                            |
|--------------------|--------------------------------------------------------------------|
| `MONGO_URL`        | MongoDB connection string                                          |
| `DB_NAME`          | Database name                                                      |
| `CORS_ORIGINS`     | Allowed origins                                                    |
| `JWT_SECRET`       | JWT signing secret                                                 |
| `ADMIN_EMAIL`      | Seeded admin account email                                        |
| `ADMIN_PASSWORD`   | Seeded admin account password                                     |
| `EMERGENT_LLM_KEY` | Emergent universal key used for all GPT-5.6-sol calls (extraction, memo, Ask Brain) |
| `MISTRAL_API_KEY`  | Mistral API key used for document OCR (`mistral-ocr-latest`)       |

Frontend (`frontend/.env`): `REACT_APP_BACKEND_URL` — the public backend URL the SPA calls.

All keys are used **server-side only** and are never exposed to the browser.

---

## Running

Both services are supervised in this environment:

```
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
```

- Backend binds `0.0.0.0:8001`; all routes are prefixed with `/api`.
- Frontend calls the backend via `REACT_APP_BACKEND_URL`.
- Local dev (outside supervisor): `uvicorn server:app --reload --port 8001` (backend) and `yarn start` (frontend).

Install dependencies: `pip install -r backend/requirements.txt` and `yarn install` inside `frontend/`.

---

## API endpoints (selected)

| Method | Path                                      | Description                                        |
|--------|-------------------------------------------|----------------------------------------------------|
| POST   | `/api/auth/login`                         | Returns `{ token, user }`                          |
| GET    | `/api/auth/me`                            | Current user (Bearer)                              |
| POST   | `/api/applications`                       | Create application                                 |
| GET    | `/api/applications`                       | List (search / status / loan_type filters)         |
| GET    | `/api/applications/{id}`                  | Application + documents + decision + credit brain  |
| POST   | `/api/applications/{id}/documents/upload` | Upload documents → Mistral OCR + GPT-5.6 extraction |
| POST   | `/api/applications/{id}/decision`         | Run the decision engine on extracted data          |
| POST   | `/api/applications/{id}/ask`              | Ask Credit Brain assistant                         |
| GET    | `/api/applications/{id}/chat`             | Ask Brain chat history                             |
| GET    | `/api/applications/{id}/audit`            | Audit trail                                        |
| GET    | `/api/credit-policy` / `PUT`              | Get / update active credit policy (versioned)      |
| GET    | `/api/dashboard/stats`                    | Portfolio metrics                                  |

---

## Demo flow (< 3 minutes)

1. Sign in with the admin account.
2. Create a **New Application** (borrower, loan type, requested amount).
3. **Documents** tab → **Add documents** → upload bank statement / CIBIL / GST PDFs (classify each). Watch the OCR + AI extraction run.
4. **Credit Brain** tab → review Risk Radar, CIBIL analysis, bank-statement analysis, anomalies, contradictions and the evidence chain.
5. **Run Decision** → see the decision badge, PD gauge, and the fully expandable eligibility waterfall with formulas and the binding constraint.
6. **Ask Brain** tab → ask "why this amount?" or "key risks?" — answers cite real figures and policy rules.
7. **Credit Memo** tab → export the appraisal memo.
8. **Audit Trail** tab → expand any event to inspect the JSON payload.

> Sample synthetic documents can be generated with `python gen_docs.py` (clean profile) and `python gen_bad.py` (risky profile with gambling anomalies) — useful for testing the extraction pipeline end-to-end.

---

_This is a decision-support platform for NBFC credit teams. It surfaces explainable, traceable recommendations; final credit sanctions remain the responsibility of authorised approvers. No regulatory certification is claimed._
