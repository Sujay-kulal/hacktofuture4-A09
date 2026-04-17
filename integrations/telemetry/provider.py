from __future__ import annotations

from app.config import settings
from app.dependency_graph import DependencyGraph
from app.models import TelemetryEvent
from app.telemetry_queue import TelemetryQueueStore
from integrations.telemetry.live_clients import LokiClient, PrometheusClient, maybe_query, render_query
from integrations.tracing.client import build_trace_client


class TelemetryProvider:
    def __init__(
        self,
        queue: list[TelemetryEvent] | None = None,
        queue_store: TelemetryQueueStore | None = None,
    ) -> None:
        self.queue = queue if queue is not None else []
        self.queue_store = queue_store
        self.prometheus = PrometheusClient(settings.prometheus_url) if settings.prometheus_url else None
        self.loki = LokiClient(settings.loki_url) if settings.loki_url else None
        self.traces = build_trace_client(settings.trace_url, settings.trace_backend)
        self.dependency_graph = DependencyGraph(settings.dependency_graph_file)

    def push(self, event: TelemetryEvent) -> None:
        if self.queue_store is not None:
            self.queue_store.enqueue(event)
            return
        self.queue.append(event)

    def next_event(self) -> TelemetryEvent | None:
        if self.queue_store is not None:
            return self.queue_store.dequeue()
        if not self.queue:
            return None
        return self.queue.pop(0)

    def complete(self, event: TelemetryEvent | None) -> None:
        if self.queue_store is None or event is None:
            return
        queue_record_id = event.metadata.get("_queue_record_id")
        try:
            queue_record_id = int(queue_record_id)
        except (TypeError, ValueError):
            queue_record_id = None
        self.queue_store.mark_processed(queue_record_id)

    def fail(self, event: TelemetryEvent | None, error: str) -> str:
        if self.queue_store is None or event is None:
            return "missing"
        queue_record_id = event.metadata.get("_queue_record_id")
        try:
            queue_record_id = int(queue_record_id)
        except (TypeError, ValueError):
            queue_record_id = None
        return self.queue_store.mark_failed(queue_record_id, error)

    def depth(self) -> int:
        if self.queue_store is not None:
            return self.queue_store.depth()
        return len(self.queue)

    def collect_live(self, service: str, namespace: str) -> TelemetryEvent | None:
        if self.prometheus is None:
            return None

        dependency_node = self.dependency_graph.describe_service(service)

        restarts = maybe_query(
            self.prometheus.query,
            render_query(settings.prometheus_restart_query, service, namespace),
        )
        ready = maybe_query(
            self.prometheus.query,
            render_query(settings.prometheus_ready_query, service, namespace),
        )
        desired = maybe_query(
            self.prometheus.query,
            render_query(settings.prometheus_desired_query, service, namespace),
        )
        error_rate = maybe_query(
            self.prometheus.query,
            render_query(settings.prometheus_error_rate_query, service, namespace),
        )
        latency_ms = maybe_query(
            self.prometheus.query,
            render_query(settings.prometheus_latency_query, service, namespace),
        )

        log_error_count = 0.0
        log_messages: list[str] = []
        if self.loki is not None:
            try:
                log_error_count, log_messages = self.loki.query(
                    render_query(settings.loki_error_query, service, namespace)
                )
            except Exception:
                log_error_count, log_messages = 0.0, []

        trace_error_count = 0.0
        trace_summaries: list[str] = []
        suspected_dependency: str | None = None
        if self.traces is not None:
            try:
                trace_error_count, trace_summaries, suspected_dependency = self.traces.find_errors(service, namespace)
            except Exception:
                trace_error_count, trace_summaries, suspected_dependency = 0.0, [], None

        symptoms: list[str] = []
        scenario = "observed-anomaly"

        if restarts >= settings.prometheus_restart_threshold:
            symptoms.extend(["CrashLoopBackOff suspected", f"restarts={restarts:.0f}"])
            scenario = "crashloop"

        if latency_ms >= settings.prometheus_latency_threshold_ms:
            symptoms.append(f"p95 latency {latency_ms:.0f}ms")
            scenario = "high-latency"

        if error_rate >= settings.prometheus_error_rate_threshold:
            symptoms.append(f"error rate {error_rate:.2f}")
            scenario = "high-latency"

        if desired > 0 and ready == 0:
            symptoms.append("desired replicas available but none ready")
            scenario = "failed-rollout"

        lower_logs = " ".join(log_messages).lower()
        if "oomkilled" in lower_logs or "exit code 137" in lower_logs:
            symptoms.append("oom signatures found in logs")
            scenario = "oomkill"
        if "connection refused" in lower_logs or "timed out" in lower_logs:
            symptoms.append("dependency connectivity errors found in logs")
            scenario = "dependency-down"

        if log_error_count >= settings.loki_error_log_threshold:
            symptoms.append(f"log errors {log_error_count:.0f}")

        if trace_error_count >= settings.trace_error_threshold:
            symptoms.append(f"trace errors {trace_error_count:.0f}")
            if scenario == "observed-anomaly":
                scenario = "dependency-down" if suspected_dependency else "high-latency"

        if dependency_node.impacted_services and scenario != "observed-anomaly":
            symptoms.append(
                f"cascading risk to {', '.join(dependency_node.impacted_services[:3])}"
            )
        if dependency_node.transitive_impacted_services and scenario != "observed-anomaly":
            symptoms.append(
                f"transitive impact may reach {', '.join(dependency_node.transitive_impacted_services[:3])}"
            )

        if not symptoms:
            return None

        return TelemetryEvent(
            scenario=scenario,
            service=service,
            namespace=namespace,
            symptoms=symptoms,
            metrics={
                "restarts": restarts,
                "ready_replicas": ready,
                "desired_replicas": desired,
                "error_rate": error_rate,
                "p95_latency_ms": latency_ms,
                "log_error_count": log_error_count,
            },
            logs=log_messages,
            traces=trace_summaries,
            metadata={
                "source": "live",
                "dependencies": dependency_node.depends_on,
                "impacted_services": dependency_node.impacted_services,
                "transitive_impacted_services": dependency_node.transitive_impacted_services,
                "cascading_risk_score": dependency_node.cascading_risk_score,
                "criticality": dependency_node.criticality,
                "trace_error_count": trace_error_count,
                "suspected_dependency": suspected_dependency,
            },
        )
