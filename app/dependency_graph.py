from __future__ import annotations

from pathlib import Path

import yaml

from app.models import DependencyNode


class DependencyGraph:
    def __init__(self, graph_file: Path) -> None:
        self.nodes_by_service: dict[str, DependencyNode] = {}
        if graph_file.exists():
            with graph_file.open("r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle) or {}
            for item in payload.get("services", []):
                node = DependencyNode(
                    service=str(item.get("service")),
                    namespace=str(item.get("namespace", "default")),
                    depends_on=list(item.get("depends_on", [])),
                    criticality=str(item.get("criticality", "medium")),
                )
                self.nodes_by_service[node.service] = node

        reverse_edges: dict[str, list[str]] = {service: [] for service in self.nodes_by_service}
        for node in self.nodes_by_service.values():
            for dependency in node.depends_on:
                reverse_edges.setdefault(dependency, []).append(node.service)

        for service, impacted in reverse_edges.items():
            if service in self.nodes_by_service:
                self.nodes_by_service[service].impacted_services = sorted(impacted)

        for service, node in self.nodes_by_service.items():
            transitive = self._collect_transitive_impacts(service)
            node.transitive_impacted_services = transitive
            direct_weight = len(node.impacted_services) * 1.0
            transitive_weight = len(transitive) * 0.5
            criticality_weight = {"low": 0.5, "medium": 1.0, "high": 2.0, "critical": 3.0}.get(
                node.criticality,
                1.0,
            )
            node.cascading_risk_score = round((direct_weight + transitive_weight) * criticality_weight, 2)

    def describe_service(self, service: str) -> DependencyNode:
        if service in self.nodes_by_service:
            return self.nodes_by_service[service]
        return DependencyNode(service=service, namespace="default")

    def all_nodes(self) -> list[DependencyNode]:
        return list(self.nodes_by_service.values())

    def _collect_transitive_impacts(self, service: str) -> list[str]:
        seen: set[str] = set()
        stack = list(self.nodes_by_service.get(service, DependencyNode(service=service, namespace="default")).impacted_services)
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            current_node = self.nodes_by_service.get(current)
            if current_node is not None:
                stack.extend(current_node.impacted_services)
        return sorted(seen)
