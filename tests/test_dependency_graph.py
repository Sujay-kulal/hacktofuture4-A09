from pathlib import Path

from app.dependency_graph import DependencyGraph


def test_dependency_graph_loads_impacted_services() -> None:
    graph = DependencyGraph(Path("dependencies/default.yaml"))

    checkout = graph.describe_service("checkout")
    auth = graph.describe_service("auth")

    assert "auth" in checkout.depends_on
    assert "checkout" in auth.impacted_services
    assert "storefront" in checkout.impacted_services
    assert checkout.criticality == "critical"
    assert auth.cascading_risk_score > 0


def test_dependency_graph_calculates_transitive_impact() -> None:
    graph = DependencyGraph(Path("dependencies/default.yaml"))

    redis = graph.describe_service("redis")

    assert "checkout" in redis.impacted_services
    assert "storefront" in redis.transitive_impacted_services
