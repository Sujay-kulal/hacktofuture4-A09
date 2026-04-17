from pathlib import Path

from app.models import RemediationAction
from app.policy_engine import PolicyEngine


def test_policy_allows_small_scale_up() -> None:
    engine = PolicyEngine(Path("policies/default.yaml"))
    action = RemediationAction(
        action="scale_deployment",
        target_kind="Deployment",
        target_name="checkout",
        namespace="demo",
        reason="latency",
        parameters={"replicas": 4},
    )

    decision = engine.evaluate(action)

    assert decision.allowed is True
    assert decision.reason == "allowed"


def test_policy_blocks_large_scale_up() -> None:
    engine = PolicyEngine(Path("policies/default.yaml"))
    action = RemediationAction(
        action="scale_deployment",
        target_kind="Deployment",
        target_name="checkout",
        namespace="demo",
        reason="latency",
        parameters={"replicas": 10},
    )

    decision = engine.evaluate(action)

    assert decision.allowed is False
    assert "exceed policy limit" in decision.reason


def test_policy_requires_approval_for_protected_namespace() -> None:
    engine = PolicyEngine(Path("policies/default.yaml"))
    action = RemediationAction(
        action="restart_deployment",
        target_kind="Deployment",
        target_name="grafana",
        namespace="monitoring",
        reason="rollout issue",
    )

    decision = engine.evaluate(action, impacted_services=["alerts", "dashboards"])

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert "protected" in decision.reason
