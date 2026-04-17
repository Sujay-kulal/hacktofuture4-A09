from __future__ import annotations

import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings

logger = logging.getLogger("selfheal.tracing")
_configured = False


def configure_tracing(app: FastAPI) -> None:
    global _configured
    if _configured or not settings.tracing_enabled or not settings.otel_exporter_otlp_endpoint:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment": "local",
            }
        )
    )
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint.rstrip("/") + "/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    _configured = True
    logger.info(
        "OpenTelemetry tracing enabled for service=%s exporter=%s",
        settings.otel_service_name,
        settings.otel_exporter_otlp_endpoint,
    )


def get_tracer(name: str = "selfheal") -> trace.Tracer:
    return trace.get_tracer(name)
