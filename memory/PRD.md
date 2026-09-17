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
- Await user feedback on UI/flow; enable real LLM memo toggle in-product if desired; build out Reports module.
