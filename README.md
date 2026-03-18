# DocAgent — Enterprise Document AI Agent

Multi-tenant document intelligence platform: upload PDF/DOCX, async ingestion, LangGraph agent with cited answers.

See **agent_action_plan.md** for full architecture. Track progress in **AGENT_PROGRESS.md**.

## Quick start (local)

```bash
# 1. Copy env
cp .env.example .env
# Set DATABASE_URL and optionally OPENAI_API_KEY

# 2. Start infrastructure
docker compose -f infra/docker-compose.yml up -d

# 3. Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # or: uv venv && source .venv/bin/activate
pip install -r requirements/base.txt -r requirements/dev.txt
# Set PYTHONPATH or install app in editable mode: pip install -e .
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 4. Migrations
alembic upgrade head

# 5. Run API
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs  
- Health: http://localhost:8000/api/v1/health  
- Ready: http://localhost:8000/api/v1/ready  

## Project layout

- **backend/** — FastAPI app, ingestion, agent, workers
- **infra/** — docker-compose, Prometheus, (future K8s)
- **scripts/** — check_agent_progress.py, (future seed scripts)

## Phase 2 — Ingestion (optional worker)

After upload, process documents with either:

1. **Kafka consumer** (processes from Kafka):  
   `cd backend && PYTHONPATH=. python -m workers.kafka_consumer`

2. **Celery worker** (processes from Redis; upload endpoint also enqueues to Celery):  
   `cd backend && celery -A workers.tasks worker -Q ingestion -c 2 --loglevel=info`

Ensure Kafka (and Redis for Celery) are running via `docker compose -f infra/docker-compose.yml up -d`.

## Progress

Run `python scripts/check_agent_progress.py` to see completion and next task.
