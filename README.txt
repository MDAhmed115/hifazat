# Hifazat — AI Scam Protection on Public Rails

**Coder's Cup '26 | The Last Mile: AI on Public Rails**

Hifazat is an AI-powered scam-detection SaaS that protects Pakistani citizens
from SMS, WhatsApp and document-based fraud (prize scams, fake police calls,
advance-fee "Baitul Maal" fraud, phishing screenshots). Every message gets a
single verdict — approve / warn / escalate — with a plain-language explanation
for the citizen and a full audit trail for officers.

## Live Demo

| | URL |
|---|---|
| Frontend | <https://hifazat.vercel.app> |
| Backend API docs | <https://hifazat-api.onrender.com/docs> |

> Free-tier hosting: the backend sleeps after inactivity and takes ~50 s to
> wake. Open the docs link once, then use the app.

## Demo Accounts

| Role | Phone | Password | What to look at |
|---|---|---|---|
| Citizen | `03000000301` | `citizen123` | Submit a scam SMS, get verdict + explanation |
| Officer | `03000000101` | `officer123` | Case queue, escalate / resolve |
| Helper | `03000000201` | `helper123` | Assisted intake for walk-in users |
| Admin | `03000000000` | `admin123` | Analytics, anomaly alerts, rule versioning |
| Auditor | `03000000401` | `auditor123` | Full decision audit trail, consent logs |

## How the Decision Engine Works

One engine, one verdict object — used by every role:

```json
{
  "label": "scam",
  "confidence": 0.93,
  "route": "warn_user",
  "explanation_user": "This message asks for money and personal details...",
  "explanation_audit": "Rule pack v3: advance-fee keywords; LLM score 0.93"
}
```

Asymmetric thresholds (a wrong approval costs ~Rs. 25,000 to a victim, a wrong
rejection only ~Rs. 2,000 of friction): approve at confidence ≥ 0.90, warn at
≥ 0.85, anything below 0.60 is escalated to a human officer instead of guessed.

**Pipeline:** high-risk keyword pre-check → LLM classification (Groq /
llama-3.3-70b) → guardrails → RAG over the official rules corpus (Baitul Maal
policy, complaint procedure) → OCR + filename guardrails for uploaded
"proof" documents → IsolationForest anomaly detection on submission patterns
→ audit log + rule version stamped on every decision.

## Tech Stack

| Layer | Tool |
|---|---|
| Backend | FastAPI (Python 3.11), SQLAlchemy, Alembic |
| Database | Neon Postgres (prod) / SQLite (local) |
| LLM | Groq API — llama-3.3-70b-versatile |
| RAG | ChromaDB + sentence-transformers over official rules docs |
| OCR | Tesseract (screenshot evidence) |
| Anomaly detection | IsolationForest (scikit-learn) |
| Frontend | React 18 + Vite, Web Speech API (ur-PK voice input) |
| Hosting | Render (API) + Vercel (web) + Neon (DB) |

## Run Locally

```bash
# backend
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
copy .env.example .env           # fill GROQ_API_KEY
python scripts/seed.py
uvicorn app.main:app --reload --port 9000

# frontend (second terminal)
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

## Environment Variables

| Variable | Used for |
|---|---|
| `DATABASE_URL` | Neon Postgres in prod, `sqlite:///./hifazat.db` locally |
| `JWT_SECRET` | signing login tokens |
| `GROQ_API_KEY` | LLM classification |
| `API_KEY` | internal service key for audit endpoints |

Never commit `.env` — see `.env.example` for the template.

## Repo Structure

```
backend/
  app/            FastAPI app, routers, decision engine, auth, audit
  alembic/        DB migrations
  scripts/        seed + smoke tests
  tests/          pytest suite
frontend/
  src/pages/      role dashboards (Citizen, Officer, Admin, Auditor...)
  src/api.js      single API client
docs_corpus/      official rules texts used by RAG
```

## Team

Team GeoMatrix — Ahmed Ashfaq: architecture & integration · Fahad-ul-Islam: auth & platform ·
Moazamuddin: AI pipeline · Abu Saad: citizen experience
