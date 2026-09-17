# LendSprint AI

**Explainable AI credit decisioning for Indian NBFCs.**

LendSprint AI is a demonstration credit-decisioning platform for mid-market Indian NBFCs. It walks an application from intake to an auditable, explainable credit decision:

> Borrower application → Upload financial documents → Decision engine → Explainable reason codes → Cash-flow analysis → AI-drafted credit memo → Complete audit trail.

The app runs entirely in **MOCK MODE** by default — no external AI/OCR/LLM calls are required.

---

## Architecture

- **Frontend:** React (CRA + CRACO), Tailwind CSS, shadcn/ui, lucide-react, sonner.
- **Backend:** FastAPI (Python), Motor (async MongoDB driver), PyJWT + bcrypt auth.
- **Database:** MongoDB.
- **Auth:** Single-user JWT (Bearer token in `Authorization` header; stored in `localStorage`).

```
/app
├── backend/
│   ├── server.py          # FastAPI app: auth, applications, documents, decisions, audit, demo seed
│   ├── requirements.txt
│   ├── .env / .env.example
│   └── uploads/           # locally-persisted uploaded PDFs (outside frontend source)
└── frontend/
    └── src/
        ├── pages/         # Login, Dashboard, NewApplication, ApplicationDetail
        ├── components/
        │   ├── layout/    # AppShell, Sidebar, Header
        │   ├── common/    # StatusBadge, PdGauge
        │   └── application/  # DecisionTab, MemoTab, AuditTab
        ├── context/AuthContext.js
        └── lib/           # api.js (typed API layer), format.js
```

## Environment variables (backend/.env)

| Variable          | Purpose                                             |
|-------------------|-----------------------------------------------------|
| `MOCK_MODE`       | `true` = deterministic mock engine, no external AI  |
| `MONGO_URL`       | MongoDB connection string                           |
| `DB_NAME`         | Database name (`lendsprint`)                        |
| `CORS_ORIGINS`    | Allowed origins                                     |
| `JWT_SECRET`      | JWT signing secret                                  |
| `ADMIN_EMAIL`     | Seeded single-user account                          |
| `ADMIN_PASSWORD`  | Seeded account password                             |
| `EMERGENT_LLM_KEY`| Used only when `MOCK_MODE=false` for memo drafting  |
| `OPENAI_API_KEY` / `OCR_API_KEY` | Reserved for the real pipeline       |

Never commit real secrets. `.env.example` documents the required keys.

## Running

Both services are supervised in this environment:

```
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
```

- Backend binds `0.0.0.0:8001`, all routes prefixed `/api`.
- Frontend calls the backend via `REACT_APP_BACKEND_URL`.

## API endpoints

| Method | Path                                   | Description                              |
|--------|----------------------------------------|------------------------------------------|
| POST   | `/api/auth/login`                      | Returns `{ token, user }`                |
| GET    | `/api/auth/me`                         | Current user (Bearer)                    |
| POST   | `/api/applications`                    | Create application                       |
| GET    | `/api/applications`                    | List (search / status / loan_type)       |
| GET    | `/api/applications/{id}`               | Application + documents + decision        |
| POST   | `/api/applications/{id}/documents`     | Upload PDFs (multipart)                   |
| POST   | `/api/applications/{id}/decision`      | Run decision engine (400 if no docs)     |
| GET    | `/api/applications/{id}/audit`         | Audit trail                              |
| GET    | `/api/documents/{id}/download`         | Download a stored PDF                     |
| DELETE | `/api/documents/{id}`                  | Remove a document                        |
| GET    | `/api/dashboard/stats`                 | Portfolio metrics                        |
| POST   | `/api/demo/seed`                       | Idempotent sample portfolio seed         |

## Mock mode

With `MOCK_MODE=true`, `compute_decision()` produces **deterministic** output from the borrower name + amount (same input → same decision). No external services are contacted. Seeded borrowers have fixed, realistic profiles.

## Demo flow (< 2 minutes)

1. Sign in.
2. Dashboard → **Load sample data** (3 applications appear).
3. Open **BluePeak Traders** (pending, no documents).
4. Documents tab → **Add documents** → upload a PDF.
5. **Run Decision** → watch the processing sequence.
6. Review PD score, decision badge, reason codes and cash-flow summary.
7. **Credit Memo** tab → **Copy Memo**.
8. **Audit Trail** tab → expand *Decision Generated* to see the JSON payload.

## Future real AI integration

See the `# TODO: REAL DOCUMENT INTELLIGENCE PIPELINE` block in `server.py` and `generate_ai_memo()`. When `MOCK_MODE=false`, the credit memo is drafted by an LLM via the Emergent integrations layer; the OCR/extraction/ratio/policy stages are stubbed for future implementation. All keys stay server-side.

---

_This is a demonstration prototype. Decisions are mock-generated and must not be treated as final credit sanctions. Designed for traceable, defensible credit decisions — no regulatory certification is claimed._
