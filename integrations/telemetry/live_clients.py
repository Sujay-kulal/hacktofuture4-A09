from __future__ import annotations

from collections.abc import Callable

import httpx


class PrometheusClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def query(self, expression: str) -> float:
        response = httpx.get(f"{self.base_url}/api/v1/query", params={"query": expression}, timeout=10)
        response.raise_for_status()
        payload = response.json()
        result = payload.get("data", {}).get("result", [])
        if not result:
            return 0.0
        value = result[0].get("value", [0, "0"])[1]
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0


class LokiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def query(self, expression: str) -> tuple[float, list[str]]:
        response = httpx.get(f"{self.base_url}/loki/api/v1/query", params={"query": expression}, timeout=10)
        response.raise_for_status()
        payload = response.json()
        result = payload.get("data", {}).get("result", [])
        if not result:
            return 0.0, []

        stream = result[0]
        sample_value = stream.get("value")
        if sample_value:
            try:
                return float(sample_value[1]), []
            except (TypeError, ValueError):
                return 0.0, []

        values = stream.get("values", [])
        messages = [entry[1] for entry in values[:5]]
        return float(len(messages)), messages


def render_query(template: str, service: str, namespace: str) -> str:
    return template.replace("{service}", service).replace("{namespace}", namespace)


def maybe_query(query_fn: Callable[[str], float], expression: str) -> float:
    try:
        return query_fn(expression)
    except Exception:
        return 0.0
