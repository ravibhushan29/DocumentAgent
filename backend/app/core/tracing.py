"""OpenTelemetry tracer setup → Jaeger exporter (Section 16.2)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def setup_tracing(app: object | None = None) -> Any | None:
    """
    Configure OpenTelemetry tracer if OTLP endpoint is set and packages available.
    Optionally instrument FastAPI app.
    """
    settings = get_settings()
    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatioBased
    except ImportError:
        return None

    try:
        ratio = float(settings.OTEL_TRACES_SAMPLER_ARG)
    except ValueError:
        ratio = 1.0
    sampler = ParentBasedTraceIdRatioBased(ratio)
    provider = TracerProvider(sampler=sampler)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True))
    )
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(settings.OTEL_SERVICE_NAME, "0.1.0")

    if app is not None:
        FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]

    return tracer
