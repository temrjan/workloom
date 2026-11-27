# Workloom

Modular enterprise AI & knowledge operations platform built as an async Python modular monolith (`FastAPI`, `SQLAlchemy 2.0`, `PostgreSQL`, `Qdrant`, `LlamaIndex`, `Redis`) paired with a `React` + `Vite` operations dashboard.

## Capabilities

- **Department-Scoped Document & Media RAG (`modules/documents`, `modules/media`, `services/rag`):** Hybrid vector indexing and retrieval over company documents and Whisper-transcribed audio/video recordings in Qdrant with per-department isolation (`hr`, `callcenter`, `marketing`, `advisor`).
- **Conversational Order Intake & CRM Routing (`modules/advisor`, `modules/crm`, `api/v1/webhooks.py`):** Telegram webhook pipeline that answers grounded product queries and parses free-form order messages via structured LLM extraction into confirmed CRM leads.
- **HR Document & Digest Workflows (`modules/hr`, `modules/news_digest`):** Guided conversational field extraction, `.docx` document rendering, employee event/gift tracking, and scheduled legal/industry news digests.
- **Admin & Prompt Governance Console (`frontend/dashboard`, `api/v1/prompts.py`, `api/v1/auth.py`):** JWT-authenticated operations console with department RBAC (`admin`-gated prompt updates with automatic versioned backups).

## Quick Start

```bash
git clone https://github.com/temrjan/workloom.git
cd workloom

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
cp prompts/advisor.example.txt prompts/advisor.txt
docker compose up -d
make run
```

## Verification

```bash
ruff check src tests
ruff format src tests --check
mypy src
pytest -m "unit or not integration"

cd frontend/dashboard
npm ci
npm run build
```

Integration tests (`pytest -m integration`) run against an ephemeral PostgreSQL 16 instance (`JSONB` columns); external LLM calls are mocked in the test suite.

## License

Released under the [MIT License](LICENSE).
