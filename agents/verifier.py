from __future__ import annotations

from app.models import RemediationAction, TelemetryEvent


class VerificationAgent:
    def verify(self, event: TelemetryEvent, action: RemediationAction) -> bool:
        if action.status.value in {"failed", "blocked"}:
            return False

        if event.scenario in {"crashloop", "failed-rollout", "oomkill", "high-latency", "dependency-down"}:
            return True

        return False

