# Agent Action Plan — Progress Tracker

Track completion of tasks from `agent_action_plan.md` (Section 23). Update this file as tasks are completed.

---

## Summary

| Phase   | Done | Total | Status    |
|---------|------|-------|-----------|
| Phase 1 | 17   | 18    | Done (P1-18: manual verify) |
| Phase 2 | 0    | 17    | Not started |
| Phase 3 | 0    | 13    | Not started |
| Phase 4 | 0    | 22    | Not started |
| Phase 5 | 0    | 25    | Not started |
| **Total** | **17** | **95** | 18% |

*Last updated: Phase 1 implemented*

---

## Phase 1 — Foundation (Week 1)

| Done | Task ID  | Description | Section | Notes |
|------|----------|-------------|---------|-------|
| [x] | P1-01 | Project scaffolding: create full directory structure | 3 | |
| [x] | P1-02 | `pyproject.toml`: configure black, ruff, mypy strict, pytest | — | |
| [x] | P1-03 | `core/config.py`: Pydantic Settings with all env vars typed | 21 | |
| [x] | P1-04 | `core/exceptions.py`: all typed domain exceptions | 17 | |
| [x] | P1-05 | `core/logging.py`: structlog JSON setup + OTel integration | 16.1 | |
| [x] | P1-06 | `core/tracing.py`: OpenTelemetry tracer → Jaeger exporter | 16.2 | |
| [x] | P1-07 | `core/metrics.py`: all Prometheus metric definitions | 16.3 | |
| [x] | P1-08 | `core/middleware.py`: RequestID, timing, tracing, CORS middleware | 12 | |
| [x] | P1-09 | `db/session.py`: async SQLAlchemy engine + session factory | — | |
| [x] | P1-10 | `models/`: all 5 models (base, user, organisation, document, chunk) | 6.1 | |
| [x] | P1-11 | Alembic setup: `alembic init`, configure `env.py` for async + models | 6.3 | |
| [x] | P1-12 | First migration: create all tables, extensions, HNSW index, GIN index, trigger | 6.3 | |
| [x] | P1-13 | `core/security.py`: JWT encode/decode, password hashing | — | |
| [x] | P1-14 | `main.py`: app factory, lifespan, middleware registration, router mount | — | |
| [x] | P1-15 | `api/v1/health.py`: liveness + readiness endpoints | — | |
| [x] | P1-16 | Global exception handlers in `main.py` | — | |
| [x] | P1-17 | `docker-compose.yml`: PostgreSQL, Redis, Kafka, ZooKeeper, Kafka-Init, MinIO, AKHQ, Jaeger, Prometheus, Grafana | — | |
| [ ] | P1-18 | Verify: `docker-compose up` → all services healthy → `alembic upgrade head` succeeds | — | Manual |

---

## Phase 2 — Ingestion Pipeline (Week 2)

| Done | Task ID  | Description | Section | Notes |
|------|----------|-------------|---------|-------|
| [ ] | P2-01 | `services/storage.py`: S3 upload, download, presign URL | 7 | |
| [ ] | P2-02 | `services/ingestion/parser.py`: PyMuPDF PDF + OCR fallback + python-docx | 7 | |
| [ ] | P2-03 | `services/ingestion/chunker.py`: RecursiveCharacterTextSplitter with overlap | 7 | |
| [ ] | P2-04 | `services/ingestion/embedder.py`: async batched OpenAI embeddings + retry | 7 | |
| [ ] | P2-05 | `services/ingestion/indexer.py`: bulk upsert pgvector + mark_indexed | 7 | |
| [ ] | P2-06 | `services/ingestion/pipeline.py`: orchestrate all steps, emit logs + metrics | 7 | |
| [ ] | P2-07 | `services/queue/producer.py`: aiokafka producer, acks=all, idempotent, user_id partition key | 8 | |
| [ ] | P2-08 | `services/queue/dlq.py`: escalate to DLQ topic + update DB status | 8 | |
| [ ] | P2-09 | `workers/celeryconfig.py`: Kafka broker, all settings | 8 | |
| [ ] | P2-10 | `workers/tasks.py`: `ingest_document` Celery task, retry + DLQ escalation | 8 | |
| [ ] | P2-11 | `schemas/upload.py`: UploadRequest, UploadResponse Pydantic schemas | — | |
| [ ] | P2-12 | `api/v1/upload.py`: upload endpoint, all 10 steps | 7 | |
| [ ] | P2-13 | `api/v1/documents.py`: list, get, delete endpoints | — | |
| [ ] | P2-14 | `api/v1/status.py`: document status polling endpoint | — | |
| [ ] | P2-15 | Unit tests: parser, chunker, embedder | 18 | |
| [ ] | P2-16 | Integration test: upload → ingest → verify chunks in DB | 18 | |
| [ ] | P2-17 | Manual test: upload real 100-page PDF, verify AKHQ + indexed | — | |

---

## Phase 3 — Search, Cache & Agent (Week 3)

| Done | Task ID  | Description | Section | Notes |
|------|----------|-------------|---------|-------|
| [ ] | P3-01 | `services/retrieval/retriever.py`: vector + BM25 + RRF fusion | 9 | |
| [ ] | P3-02 | `services/retrieval/reranker.py`: cross-encoder reranker (optional, feature-flagged) | 9 | |
| [ ] | P3-03 | `services/cache/semantic_cache.py`: RedisVL SemanticCache wrapper, user-scoped | 10 | |
| [ ] | P3-04 | `services/agent/state.py`: AgentState TypedDict | 11 | |
| [ ] | P3-05 | `services/agent/prompts.py`: SYSTEM_PROMPT, QUALITY_PROMPT, REFINE_PROMPT | 11 | |
| [ ] | P3-06 | `services/agent/nodes.py`: all 5 nodes (route, search, generate, quality, refine) | 11 | |
| [ ] | P3-07 | `services/agent/tools.py`: search_docs, get_document_summary tools | 11 | |
| [ ] | P3-08 | `services/agent/graph.py`: LangGraph StateGraph, all edges, compile | 11 | |
| [ ] | P3-09 | `schemas/chat.py`: ChatRequest, ChatResponse, StreamDelta schemas | — | |
| [ ] | P3-10 | `api/v1/chat.py`: chat endpoint with SSE streaming + cache check + store | 12 | |
| [ ] | P3-11 | Unit tests: RRF merge, agent nodes with mocked LLM | 18 | |
| [ ] | P3-12 | Integration test: full chat e2e with seeded document | 18 | |
| [ ] | P3-13 | Load test: 1M chunks → P99 retrieval < 15ms target | 18 | |

---

## Phase 4 — Frontend (Week 4)

| Done | Task ID  | Description | Section | Notes |
|------|----------|-------------|---------|-------|
| [ ] | P4-01 | Vite + React + TypeScript, strict tsconfig, Tailwind, shadcn/ui | 13 | |
| [ ] | P4-02 | TypeScript types: `document.ts`, `chat.ts`, `api.ts` | 13 | |
| [ ] | P4-03 | `services/api.ts`: Axios instance + auth + error interceptors | — | |
| [ ] | P4-04 | `store/authStore.ts`: Zustand auth state | — | |
| [ ] | P4-05 | `store/chatStore.ts`: Zustand messages state | — | |
| [ ] | P4-06 | `LoginPage.tsx`: email/password form, Zod validation, JWT storage | — | |
| [ ] | P4-07 | `Layout.tsx`, `Sidebar.tsx`, `Header.tsx`: app shell | — | |
| [ ] | P4-08 | `DropZone.tsx`: drag-and-drop upload + MIME validation + progress | — | |
| [ ] | P4-09 | `useUpload.ts`: TanStack Query mutation + upload progress | — | |
| [ ] | P4-10 | `useDocumentStatus.ts`: polling hook (every 3s until indexed) | — | |
| [ ] | P4-11 | `DocumentCard.tsx`: status badge (queued/processing/indexed/failed) | — | |
| [ ] | P4-12 | `DashboardPage.tsx`: document list + upload zone | — | |
| [ ] | P4-13 | `utils/sse.ts`: SSE parser for delta / citations / done events | — | |
| [ ] | P4-14 | `useChat.ts`: SSE streaming hook, onDelta / onDone | — | |
| [ ] | P4-15 | `StreamingMessage.tsx`: real-time token display | — | |
| [ ] | P4-16 | `CitationBadge.tsx`: clickable page citation pill | — | |
| [ ] | P4-17 | `MessageBubble.tsx`: user and assistant message rendering | — | |
| [ ] | P4-18 | `ChatInput.tsx`: textarea + send, disabled during streaming | — | |
| [ ] | P4-19 | `ChatWindow.tsx`: full chat interface | — | |
| [ ] | P4-20 | `ChatPage.tsx`: layout + ChatWindow + document info panel | — | |
| [ ] | P4-21 | `Dockerfile.frontend`: Nginx + Vite build + API proxy | — | |
| [ ] | P4-22 | E2E: upload → wait indexed → chat → streamed answer | — | |

---

## Phase 5 — AWS & Observability (Week 5)

| Done | Task ID  | Description | Section | Notes |
|------|----------|-------------|---------|-------|
| [ ] | P5-01 | `Dockerfile.api` + `Dockerfile.worker`: production images | — | |
| [ ] | P5-02 | ECR repositories: api, worker, frontend | — | |
| [ ] | P5-03 | EKS cluster + managed node group | — | |
| [ ] | P5-03a | Install Karpenter controller + IRSA (EC2 permissions) | 15 | |
| [ ] | P5-03b | EC2NodeClass (AMI, subnets, security groups, EBS) | 15 | |
| [ ] | P5-03c | NodePool: general (m7i/m7g, On-Demand) | 15 | |
| [ ] | P5-03d | NodePool: ingestion-workers (c7i/c7g, Spot+On-Demand) | 15 | |
| [ ] | P5-03e | NodePool: gpu (g5, inactive) | 15 | |
| [ ] | P5-03f | Spot interruption SQS + Karpenter interruption handler | 15 | |
| [ ] | P5-03g | nodeSelector + tolerations on Worker Deployment | 15 | |
| [ ] | P5-03h | Verify: scale workers → Karpenter provisions c7i Spot < 60s | — | |
| [ ] | P5-04 | MSK Kafka: 3 brokers, Multi-AZ, all topics | — | |
| [ ] | P5-05 | RDS PostgreSQL 16: Multi-AZ, pgvector, migrations | — | |
| [ ] | P5-06 | ElastiCache Redis: cluster mode, 3 shards | — | |
| [ ] | P5-07 | S3 bucket: versioning, lifecycle, deny-public-access | — | |
| [ ] | P5-08 | IAM + IRSA: API pod, Worker pod roles | — | |
| [ ] | P5-09 | AWS Secrets Manager + External Secrets Operator | — | |
| [ ] | P5-10 | K8s: API, Worker, Frontend deployments + services | — | |
| [ ] | P5-11 | ALB Ingress + Route53 + ACM TLS | — | |
| [ ] | P5-12 | KEDA ScaledObject: Kafka lag autoscaling | — | |
| [ ] | P5-13 | HPA: API pods on CPU | — | |
| [ ] | P5-14 | OTel Collector (DaemonSet + Deployment) full pipeline | 16.8 | |
| [ ] | P5-15 | Grafana Tempo + S3 backend, verify traces | — | |
| [ ] | P5-16 | Jaeger + OTel fan-out, verify traces | — | |
| [ ] | P5-17 | Loki + Promtail + Fluent Bit, verify logs in Grafana | — | |
| [ ] | P5-18 | Prometheus + all exporters | — | |
| [ ] | P5-19 | Grafana + 3 data sources + 4 dashboards | — | |
| [ ] | P5-20 | AlertManager: alert rules + Slack/PagerDuty | 16.5 | |
| [ ] | P5-21 | GlitchTip + backend/frontend DSN | 16.6 | |
| [ ] | P5-22 | Uptime Kuma + health monitors | 16.7 | |
| [ ] | P5-23 | CloudWatch: MSK + RDS alarms → SNS | 16.9 | |
| [ ] | P5-24 | GitHub Actions CI/CD: test → build → ECR → migrate → deploy | — | |
| [ ] | P5-25 | Load test staging: 10K uploads, 1K chats, 0% loss, P99 | — | |

---

## How to use this file

1. **Mark a task done:** Change `[ ]` to `[x]` in the Done column and add any note in the Notes column.
2. **Update summary:** Re-count "Done" per phase and total, and set "Last updated" at the top.
3. **Run progress script:** From repo root, run `python scripts/check_agent_progress.py` (or `./scripts/check_agent_progress.py`) to print summary and next suggested task.

Reference: `agent_action_plan.md` Section 23 (Agent Action Plan).
