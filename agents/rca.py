from __future__ import annotations

from app.models import TelemetryEvent
from integrations.llm.gemini_client import GeminiAutomationClient


class RCAAgent:
    def __init__(
        self,
        automation_client: GeminiAutomationClient | None = None,
        automation_mode: str = "hybrid",
    ) -> None:
        self.automation_client = automation_client
        self.automation_mode = automation_mode
        self.last_source = "rules"

    def analyze(self, event: TelemetryEvent) -> str:
        if self.automation_client is not None:
            suggestion = self.automation_client.analyze_event(event)
            if suggestion and suggestion.get("root_cause"):
                self.last_source = "gemini"
                return str(suggestion["root_cause"])
            if self.automation_mode == "gemini_only":
                self.last_source = "gemini_failed"
                detail = getattr(self.automation_client, "last_error", None) or "no usable diagnosis returned"
                return f"Gemini RCA failed: {detail}"

        self.last_source = "rules"
        error_logs = " ".join(event.logs).lower()
        suspected_dependency = event.metadata.get("suspected_dependency")
        impacted_services = event.metadata.get("impacted_services", [])
        trace_count = event.metadata.get("trace_error_count", 0)
        if event.scenario == "crashloop":
            return "application startup misconfiguration"
        if event.scenario == "oomkill":
            return "container memory limit too low for current load"
        if event.scenario == "high-latency":
            if suspected_dependency:
                return f"upstream dependency '{suspected_dependency}' is increasing tail latency"
            return "upstream dependency timeout causing tail latency"
        if event.scenario == "dependency-down":
            if suspected_dependency and impacted_services:
                impacted = ", ".join(impacted_services[:3])
                return f"dependency '{suspected_dependency}' is unavailable and may cascade into {impacted}"
            if suspected_dependency:
                return f"dependency '{suspected_dependency}' is unavailable"
            return "critical backing service unavailable"
        if event.scenario == "failed-rollout":
            if trace_count:
                return "deployment revision is failing readiness and surfacing trace errors"
            return "bad deployment revision causing readiness failures"
        if "oomkilled" in error_logs or "exit code 137" in error_logs:
            return "container memory exhaustion detected in logs"
        if "connection refused" in error_logs:
            return "dependency refused connection"
        return "unknown anomaly"
