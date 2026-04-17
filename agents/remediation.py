from __future__ import annotations

from pathlib import Path

import yaml

from app.models import RemediationAction, TelemetryEvent
from integrations.llm.gemini_client import GeminiAutomationClient


class RemediationAgent:
    def __init__(
        self,
        playbooks_file: Path,
        automation_client: GeminiAutomationClient | None = None,
        automation_mode: str = "hybrid",
    ) -> None:
        with playbooks_file.open("r", encoding="utf-8") as handle:
            self.playbooks = yaml.safe_load(handle) or {}
        self.automation_client = automation_client
        self.automation_mode = automation_mode
        self.last_source = "playbook"

    def choose(self, event: TelemetryEvent, root_cause: str) -> RemediationAction:
        mapping = self.playbooks.get(event.scenario, {})
        action = mapping.get("action", "restart_deployment")
        target_kind = mapping.get("target_kind", "Deployment")

        parameters: dict[str, int | str] = {}
        if action == "scale_deployment":
            parameters["replicas"] = int(mapping.get("replicas", 3))
        if action == "restart_deployment" and "restart_annotation" in mapping:
            parameters["restart_annotation"] = str(mapping["restart_annotation"])

        if self.automation_client is not None:
            suggestion = self.automation_client.recommend_action(event, root_cause, action)
            if suggestion:
                suggested_action = str(suggestion.get("action", action))
                if suggested_action in {"restart_deployment", "scale_deployment", "rollback_deployment"}:
                    action = suggested_action
                target_kind = str(suggestion.get("target_kind", target_kind)).capitalize()
                suggested_parameters = suggestion.get("parameters", {})
                if isinstance(suggested_parameters, dict):
                    parameters = self._normalize_parameters(suggested_parameters, event)
                self.last_source = "gemini"
            elif self.automation_mode == "gemini_only":
                self.last_source = "gemini_failed"
                detail = getattr(self.automation_client, "last_error", None) or "no usable action returned"
                return RemediationAction(
                    action="restart_deployment",
                    target_kind="Deployment",
                    target_name=event.service,
                    namespace=event.namespace,
                    reason=f"Gemini remediation failed: {detail}",
                    parameters={},
                )
            else:
                self.last_source = "playbook"
        else:
            self.last_source = "playbook"

        return RemediationAction(
            action=action,
            target_kind=target_kind,
            target_name=event.service,
            namespace=event.namespace,
            reason=root_cause,
            parameters=parameters,
        )

    def _normalize_parameters(self, parameters: dict, event: TelemetryEvent) -> dict[str, int | str]:
        normalized: dict[str, int | str] = {}
        for key, value in parameters.items():
            if key == "replicas":
                try:
                    normalized["replicas"] = int(value)
                except (TypeError, ValueError):
                    continue
            elif key in {"name", "namespace"}:
                continue
            elif isinstance(value, (int, str)):
                normalized[key] = value

        if "replicas" in normalized:
            return normalized
        return normalized
