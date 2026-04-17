from __future__ import annotations

from pathlib import Path

import yaml

from app.models import PolicyDecision, RemediationAction


class PolicyEngine:
    def __init__(self, policy_file: Path) -> None:
        with policy_file.open("r", encoding="utf-8") as handle:
            self.rules = yaml.safe_load(handle) or {}

    def evaluate(
        self,
        action: RemediationAction,
        *,
        impacted_services: list[str] | None = None,
    ) -> PolicyDecision:
        blocked_actions = set(self.rules.get("blocked_actions", []))
        allowed_actions = set(self.rules.get("allowed_actions", []))
        max_scale_replicas = int(self.rules.get("max_scale_replicas", 5))
        approval_required_actions = set(self.rules.get("approval_required_actions", []))
        protected_namespaces = set(self.rules.get("protected_namespaces", []))
        rbac_allowed_namespaces = set(self.rules.get("rbac_allowed_namespaces", []))
        max_blast_radius_without_approval = int(self.rules.get("max_blast_radius_without_approval", 3))
        rollback_requires_approval = bool(self.rules.get("rollback_requires_approval", True))
        blast_radius = 1 + len(impacted_services or [])
        tags: list[str] = []
        risk_level = "low"

        if action.action in blocked_actions:
            return PolicyDecision(
                allowed=False,
                reason=f"Action '{action.action}' is blocked by policy",
                risk_level="critical",
                blast_radius=blast_radius,
                policy_tags=["blocked-action"],
            )

        if action.action not in allowed_actions:
            return PolicyDecision(
                allowed=False,
                reason=f"Action '{action.action}' is not in the allow list",
                risk_level="high",
                blast_radius=blast_radius,
                policy_tags=["not-allowlisted"],
            )

        if rbac_allowed_namespaces and action.namespace not in rbac_allowed_namespaces:
            return PolicyDecision(
                allowed=False,
                reason=f"Namespace '{action.namespace}' is outside the RBAC remediation scope",
                risk_level="high",
                blast_radius=blast_radius,
                policy_tags=["rbac-scope"],
            )

        if action.action == "scale_deployment":
            replicas = int(action.parameters.get("replicas", 1))
            if replicas > max_scale_replicas:
                return PolicyDecision(
                    allowed=False,
                    reason=f"Requested replicas {replicas} exceed policy limit {max_scale_replicas}",
                    risk_level="high",
                    blast_radius=blast_radius,
                    policy_tags=["scale-limit"],
                )
            risk_level = "medium"
            tags.append("scale-action")

        if action.action == "restart_deployment":
            risk_level = "medium" if blast_radius > 2 else "low"

        if action.action == "rollback_deployment" and rollback_requires_approval:
            return PolicyDecision(
                allowed=False,
                reason="Rollback requires human approval by policy",
                risk_level="high",
                requires_approval=True,
                blast_radius=blast_radius,
                policy_tags=["rollback-approval"],
            )

        if action.action in approval_required_actions:
            tags.append("approval-required-action")

        if action.namespace in protected_namespaces:
            return PolicyDecision(
                allowed=False,
                reason=f"Namespace '{action.namespace}' is protected and requires human approval",
                risk_level="high",
                requires_approval=True,
                blast_radius=blast_radius,
                policy_tags=[*tags, "protected-namespace"],
            )

        if blast_radius > max_blast_radius_without_approval:
            return PolicyDecision(
                allowed=False,
                reason=(
                    f"Blast radius {blast_radius} exceeds the auto-remediation limit "
                    f"{max_blast_radius_without_approval}; approval required"
                ),
                risk_level="high",
                requires_approval=True,
                blast_radius=blast_radius,
                policy_tags=[*tags, "blast-radius"],
            )

        if action.action in approval_required_actions:
            return PolicyDecision(
                allowed=False,
                reason=f"Action '{action.action}' requires human approval by policy",
                risk_level="high",
                requires_approval=True,
                blast_radius=blast_radius,
                policy_tags=tags,
            )

        return PolicyDecision(
            allowed=True,
            reason="allowed",
            risk_level=risk_level,
            blast_radius=blast_radius,
            policy_tags=tags,
        )
