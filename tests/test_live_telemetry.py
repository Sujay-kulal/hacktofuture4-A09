from app.models import TelemetryEvent
from integrations.telemetry.provider import TelemetryProvider


def test_collect_live_detects_crashloop(monkeypatch) -> None:
    provider = TelemetryProvider([])

    class FakePrometheus:
        def query(self, expression: str) -> float:
            if "restarts_total" in expression:
                return 8.0
            if "replicas_available" in expression:
                return 1.0
            if "spec_replicas" in expression:
                return 1.0
            return 0.0

    provider.prometheus = FakePrometheus()
    provider.loki = None

    event = provider.collect_live(service="checkout", namespace="demo")

    assert isinstance(event, TelemetryEvent)
    assert event is not None
    assert event.scenario == "crashloop"
    assert "CrashLoopBackOff suspected" in event.symptoms


def test_collect_live_uses_trace_and_dependency_signals() -> None:
    provider = TelemetryProvider([])

    class FakePrometheus:
        def query(self, expression: str) -> float:
            if "restarts_total" in expression:
                return 0.0
            if "replicas_available" in expression:
                return 1.0
            if "spec_replicas" in expression:
                return 1.0
            return 0.0

    class FakeTraceClient:
        def find_errors(self, service: str, namespace: str):
            return 2.0, ["checkout -> payment timeout"], "payment"

    provider.prometheus = FakePrometheus()
    provider.loki = None
    provider.traces = FakeTraceClient()

    event = provider.collect_live(service="checkout", namespace="demo")

    assert event is not None
    assert event.scenario == "dependency-down"
    assert event.metadata["suspected_dependency"] == "payment"
    assert event.traces == ["checkout -> payment timeout"]
