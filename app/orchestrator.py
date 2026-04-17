from __future__ import annotations

from collections.abc import Callable
import logging
from uuid import uuid4

from agents import MonitorAgent, RCAAgent, RemediationAgent, VerificationAgent
from app.models import ActionStatus, Incident, IncidentStatus, LoopResult
from app.policy_engine import PolicyEngine
from app.repository import IncidentRepository
from integrations.kubernetes.client import KubernetesExecutor
from integrations.telemetry.provider import TelemetryProvider

logger = logging.getLogger("selfheal.orchestrator")


class SelfHealingOrchestrator:
    def __init__(
        self,
        telemetry: TelemetryProvider,
        monitor: MonitorAgent,
        rca: RCAAgent,
        remediator: RemediationAgent,
        verifier: VerificationAgent,
        policies: PolicyEngine,
        executor: KubernetesExecutor,
        event_logger: Callable[[str, str], None] | None = None,
        automation_mode: str = "hybrid",
    ) -> None:
        self.telemetry = telemetry
        self.monitor = monitor
        self.rca = rca
        self.remediator = remediator
        self.verifier = verifier
        self.policies = policies
        self.executor = executor
        self.event_logger = event_logger or (lambda message, level="info": None)
        self.automation_mode = automation_mode
        self.last_event = None

    def run_once(self, repository: IncidentRepository) -> LoopResult:
        event = self.telemetry.next_event()
        self.last_event = event
        if event is None:
            self.event_logger("Healing cycle skipped because no telemetry events were queued", "warning")
            logger.warning("No telemetry events available for processing")
            return LoopResult(notes=["No telemetry events available"])
        try:
            self.event_logger(
                f"Processing telemetry event for service '{event.service}' in namespace '{event.namespace}'",
                "info",
            )
            logger.info("Processing event: service=%s namespace=%s scenario=%s", event.service, event.namespace, event.scenario)
            incident = self.monitor.detect(event, incident_id=str(uuid4()))

            root_cause = self.rca.analyze(event)
            incident.root_cause = root_cause
            incident.rca_source = self.rca.last_source
            incident.timeline.append(f"Root cause estimated as '{root_cause}'")
            incident.timeline.append(f"RCA source: {self.rca.last_source}")
            if self.rca.last_source == "gemini":
                incident.timeline.append("Gemini analyzed the telemetry and proposed the diagnosis")
            self.event_logger(f"Root cause estimated as '{root_cause}'", "info")
            logger.info("Root cause estimated: %s (source=%s)", root_cause, self.rca.last_source)
            if self.automation_mode == "gemini_only" and self.rca.last_source == "gemini_failed":
                incident.status = IncidentStatus.escalated
                incident.timeline.append("Gemini-only mode blocked fallback to rules during RCA")
                repository.save_incident(incident)
                self.telemetry.complete(event)
                self.event_logger("Gemini-only mode blocked fallback during RCA", "error")
                logger.error("Gemini-only mode blocked RCA fallback")
                return LoopResult(incident=incident, notes=list(incident.timeline))

            action = self.remediator.choose(event, root_cause)
            incident.remediation_source = self.remediator.last_source
            incident.timeline.append(f"Remediation source: {self.remediator.last_source}")
            if self.remediator.last_source == "gemini":
                incident.timeline.append("Gemini recommended the remediation plan")
            if self.automation_mode == "gemini_only" and self.remediator.last_source == "gemini_failed":
                incident.status = IncidentStatus.escalated
                incident.timeline.append("Gemini-only mode blocked fallback to playbooks during remediation")
                repository.save_incident(incident)
                self.telemetry.complete(event)
                self.event_logger("Gemini-only mode blocked fallback during remediation", "error")
                logger.error("Gemini-only mode blocked remediation fallback")
                return LoopResult(incident=incident, action=action, notes=list(incident.timeline))
            impacted_services = list(
                {
                    *list(event.metadata.get("impacted_services", [])),
                    *list(event.metadata.get("transitive_impacted_services", [])),
                }
            )
            policy_decision = self.policies.evaluate(
                action,
                impacted_services=impacted_services,
            )
            incident.timeline.append(
                "Policy decision: "
                f"{policy_decision.reason} "
                f"(risk={policy_decision.risk_level}, blast_radius={policy_decision.blast_radius}, "
                f"approval_required={policy_decision.requires_approval})"
            )
            self.event_logger(
                f"Policy decision for '{action.action}': {policy_decision.reason}",
                "info",
            )
            logger.info(
                "Policy decision: action=%s allowed=%s reason=%s remediation_source=%s risk=%s blast_radius=%s",
                action.action,
                policy_decision.allowed,
                policy_decision.reason,
                self.remediator.last_source,
                policy_decision.risk_level,
                policy_decision.blast_radius,
            )

            if not policy_decision.allowed:
                action.status = ActionStatus.blocked
                incident.latest_action = action.action
                incident.latest_action_status = action.status
                if policy_decision.requires_approval:
                    incident.status = IncidentStatus.pending_approval
                    repository.save_incident(incident)
                    approval = repository.create_approval_request(
                        incident=incident,
                        action=action,
                        policy_decision=policy_decision,
                    )
                    incident.timeline.append(f"Approval request created: #{approval.id}")
                    repository.save_incident(incident, action)
                    self.telemetry.complete(event)
                    self.event_logger(
                        f"Approval required for '{action.action}' on service '{event.service}'",
                        "warning",
                    )
                    logger.warning("Approval required: action=%s service=%s approval_id=%s", action.action, event.service, approval.id)
                    return LoopResult(incident=incident, action=action, notes=list(incident.timeline))

                incident.status = IncidentStatus.blocked
                repository.save_incident(incident, action)
                self.telemetry.complete(event)
                self.event_logger(
                    f"Blocked remediation '{action.action}' for service '{event.service}'",
                    "warning",
                )
                logger.warning("Remediation blocked: action=%s service=%s", action.action, event.service)
                return LoopResult(incident=incident, action=action, notes=[policy_decision.reason])

            executed = self.executor.execute(action)
            incident.timeline.append(f"Executor result: {executed.status}")
            incident.latest_action = executed.action
            incident.latest_action_status = executed.status
            self.event_logger(
                f"Executed remediation '{executed.action}' with status '{executed.status.value}'",
                "info",
            )
            logger.info("Executor result: action=%s status=%s", executed.action, executed.status.value)

            verified = self.verifier.verify(event, executed)
            if verified:
                executed.status = ActionStatus.verified
                incident.status = IncidentStatus.remediated
                incident.timeline.append("Verification passed")
                self.event_logger(
                    f"Verification passed for service '{event.service}'",
                    "success",
                )
                logger.info("Verification passed: service=%s", event.service)
            else:
                incident.status = IncidentStatus.escalated
                incident.timeline.append("Verification failed; escalation required")
                self.event_logger(
                    f"Verification failed for service '{event.service}', escalation required",
                    "error",
                )
                logger.error("Verification failed: service=%s", event.service)
            incident.latest_action_status = executed.status
            repository.save_incident(incident, executed)
            self.telemetry.complete(event)

            return LoopResult(
                incident=incident,
                action=executed,
                verification_passed=verified,
                notes=list(incident.timeline),
            )
        except Exception as exc:
            queue_status = self.telemetry.fail(event, str(exc))
            self.event_logger(
                f"Healing cycle failed unexpectedly for service '{event.service}': {exc}",
                "error",
            )
            logger.exception("Healing cycle failed unexpectedly; queue_status=%s", queue_status)
            return LoopResult(notes=[f"Unexpected platform error: {exc}", f"queue_status={queue_status}"])
