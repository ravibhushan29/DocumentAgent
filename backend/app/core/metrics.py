"""Prometheus metrics definitions (Section 16.3)."""

from __future__ import annotations

from prometheus_client import Counter, Histogram, Gauge

# ── Upload ─────────────────────────────────────────────────────────────────
uploads_total = Counter(
    "uploads_total",
    "Total uploads by file_type and status",
    ["file_type", "status"],
)
upload_size_bytes = Histogram(
    "upload_size_bytes",
    "Upload size in bytes",
    ["file_type"],
    buckets=[100_000, 1_000_000, 10_000_000, 50_000_000, 100_000_000, 500_000_000],
)
upload_duration_seconds = Histogram(
    "upload_duration_seconds",
    "Upload API latency",
    ["file_type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# ── Ingestion ──────────────────────────────────────────────────────────────
ingestion_duration_seconds = Histogram(
    "ingestion_duration_seconds",
    "Ingestion pipeline duration",
    ["file_type", "status"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)
chunks_per_document = Histogram(
    "chunks_per_document",
    "Chunks per document",
    buckets=[10, 50, 100, 200, 500, 1000, 2000, 5000],
)
ingestion_errors_total = Counter(
    "ingestion_errors_total",
    "Ingestion errors",
    ["error_type", "file_type"],
)
dlq_events_total = Counter("dlq_events_total", "DLQ escalations", ["reason"])

# ── Retrieval ─────────────────────────────────────────────────────────────
retrieval_latency_ms = Histogram(
    "retrieval_latency_ms",
    "Retrieval latency in ms",
    ["search_type"],
    buckets=[1, 5, 10, 25, 50, 100, 250, 500],
)
chunks_retrieved = Histogram(
    "chunks_retrieved",
    "Chunks returned per query",
    buckets=[1, 5, 8, 10, 15, 20, 50],
)
retrieval_errors_total = Counter("retrieval_errors_total", "Retrieval errors")

# ── Cache ─────────────────────────────────────────────────────────────────
semantic_cache_hits_total = Counter("semantic_cache_hits_total", "Semantic cache hits")
semantic_cache_misses_total = Counter("semantic_cache_misses_total", "Semantic cache misses")
semantic_cache_hit_rate = Gauge("semantic_cache_hit_rate", "Cache hit rate (hits/(hits+misses))")

# ── Agent ──────────────────────────────────────────────────────────────────
agent_total_duration_ms = Histogram(
    "agent_total_duration_ms",
    "Full agent execution time in ms",
    buckets=[100, 500, 1000, 2000, 5000, 10000, 30000],
)
agent_refinement_loops_total = Counter("agent_refinement_loops_total", "Quality check failures")
agent_nodes_executed_total = Counter(
    "agent_nodes_executed_total",
    "Nodes executed",
    ["node_name"],
)
llm_tokens_used_total = Counter(
    "llm_tokens_used_total",
    "LLM tokens",
    ["model", "direction"],
)

# ── Queue ─────────────────────────────────────────────────────────────────
kafka_messages_produced_total = Counter("kafka_messages_produced_total", "Messages produced")
kafka_messages_consumed_total = Counter("kafka_messages_consumed_total", "Messages consumed")
