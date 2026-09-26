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

## Loan Eligibility Calculation makeover (2026-06-18)
Shipped + tested (iteration_10: frontend 100%, backend curl-verified, no bugs):
- ✅ Each eligibility_waterfall step now carries kind/binding/formula/calculation/inputs; decision exposes top-level binding_constraint. compute_full_decision builds the enriched steps (Requested, Policy maximum, Cash-flow, Collateral, Final eligible, Recommended) with real-number calculations.
- ✅ Decision-tab UI reworked into an expandable, fully-explained flow: click any step to reveal its formula, calculation with numbers and input chips; binding constraint highlighted (amber 'binding' tag + 'Binding: X' header chip); bottom 'How the number was reached' flow summary (Requested → Ceilings → Binding → Recommended → decision) with EMI/FOIR/interest/repayment line. Testids: eligibility-waterfall, binding-constraint, wf-step-{slug} (no trailing dash), wf-detail-{slug}, eligibility-flow-summary. openStep useState declared before early returns (no hook-order issue).

## CIBIL Classification Rules (2026-06-18)
- ✅ `classify_cibil(score, max_dpd)` rates every bureau profile; DPD is the dominant gate: max DPD ≥90 → **Danger / Bad Profile** (critical); 7 < DPD < 90 → **Not a Good Customer** (review); DPD ≤7 (or none) → score ≥750 **Excellent**, ≥650 **Good**, else **Average**. Tolerance constant CIBIL_DPD_TOLERANCE=7. Exposed as credit_brain.cibil_rating and shown as a coloured badge + reason line in the CIBIL section (data-testid cibil-rating). Verified: 771/0d=Excellent, 648/62d=Not a Good Customer, 760/120d=Danger, 640/0d=Average.

## Risk Radar + Month-wise Banking (2026-06-18)
- ✅ **Risk Radar**: backend `compute_risk_radar()` produces a 0-100 composite (higher = safer) from four sub-scores — Bureau Health (CIBIL), Repayment Track (DPD/overdue), Banking Conduct (anomalies + bounces), Cash Flow (DSCR/FOIR/net) — plus a band (Low/Moderate/High). Rendered as a coloured band with factor bars at the top of the Credit Brain tab (data-testid risk-radar, risk-radar-score, risk-radar-band). Verified: strong=92/Low, risky=31/High.
- ✅ **Month-wise banking**: extraction schema + prompt now capture `banking_analysis.monthly_breakdown` (per-month credits/debits/closing balance); shown as a "Month-wise Summary" table (data-testid monthly-breakdown, month-row-N) in Bank Statement Analysis, alongside the existing average monthly balance tile. Demo docs include 12 months of data.

## Deep CIBIL + Bank-Statement Analysis (2026-06-18)
Shipped + tested (iteration_9: frontend 100%, backend curl-verified, zero issues):
- ✅ On upload, Mistral OCR + GPT-5.6-sol now also extract a full **CIBIL report** (score, active loans, sanctioned/outstanding/overdue, worst DPD, 6-month enquiries, per-account tradelines table with lender/type/sanctioned/outstanding/EMI/DPD/status) and **bank-statement analysis** (avg balance, EMI count + list of instalments/beneficiaries, top credit sources & debit destinations, cash-flow pattern, inflow/outflow ratio).
- ✅ **Anomaly detection**: flags online rummy/gambling, fantasy gaming, betting, large cash withdrawals, unexplained deposits, payment returns — with type/description/amount/severity. High-severity anomalies + DPD≥30/overdue become risk signals; any critical risk signal downgrades approve→review (Grade C rejects).
- ✅ Two new Credit Brain tab sections: "Credit Bureau (CIBIL) Analysis" (score chip + tiles + tradelines table) and "Bank Statement Analysis" (tiles, EMI list, credit/debit sources, red-flag anomalies). Absent (correctly) for estimate-mode/docs-less apps.
- Stored in application.extracted_financials.{cibil_report, banking_analysis}; passed through credit_brain output. Verified: strong app CIBIL 771/0 anomalies; risky app CIBIL 648, DPD 62, ₹6.4L gambling flagged → reject Grade C PD 0.43. Richer synthetic demo docs in /app/synthetic_docs (bank/cibil/gst + bad_bank/bad_cibil/bad_gst); regenerate with python /app/gen_docs.py and /app/gen_bad.py.

## Mistral OCR + GPT-5.6 upgrade (2026-06-18)
- Document extraction now uses **Mistral OCR** (`mistral-ocr-latest`, POST https://api.mistral.ai/v1/ocr, async httpx, base64 data URL) as the primary text/markdown extractor — handles scanned PDFs & images. `pypdf` retained only as a silent fallback (extract_document_text → mistral_ocr_text → extract_pdf_text). Requires MISTRAL_API_KEY in backend/.env (server-side only).
- All LLM analysis calls (structured financial extraction, credit memo, Ask-Brain assistant) upgraded from gpt-5.4 → **gpt-5.6-sol** via the ANALYSIS_MODEL constant. Model constants centralised: ANALYSIS_MODEL, OCR_MODEL.
- Verified: Mistral OCR HTTP 200 + markdown output; gpt-5.6-sol extracted exact figures from synthetic PDFs (0.99 confidence); decision genuine end-to-end. Upload latency ~8s (OCR + LLM).

## Genuine AI Credit Brain — real document extraction (2026-06-18)
Shipped + tested (iteration_8: 7/7 backend + full frontend E2E, 100%). Aligns the app with the BFSI buildathon rule "must be genuinely AI-driven, not hardcoded to simulate intelligence":
- ✅ Real PDF text extraction (pypdf) on document upload, then LLM (gpt-5.4 via emergentintegrations) extracts structured underwriting financials → stored as application.extracted_financials.
- ✅ PD score is now a transparent function of the extracted metrics (_pd_from_financials); the decision comes from the policy engine on real data. Removed the hardcoded KNOWN_PROFILES `force_known` override that faked outcomes.
- ✅ Contradictions (GST vs banking turnover, ITR vs banking) computed from the REAL extracted numbers; cash-flow summary + reason codes now flow from extracted financials.
- ✅ Credit Brain tab badge: "AI-extracted from documents · N% confidence" vs "Estimated · no parsed documents" (docs-less legacy rows fall back gracefully). "Documents Analysed" audit event on upload.
- Verified: Nova Precision (strong synthetic PDFs) → real extraction (₹18.5L credits, ₹2.22Cr banking TO, CIBIL 771) → approve/Grade A/policy PASS; Skyline (mismatched PDFs) → PD 0.544 + critical GST-vs-banking contradiction (46%) + blocked (missing ITR). Synthetic test PDFs kept in /app/synthetic_docs/.
- Backlog from review: run extraction as background task (upload latency ~5-10s), centralise gpt-5.4 model constant, split server.py into modules.

## Contradiction Flags + Document Readiness (2026-06-18)
Shipped + tested (iteration_7: 6/6 backend + full frontend E2E, 100%):
- ✅ Cross-source contradiction detection in Credit Brain: GST turnover vs banking turnover (CONTRA-TURNOVER) and ITR income vs banking credits (CONTRA-INCOME), each with severity (critical/review) and % variance. Surfaced in a "Contradictions & Data Integrity" panel on the Credit Brain tab and in the Decision Trace Extraction node. A critical contradiction downgrades an approve→review.
- ✅ Document readiness gating: mandatory docs (Bank Statement, ITR, GST Returns) required. run_decision returns 400 and writes a "Decision Blocked" audit when any mandatory doc is missing; "Document Readiness" checklist shown on Credit Brain tab. New per-file doc-type classification dialog on the Application Detail Add-documents flow so users can satisfy the mandatory set.
- Backend: build_contradictions(), evaluate_document_readiness(), REQUIRED_DOC_MAP, DEFAULT_POLICY.mandatory_documents; credit_brain adds gst_turnover/banking_turnover/itr_declared_income + contradictions; endpoints return readiness and null-safe backfill evidence/contradictions for pre-existing decisions.
- Demo: Arvind ready+clean; Sri Lakshmi 28% turnover contradiction + blocked (missing ITR); BluePeak critical 42% turnover + 33% income contradiction + blocked (missing ITR, GST).

## Decision Trace (2026-06-18)
Shipped + tested (iteration_6, frontend-only, 95% — no bugs):
- ✅ New "Trace" tab on Application Detail: interactive 6-stage flow Documents → Extraction → Credit Brain → Policy → Structuring → Decision. Clickable nodes with status dots; each opens a detail panel (docs list, extracted financials, PD/grade/FOIR/DSCR + signals, policy rule table, eligibility waterfall + terms, final decision). Built entirely from existing GET /api/applications/{id} data; empty state prompts Run Decision. Component: DecisionTraceTab.js.

## Ask Credit Brain + Evidence Chain (2026-06-18)
Shipped + tested (iteration_5: 6/6 backend + full frontend E2E, 100%):
- ✅ Ask Credit Brain: new "Ask Brain" tab on Application Detail. Application-grounded LLM assistant (Emergent LLM key, OpenAI gpt-5.4 via emergentintegrations, LIVE not mocked). Preset chips (why approved / why this amount / key risks / rules triggered) + free-text. Answers cite figures & policy rule IDs; refuses out-of-scope questions. Chat persisted in `brain_chats` collection; history rehydrates on reload. Endpoints: POST /api/applications/{id}/ask {question, session_id?}, GET /api/applications/{id}/chat.
- ✅ Evidence Chain: every Credit Brain financial figure (FOIR, DSCR, turnover, avg credits, balance, net cash flow, existing EMI, CIBIL, vintage, bounces) is clickable → right-side Sheet with value, calculation formula + inputs, source document + page ref, and extraction confidence (deterministic mock attribution). Wired into Credit Brain tab (12 metrics) and Decision tab (3 cash-flow cards). Backend `build_evidence()` adds `evidence` to credit_brain output; GET /credit-brain/{id} and GET /applications/{id} backfill evidence for decisions computed before this feature.


## GitHub docs refresh + Genuine-AI Sample Data (2026-06-XX / current session)
- ✅ **README.md rewritten** (top-level) + `backend/.env.example` refreshed: removed all MOCK_MODE / "sample data / mock-generated" language; now documents the real pipeline (Mistral OCR → GPT-5.6-sol extraction → Credit Brain → Policy engine → decision → memo → audit), full feature list, architecture, correct env vars (EMERGENT_LLM_KEY, MISTRAL_API_KEY), setup/run + API endpoints. No secrets written. (User to push via "Save to GitHub".)
- ✅ **New document types** added end-to-end: `kyc`, `cibil`, `purchase_bills`, `sales_bills` (added to backend DOC_TYPE_LABELS + REQUIRED_DOC_MAP, frontend DOC_TYPE_LABEL, NewApplication upload dialog, ApplicationDetail classify dialog).
- ✅ **Genuine-AI demo seed** (`POST /api/demo/seed` rewritten): generates REAL synthetic PDFs (reportlab) for 3 borrowers × 7 doc types (KYC, CIBIL, Bank, ITR, GST, Purchase Bills, Sales Bills), writes them to UPLOAD_DIR, and runs the true Mistral OCR + GPT-5.6-sol extraction + decision in a background asyncio task (`_run_seed_processing` / `_process_seed_app`). Seed returns immediately with `{created, refs, processing}`; Dashboard polls until seeded apps leave "pending".
  - Borrowers: **Nova Precision Tools Pvt Ltd** (LS-2026-00201, MSME ₹40L) → genuine extraction CIBIL 771/DPD0/conf0.94 → **approve/Grade A**; **Skyline Traders** (LS-2026-00202, ₹35L) → CIBIL 648/DPD62/₹3.2L overdue/gambling+betting critical anomalies/turnover mismatch → **reject/Grade C**; **Sri Lakshmi Components** (LS-2026-00203, ₹25L) → CIBIL 705/DPD22/moderate mismatch → **review/Grade C**.
  - Verified end-to-end: DB shows `extracted_financials._source=ai` with real CIBIL reports, tradelines, anomalies for all three; dashboard + Credit Brain tab render correctly (Risk Radar, anomalies, 7 docs, AI-confidence badge).
- Note: dashboard also contains many leftover test apps (RiskRadar*, DeepAnalysis*, TEST_*, Demo*) from prior QA iterations — candidate for a future cleanup if the user wants a pristine demo list.
