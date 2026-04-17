from integrations.kubernetes.client import KubernetesExecutor


def test_mock_impact_view_explains_simulated_incident() -> None:
    executor = KubernetesExecutor(mode="mock")

    impact = executor.impact_view(
        service="checkout",
        namespace="demo",
        scenario="dependency-down",
        latest_action="restart_deployment",
        latest_action_status="verified",
        incident_id="incident-123",
        simulated_incident_only=True,
    )

    assert impact.mode == "mock"
    assert impact.simulated_incident_only is True
    assert impact.workload is not None
    assert "No real cluster workload was changed" in impact.summary
