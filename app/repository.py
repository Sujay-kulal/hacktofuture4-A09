from __future__ import annotations

from datetime import datetime, timezone
from statistics import median

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db_models import ActionRecord, ApprovalRequestRecord, IncidentRecord
from app.models import (
    ActionStatus,
    ApprovalRequest,
    AutomationStatus,
    BenchmarkReport,
    DashboardSummary,
    Incident,
    IncidentStatus,
    MTTRReport,
    PolicyDecision,
    RemediationAction,
    ScenarioBenchmark,
    ScenarioMTTR,
)


class IncidentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save_incident(self, incident: Incident, action: RemediationAction | None = None) -> None:
        record = self.db.get(IncidentRecord, incident.id)
        if record is None:
            record = IncidentRecord(
                id=incident.id,
                scenario=incident.scenario,
                service=incident.service,
                namespace=incident.namespace,
                symptoms=incident.symptoms,
                metrics=incident.metrics,
                root_cause=incident.root_cause,
                status=incident.status.value,
                timeline=incident.timeline,
                traces=incident.traces,
                rca_source=incident.rca_source,
                remediation_source=incident.remediation_source,
                resolved_at=self._resolved_at_value(incident.status),
            )
            self.db.add(record)
        else:
            record.root_cause = incident.root_cause
            record.status = incident.status.value
            record.timeline = incident.timeline
            record.metrics = incident.metrics
            record.traces = incident.traces
            record.rca_source = incident.rca_source
            record.remediation_source = incident.remediation_source
            record.resolved_at = self._resolved_at_value(incident.status, record.resolved_at)

        if action is not None:
            record.actions.append(
                ActionRecord(
                    action=action.action,
                    target_kind=action.target_kind,
                    target_name=action.target_name,
                    namespace=action.namespace,
                    reason=action.reason,
                    parameters=action.parameters,
                    status=action.status.value,
                )
            )

        self.db.commit()

    def list_incidents(self, limit: int = 100) -> list[Incident]:
        stmt = select(IncidentRecord).order_by(desc(IncidentRecord.created_at)).limit(limit)
        records = self.db.execute(stmt).unique().scalars().all()
        return [self._to_model(record) for record in records]

    def latest_incident(self) -> Incident | None:
        stmt = select(IncidentRecord).order_by(desc(IncidentRecord.created_at)).limit(1)
        record = self.db.execute(stmt).unique().scalars().first()
        if record is None:
            return None
        return self._to_model(record)

    def get_incident(self, incident_id: str) -> Incident | None:
        record = self.db.get(IncidentRecord, incident_id)
        if record is None:
            return None
        return self._to_model(record)

    def summary(self, queue_depth: int, kubernetes_mode: str, telemetry_mode: str) -> DashboardSummary:
        total = self.db.scalar(select(func.count()).select_from(IncidentRecord)) or 0

        def count_status(status: IncidentStatus) -> int:
            return self.db.scalar(
                select(func.count()).select_from(IncidentRecord).where(IncidentRecord.status == status.value)
            ) or 0

        return DashboardSummary(
            total_incidents=total,
            remediated_incidents=count_status(IncidentStatus.remediated),
            pending_approval_incidents=count_status(IncidentStatus.pending_approval),
            blocked_incidents=count_status(IncidentStatus.blocked),
            escalated_incidents=count_status(IncidentStatus.escalated),
            open_incidents=count_status(IncidentStatus.open),
            queue_depth=queue_depth,
            kubernetes_mode=kubernetes_mode,
            telemetry_mode=telemetry_mode,
        )

    def mttr_report(self) -> MTTRReport:
        stmt = select(IncidentRecord).where(IncidentRecord.resolved_at.is_not(None))
        records = self.db.execute(stmt).unique().scalars().all()
        durations = [self._duration_seconds(record) for record in records if self._duration_seconds(record) is not None]
        durations = [duration for duration in durations if duration is not None]
        durations.sort()

        scenario_map: dict[str, list[float]] = {}
        for record in records:
            duration = self._duration_seconds(record)
            if duration is None:
                continue
            scenario_map.setdefault(record.scenario, []).append(duration)

        now = datetime.now(timezone.utc)
        recovered_last_24h = sum(
            1
            for record in records
            if record.resolved_at is not None and (now - record.resolved_at).total_seconds() <= 86400
        )

        return MTTRReport(
            resolved_incidents=len(durations),
            average_mttr_seconds=round(sum(durations) / len(durations), 2) if durations else 0.0,
            median_mttr_seconds=round(float(median(durations)), 2) if durations else 0.0,
            p95_mttr_seconds=round(self._percentile(durations, 0.95), 2) if durations else 0.0,
            recovered_last_24h=recovered_last_24h,
            scenarios=[
                ScenarioMTTR(
                    scenario=scenario,
                    resolved_incidents=len(values),
                    average_mttr_seconds=round(sum(values) / len(values), 2),
                )
                for scenario, values in sorted(scenario_map.items())
            ],
        )

    def automation_status(
        self,
        *,
        configured: bool,
        provider: str,
        model: str | None,
        automation_mode: str,
        last_error: str | None,
    ) -> AutomationStatus:
        total_ai_assisted = self.db.scalar(
            select(func.count()).select_from(IncidentRecord).where(
                (IncidentRecord.rca_source == "gemini") | (IncidentRecord.remediation_source == "gemini")
            )
        ) or 0
        gemini_rca = self.db.scalar(
            select(func.count()).select_from(IncidentRecord).where(IncidentRecord.rca_source == "gemini")
        ) or 0
        gemini_remediation = self.db.scalar(
            select(func.count()).select_from(IncidentRecord).where(IncidentRecord.remediation_source == "gemini")
        ) or 0

        return AutomationStatus(
            provider=provider,
            configured=configured,
            model=model,
            automation_mode=automation_mode,
            last_error=last_error,
            total_ai_assisted_incidents=total_ai_assisted,
            gemini_rca_incidents=gemini_rca,
            gemini_remediation_incidents=gemini_remediation,
        )

    def benchmark_report(self) -> BenchmarkReport:
        records = self.db.execute(select(IncidentRecord)).unique().scalars().all()
        baselines = {
            "crashloop": 2400.0,
            "oomkill": 2700.0,
            "high-latency": 3600.0,
            "dependency-down": 4200.0,
            "failed-rollout": 3000.0,
        }
        incidents_by_status: dict[str, int] = {}
        incidents_by_scenario: dict[str, int] = {}
        scenario_durations: dict[str, list[float]] = {}
        scenario_total: dict[str, int] = {}
        scenario_resolved: dict[str, int] = {}

        for record in records:
            incidents_by_status[record.status] = incidents_by_status.get(record.status, 0) + 1
            incidents_by_scenario[record.scenario] = incidents_by_scenario.get(record.scenario, 0) + 1
            scenario_total[record.scenario] = scenario_total.get(record.scenario, 0) + 1
            duration = self._duration_seconds(record)
            if duration is not None:
                scenario_resolved[record.scenario] = scenario_resolved.get(record.scenario, 0) + 1
                scenario_durations.setdefault(record.scenario, []).append(duration)

        resolved_durations = [duration for values in scenario_durations.values() for duration in values]
        average_mttr = round(sum(resolved_durations) / len(resolved_durations), 2) if resolved_durations else 0.0
        baseline_values = [baselines.get(record.scenario, 3600.0) for record in records] or [3600.0]
        baseline_mttr = round(sum(baseline_values) / len(baseline_values), 2)
        improvement = (
            round(max(0.0, ((baseline_mttr - average_mttr) / baseline_mttr) * 100), 2)
            if baseline_mttr
            else 0.0
        )
        remediation_success_rate = (
            round((incidents_by_status.get(IncidentStatus.remediated.value, 0) / len(records)) * 100, 2)
            if records
            else 0.0
        )

        scenarios: list[ScenarioBenchmark] = []
        for scenario, total_count in sorted(scenario_total.items()):
            resolved_count = scenario_resolved.get(scenario, 0)
            durations = scenario_durations.get(scenario, [])
            scenario_average = round(sum(durations) / len(durations), 2) if durations else 0.0
            baseline = baselines.get(scenario, 3600.0)
            scenario_improvement = (
                round(max(0.0, ((baseline - scenario_average) / baseline) * 100), 2)
                if durations and baseline
                else 0.0
            )
            success_rate = round((resolved_count / total_count) * 100, 2) if total_count else 0.0
            scenarios.append(
                ScenarioBenchmark(
                    scenario=scenario,
                    incidents=total_count,
                    resolved_incidents=resolved_count,
                    average_mttr_seconds=scenario_average,
                    baseline_mttr_seconds=baseline,
                    improvement_percent=scenario_improvement,
                    remediation_success_rate=success_rate,
                )
            )

        return BenchmarkReport(
            total_incidents=len(records),
            resolved_incidents=len(resolved_durations),
            remediation_success_rate=remediation_success_rate,
            average_mttr_seconds=average_mttr,
            baseline_mttr_seconds=baseline_mttr,
            improvement_percent=improvement,
            incidents_by_status=incidents_by_status,
            incidents_by_scenario=incidents_by_scenario,
            scenarios=scenarios,
        )

    def create_approval_request(
        self,
        *,
        incident: Incident,
        action: RemediationAction,
        policy_decision: PolicyDecision,
    ) -> ApprovalRequest:
        record = ApprovalRequestRecord(
            incident_id=incident.id,
            service=incident.service,
            namespace=incident.namespace,
            scenario=incident.scenario,
            action=action.action,
            target_kind=action.target_kind,
            target_name=action.target_name,
            reason=policy_decision.reason,
            risk_level=policy_decision.risk_level,
            blast_radius=policy_decision.blast_radius,
            status="pending",
            parameters=action.parameters,
            policy_tags=policy_decision.policy_tags,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._to_approval(record)

    def list_approvals(self, status: str | None = None, limit: int = 50) -> list[ApprovalRequest]:
        stmt = select(ApprovalRequestRecord).order_by(desc(ApprovalRequestRecord.created_at)).limit(limit)
        if status:
            stmt = stmt.where(ApprovalRequestRecord.status == status)
        records = self.db.execute(stmt).scalars().all()
        return [self._to_approval(record) for record in records]

    def get_approval(self, approval_id: int) -> ApprovalRequest | None:
        record = self.db.get(ApprovalRequestRecord, approval_id)
        if record is None:
            return None
        return self._to_approval(record)

    def resolve_approval(self, approval_id: int, status: str, comment: str | None = None) -> ApprovalRequest | None:
        record = self.db.get(ApprovalRequestRecord, approval_id)
        if record is None:
            return None
        record.status = status
        record.reviewer_comment = comment
        record.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return self._to_approval(record)

    def _to_model(self, record: IncidentRecord) -> Incident:
        latest_action = record.actions[-1] if record.actions else None
        latest_action_status = None
        if latest_action is not None:
            latest_action_status = ActionStatus(latest_action.status)

        return Incident(
            id=record.id,
            scenario=record.scenario,
            service=record.service,
            namespace=record.namespace,
            symptoms=record.symptoms,
            metrics=record.metrics,
            traces=record.traces,
            root_cause=record.root_cause,
            status=IncidentStatus(record.status),
            timeline=record.timeline,
            latest_action=latest_action.action if latest_action is not None else None,
            latest_action_status=latest_action_status,
            rca_source=record.rca_source,
            remediation_source=record.remediation_source,
        )

    def _to_approval(self, record: ApprovalRequestRecord) -> ApprovalRequest:
        return ApprovalRequest(
            id=int(record.id),
            incident_id=record.incident_id,
            service=record.service,
            namespace=record.namespace,
            scenario=record.scenario,
            action=record.action,
            target_kind=record.target_kind,
            target_name=record.target_name,
            reason=record.reason,
            risk_level=record.risk_level,
            blast_radius=int(record.blast_radius),
            status=record.status,
            parameters=record.parameters or {},
            policy_tags=record.policy_tags or [],
            reviewer_comment=record.reviewer_comment,
            created_at=record.created_at.isoformat(),
            resolved_at=record.resolved_at.isoformat() if record.resolved_at else None,
        )

    def _resolved_at_value(
        self,
        status: IncidentStatus,
        current: datetime | None = None,
    ) -> datetime | None:
        if status in {IncidentStatus.remediated, IncidentStatus.blocked, IncidentStatus.escalated}:
            return current or datetime.now(timezone.utc)
        return None

    def _duration_seconds(self, record: IncidentRecord) -> float | None:
        if record.resolved_at is None:
            return None
        return float((record.resolved_at - record.created_at).total_seconds())

    def _percentile(self, values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]
        index = (len(values) - 1) * percentile
        lower = int(index)
        upper = min(lower + 1, len(values) - 1)
        weight = index - lower
        return values[lower] * (1 - weight) + values[upper] * weight
