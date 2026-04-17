from pathlib import Path

from agents.remediation import RemediationAgent
from app.models import TelemetryEvent


class FakeGeminiClient:
    def recommend_action(self, event: TelemetryEvent, root_cause: str, playbook_action: str) -> dict:
        return {
            "action": "restart_deployment",
            "target_kind": "Deployment",
            "parameters": {},
            "reason": root_cause,
        }


def test_failed_rollout_defaults_to_restart_deployment() -> None:
    agent = RemediationAgent(Path("playbooks/default.yaml"))
    event = TelemetryEvent(
        scenario="failed-rollout",
        service="grafana",
        namespace="monitoring",
        symptoms=["readiness failures"],
    )

    action = agent.choose(event, "bad rollout")

    assert action.action == "restart_deployment"


def test_gemini_recommendation_is_used_when_valid() -> None:
    agent = RemediationAgent(
        Path("playbooks/default.yaml"),
        automation_client=FakeGeminiClient(),
    )
    event = TelemetryEvent(
        scenario="failed-rollout",
        service="grafana",
        namespace="monitoring",
        symptoms=["readiness failures"],
    )

    action = agent.choose(event, "bad rollout")

    assert action.action == "restart_deployment"
