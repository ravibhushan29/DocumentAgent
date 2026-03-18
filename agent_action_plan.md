# CLAUDE.md — Enterprise Document AI Agent
> **Master architectural plan. No implementation code — use this file to drive code generation.**
> Every section defines WHAT to build, WHY, and HOW it connects. Update this file when architecture changes.

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Architecture Philosophy](#2-architecture-philosophy)
3. [Full Project Structure](#3-full-project-structure)
4. [Tech Stack & Decisions](#4-tech-stack--decisions)
5. [Data Flow — End to End](#5-data-flow--end-to-end)
6. [Database — Models & Migrations](#6-database--models--migrations)
7. [Upload & Ingestion Pipeline](#7-upload--ingestion-pipeline)
8. [Kafka Queue, Celery Workers & DLQ](#8-kafka-queue-celery-workers--dlq)
9. [Vector Search & Hybrid Retrieval](#9-vector-search--hybrid-retrieval)
10. [RedisVL Semantic Cache](#10-redisvl-semantic-cache)
11. [LangGraph Agent](#11-langgraph-agent)
12. [API Layer — FastAPI](#12-api-layer--fastapi)
13. [Frontend — React + TypeScript](#13-frontend--react--typescript)
14. [Auth & Multi-Tenancy](#14-auth--multi-tenancy)
15. [AWS Cloud Infrastructure](#15-aws-cloud-infrastructure)
16. [Observability Stack](#16-observability-stack)
17. [Error Handling Strategy](#17-error-handling-strategy)
18. [Testing Strategy](#18-testing-strategy)
19. [Scaling Strategy](#19-scaling-strategy)
20. [Developer Conventions](#20-developer-conventions)
21. [Environment Variables](#21-environment-variables)
22. [Local Setup](#22-local-setup)
23. [Agent Action Plan](#23-agent-action-plan)

---

## 1. Project Overview

**What this system does:**
A production-grade, multi-tenant document intelligence platform. Users upload PDFs and DOCX files. A LangGraph AI agent answers questions grounded exclusively in those documents, with streaming responses and cited page numbers.

**Core capabilities:**
- Upload PDF / DOCX (up to 500MB) → stored in AWS S3
- Async ingestion: parse → chunk → embed → index into pgvector
- Kafka-backed queue with Celery workers — 0% data loss, horizontally scalable
- Hybrid vector + BM25 keyword search with RedisVL semantic caching
- LangGraph agent with self-grading quality check and streamed SSE responses
- React + TypeScript frontend with real-time upload progress and chat UI
- Full observability: Prometheus, Grafana, Jaeger, OpenTelemetry, Sentry, CloudWatch
- Scales to millions of users on AWS EKS

**Supported file types:** PDF, DOCX only (for now).

---

## 2. Architecture Philosophy

> "Every component has one job. Every failure has a recovery path. Every request is observable."

### Non-Negotiable Principles

| Principle | Rule |
|---|---|
| **Single Responsibility** | Each class/service does ONE thing. Parser only parses. Embedder only embeds. |
| **Async First** | All I/O (DB, S3, Redis, Kafka, LLM APIs) must be async/await. Zero blocking calls. |
| **Explicit Dependencies** | All dependencies injected via FastAPI `Depends()`. No hidden globals. |
| **Typed Everything** | Python: full type annotations. TypeScript: strict mode, no `any`. |
| **0% Data Loss** | Messages committed only after confirmed processing. DLQ catches everything else. |
| **Idempotent Writes** | Every DB write is safely retryable. `ON CONFLICT DO NOTHING` everywhere. |
| **Observability by Default** | Every service emits structured logs, metrics, and traces. No silent failures. |
| **Fail Loudly** | Typed exceptions everywhere. Global handler converts to HTTP responses. |
| **Security by Default** | All DB queries scoped to `user_id`. JWT on every endpoint. Secrets via AWS Secrets Manager. |
| **Test Everything** | Unit tests for pure logic. Integration tests for pipelines. Load tests for retrieval. |

---

## 3. Full Project Structure

```
doc_agent/
│
├── CLAUDE.md                            ← This file (master plan)
├── README.md                            ← Quick start for new developers
├── .env.example                         ← All env vars with descriptions
├── pyproject.toml                       ← Python project config, ruff, black, mypy
│
├── backend/
│   │
│   ├── app/
│   │   ├── main.py                      ← FastAPI app factory, lifespan, middleware, router mount
│   │   │
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── upload.py            ← POST /documents/upload
│   │   │       ├── chat.py              ← POST /chat/query  (SSE streaming)
│   │   │       ├── documents.py         ← GET /documents, GET /documents/{id}
│   │   │       ├── status.py            ← GET /status/{job_id}
│   │   │       ├── health.py            ← GET /health, GET /ready (K8s probes)
│   │   │       └── admin.py             ← DLQ inspect/replay (internal, admin-only)
│   │   │
│   │   ├── core/
│   │   │   ├── config.py                ← Pydantic Settings — all env vars typed + validated
│   │   │   ├── security.py              ← JWT encode/decode, password hashing
│   │   │   ├── exceptions.py            ← All typed domain exceptions
│   │   │   ├── logging.py               ← structlog JSON logger + OpenTelemetry integration
│   │   │   ├── metrics.py               ← Prometheus metrics definitions (counters, histograms)
│   │   │   ├── tracing.py               ← OpenTelemetry tracer setup → Jaeger exporter
│   │   │   └── middleware.py            ← RequestID injection, timing, CORS, tracing middleware
│   │   │
│   │   ├── models/                      ← SQLAlchemy ORM models (source of truth for DB schema)
│   │   │   ├── base.py                  ← Base with id (UUID), created_at, updated_at
│   │   │   ├── user.py                  ← User model
│   │   │   ├── organisation.py          ← Organisation model (multi-tenancy)
│   │   │   ├── document.py              ← Document model (upload metadata + status)
│   │   │   └── chunk.py                 ← DocumentChunk model (text + pgvector embedding)
│   │   │
│   │   ├── schemas/                     ← Pydantic v2 request/response schemas (API contracts)
│   │   │   ├── upload.py                ← UploadRequest, UploadResponse
│   │   │   ├── chat.py                  ← ChatRequest, ChatResponse, StreamDelta
│   │   │   ├── document.py              ← DocumentOut, DocumentStatus
│   │   │   └── user.py                  ← UserOut, TokenResponse
│   │   │
│   │   ├── services/
│   │   │   │
│   │   │   ├── ingestion/
│   │   │   │   ├── pipeline.py          ← Orchestrator: parse→chunk→embed→index
│   │   │   │   ├── parser.py            ← PDF (PyMuPDF + OCR fallback) + DOCX parser
│   │   │   │   ├── chunker.py           ← RecursiveCharacterTextSplitter, semantic overlap
│   │   │   │   ├── embedder.py          ← Async batched embedding (text-embedding-3-large)
│   │   │   │   └── indexer.py           ← Bulk upsert to pgvector, mark document indexed
│   │   │   │
│   │   │   ├── queue/
│   │   │   │   ├── producer.py          ← aiokafka producer (acks=all, idempotent)
│   │   │   │   └── dlq.py               ← DLQ escalation to Kafka DLQ topic + DB update
│   │   │   │
│   │   │   ├── retrieval/
│   │   │   │   ├── retriever.py         ← Hybrid: vector (HNSW) + BM25 + RRF fusion
│   │   │   │   └── reranker.py          ← Cross-encoder reranking (optional precision boost)
│   │   │   │
│   │   │   ├── cache/
│   │   │   │   └── semantic_cache.py    ← RedisVL SemanticCache wrapper (user-scoped)
│   │   │   │
│   │   │   ├── agent/
│   │   │   │   ├── graph.py             ← LangGraph StateGraph compile + export
│   │   │   │   ├── nodes.py             ← route / search / generate / quality / refine nodes
│   │   │   │   ├── tools.py             ← Agent tools: search_docs, get_document_summary
│   │   │   │   ├── state.py             ← AgentState TypedDict
│   │   │   │   └── prompts.py           ← ALL prompts live here, never inline
│   │   │   │
│   │   │   └── storage.py               ← AWS S3 abstraction (upload, download, presign)
│   │   │
│   │   └── db/
│   │       ├── session.py               ← Async SQLAlchemy engine + session factory
│   │       └── migrations/              ← Alembic migration directory
│   │           ├── env.py               ← Alembic env (reads async SQLAlchemy models)
│   │           ├── script.py.mako       ← Migration template
│   │           └── versions/            ← Auto-generated migration files (never edit manually)
│   │
│   ├── workers/
│   │   ├── celeryconfig.py              ← All Celery settings (Kafka broker, routing, retries)
│   │   ├── tasks.py                     ← Celery task definitions (thin wrappers → pipeline)
│   │   └── kafka_consumer.py            ← aiokafka consumer loop → dispatches Celery tasks
│   │
│   ├── tests/
│   │   ├── conftest.py                  ← Shared fixtures: test DB, mock S3, mock Kafka
│   │   ├── unit/
│   │   │   ├── test_parser.py
│   │   │   ├── test_chunker.py
│   │   │   ├── test_embedder.py
│   │   │   ├── test_rrf_merge.py
│   │   │   └── test_agent_nodes.py
│   │   ├── integration/
│   │   │   ├── test_upload_pipeline.py
│   │   │   ├── test_retrieval.py
│   │   │   └── test_chat_e2e.py
│   │   └── load/
│   │       └── test_retrieval_latency.py
│   │
│   └── requirements/
│       ├── base.txt
│       ├── dev.txt
│       └── prod.txt
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── main.tsx                     ← React entry point
│   │   ├── App.tsx                      ← Router setup
│   │   │
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx        ← Document list + upload
│   │   │   └── ChatPage.tsx             ← Chat interface for a document
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── Header.tsx
│   │   │   │   └── Layout.tsx
│   │   │   ├── upload/
│   │   │   │   ├── DropZone.tsx         ← Drag-and-drop file upload
│   │   │   │   ├── UploadProgress.tsx   ← Progress bar with status polling
│   │   │   │   └── DocumentCard.tsx     ← Document tile with status badge
│   │   │   └── chat/
│   │   │       ├── ChatWindow.tsx       ← Full chat interface
│   │   │       ├── MessageBubble.tsx    ← User / AI message bubble
│   │   │       ├── CitationBadge.tsx    ← Clickable page citation
│   │   │       ├── StreamingMessage.tsx ← Real-time token streaming display
│   │   │       └── ChatInput.tsx        ← Input bar with send button
│   │   │
│   │   ├── hooks/
│   │   │   ├── useUpload.ts             ← Upload mutation + progress tracking
│   │   │   ├── useDocuments.ts          ← Document list query
│   │   │   ├── useDocumentStatus.ts     ← Polling hook for indexing status
│   │   │   └── useChat.ts               ← SSE streaming chat hook
│   │   │
│   │   ├── services/
│   │   │   ├── api.ts                   ← Axios instance + interceptors
│   │   │   ├── documents.ts             ← Document API calls
│   │   │   └── chat.ts                  ← Chat SSE connection manager
│   │   │
│   │   ├── store/
│   │   │   ├── authStore.ts             ← Zustand auth state (token, user)
│   │   │   └── chatStore.ts             ← Zustand chat messages state
│   │   │
│   │   ├── types/
│   │   │   ├── document.ts              ← Document, DocumentStatus types
│   │   │   ├── chat.ts                  ← Message, Citation, StreamDelta types
│   │   │   └── api.ts                   ← API response wrapper types
│   │   │
│   │   └── utils/
│   │       ├── formatters.ts            ← Date, file size formatters
│   │       └── sse.ts                   ← SSE event parser utility
│   │
│   ├── package.json
│   ├── tsconfig.json                    ← Strict mode enabled
│   ├── vite.config.ts
│   └── tailwind.config.ts
│
└── infra/
    ├── docker-compose.yml               ← Full local dev stack
    ├── docker-compose.prod.yml          ← Prod overrides
    ├── Dockerfile.api
    ├── Dockerfile.worker
    ├── Dockerfile.frontend
    └── k8s/
        ├── namespace.yaml
        ├── api-deployment.yaml
        ├── worker-deployment.yaml
        ├── frontend-deployment.yaml
        ├── kafka-statefulset.yaml
        ├── redis-statefulset.yaml
        ├── postgres-statefulset.yaml
                    ├── karpenter/
            │   ├── ec2nodeclass.yaml
            │   ├── nodepool-general.yaml
            │   ├── nodepool-ingestion-workers.yaml
            │   └── nodepool-gpu.yaml
            ├── keda-scaledobject.yaml       ← KEDA autoscale on Kafka consumer lag
        ├── hpa-api.yaml                 ← HPA for API pods on CPU/memory
        ├── ingress.yaml                 ← AWS ALB Ingress Controller
        ├── secrets.yaml                 ← References AWS Secrets Manager via ESO
        ├── monitoring/
            ├── otel-collector.yaml      ← DaemonSet + Deployment, full pipeline config
            ├── prometheus.yaml          ← Prometheus + AlertManager
            ├── grafana.yaml             ← Grafana + data sources (Prometheus, Loki, Tempo)
            ├── loki.yaml                ← Grafana Loki StatefulSet + S3 backend config
            ├── tempo.yaml               ← Grafana Tempo StatefulSet + S3 backend config
            ├── jaeger.yaml              ← Jaeger Deployment (secondary trace UI)
            ├── promtail.yaml            ← Promtail DaemonSet → Loki
            ├── fluent-bit.yaml          ← Fluent Bit DaemonSet → Loki + CloudWatch
            ├── glitchtip.yaml           ← GlitchTip Deployment (open-source error tracking)
            ├── uptime-kuma.yaml         ← Uptime Kuma Deployment
            ├── akhq.yaml                ← Kafka UI
            ├── exporters/
            │   ├── postgres-exporter.yaml
            │   ├── redis-exporter.yaml
            │   └── kafka-exporter.yaml
            └── dashboards/              ← Grafana dashboard JSON (provisioned via ConfigMap)
                ├── system-overview.json
                ├── ingestion-pipeline.json
                ├── retrieval-chat.json
                └── infrastructure.json
```

---

## 4. Tech Stack & Decisions

### Backend
| Component | Technology | Decision Rationale |
|---|---|---|
| API Framework | **FastAPI** | Async-native, auto OpenAPI docs, best DI system in Python |
| ORM | **SQLAlchemy 2.0 (async)** | Typed, async sessions, native pgvector support |
| DB | **PostgreSQL 16 + pgvector** | No separate vector DB to manage; HNSW index; hybrid SQL+vector |
| Migrations | **Alembic** | Version-controlled schema, auto-generates diffs from models |
| Queue Broker | **Kafka (MSK on AWS)** | 1M+ msg/sec, immutable log, replayable, multi-consumer, durable |
| Task Worker | **Celery + Kafka broker** | Mature retry logic; Kafka broker replaces Redis for queuing |
| Semantic Cache | **RedisVL** | Purpose-built vector similarity cache; sub-2ms repeat queries |
| Agent Framework | **LangGraph** | Stateful multi-step agents, explicit graph, debuggable, streamable |
| Embeddings | **OpenAI text-embedding-3-large** | 3072-dim; best retrieval quality; swap to `bge-m3` for self-hosted |
| LLM | **GPT-4o (streaming)** | Best reasoning + tool use; swappable to Claude 3.5 via LangChain |
| PDF Parser | **PyMuPDF (fitz)** | 10x faster than pdfplumber; native text extraction + OCR fallback |
| DOCX Parser | **python-docx** | Official library; paragraphs, tables, headings |
| OCR | **Tesseract** | Fallback for scanned/image-only PDFs |
| Object Storage | **AWS S3** | Permanent raw file storage; presigned URLs; lifecycle policies |
| Config | **pydantic-settings** | Typed env vars; fails at startup if misconfigured |
| Logging | **structlog** | JSON structured logs; request ID correlation; OTel integration |

### Frontend
| Component | Technology | Decision Rationale |
|---|---|---|
| Framework | **React 18** | Industry standard; concurrent features for streaming UI |
| Language | **TypeScript (strict)** | Catches bugs at compile time; required for enterprise code |
| Build | **Vite** | Fastest dev server + build; native ESM |
| Styling | **Tailwind CSS** | Utility-first; no CSS file sprawl |
| State | **Zustand** | Lightweight, no boilerplate, TypeScript-first |
| Server State | **TanStack Query v5** | Caching, polling, mutations, optimistic updates |
| HTTP Client | **Axios** | Interceptors for auth token injection; error handling |
| Routing | **React Router v6** | Industry standard; nested routes |
| SSE Streaming | **Native EventSource / custom hook** | Real-time token streaming from FastAPI SSE |
| Forms | **React Hook Form + Zod** | Typed validation; integrates with TypeScript schemas |
| UI Components | **shadcn/ui + Radix UI** | Accessible, unstyled primitives; fully customisable |
| Icons | **Lucide React** | Clean, consistent icon set |
| File Upload | **react-dropzone** | Drag-and-drop with MIME type validation |

### AWS Infrastructure
| Service | Purpose |
|---|---|
| **EKS** | Kubernetes cluster (API, workers, frontend pods) |
| **MSK (Managed Kafka)** | Fully managed Kafka — no ops overhead |
| **RDS PostgreSQL 16** | Managed Postgres with Multi-AZ, pgvector extension |
| **ElastiCache Redis** | RedisVL semantic cache + Celery result backend |
| **S3** | Raw document storage |
| **ECR** | Docker image registry |
| **ALB** | Application Load Balancer + WAF |
| **Route53** | DNS |
| **ACM** | TLS certificates |
| **CloudWatch** | AWS-native logs, metrics, alarms |
| **AWS Secrets Manager** | All secrets (DB, API keys, JWT secret) |
| **External Secrets Operator** | Sync Secrets Manager → K8s secrets |
| **KEDA** | Event-driven autoscaling on Kafka consumer lag |
| **Karpenter** | Node autoprovisioning — automatically adds/removes EC2 nodes based on pod demand |
| **IAM IRSA** | Pod-level IAM roles (no static credentials in pods) |

---

## 5. Data Flow — End to End

```
═══════════════════════════════════════════════════════════════════
 UPLOAD FLOW
═══════════════════════════════════════════════════════════════════

User (React)
  │  POST /api/v1/documents/upload  (multipart/form-data)
  ▼
FastAPI Upload Endpoint
  1. Validate file type (PDF/DOCX only) → 400 if invalid
  2. Validate file size (max 500MB)     → 413 if too large
  3. SHA-256 hash content               → deduplicate
  4. Upload raw bytes → AWS S3          → s3://bucket/uploads/{user_id}/{hash}.{ext}
  5. INSERT documents row (status=pending)
  6. Kafka PRODUCE → topic: doc.ingestion (partition key = user_id, acks=all)
  7. Return HTTP 202 { document_id, status: "queued" }
  │
  ▼
React frontend polls GET /documents/{id}/status every 3s
  → shows: queued → processing → indexed (or failed)

  │
  ▼ Kafka topic: doc.ingestion
  │
Celery Worker (Kafka consumer group: ingestion-workers)
  → task_acks_late=True (offset committed only after success)
  │
  ▼ IngestionPipeline.run()
  1. Download raw file from S3
  2. Parse → List[PageContent]        (PyMuPDF or python-docx)
  3. Chunk → List[Chunk]              (RecursiveCharacterTextSplitter, 512 tokens, 64 overlap)
  4. Embed → List[Vector 3072-dim]    (OpenAI text-embedding-3-large, batched 100/call)
  5. Bulk upsert → pgvector           (ON CONFLICT DO NOTHING — safe to retry)
  6. UPDATE document status=indexed
  │
  ├── On failure: retry up to 5x with exponential backoff (2^n seconds)
  └── After 5 failures: publish to doc.ingestion.dlq + status=failed

═══════════════════════════════════════════════════════════════════
 CHAT FLOW
═══════════════════════════════════════════════════════════════════

User (React ChatWindow)
  │  POST /api/v1/chat/query  { query, document_ids? }
  ▼
FastAPI Chat Endpoint
  │
  ├── 1. Check RedisVL SemanticCache (cosine similarity ≥ 0.90)
  │         HIT  → stream cached answer immediately (< 2ms)
  │         MISS → continue to agent
  │
  ▼ Cache miss
  │
LangGraph Agent (stateful graph execution)
  │
  ├── Node: route_query
  │     Classify: needs_retrieval | greeting | out_of_scope
  │     If greeting → answer directly, skip retrieval
  │
  ├── Node: search_documents
  │     HybridRetriever.retrieve(query, user_id)
  │       ├── Vector search  (HNSW, top 20, scoped to user_id)
  │       ├── BM25 keyword   (GIN full-text, top 20, scoped to user_id)
  │       └── RRF fusion     → top 8 chunks with citations
  │
  ├── Node: generate_answer
  │     GPT-4o streams answer grounded in retrieved context
  │     Tokens streamed → SSE → React StreamingMessage component
  │
  ├── Node: check_quality
  │     LLM self-grades: is answer fully grounded in context?
  │     PASS → END
  │     FAIL → refine_answer (max 2 refinement loops)
  │
  └── Node: refine_answer
        Re-generates with stricter grounding instruction
        → back to check_quality
  │
  ▼ Final answer
  FastAPI streams SSE events:
    { type: "delta",    content: "token" }
    { type: "done",     citations: [{page, doc_id}] }
  │
  RedisVL.store(query, answer)    ← cache for next similar query
  │
  ▼
React renders answer with citation badges
  CitationBadge → click → highlights source page in document viewer
```

---

## 6. Database — Models & Migrations

### 6.1 SQLAlchemy Models

**`models/base.py`**
- Abstract base with: `id` (UUID, primary key), `created_at` (TIMESTAMPTZ), `updated_at` (TIMESTAMPTZ, auto-updated via `onupdate`)
- All models inherit from this base

**`models/organisation.py`**
- Fields: `id`, `name`, `slug` (unique), `plan` (free/pro/enterprise), `created_at`
- Purpose: top-level multi-tenancy grouping

**`models/user.py`**
- Fields: `id`, `email` (unique), `hashed_password`, `org_id` (FK → organisations), `role` (admin/member), `is_active`, `created_at`
- Index: `email`, `org_id`

**`models/document.py`**
- Fields: `id`, `user_id` (FK → users), `org_id` (denormalised for fast scoping), `filename`, `file_type` (pdf/docx), `s3_key` (unique), `content_hash` (SHA-256, for dedup), `status` (pending/processing/indexed/failed), `page_count`, `chunk_count`, `file_size_bytes`, `error_msg`, `created_at`, `updated_at`
- Indexes: `user_id`, `org_id`, `status`, `content_hash`
- Constraints: `file_type` CHECK IN ('pdf', 'docx'), `status` CHECK IN (...)

**`models/chunk.py`**
- Fields: `id`, `document_id` (FK → documents, CASCADE DELETE), `user_id` (denormalised), `org_id` (denormalised), `chunk_index`, `content` (TEXT), `token_count`, `page_number`, `embedding` (vector(3072)), `metadata` (JSONB)
- Indexes:
  - HNSW: `embedding vector_cosine_ops` WITH `(m=16, ef_construction=128)` — primary ANN search
  - GIN: `to_tsvector('english', content)` — BM25 full-text keyword search
  - BTREE: `user_id`, `document_id`

### 6.2 Additional DB Objects (not in models — created via raw migration)

- `pgvector` extension
- `pg_trgm` extension
- `uuid-ossp` extension
- `set_updated_at()` trigger function → applied to `documents` table
- `dlq_events` table — tracks DLQ escalations for ops visibility (id, job_id, document_id, error, payload JSONB, retry_count, resolved, resolved_at)

### 6.3 Alembic Migration Strategy

**Setup:**
- `alembic.ini` at `backend/` root
- `migrations/env.py` imports all models and uses async SQLAlchemy engine
- `target_metadata = Base.metadata` so Alembic auto-detects schema diffs

**Migration naming convention:**
```
{revision_id}_{short_description}.py
e.g. 0001_create_users_and_organisations.py
     0002_create_documents.py
     0003_create_chunks_with_pgvector.py
     0004_add_dlq_events.py
```

**Migration rules:**
- Never edit a migration that has been applied to staging or production
- Always generate via `alembic revision --autogenerate -m "description"`
- Review autogenerated migration before applying — Alembic misses some things (e.g. HNSW indexes, GIN indexes, custom functions)
- HNSW index and GIN index must be added manually in the migration `upgrade()` function
- Every migration must have a working `downgrade()` function
- Run in CI before deploying: `alembic upgrade head`

**Migration execution in K8s:**
- Run as a Kubernetes Job before deploying new API pods
- Job uses same Docker image as API
- Command: `alembic upgrade head`
- Must complete successfully before API deployment proceeds

---

## 7. Upload & Ingestion Pipeline

### Upload Endpoint responsibilities (in order):
1. Authenticate user (JWT)
2. Validate `Content-Type` → only `application/pdf` and `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
3. Read file bytes into memory (streaming for large files)
4. Reject if `len(bytes) > 500MB`
5. Compute SHA-256 hash → check if `content_hash` already exists in documents table for this user → return existing document_id if duplicate
6. Upload to S3: key = `uploads/{user_id}/{content_hash}.{ext}`
7. INSERT document row with `status=pending`
8. Kafka PRODUCE with `acks=all`, `key=user_id` (partition by user), full payload in value
9. Emit Prometheus counter: `uploads_total{file_type, user_id}`
10. Return HTTP 202

### Ingestion Pipeline steps (inside Celery task):

**Step 1 — Download**
- Download file bytes from S3 using `storage.download(s3_key)`
- Update document `status=processing`

**Step 2 — Parse**
- PDF: use PyMuPDF (`fitz`) to extract text page by page
  - If extracted text < 50 chars on a page → OCR fallback via Tesseract (scanned PDF)
  - Extract metadata: page count, title, author if available
- DOCX: use `python-docx` to extract paragraphs, headings, and table cell text
  - DOCX has no page concept → treat as single logical page

**Step 3 — Chunk**
- Use `RecursiveCharacterTextSplitter` with separators: `["\n\n", "\n", ". ", "! ", "? ", " "]`
- `chunk_size=512` tokens, `overlap=64` tokens
- Each chunk carries: `chunk_index`, `content`, `page_number`, `token_count`, `metadata`

**Step 4 — Embed**
- Call OpenAI `text-embedding-3-large` in async batches of 100 chunks
- Batches run in parallel (`asyncio.gather`)
- Retry on OpenAI rate limit with exponential backoff

**Step 5 — Index**
- Bulk upsert all chunks to `document_chunks` in a single DB transaction
- Use `INSERT ... ON CONFLICT DO NOTHING` — safe to retry
- Batch size: 500 rows per insert statement

**Step 6 — Finalise**
- UPDATE `documents` SET `status=indexed`, `chunk_count=N`, `page_count=M`
- Emit Prometheus histogram: `ingestion_duration_seconds{file_type}`
- Emit Prometheus histogram: `chunks_per_document`
- Invalidate user's RedisVL cache entries (optional — new doc changes answer space)

---

## 8. Kafka Queue, Celery Workers & DLQ

### Why Kafka as Celery Broker
- Celery supports Kafka via `celery-kafka-dispatcher` or custom transport
- Kafka replaces Redis as the Celery broker — all task messages go through Kafka
- Benefits over Redis broker: durable disk storage, replay, multi-consumer, partition ordering
- Redis is kept for Celery **result backend** only (storing task return values)
- RedisVL uses Redis for semantic cache (separate DB index)

### Kafka Topics

| Topic | Partitions | Replication | Retention | Purpose |
|---|---|---|---|---|
| `doc.ingestion` | 32 | 3 | 7 days | Primary ingestion jobs |
| `doc.ingestion.retry` | 8 | 3 | 1 day | Retry queue with delay |
| `doc.ingestion.dlq` | 8 | 3 | 30 days | Failed jobs for ops |
| `doc.events` | 16 | 3 | 7 days | Status change events (webhooks, audit) |

**Partition key:** `user_id` — guarantees per-user message ordering

### Celery Configuration (celeryconfig.py)
- `broker_url`: Kafka bootstrap servers (MSK endpoint in prod)
- `result_backend`: Redis (ElastiCache in prod)
- `task_acks_late = True` — ACK only after task success (0% data loss)
- `task_reject_on_worker_lost = True` — requeue if pod dies mid-task
- `task_serializer = "json"`
- `worker_prefetch_multiplier = 1` — one task per worker, prevents memory spikes on large docs
- `task_routes`: route `ingest_document` to `ingestion` queue
- `task_max_retries = 5`
- `task_default_retry_delay = 30`

### Worker Scaling
- Worker pods run in K8s Deployment
- **KEDA ScaledObject** watches `doc.ingestion` consumer group lag
- `minReplicas: 5` (always warm), `maxReplicas: 500`
- `lagThreshold: 1000` — add 1 pod per 1000 pending messages

### Retry Strategy
- Retry 1: 1s delay
- Retry 2: 2s delay
- Retry 3: 4s delay
- Retry 4: 8s delay
- Retry 5: 16s delay
- After retry 5: DLQ escalation

### DLQ (Dead Letter Queue)
- DLQ is Kafka topic `doc.ingestion.dlq` — durable 30-day retention
- On escalation: publish to DLQ topic + mark document `status=failed` in DB
- AKHQ UI provides ops dashboard for DLQ inspection
- Replay: reset consumer group offset or use `dlq_replay.py` script
- Admin API endpoint: `POST /admin/dlq/replay` (admin-only JWT role)

### 0% Data Loss Guarantees (layered)
1. Kafka `acks=all` — message durably written to all replicas before producer returns
2. `enable_idempotence=True` — no duplicate messages on producer retry
3. `enable_auto_commit=False` — offset committed only after pipeline succeeds
4. `task_acks_late=True` — Celery ACKs only after task completes
5. `task_reject_on_worker_lost=True` — requeued if pod dies
6. Exponential backoff retries (5x) before DLQ
7. DLQ topic: 30-day retention for ops replay
8. S3 raw file: original always available for re-ingestion from scratch
9. Idempotent DB inserts: safe to retry pipeline multiple times

---

## 9. Vector Search & Hybrid Retrieval

### Strategy: Hybrid = Vector + BM25 + RRF

**Why hybrid over pure vector:**
- Pure vector: misses exact terms (product codes, names, acronyms)
- Pure BM25: misses semantic paraphrasing ("revenue" vs "income")
- Hybrid with RRF: gets the best of both — highest recall in benchmarks

### Vector Search
- Algorithm: HNSW (Hierarchical Navigable Small World)
- Index params: `m=16`, `ef_construction=128` — 99% recall, <15ms P99 at 100M vectors
- Distance: cosine similarity (`vector_cosine_ops`)
- Query scoped to `user_id` (row-level isolation)
- Fetch top 20 before fusion

### Keyword Search
- PostgreSQL `tsvector` + `GIN` index
- `plainto_tsquery('english', query)` — handles stopwords, stemming
- `ts_rank_cd` scoring function
- Scoped to `user_id`
- Fetch top 20 before fusion

### RRF Fusion
- Reciprocal Rank Fusion: `score(d) = Σ 1 / (k + rank(d))` where `k=60`
- Merge both top-20 lists → unified ranking
- Return top 8 chunks to agent

### Reranker (optional, enable for premium tier)
- Cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`)
- Takes query + each chunk → relevance score (more accurate than bi-encoder)
- Adds ~50ms latency — worth it for long complex documents

---

## 10. RedisVL Semantic Cache

### Purpose
Cache LLM answers by semantic similarity — not exact string match.
"What is total revenue?" and "What's the revenue figure?" → same cached answer.

### Configuration
- Library: `redisvl` `SemanticCache` class
- Similarity threshold: `0.90` cosine similarity (tune per use case)
- TTL: 3600 seconds (1 hour) per cached entry
- Vectorizer: same model as ingestion (`text-embedding-3-large`) — consistent embedding space
- Redis DB: dedicated index (separate from Celery result backend)

### Namespacing
- Cache keys namespaced by `user_id` — prevents cross-tenant cache pollution
- Format: `cache:user:{user_id}:{query_embedding_hash}`
- On new document upload: invalidate all cache entries for that user

### Cache Failure Handling
- Cache read/write failures must NEVER break the chat flow
- Wrap all cache calls in `try/except` — log warning, continue to agent

### Cost Impact
- Estimated 30–60% of production queries are semantically similar repeats
- Each cache hit saves ~$0.01–$0.05 in LLM API costs + ~1000ms latency

---

## 11. LangGraph Agent

### Agent State (AgentState TypedDict)
Fields that flow through all nodes:
- `query` — original user question
- `user_id`, `org_id`
- `messages` — LangGraph message history (Annotated with `add_messages`)
- `retrieved_chunks` — List of RetrievedChunk objects from retrieval
- `context` — formatted string of chunks with page numbers
- `answer` — generated answer text
- `quality_pass` — bool from self-grading node
- `refinement_count` — int, max 2
- `citations` — List of `{page_number, document_id, score}`

### Nodes

**`route_query`**
- Classify query: `needs_retrieval` | `greeting` | `out_of_scope`
- Greetings → set answer directly, skip to END
- Out of scope → "I can only answer questions about your documents"

**`search_documents`**
- Call `HybridRetriever.retrieve(query, user_id)`
- Build formatted context string with page citations
- Store chunks and citations in state

**`generate_answer`**
- Call GPT-4o with system prompt + context + question
- Streaming enabled — tokens flow to SSE response
- Store full answer in state

**`check_quality`**
- Ask LLM: "Is this answer fully grounded in the context? Reply PASS or FAIL"
- If `refinement_count >= 2` → force PASS (safety valve)
- Return `quality_pass` bool

**`refine_answer`**
- Re-generate with explicit instruction: stay grounded, cite pages, say "not found" if missing
- Increment `refinement_count`
- Returns to `check_quality`

### Graph Edges
```
START → route_query
route_query → END                   (if greeting/out_of_scope)
route_query → search_documents      (if needs_retrieval)
search_documents → generate_answer
generate_answer → check_quality
check_quality → END                 (if quality_pass=True)
check_quality → refine_answer       (if quality_pass=False)
refine_answer → check_quality       (loop, max 2x)
```

### Prompts (all in `prompts.py`)
- `SYSTEM_PROMPT` — grounding rules, citation format, fallback message
- `QUALITY_PROMPT` — grounding checker instructions
- `REFINE_PROMPT` — stricter grounding instruction for re-generation
- Rule: **never write prompts inline in node functions**

---

## 12. API Layer — FastAPI

### Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Public | Register new user |
| POST | `/api/v1/auth/login` | Public | Login → JWT token |
| POST | `/api/v1/documents/upload` | JWT | Upload PDF/DOCX |
| GET | `/api/v1/documents` | JWT | List user's documents |
| GET | `/api/v1/documents/{id}` | JWT | Get document detail |
| GET | `/api/v1/documents/{id}/status` | JWT | Poll indexing status |
| DELETE | `/api/v1/documents/{id}` | JWT | Delete document + chunks |
| POST | `/api/v1/chat/query` | JWT | Chat query → SSE stream |
| GET | `/api/v1/health` | Public | Liveness probe |
| GET | `/api/v1/ready` | Public | Readiness probe (checks DB + Redis) |
| GET | `/api/v1/admin/dlq` | Admin JWT | List DLQ entries |
| POST | `/api/v1/admin/dlq/replay` | Admin JWT | Replay DLQ messages |
| GET | `/metrics` | Internal | Prometheus scrape endpoint |

### Middleware Stack (applied in order)
1. `RequestIDMiddleware` — inject `X-Request-ID` header (UUID), attach to structlog context
2. `TracingMiddleware` — OpenTelemetry trace per request → Jaeger
3. `TimingMiddleware` — record request duration → Prometheus histogram
4. `CORSMiddleware` — allow frontend origin
5. Global exception handlers — convert typed exceptions to JSON responses

### SSE Streaming Protocol
Chat responses use Server-Sent Events:
```
data: {"type": "delta", "content": "token text"}
data: {"type": "delta", "content": " more tokens"}
data: {"type": "citations", "citations": [{"page": 5, "document_id": "..."}]}
data: {"type": "done"}
```
Frontend reads these via `EventSource` or `fetch` with `ReadableStream`.

---

## 13. Frontend — React + TypeScript

### Pages

**`LoginPage`**
- Email + password form with React Hook Form + Zod validation
- On success: store JWT in Zustand `authStore`, redirect to Dashboard
- Handle 401 errors gracefully

**`DashboardPage`**
- Left sidebar: list of uploaded documents with status badges (queued/processing/indexed/failed)
- Main area: DropZone for new uploads
- Click document → navigate to ChatPage
- TanStack Query polls `GET /documents/{id}/status` every 3s while `status !== 'indexed'`

**`ChatPage`**
- Split layout: document info panel (left) + chat window (right)
- ChatWindow renders MessageBubble components
- StreamingMessage shows tokens as they arrive via SSE
- CitationBadge: clickable badge showing "Page 5" — future: scroll to page in viewer
- ChatInput: textarea with send button, disabled while streaming

### State Management

**`authStore` (Zustand)**
- `token: string | null`
- `user: UserOut | null`
- `login(token, user)` / `logout()`
- Persisted to `localStorage`

**`chatStore` (Zustand)**
- `messages: Message[]` per document
- `addMessage()`, `appendDelta()` (for streaming), `clearMessages()`

### API Layer (`services/`)

**`api.ts`**
- Axios instance with `baseURL = VITE_API_URL`
- Request interceptor: attach `Authorization: Bearer {token}`
- Response interceptor: on 401 → clear auth + redirect to login

**`chat.ts` — SSE Manager**
- Opens `fetch` stream to `/api/v1/chat/query`
- Reads `ReadableStream`, parses SSE lines
- Calls callbacks: `onDelta(token)`, `onCitations(citations)`, `onDone()`
- Handles connection errors and reconnection

### TypeScript Types (`types/`)

**`document.ts`**
```
DocumentStatus: "pending" | "processing" | "indexed" | "failed"
Document: { id, filename, file_type, status, chunk_count, page_count, created_at }
```

**`chat.ts`**
```
MessageRole: "user" | "assistant"
Citation: { page_number, document_id, score }
Message: { id, role, content, citations?, timestamp }
StreamDelta: { type: "delta" | "citations" | "done", content?, citations? }
```

### Environment Variables (frontend)
```
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=DocAgent
```

### Build & Deployment
- `vite build` → static assets in `dist/`
- Served via Nginx in Docker container
- Nginx also proxies `/api/*` to backend (avoids CORS in prod)
- Frontend Docker image deployed to EKS as separate Deployment

---

## 14. Auth & Multi-Tenancy

### JWT Strategy
- Access token: 24h expiry, signed with `HS256` and `JWT_SECRET`
- Payload: `{ sub: user_id, org_id, role, exp }`
- No refresh tokens in v1 (add later)
- `JWT_SECRET` stored in AWS Secrets Manager → injected via External Secrets Operator

### Multi-Tenancy Rules
- Every DB table has `user_id` column
- Every DB query MUST include `WHERE user_id = :user_id` — never omit this
- `org_id` denormalised onto `documents` and `chunks` for org-level queries (future: org-scoped search)
- S3 keys include `user_id` in path
- Semantic cache keys include `user_id` prefix
- Admin endpoints require `role=admin` in JWT

### Security Checklist
- [ ] All endpoints behind JWT except `/health`, `/ready`, `/metrics`, auth endpoints
- [ ] All vector search queries include `user_id` filter
- [ ] All document queries include `user_id` filter
- [ ] S3 presigned URLs expire in 15 minutes
- [ ] File type validated by content inspection, not just extension/MIME
- [ ] SQL uses bound parameters (no string interpolation ever)
- [ ] Secrets never in environment variables in prod — AWS Secrets Manager only

---

## 15. AWS Cloud Infrastructure

### Architecture Overview
```
Internet
  │
  ▼
Route53 (DNS)
  │
  ▼
ACM (TLS)
  │
  ▼
ALB (Application Load Balancer)
  │     WAF rules (rate limiting, IP blocking)
  │
  ├──▶ /api/*     → EKS API Service (FastAPI pods)
  └──▶ /*         → EKS Frontend Service (Nginx pods)

EKS Cluster
  ├── Namespace: docagent-prod
  │     ├── API Deployment         (3–20 pods, HPA on CPU)
  │     ├── Worker Deployment      (5–500 pods, KEDA on Kafka lag)
  │     ├── Frontend Deployment    (2–5 pods, HPA)
  │     └── Monitoring Namespace
  │           ├── Prometheus
  │           ├── Grafana
  │           ├── Jaeger
  │           └── OTel Collector
  │
  ├── MSK (Managed Kafka)
  │     3 brokers, Multi-AZ, mTLS auth
  │     Topics: doc.ingestion, doc.ingestion.retry, doc.ingestion.dlq, doc.events
  │
  ├── RDS PostgreSQL 16 (Multi-AZ)
  │     pgvector extension enabled
  │     Read replica for analytics queries
  │     Daily snapshots → S3
  │
  ├── ElastiCache Redis (Cluster mode)
  │     Semantic cache (RedisVL)
  │     Celery result backend
  │
  └── S3 Bucket: docagent-uploads-prod
        Versioning enabled
        Lifecycle: move to Glacier after 90 days
        Bucket policy: deny public access
```

### Karpenter Configuration Plan

**Why Karpenter over Cluster Autoscaler:**
| Concern | Cluster Autoscaler | Karpenter |
|---|---|---|
| Node provisioning speed | 3–5 minutes | 30–60 seconds |
| Instance type selection | Fixed node group types | Picks best fit from any EC2 family |
| Bin packing | Poor — one instance type | Excellent — right-sizes to pod requests |
| Spot handling | Manual node groups per type | Automatic Spot fallback to On-Demand |
| Node consolidation | No | Yes — terminates underused nodes automatically |
| Cost optimisation | Manual | Automatic — always picks cheapest fitting instance |

**NodePools to define (`infra/k8s/karpenter/`):**

`NodePool: general`
- Purpose: API pods, frontend pods, monitoring stack
- Instance families: `m7i`, `m7g`, `m6i`, `m6g` (Intel + ARM Graviton mix)
- Capacity type: On-Demand (stable, predictable workloads)
- Zones: `us-east-1a`, `us-east-1b`, `us-east-1c` (Multi-AZ)
- Taints: none
- Node labels: `workload-type: general`
- Limits: max 50 nodes, max 400 vCPU, max 1600Gi memory

`NodePool: ingestion-workers`
- Purpose: Celery ingestion worker pods only
- Instance families: `c7i`, `c7g`, `c6i`, `c6g` (compute-optimised, CPU-heavy embedding)
- Capacity type: Spot (80%) + On-Demand (20%) via `capacityType: [spot, on-demand]`
- Zones: all 3 AZs
- Taints: `workload-type=ingestion-worker:NoSchedule` (only worker pods land here)
- Node labels: `workload-type: ingestion-worker`
- Limits: max 200 nodes, max 1600 vCPU
- Disruption: `consolidationPolicy: WhenUnderutilized` — scale down idle nodes fast

`NodePool: gpu` (optional — activate when switching to self-hosted embeddings)
- Purpose: `bge-m3` embedding model server
- Instance families: `g5` (NVIDIA A10G GPU)
- Capacity type: On-Demand
- Taints: `nvidia.com/gpu=true:NoSchedule`
- Limits: max 5 nodes

**EC2NodeClass to define:**
- AMI: `AL2023` (Amazon Linux 2023 — recommended for EKS)
- Instance profile: Karpenter node instance profile (IRSA)
- Security groups: EKS node security group
- Subnets: private subnets only (tagged `karpenter.sh/discovery: docagent-prod`)
- User data: EKS bootstrap + kubelet config (max pods, image GC thresholds)
- Block device: 100Gi gp3 EBS root volume

**Pod scheduling rules (set on Deployments):**
```yaml
# Worker pods — land on ingestion-worker NodePool only
tolerations:
  - key: workload-type
    value: ingestion-worker
    effect: NoSchedule
nodeSelector:
  workload-type: ingestion-worker

# API/frontend pods — land on general NodePool
nodeSelector:
  workload-type: general
```

**Karpenter + KEDA interaction:**
```
KEDA detects Kafka consumer lag > threshold
  → KEDA increases Worker Deployment replicas (e.g. 5 → 50)
  → New pods are Pending (no nodes available)
  → Karpenter detects Pending pods with ingestion-worker toleration
  → Karpenter provisions c7i Spot nodes in ~45 seconds
  → Pods scheduled, processing resumes

Kafka lag drops to 0
  → KEDA scales Worker Deployment back to minReplicas (5)
  → Nodes become underutilised
  → Karpenter consolidation kicks in after 30s
  → Karpenter drains + terminates excess nodes
  → EC2 Spot costs drop to near zero between bursts
```

**Files to create in `infra/k8s/karpenter/`:**
- `ec2nodeclass.yaml` — EC2NodeClass definition (AMI, subnets, security groups)
- `nodepool-general.yaml` — general workload NodePool
- `nodepool-ingestion-workers.yaml` — compute-optimised Spot NodePool
- `nodepool-gpu.yaml` — GPU NodePool (committed but inactive until needed)
- `karpenter-controller-irsa.yaml` — IAM role for Karpenter controller (EC2 permissions)

**IAM permissions Karpenter needs (IRSA):**
- `ec2:RunInstances`, `ec2:TerminateInstances`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceTypes`
- `ec2:CreateFleet`, `ec2:CreateLaunchTemplate`
- `iam:PassRole` (to pass instance profile to new nodes)
- `pricing:GetProducts` (for cost-aware instance selection)
- `sqs:*` on Karpenter interruption queue (handles Spot interruption notices)

**Spot interruption handling:**
- Karpenter watches EC2 Spot interruption notices via SQS queue
- On interruption notice: cordons node, drains pods gracefully (2-minute warning)
- Celery worker uses `task_acks_late=True` + `task_reject_on_worker_lost=True`
  → In-flight task is re-queued to Kafka before node terminates
  → 0% data loss even on Spot interruption
- API pod role: `s3:PutObject`, `s3:GetObject`, `secretsmanager:GetSecretValue`
- Worker pod role: `s3:GetObject`, `secretsmanager:GetSecretValue`
- No static AWS credentials in any pod — IRSA only
- Each service gets minimum required permissions

### Networking
- VPC with public subnets (ALB) and private subnets (EKS, RDS, MSK, ElastiCache)
- EKS nodes in private subnets — no direct internet access
- NAT Gateway for outbound traffic (OpenAI API calls)
- Security groups: RDS only accessible from EKS worker nodes; MSK only from EKS

### CI/CD Pipeline
```
Developer pushes to main branch
  │
  ▼
GitHub Actions
  1. Run tests (pytest, vitest)
  2. Run linting (ruff, eslint)
  3. Run type checks (mypy, tsc)
  4. Build Docker images
  5. Push to ECR
  6. Run Alembic migrations (K8s Job)
  7. Rolling deploy to EKS (kubectl set image)
  8. Health check: wait for /ready to return 200
```

---

## 16. Observability Stack

> "You can't fix what you can't see."
> Every request, every queue message, every DB query must be traceable.

### Observability Philosophy
> 100% open-source. Zero vendor lock-in. All data stays in your cluster.
> The stack follows the **OpenTelemetry standard** as the single instrumentation layer —
> backends are swappable without touching application code.

### The Three Pillars

| Pillar | What It Answers |
|---|---|
| **Logs** | What happened and when? Full event trail. |
| **Metrics** | How is the system performing over time? Trends, SLOs. |
| **Traces** | Why is this request slow? Where is the bottleneck? |

### Full Stack Components

| Tool | Category | Role | Deployed As |
|---|---|---|---|
| **structlog** | Logs | Structured JSON application logging | Python library |
| **OpenTelemetry SDK** | All pillars | Single instrumentation layer for logs, metrics, traces | Python + JS library |
| **OTel Collector** | All pillars | Centralised telemetry pipeline — receives, processes, exports | K8s DaemonSet + Deployment |
| **Prometheus** | Metrics | Metrics scraping, storage, alerting rules | K8s Deployment |
| **Prometheus AlertManager** | Metrics | Alert routing → Slack / PagerDuty | K8s Deployment |
| **Grafana** | Metrics + Logs + Traces | Unified dashboard UI (queries Prometheus, Loki, Tempo) | K8s Deployment |
| **Grafana Loki** | Logs | Log aggregation and querying (like ELK but lightweight) | K8s StatefulSet |
| **Promtail** | Logs | Log shipper — tails pod logs → Loki | K8s DaemonSet |
| **Grafana Tempo** | Traces | Distributed trace storage and querying | K8s StatefulSet |
| **Jaeger** | Traces | Alternative trace UI (optional alongside Tempo) | K8s Deployment |
| **GlitchTip** | Errors | Open-source Sentry alternative — exception tracking + releases | K8s Deployment |
| **Uptime Kuma** | Uptime | Self-hosted uptime/health monitoring with alerting | K8s Deployment |
| **AKHQ** | Kafka | Kafka topic browser, consumer lag, DLQ inspection | K8s Deployment |
| **Fluent Bit** | Logs | K8s pod log collector → Loki + CloudWatch | K8s DaemonSet |
| **kube-state-metrics** | Metrics | K8s object metrics (pod states, deployments) | K8s Deployment |
| **node-exporter** | Metrics | Host-level CPU/memory/disk metrics | K8s DaemonSet |
| **postgres-exporter** | Metrics | PostgreSQL metrics → Prometheus | K8s Deployment |
| **redis-exporter** | Metrics | Redis metrics → Prometheus | K8s Deployment |
| **kafka-exporter** | Metrics | Kafka consumer lag + broker metrics → Prometheus | K8s Deployment |

---

### 16.1 Structured Logging (structlog)

**Setup:**
- Configure structlog with JSON renderer in production, coloured console in development
- Every log line is a JSON object — machine-readable, searchable in CloudWatch
- Bind `request_id`, `user_id`, `document_id` to log context at request start
- Log at `INFO` level by default; `DEBUG` behind feature flag

**Required log fields on every line:**
```json
{
  "timestamp": "2025-01-01T10:00:00.123Z",
  "level": "info",
  "service": "api",
  "event": "pipeline.complete",
  "request_id": "abc-123",
  "user_id": "uuid",
  "document_id": "uuid",
  "duration_ms": 8430,
  "chunks_indexed": 142
}
```

**Key log events to emit:**
- `upload.received`, `upload.validated`, `upload.s3_uploaded`, `upload.enqueued`
- `pipeline.start`, `pipeline.downloaded`, `pipeline.parsed`, `pipeline.chunked`, `pipeline.embedded`, `pipeline.indexed`, `pipeline.complete`
- `pipeline.retry`, `pipeline.dlq_escalated`, `pipeline.failed`
- `retrieval.start`, `retrieval.vector_search_done`, `retrieval.keyword_search_done`, `retrieval.rrf_done`
- `cache.hit`, `cache.miss`, `cache.stored`, `cache.error`
- `agent.route`, `agent.search`, `agent.generate`, `agent.quality_pass`, `agent.quality_fail`, `agent.refine`, `agent.complete`
- `kafka.produced`, `kafka.consumed`, `kafka.commit`
- `auth.login`, `auth.token_invalid`, `auth.unauthorized`

---

### 16.2 Distributed Tracing (OpenTelemetry → Grafana Tempo + Jaeger)

**Purpose:** Visualise the full journey of a request across API → Kafka → Worker → DB → LLM.

**Trace backends:**
- **Grafana Tempo** — primary trace store; integrates directly with Grafana dashboards; S3-compatible object storage backend (use AWS S3 or MinIO); cost-efficient at high volume
- **Jaeger** — secondary trace UI; useful for detailed span inspection and dependency graphs; receives same traces via OTel Collector fan-out

**OTel Collector pipeline:**
- Receives traces from all services on OTLP port (gRPC 4317 / HTTP 4318)
- Processes: batch, memory limiter, resource attributes
- Exports to: Grafana Tempo (primary) + Jaeger (secondary) simultaneously

**Instrumentation (auto + manual):**
- `opentelemetry-instrumentation-fastapi` → auto-instruments all HTTP endpoints
- `opentelemetry-instrumentation-sqlalchemy` → auto-instruments all DB queries
- `opentelemetry-instrumentation-redis` → auto-instruments Redis calls
- `opentelemetry-instrumentation-kafka-python` → instruments Kafka produce/consume
- Manual spans for: S3 operations, OpenAI API calls, LangGraph node execution

**Trace structure for upload + ingestion:**
```
Trace: POST /api/v1/documents/upload
  │
  ├── Span: validate_file (2ms)
  ├── Span: s3_upload (450ms)
  ├── Span: db_insert_document (8ms)
  └── Span: kafka_produce (3ms)

Trace: celery.ingest_document (linked via trace context propagated in Kafka message)
  │
  ├── Span: s3_download (380ms)
  ├── Span: parse_pdf (1200ms)
  │     Attribute: pages=48
  ├── Span: chunk_text (45ms)
  │     Attribute: chunks=142
  ├── Span: embed_batch (2300ms)
  │     Attribute: vectors=142, model=text-embedding-3-large
  ├── Span: db_bulk_upsert (180ms)
  │     Attribute: rows=142
  └── Span: db_update_status (5ms)
```

**Trace context propagation:**
- Inject W3C `traceparent` header into Kafka message payload
- Worker extracts and continues the trace from the same trace ID
- This links upload trace → ingestion trace → single timeline in Jaeger

**Trace storage:**
- Grafana Tempo: object storage backend (S3 bucket: `docagent-traces-prod`)
- Jaeger: Badger (local) for staging; Cassandra or Elasticsearch for production
- Retention: 7 days of traces in Tempo; 3 days in Jaeger
- Sampling: 100% in staging, 10% in production (head-based via OTel Collector)

---

### 16.3 Metrics (Prometheus)

**Scrape targets:**
- FastAPI `/metrics` endpoint (via `prometheus-fastapi-instrumentator`)
- Celery worker metrics (via `celery-prometheus-exporter`)
- PostgreSQL metrics (via `postgres_exporter`)
- Redis metrics (via `redis_exporter`)
- Kafka metrics (via `kafka_exporter` or MSK CloudWatch integration)
- Node metrics (via `node_exporter` on EKS nodes)

**Custom application metrics to define in `core/metrics.py`:**

*Upload metrics:*
- `uploads_total` — Counter — labels: `file_type`, `status` (success/rejected)
- `upload_size_bytes` — Histogram — labels: `file_type`
- `upload_duration_seconds` — Histogram — end-to-end upload API latency

*Ingestion metrics:*
- `ingestion_duration_seconds` — Histogram — labels: `file_type`, `status`
- `chunks_per_document` — Histogram — distribution of chunk counts
- `ingestion_errors_total` — Counter — labels: `error_type`, `file_type`
- `dlq_events_total` — Counter — labels: `reason`

*Retrieval metrics:*
- `retrieval_latency_ms` — Histogram — labels: `search_type` (vector/keyword/hybrid)
- `chunks_retrieved` — Histogram — how many chunks returned per query
- `retrieval_errors_total` — Counter

*Cache metrics:*
- `semantic_cache_hits_total` — Counter
- `semantic_cache_misses_total` — Counter
- `semantic_cache_hit_rate` — Gauge (derived: hits / (hits + misses))

*Agent metrics:*
- `agent_total_duration_ms` — Histogram — full agent execution time
- `agent_refinement_loops_total` — Counter — how often quality check fails
- `agent_nodes_executed_total` — Counter — labels: `node_name`
- `llm_tokens_used_total` — Counter — labels: `model`, `direction` (input/output)

*Queue metrics:*
- `kafka_consumer_lag` — Gauge — per topic/partition (from kafka_exporter)
- `kafka_messages_produced_total` — Counter
- `kafka_messages_consumed_total` — Counter

*API metrics (auto from instrumentator):*
- `http_requests_total` — labels: `method`, `endpoint`, `status_code`
- `http_request_duration_seconds` — Histogram

---

### 16.4 Log Aggregation (Grafana Loki + Promtail)

**Why Loki over ELK:**
- 10x cheaper on storage — indexes only metadata (labels), not full text
- Native Grafana integration — logs, metrics, and traces in one UI
- Label-based querying with LogQL (similar to PromQL)
- Horizontally scalable on S3 backend

**Log pipeline:**
```
Pod stdout/stderr
      │
      ▼
Promtail DaemonSet          ← tails all pod logs, adds K8s labels
      │
      ▼
Grafana Loki                ← stores logs, indexed by labels
      │
      ▼
Grafana (LogQL queries)     ← search, filter, correlate with traces
```

**Loki labels to apply (via Promtail):**
- `namespace`, `pod`, `container`, `app`
- `service` (api / worker / frontend)
- `level` (info / warning / error)
- `request_id` (extracted from JSON log via pipeline stage)
- `user_id` (extracted from JSON log — useful for per-user debugging)
- `document_id` (extracted from JSON log — track a single document's journey)

**Loki storage backend:**
- Local dev: filesystem
- Production: S3 bucket (`docagent-logs-prod`) via Loki's S3 storage config

**Key LogQL queries to document for the team:**
```logql
# All errors in the last 1h
{app="docagent-api"} |= "error" | json | level="error"

# Full journey of one document (logs + worker)
{app=~"docagent-api|docagent-worker"} | json | document_id="<uuid>"

# DLQ escalations
{app="docagent-worker"} |= "dlq_escalated" | json

# Slow ingestion (> 30s)
{app="docagent-worker"} | json | event="pipeline.complete" | duration_ms > 30000

# All requests for a user
{app="docagent-api"} | json | user_id="<uuid>"
```

**Retention:** 30 days in production (set via Loki `compactor` retention rules)

---

### 16.5 Grafana Dashboards (Unified: Metrics + Logs + Traces)

Grafana connects to **three data sources**: Prometheus (metrics), Loki (logs), Tempo (traces).
This enables correlated observability — click a spike on a chart → see the logs → see the trace.

Define these dashboards (provision via ConfigMap in K8s):

**Dashboard 1: System Overview**
- Active API pods, Worker pods (Prometheus / kube-state-metrics)
- Total uploads today, documents indexed (Prometheus counters)
- HTTP error rate 5xx over time (Prometheus)
- Kafka consumer lag live (kafka-exporter → Prometheus)
- Redis cache hit rate (redis-exporter → Prometheus)
- Recent error logs panel (Loki — last 50 error lines)

**Dashboard 2: Ingestion Pipeline**
- Queue depth (Kafka consumer lag — Prometheus)
- Ingestion throughput docs/minute (Prometheus)
- P50 / P95 / P99 ingestion duration (Prometheus histogram)
- DLQ event count — alert if > 0 (Prometheus counter)
- Error breakdown by type: parse / embed / index (Prometheus labels)
- Log panel: live worker logs filtered by `event="pipeline.*"` (Loki)
- Trace link: click document_id → opens Tempo trace for that ingestion

**Dashboard 3: Retrieval & Chat**
- P50 / P95 / P99 retrieval latency ms (Prometheus)
- Cache hit rate over time (Prometheus)
- Agent refinement loop rate — % queries needing quality re-check (Prometheus)
- LLM token usage / hour — input vs output (Prometheus counter)
- Streaming TTFT P95 — time to first token (Prometheus)
- Log panel: agent node execution events (Loki)

**Dashboard 4: Infrastructure**
- EKS node CPU / memory per node (node-exporter → Prometheus)
- Pod restarts over time (kube-state-metrics → Prometheus)
- RDS CPU, connections, read/write IOPS, free storage (postgres-exporter)
- ElastiCache memory usage, eviction rate (redis-exporter)
- Kafka broker CPU, bytes in/out, under-replicated partitions (kafka-exporter)

**Dashboard 5: Error Tracking (GlitchTip)**
- GlitchTip has its own UI — link from Grafana via annotation or iframe panel
- Shows: exception type, frequency, affected users, stack trace, release version

**Grafana Alerting rules (all defined in Grafana, routed via AlertManager):**
- DLQ events > 0 for 5 minutes → page on-call
- Kafka consumer lag > 10,000 for 10 minutes → Slack warning
- API 5xx error rate > 1% over 5 minutes → Slack warning
- P99 retrieval latency > 100ms sustained → Slack warning
- RDS free storage < 20% → page on-call
- Worker pod count < 3 (all replicas unhealthy) → page on-call
- Redis memory > 80% → Slack warning
- Any unresolved GlitchTip issue spike (+500% in 10min) → Slack

---

### 16.6 Error Tracking — GlitchTip (Open-Source Sentry Alternative)

**Why GlitchTip:**
- 100% open-source (MIT licence), self-hosted
- API-compatible with Sentry SDK — use `sentry-sdk` Python package, just point DSN to GlitchTip
- Tracks: exceptions, performance issues, uptime monitors
- Stores data in your own PostgreSQL — no external data sharing

**Backend (FastAPI) integration:**
- Use `sentry-sdk[fastapi]` (works with GlitchTip via DSN URL)
- Point `GLITCHTIP_DSN` to self-hosted GlitchTip instance
- Auto-captures all unhandled exceptions with full stack trace
- Attach context: `user_id`, `request_id`, `document_id` to every event
- Filter out expected errors: 404, 401, 422 — only capture 500s
- Performance transactions: 10% sample rate

**Frontend (React) integration:**
- Use `@sentry/react` package (GlitchTip-compatible)
- ErrorBoundary wraps entire app — catches render errors
- Capture JS errors with component stack
- Attach `user_id` from Zustand auth store
- Breadcrumbs: route changes, API calls, button clicks

**GlitchTip deployment:**
- Deployed as K8s Deployment in monitoring namespace
- Uses the same RDS PostgreSQL cluster (separate `glitchtip` database)
- Or: deploy its own PostgreSQL StatefulSet in monitoring namespace
- Exposed internally via K8s Service (not public-facing)

**Alerting from GlitchTip:**
- Configure GlitchTip alert rules → Slack webhook on new unresolved issues
- Integrate with Grafana via annotation API: new GlitchTip issue → annotation on dashboards

---

### 16.7 Uptime Monitoring — Uptime Kuma

**Why Uptime Kuma:**
- 100% open-source, self-hosted
- Monitors: HTTP endpoints, TCP ports, Kafka topics (custom), DNS
- Beautiful status page (publicly shareable if desired)
- Alerting: Slack, email, webhook

**Monitors to configure:**
- `GET /api/v1/health` — liveness (every 30s)
- `GET /api/v1/ready` — readiness: checks DB + Redis connectivity (every 30s)
- RDS TCP port 5432 (every 60s)
- ElastiCache TCP port 6379 (every 60s)
- Kafka broker TCP port 9092 (every 60s)
- Frontend `GET /` (every 60s)

**Alert:** any monitor down for > 2 consecutive checks → Slack notification

---

### 16.8 OTel Collector Configuration

The OTel Collector is the **central telemetry hub** — all services send to it, it fans out to backends.

**Collector pipeline design:**
```
Receivers:
  - OTLP (gRPC :4317, HTTP :4318)   ← all app traces + metrics
  - Prometheus scrape (pull metrics)  ← /metrics endpoints

Processors:
  - memory_limiter                    ← prevent OOM
  - batch (timeout=5s, size=1000)     ← reduce export calls
  - resource (add: service.env, cluster.name)
  - tail_sampling (10% in prod)       ← head-based sampling

Exporters:
  Traces  → Grafana Tempo (OTLP gRPC)
  Traces  → Jaeger (OTLP gRPC)        ← fan-out both
  Metrics → Prometheus (remote_write)
  Logs    → Grafana Loki (loki exporter)
```

**Deployment:**
- DaemonSet for node-level collection (logs, node metrics)
- Deployment (2 replicas) for centralised trace/metric processing
- ConfigMap holds the full pipeline YAML — version controlled in `infra/k8s/monitoring/otel-collector.yaml`

---

### 16.9 AWS CloudWatch Integration (Minimal — Augments, Not Replaces)

CloudWatch is used only for AWS-managed service metrics that are not accessible from within K8s:

- **MSK (Kafka)** — broker CPU, disk, bytes in/out → CloudWatch (built-in MSK publishing)
- **RDS Enhanced Monitoring** → CloudWatch (OS-level metrics)
- **EKS control plane logs** → CloudWatch (API server, scheduler logs)
- **CloudWatch Alarms** → SNS → on-call for AWS-level failures (RDS instance down, MSK broker unavailable)

Application logs are **not** sent to CloudWatch — Loki handles all application logs.
This avoids CloudWatch log ingestion costs while keeping full log observability.

---

## 17. Error Handling Strategy

### Typed Exceptions (`core/exceptions.py`)
Define one exception class per error condition. No raw `raise Exception("message")` anywhere.

**Domain exceptions to define:**
- `UnsupportedFileTypeError(file_type)` → HTTP 400
- `FileTooLargeError(size, max_size)` → HTTP 413
- `DuplicateDocumentError(document_id)` → HTTP 409
- `DocumentNotFoundError(document_id)` → HTTP 404
- `DocumentNotIndexedError(document_id, status)` → HTTP 422
- `StorageUploadError(s3_key, reason)` → HTTP 500
- `StorageDownloadError(s3_key, reason)` → HTTP 500
- `EmbeddingError(reason)` → HTTP 500 (retried by worker)
- `QueuePublishError(reason)` → HTTP 500
- `ParseError(file_type, reason)` → HTTP 500 (retried by worker)
- `AuthenticationError` → HTTP 401
- `AuthorizationError` → HTTP 403
- `RateLimitError` → HTTP 429

### Global Exception Handler
- Registered in `main.py` via `@app.exception_handler`
- Converts all `DocAgentError` subclasses to JSON: `{"error": "message", "code": "ERROR_CODE"}`
- Catch-all for `Exception`: log to Sentry, return HTTP 500
- Never expose internal error details to client in production

---

## 18. Testing Strategy

### Unit Tests (`tests/unit/`)
- Fast. No I/O. Test pure logic only.
- Use `pytest` with `pytest-asyncio`
- Mock all external dependencies (`unittest.mock`, `pytest-mock`)

**Tests to write:**
- `test_parser.py` — PDF extraction correctness, OCR fallback trigger
- `test_chunker.py` — chunk size bounds, overlap correctness, edge cases (empty doc, 1-char doc)
- `test_embedder.py` — batch size splitting, retry on rate limit
- `test_rrf_merge.py` — RRF scoring formula, deduplication, top-k slicing
- `test_agent_nodes.py` — each node with mocked LLM, expected state mutations
- `test_dlq.py` — escalation logic, replay logic

### Integration Tests (`tests/integration/`)
- Real PostgreSQL (via testcontainers or Docker Compose)
- Real Redis
- Mock S3 (moto library)
- Mock Kafka (testcontainers-kafka or embedded Kafka)
- Mock OpenAI (recorded fixtures via `pytest-recording` / VCR)

**Tests to write:**
- `test_upload_pipeline.py` — upload → enqueue → ingest → verify chunks in DB
- `test_retrieval.py` — ingest 10-page doc → query → verify relevant chunks returned
- `test_chat_e2e.py` — full query flow → verify SSE events → verify citation format

### Load Tests (`tests/load/`)
- Use `locust` or `pytest-benchmark`
- `test_retrieval_latency.py` — index 1M synthetic chunks, query P99 must be < 15ms
- `test_chat_throughput.py` — 1000 concurrent chat queries, P99 TTFT < 300ms
- `test_ingestion_throughput.py` — 10,000 documents queued, verify all indexed (no loss)

### CI Requirements
- All unit + integration tests must pass on every PR
- Coverage minimum: 80% for `services/` directory
- Load tests run nightly, not on every PR

---

## 19. Scaling Strategy

### API Layer
- Stateless FastAPI pods — scale freely
- HPA on CPU (target 70%) — min 3, max 20 pods
- Connection pooling: `asyncpg` pool size 20 per pod + PgBouncer in front of RDS

### Worker Layer
- KEDA ScaledObject on Kafka consumer lag
- `lagThreshold: 1000` → 1 pod per 1000 unprocessed messages
- Min 5 pods (always warm), max 500 pods
- Worker pods are stateless — add/remove freely

### Database
- RDS Multi-AZ for HA
- Read replica for analytics and reporting queries (never for chat/retrieval)
- PgBouncer: connection pooling between pods and RDS
- `max_connections = 500` on RDS; PgBouncer limits actual connections
- HNSW index: sub-15ms ANN search at 100M+ vectors without extra infrastructure
- Partition `document_chunks` by `user_id` range when > 500M rows

### Kafka (MSK)
- 32 partitions on `doc.ingestion` → 32 concurrent workers maximum per consumer group
- Add partitions to scale beyond 32 (requires consumer group rebalance)
- MSK auto-scaling on storage

### Redis (ElastiCache)
- Cluster mode: 3 shards × 2 replicas = 6 nodes
- `maxmemory-policy: allkeys-lru` — evict least-recently-used cache entries
- Monitor memory usage → scale shards before hitting 80%

### Embedding Throughput
- Each OpenAI batch: 100 chunks → ~2s → 50 chunks/second per worker
- 500 workers × 50 chunks/s = 25,000 chunks/second sustained
- For self-hosted: replace with `bge-m3` on GPU nodes — 10x cheaper at scale

---

## 20. Developer Conventions

### Python Code Rules
- Python 3.11+ — use `match` statements, `X | Y` union types
- Full type annotations on all function signatures
- `black` for formatting, `ruff` for linting (replaces flake8 + isort)
- `mypy --strict` must pass — no `# type: ignore` without explanation
- Never `import *`
- Never use `print()` — always `log.info()`
- Never raw SQL strings — always `sqlalchemy.text()` with bound params
- All async functions must be awaited — never `asyncio.run()` inside async context

### Naming Conventions
| Item | Convention | Example |
|---|---|---|
| Python files | `snake_case.py` | `semantic_cache.py` |
| Python classes | `PascalCase` | `HybridRetriever` |
| Python functions | `snake_case` | `embed_batch()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_FILE_BYTES` |
| DB tables | `snake_case` | `document_chunks` |
| DB columns | `snake_case` | `user_id`, `chunk_index` |
| Kafka topics | `dot.separated` | `doc.ingestion.dlq` |
| Redis keys | `namespace:entity:id` | `cache:user:{id}` |
| Env vars | `UPPER_SNAKE_CASE` | `OPENAI_API_KEY` |
| TypeScript files | `PascalCase.tsx` for components, `camelCase.ts` for utils |
| TypeScript types | `PascalCase` | `DocumentStatus` |
| React components | `PascalCase` | `ChatWindow` |
| React hooks | `use` prefix | `useDocumentStatus` |

### Git Commit Format
```
type(scope): short description

feat(ingestion): add OCR fallback for scanned PDFs
fix(cache): prevent cross-user cache key collision
perf(retrieval): tune HNSW ef_search to 64
test(pipeline): add load test for 1M chunk retrieval
docs(claude): update Kafka broker configuration
chore(deps): upgrade langchain to 0.3.0
```

### PR Checklist
- [ ] Unit tests written for new logic
- [ ] Integration test updated if API contract changed
- [ ] `mypy --strict` passes
- [ ] `ruff` passes, `black` formatted
- [ ] `tsc --noEmit` passes (frontend)
- [ ] No secrets in code
- [ ] CLAUDE.md updated if architecture changed
- [ ] New env vars added to `.env.example`

---

## 21. Environment Variables

```bash
# .env.example — copy to .env for local development
# Production: all secrets in AWS Secrets Manager, injected via External Secrets Operator

# ── Application ──────────────────────────────────────────────────────
APP_ENV=development            # development | staging | production
LOG_LEVEL=INFO
ALLOWED_ORIGINS=http://localhost:5173

# ── Database (RDS in prod) ────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/docdb
PGBOUNCER_URL=postgresql+asyncpg://user:pass@pgbouncer:6432/docdb

# ── Redis (ElastiCache in prod) ───────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_DB=2               # DB index for RedisVL semantic cache
REDIS_CELERY_RESULT_DB=1       # DB index for Celery result backend

# ── Kafka (MSK in prod) ───────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_INGESTION=doc.ingestion
KAFKA_TOPIC_RETRY=doc.ingestion.retry
KAFKA_TOPIC_DLQ=doc.ingestion.dlq
KAFKA_TOPIC_EVENTS=doc.events
KAFKA_CONSUMER_GROUP=ingestion-workers
KAFKA_SECURITY_PROTOCOL=PLAINTEXT    # SASL_SSL in prod (MSK mTLS)

# ── AWS ───────────────────────────────────────────────────────────────
AWS_REGION=us-east-1
S3_BUCKET=docagent-uploads-dev
AWS_ACCESS_KEY_ID=              # local dev only; IRSA in prod (leave blank)
AWS_SECRET_ACCESS_KEY=          # local dev only; IRSA in prod (leave blank)

# ── AI / Embeddings ───────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-large
LLM_MODEL=gpt-4o
EMBEDDING_BATCH_SIZE=100

# ── Auth ──────────────────────────────────────────────────────────────
JWT_SECRET=change-me-use-256-bit-random-string-in-prod
JWT_EXPIRE_HOURS=24

# ── Observability ─────────────────────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317   # gRPC
OTEL_SERVICE_NAME=docagent-api
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=1.0                              # 1.0=100% dev, 0.1=10% prod
GLITCHTIP_DSN=http://glitchtip.monitoring.svc/api/0/...  # GlitchTip (open-source Sentry)
PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus                  # required for multi-worker

# ── Upload Limits ─────────────────────────────────────────────────────
MAX_FILE_BYTES=524288000        # 500MB
ALLOWED_FILE_TYPES=pdf,docx

# ── Frontend (Vite) ───────────────────────────────────────────────────
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=DocAgent
VITE_GLITCHTIP_DSN=http://glitchtip.monitoring.svc/api/0/...   # open-source error tracking
```

---

## 22. Local Setup

```bash
# Prerequisites: Docker, Python 3.11+, Node 20+, uv (Python package manager)

# 1. Clone repository
git clone https://github.com/your-org/doc-agent && cd doc-agent

# 2. Copy environment file
cp .env.example .env
# → Fill in OPENAI_API_KEY at minimum

# 3. Start all infrastructure
#    Starts: PostgreSQL, Redis, Kafka + ZooKeeper, Kafka-Init (topic creation),
#            MinIO (local S3), AKHQ (Kafka UI), Prometheus, Grafana, Jaeger
docker compose -f infra/docker-compose.yml up -d

# 4. Backend setup
cd backend
uv venv && source .venv/bin/activate
uv pip install -r requirements/dev.txt

# 5. Run database migrations
alembic upgrade head

# 6. Start Celery worker (terminal 2)
celery -A workers.tasks worker -Q ingestion -c 4 --loglevel=info

# 7. Start API server (terminal 3)
uvicorn app.main:app --reload --port 8000

# 8. Frontend setup (terminal 4)
cd ../frontend
npm install
npm run dev    # → http://localhost:5173

# 9. Verify services
open http://localhost:8000/docs      # FastAPI OpenAPI UI
open http://localhost:8080           # AKHQ Kafka UI
open http://localhost:3000           # Grafana (admin/admin)
open http://localhost:16686          # Jaeger UI
open http://localhost:5173           # React frontend

# 10. Seed test documents
python scripts/seed_test_data.py
```

---

## 23. Agent Action Plan

> Ordered phases. Each task is a unit of work for one developer or AI agent.
> Generate code for each task referencing the relevant sections of this document.

### Phase 1 — Foundation (Week 1)
- [ ] `P1-01` Project scaffolding: create full directory structure (Section 3)
- [ ] `P1-02` `pyproject.toml`: configure black, ruff, mypy strict, pytest
- [ ] `P1-03` `core/config.py`: Pydantic Settings with all env vars typed (Section 21)
- [ ] `P1-04` `core/exceptions.py`: all typed domain exceptions (Section 17)
- [ ] `P1-05` `core/logging.py`: structlog JSON setup + OTel integration (Section 16.1)
- [ ] `P1-06` `core/tracing.py`: OpenTelemetry tracer → Jaeger exporter (Section 16.2)
- [ ] `P1-07` `core/metrics.py`: all Prometheus metric definitions (Section 16.3)
- [ ] `P1-08` `core/middleware.py`: RequestID, timing, tracing, CORS middleware (Section 12)
- [ ] `P1-09` `db/session.py`: async SQLAlchemy engine + session factory
- [ ] `P1-10` `models/`: all 5 models (base, user, organisation, document, chunk) (Section 6.1)
- [ ] `P1-11` Alembic setup: `alembic init`, configure `env.py` for async + models (Section 6.3)
- [ ] `P1-12` First migration: create all tables, extensions, HNSW index, GIN index, trigger
- [ ] `P1-13` `core/security.py`: JWT encode/decode, password hashing
- [ ] `P1-14` `main.py`: app factory, lifespan, middleware registration, router mount
- [ ] `P1-15` `api/v1/health.py`: liveness + readiness endpoints
- [ ] `P1-16` Global exception handlers in `main.py`
- [ ] `P1-17` `docker-compose.yml`: PostgreSQL, Redis, Kafka, ZooKeeper, Kafka-Init, MinIO, AKHQ, Jaeger, Prometheus, Grafana
- [ ] `P1-18` Verify: `docker-compose up` → all services healthy → `alembic upgrade head` succeeds

### Phase 2 — Ingestion Pipeline (Week 2)
- [ ] `P2-01` `services/storage.py`: S3 upload, download, presign URL (Section 7)
- [ ] `P2-02` `services/ingestion/parser.py`: PyMuPDF PDF parser + OCR fallback + python-docx (Section 7)
- [ ] `P2-03` `services/ingestion/chunker.py`: RecursiveCharacterTextSplitter with overlap (Section 7)
- [ ] `P2-04` `services/ingestion/embedder.py`: async batched OpenAI embeddings + retry (Section 7)
- [ ] `P2-05` `services/ingestion/indexer.py`: bulk upsert pgvector + mark_indexed (Section 7)
- [ ] `P2-06` `services/ingestion/pipeline.py`: orchestrate all steps, emit logs + metrics (Section 7)
- [ ] `P2-07` `services/queue/producer.py`: aiokafka producer, acks=all, idempotent, user_id partition key (Section 8)
- [ ] `P2-08` `services/queue/dlq.py`: escalate to DLQ topic + update DB status (Section 8)
- [ ] `P2-09` `workers/celeryconfig.py`: Kafka broker, all settings (Section 8)
- [ ] `P2-10` `workers/tasks.py`: `ingest_document` Celery task, retry + DLQ escalation (Section 8)
- [ ] `P2-11` `schemas/upload.py`: UploadRequest, UploadResponse Pydantic schemas
- [ ] `P2-12` `api/v1/upload.py`: upload endpoint, all 10 steps (Section 7)
- [ ] `P2-13` `api/v1/documents.py`: list, get, delete endpoints
- [ ] `P2-14` `api/v1/status.py`: document status polling endpoint
- [ ] `P2-15` Unit tests: parser, chunker, embedder (Section 18)
- [ ] `P2-16` Integration test: upload → ingest → verify chunks in DB (Section 18)
- [ ] `P2-17` Manual test: upload real 100-page PDF, verify AKHQ shows message flow, verify indexed

### Phase 3 — Search, Cache & Agent (Week 3)
- [ ] `P3-01` `services/retrieval/retriever.py`: vector search + BM25 + RRF fusion (Section 9)
- [ ] `P3-02` `services/retrieval/reranker.py`: cross-encoder reranker (optional, feature-flagged) (Section 9)
- [ ] `P3-03` `services/cache/semantic_cache.py`: RedisVL SemanticCache wrapper, user-scoped (Section 10)
- [ ] `P3-04` `services/agent/state.py`: AgentState TypedDict (Section 11)
- [ ] `P3-05` `services/agent/prompts.py`: SYSTEM_PROMPT, QUALITY_PROMPT, REFINE_PROMPT (Section 11)
- [ ] `P3-06` `services/agent/nodes.py`: all 5 nodes (route, search, generate, quality, refine) (Section 11)
- [ ] `P3-07` `services/agent/tools.py`: search_docs tool, get_document_summary tool (Section 11)
- [ ] `P3-08` `services/agent/graph.py`: LangGraph StateGraph, all edges, compile (Section 11)
- [ ] `P3-09` `schemas/chat.py`: ChatRequest, ChatResponse, StreamDelta schemas
- [ ] `P3-10` `api/v1/chat.py`: chat endpoint with SSE streaming + cache check + store (Section 12)
- [ ] `P3-11` Unit tests: RRF merge, agent nodes with mocked LLM (Section 18)
- [ ] `P3-12` Integration test: full chat e2e with seeded document (Section 18)
- [ ] `P3-13` Load test: 1M chunks → P99 retrieval < 15ms target (Section 18)

### Phase 4 — Frontend (Week 4)
- [ ] `P4-01` Vite + React + TypeScript project setup, strict tsconfig, Tailwind, shadcn/ui (Section 13)
- [ ] `P4-02` All TypeScript types: `types/document.ts`, `types/chat.ts`, `types/api.ts` (Section 13)
- [ ] `P4-03` `services/api.ts`: Axios instance + auth interceptor + error interceptor
- [ ] `P4-04` `store/authStore.ts`: Zustand auth state (token, user, login, logout)
- [ ] `P4-05` `store/chatStore.ts`: Zustand messages state (add, appendDelta, clear)
- [ ] `P4-06` `LoginPage.tsx`: email/password form, Zod validation, JWT storage
- [ ] `P4-07` `Layout.tsx`, `Sidebar.tsx`, `Header.tsx`: app shell
- [ ] `P4-08` `DropZone.tsx`: drag-and-drop upload with MIME validation + progress
- [ ] `P4-09` `useUpload.ts`: TanStack Query mutation + upload progress tracking
- [ ] `P4-10` `useDocumentStatus.ts`: polling hook (every 3s until indexed)
- [ ] `P4-11` `DocumentCard.tsx`: status badge (queued/processing/indexed/failed)
- [ ] `P4-12` `DashboardPage.tsx`: document list + upload zone
- [ ] `P4-13` `utils/sse.ts`: SSE parser for `delta` / `citations` / `done` events
- [ ] `P4-14` `useChat.ts`: SSE streaming hook, calls `onDelta` / `onDone`
- [ ] `P4-15` `StreamingMessage.tsx`: real-time token display
- [ ] `P4-16` `CitationBadge.tsx`: clickable page citation pill
- [ ] `P4-17` `MessageBubble.tsx`: user and assistant message rendering
- [ ] `P4-18` `ChatInput.tsx`: textarea + send, disabled during streaming
- [ ] `P4-19` `ChatWindow.tsx`: full chat interface assembling all components
- [ ] `P4-20` `ChatPage.tsx`: layout + ChatWindow + document info panel
- [ ] `P4-21` `Dockerfile.frontend`: Nginx serving Vite build + API proxy
- [ ] `P4-22` E2E: upload doc in browser → wait for indexed → chat query → see streamed answer

### Phase 5 — AWS & Observability (Week 5)
- [ ] `P5-01` `Dockerfile.api` + `Dockerfile.worker`: production images
- [ ] `P5-02` ECR repositories: api, worker, frontend
- [ ] `P5-03` EKS cluster + managed node group (small, for system pods only — Karpenter handles app nodes)
- [ ] `P5-03a` Install Karpenter controller on EKS (Helm chart) + IRSA role with EC2 permissions
- [ ] `P5-03b` Create EC2NodeClass (AMI, subnets, security groups, EBS config)
- [ ] `P5-03c` Create NodePool: `general` (m7i/m7g, On-Demand, API + monitoring workloads)
- [ ] `P5-03d` Create NodePool: `ingestion-workers` (c7i/c7g, Spot+On-Demand, tainted for workers only)
- [ ] `P5-03e` Create NodePool: `gpu` (g5, On-Demand, inactive until self-hosted embeddings needed)
- [ ] `P5-03f` Set up Spot interruption SQS queue + Karpenter interruption handler
- [ ] `P5-03g` Add `nodeSelector` + `tolerations` to Worker Deployment manifest (Section 15)
- [ ] `P5-03h` Verify: scale worker replicas manually → Karpenter provisions c7i Spot nodes in < 60s
- [ ] `P5-04` MSK Kafka cluster: 3 brokers, Multi-AZ, create all topics
- [ ] `P5-05` RDS PostgreSQL 16: Multi-AZ, pgvector extension, run migrations
- [ ] `P5-06` ElastiCache Redis: cluster mode, 3 shards
- [ ] `P5-07` S3 bucket: versioning, lifecycle, deny-public-access policy
- [ ] `P5-08` IAM roles + IRSA: API pod role (S3+Secrets), Worker pod role (S3+Secrets)
- [ ] `P5-09` AWS Secrets Manager: store all secrets, External Secrets Operator in K8s
- [ ] `P5-10` K8s manifests: API, Worker, Frontend deployments + services
- [ ] `P5-11` ALB Ingress + Route53 + ACM TLS cert
- [ ] `P5-12` KEDA ScaledObject: Kafka consumer lag autoscaling for workers
- [ ] `P5-13` HPA: API pods on CPU
- [ ] `P5-14` Deploy OTel Collector (DaemonSet + Deployment) with full pipeline config (Section 16.8)
- [ ] `P5-15` Deploy Grafana Tempo + configure S3 backend + verify traces flow from OTel Collector
- [ ] `P5-16` Deploy Jaeger + configure OTel Collector fan-out → verify traces appear in both Tempo and Jaeger
- [ ] `P5-17` Deploy Grafana Loki + Promtail DaemonSet + Fluent Bit → verify pod logs searchable in Grafana
- [ ] `P5-18` Deploy Prometheus + all exporters (postgres, redis, kafka, node, kube-state-metrics)
- [ ] `P5-19` Deploy Grafana + connect all 3 data sources (Prometheus, Loki, Tempo) + import all 4 dashboards
- [ ] `P5-20` Configure Prometheus AlertManager: all alerting rules + Slack/PagerDuty routing (Section 16.5)
- [ ] `P5-21` Deploy GlitchTip → configure backend DSN + frontend DSN → verify exception capture (Section 16.6)
- [ ] `P5-22` Deploy Uptime Kuma → configure all health monitors (Section 16.7)
- [ ] `P5-23` CloudWatch: MSK + RDS alarms → SNS → on-call (Section 16.9)
- [ ] `P5-24` GitHub Actions CI/CD: test → build → push ECR → migrate → rolling deploy
- [ ] `P5-25` Load test in staging: 10K uploads, 1K concurrent chats — verify 0% data loss, P99 targets

---

*Last updated: keep this file current with every architectural decision.*
*Rule: if you change how the system works, update CLAUDE.md first, then write the code.*
*Owner: Platform Team*