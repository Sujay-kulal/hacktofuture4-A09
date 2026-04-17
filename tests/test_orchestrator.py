from pathlib import Path

from agents import MonitorAgent, RCAAgent, RemediationAgent, VerificationAgent
from app.models import Incident, RemediationAction, TelemetryEvent
from app.orchestrator import SelfHealingOrchestrator
from app.policy_engine import PolicyEngine
from integrations.kubernetes.client import KubernetesExecutor
from integrations.telemetry.provider import TelemetryProvider


class FakeRepository:
    def __init__(self) -> None:
        self.saved: list[tuple[Incident, RemediationAction | None]] = []

    def save_incident(self, incident: Incident, action: RemediationAction | None = None) -> None:
        self.saved.append((incident, action))


def test_orchestrator_remediates_simulated_incident() -> None:
    queue = [
        TelemetryEvent(
            scenario="crashloop",
            service="checkout",
            namespace="demo",
            symptoms=["CrashLoopBackOff"],
            metrics={"restarts": 7},
            logs=["startup failed"],
        )
    ]
    orchestrator = SelfHealingOrchestrator(
        telemetry=TelemetryProvider(queue),
        monitor=MonitorAgent(),
        rca=RCAAgent(),
        remediator=RemediationAgent(Path("playbooks/default.yaml")),
        verifier=VerificationAgent(),
        policies=PolicyEngine(Path("policies/default.yaml")),
        executor=KubernetesExecutor(mode="mock"),
    )
    repository = FakeRepository()

    result = orchestrator.run_once(repository)

    assert result.incident is not None
    assert result.incident.status.value == "remediated"
    assert result.incident.rca_source == "rules"
    assert result.incident.remediation_source == "playbook"
    assert result.action is not None
    assert result.action.action == "restart_deployment"
    assert repository.saved
