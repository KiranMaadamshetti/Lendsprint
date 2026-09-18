# LendSprint AI — PRD

## Original problem statement
Build a production-quality full-stack fintech app: **LendSprint AI**, an explainable AI credit-decisioning platform for mid-market Indian NBFCs. Flow: borrower application → upload financial documents → AI/document analysis → credit risk decision → explainable reason codes → cash-flow analysis → auto-generated credit memo → complete audit trail. Start with MOCK_MODE enabled; must work locally without external AI APIs. Enterprise, data-dense, restrained UI (light lavender-gray canvas, white surfaces, thin borders, navy primary, muted status badges). Reference screenshots used for visual language only.

## User choices
- AI: Mock now (deterministic), with optional real LLM (Emergent key) memo generation when MOCK_MODE=false.
- Auth: Simple single-user JWT login.
- Stack: React (CRA) + FastAPI + MongoDB.
- Admin/owner account: kiranmaadamshetti@gmail.com.

## Architecture
- Frontend: React, Tailwind, shadcn/ui, lucide-react, sonner. API layer in `lib/api.js`. AuthContext + ProtectedRoute + AppShell (Header + Sidebar).
- Backend: FastAPI single module `server.py`; collections: `users`, `applications`, `documents`, `decisions`, `audit_log`. JWT (Bearer) auth, bcrypt hashing, admin seeded on startup.
- Decision engine: deterministic `compute_decision()` (mock). Memo: template in mock mode, LLM (`generate_ai_memo`, gpt-5.4 via emergentintegrations) when MOCK_MODE=false.

## User personas
- Credit analyst / operations team at an NBFC: reviews applications, runs decisions, reads memos, checks audit trail.

## Core requirements (static)
- Auth-gated enterprise shell (Dashboard, Applications; Decisioning/Reports/Audit gated).
- Dashboard: 4 stat cards + filterable/searchable applications table + Load sample data + New application.
- New Application: details form + PDF drag-drop upload with per-file doc type.
- Application Detail: identity header, summary strip, tabs (Overview, Documents, Decision, Credit Memo, Audit Trail).
- Decision: empty state → processing sequence → decision card + PD gauge + cash-flow summary + explainable reason codes.
- Credit Memo: ~150-word AI-drafted memo + Copy.
- Audit Trail: chronological events with expandable JSON payloads; every decision writes audit records.
- Deterministic mock mode, no external calls. Real persistence in MongoDB.

## Implemented (2026-06-17)
- ✅ JWT single-user auth + login page; admin seeded from env.
- ✅ Applications CRUD-lite: create, list (search/status/loan_type filters), detail.
- ✅ PDF upload (multipart, PDF-only validation, safe filenames, local storage), download, delete.
- ✅ Deterministic mock decision engine: PD score, decision (approve/review/reject), reason codes + weights, cash-flow summary + coverage.
- ✅ AI-drafted credit memo (template in mock; LLM path wired for MOCK_MODE=false) + copy-to-clipboard.
- ✅ Audit trail with expandable JSON payloads; audit records on create/upload/decision/memo.
- ✅ Idempotent demo seed (3 sample applications). Dashboard stats.
- ✅ Enterprise UI matching reference visual language; responsive; toasts; loading/empty/error states.
- ✅ E2E tested: 12/12 backend pytest + all 14 UI flows passed (iteration_1).

## Backlog
- **P1:** Split `server.py` into routers (auth/applications/documents/decisions/demo) for maintainability.
- **P1:** Migrate deprecated `@app.on_event` to FastAPI lifespan handlers.
- **P2:** Real document intelligence pipeline (OCR → field extraction → ratios → policy) — TODO block in server.py.
- **P2:** In-app PDF preview/viewer.
- **P2:** Global ⌘K search, notifications, Reports/Decisioning modules.
- **P2:** Multi-user roles / RBAC (currently intentionally single-user).

## Next tasks
- Await user feedback; then Phase 2.

## CREDIT BRAIN — Phase 1 (2026-06-18)
Shipped end-to-end (backend + frontend, tested 28/28 backend + full frontend E2E):
- ✅ Credit Policy Engine: configurable rules, ROI/tenure slabs, decision matrix; GET/PUT with version bump + archive (versioning), version history. Admin/credit_manager gated.
- ✅ Policy Simulator: preview current vs proposed decision mix + per-borrower changes without activating.
- ✅ Credit Brain analysis layer: derived financials (turnover, credits, balance, FOIR, DSCR, vintage, CIBIL, bounces), cash-flow trend, positive/risk signals with evidence + source.
- ✅ Loan Eligibility waterfall (requested → policy max → cash-flow → collateral → final → recommended).
- ✅ ROI/Tenure/EMI engine (risk-grade slabs, reducing-balance EMI, total interest/repayment, processing fee, post-loan FOIR).
- ✅ Expanded Decision screen: loan structure, waterfall, why approved/review/rejected, policy rules triggered, PD gauge, risk grade.
- ✅ Policy Evaluation screen: overall PASS/REVIEW/FAIL, rule table with expandable detail + severity.
- ✅ Detailed credit memo (~740 words, 17 sections) + PDF download (print); live-LLM path via AI toggle.
- ✅ Expanded decisions model (eligible/recommended/roi/tenure/emi/risk_grade/policy_evaluation/credit_brain/signals/conditions/policy_version) + audit events (Credit Brain Completed, Policy Evaluated, Decision Generated, Memo Generated, Policy Updated/Activated).
- ✅ Dashboard columns (Product, Requested, Recommended, EMI) + expanded stats. Demo: Arvind→approve/B, Sri Lakshmi→review/C, BluePeak→reject.

## Role Access + Policy Wizard (2026-06-18)
Shipped + tested (46/46 backend + full frontend E2E):
- ✅ RBAC roles: admin, credit_manager, credit_analyst, viewer (seeded demo users). Header role badge.
- ✅ Approval authority slabs + escalation: approve blocked (403) when recommended amount exceeds caller's authority; committee actions (send_review/approve/reject/escalate) gated by role + audited; bar hidden at terminal status.
- ✅ 10-step no-code Policy Configuration Wizard (/credit-policy/wizard) creating a new active policy version; Approval Authority table on policy page.

## Phase 2 backlog (agreed, deferred)
- P1: Google Drive + OneDrive OAuth ingestion (needs Google/Microsoft app credentials) with DocumentSourceProvider abstraction; mock providers interim.
- P1: Remaining Phase-1 spec items — per-app What-If simulator, Why-Not view, Decision Trace, Credit Committee dedicated view, PD vs Data Confidence, contradiction detection, missing-evidence readiness, decision-quality feedback, Policy Replay, Policy version comparison, Decision Queue.
- P2: Editable extracted financials with change audit; Financials tab; Credit Policy & Credit Brain analytics dashboards.

## Decision Trace (2026-06-18)
Shipped + tested (iteration_6, frontend-only, 95% — no bugs):
- ✅ New "Trace" tab on Application Detail: interactive 6-stage flow Documents → Extraction → Credit Brain → Policy → Structuring → Decision. Clickable nodes with status dots; each opens a detail panel (docs list, extracted financials, PD/grade/FOIR/DSCR + signals, policy rule table, eligibility waterfall + terms, final decision). Built entirely from existing GET /api/applications/{id} data; empty state prompts Run Decision. Component: DecisionTraceTab.js.

## Ask Credit Brain + Evidence Chain (2026-06-18)
Shipped + tested (iteration_5: 6/6 backend + full frontend E2E, 100%):
- ✅ Ask Credit Brain: new "Ask Brain" tab on Application Detail. Application-grounded LLM assistant (Emergent LLM key, OpenAI gpt-5.4 via emergentintegrations, LIVE not mocked). Preset chips (why approved / why this amount / key risks / rules triggered) + free-text. Answers cite figures & policy rule IDs; refuses out-of-scope questions. Chat persisted in `brain_chats` collection; history rehydrates on reload. Endpoints: POST /api/applications/{id}/ask {question, session_id?}, GET /api/applications/{id}/chat.
- ✅ Evidence Chain: every Credit Brain financial figure (FOIR, DSCR, turnover, avg credits, balance, net cash flow, existing EMI, CIBIL, vintage, bounces) is clickable → right-side Sheet with value, calculation formula + inputs, source document + page ref, and extraction confidence (deterministic mock attribution). Wired into Credit Brain tab (12 metrics) and Decision tab (3 cash-flow cards). Backend `build_evidence()` adds `evidence` to credit_brain output; GET /credit-brain/{id} and GET /applications/{id} backfill evidence for decisions computed before this feature.
