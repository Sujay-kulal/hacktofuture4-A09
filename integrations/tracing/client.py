from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings
from integrations.telemetry.live_clients import render_query


class TraceBackendClient:
    def find_errors(self, service: str, namespace: str) -> tuple[float, list[str], str | None]:
        raise NotImplementedError


class TempoTraceClient(TraceBackendClient):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def find_errors(self, service: str, namespace: str) -> tuple[float, list[str], str | None]:
        query = render_query(settings.tempo_traceql_query, service, namespace)
        response = httpx.get(
            f"{self.base_url}/api/search",
            params={"q": query, "limit": 5},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        traces = payload.get("traces", []) or payload.get("data", [])
        summaries: list[str] = []
        suspect_dependency = None
        for trace in traces[:5]:
            root_name = trace.get("rootServiceName") or trace.get("rootService") or trace.get("serviceName") or service
            span_name = trace.get("rootTraceName") or trace.get("name") or "trace"
            summaries.append(f"{root_name}: {span_name}")
            candidate = trace.get("serviceName") or trace.get("rootServiceName")
            if candidate and candidate != service:
                suspect_dependency = candidate
        return float(len(traces)), summaries, suspect_dependency


class JaegerTraceClient(TraceBackendClient):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def find_errors(self, service: str, namespace: str) -> tuple[float, list[str], str | None]:
        response = httpx.get(
            f"{self.base_url}/api/traces",
            params={
                "service": service,
                "lookback": "1h",
                "limit": 5,
                "tags": settings.jaeger_trace_service_tag,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        traces = payload.get("data", [])
        summaries: list[str] = []
        suspect_dependency = None
        for trace in traces[:5]:
            processes = trace.get("processes", {})
            process_services = [
                details.get("serviceName")
                for details in processes.values()
                if details.get("serviceName")
            ]
            if process_services:
                summaries.append(" -> ".join(process_services[:4]))
                for candidate in process_services:
                    if candidate != service:
                        suspect_dependency = candidate
                        break
        return float(len(traces)), summaries, suspect_dependency


def build_trace_client(base_url: str | None, backend: str) -> TraceBackendClient | None:
    if not base_url:
        return None
    if backend == "jaeger":
        return JaegerTraceClient(base_url)
    return TempoTraceClient(base_url)
