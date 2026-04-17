from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IncidentStatus(str, Enum):
    open = "open"
    pending_approval = "pending_approval"
    remediated = "remediated"
    blocked = "blocked"
    escalated = "escalated"


class ActionStatus(str, Enum):
    proposed = "proposed"
    executed = "executed"
    blocked = "blocked"
    failed = "failed"
    verified = "verified"
    approved = "approved"
    rejected = "rejected"
    escalated = "escalated"


class TelemetryEvent(BaseModel):
    scenario: str
    service: str
    namespace: str = "demo"
    symptoms: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    traces: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    id: str
    scenario: str
    service: str
    namespace: str
    symptoms: list[str]
    root_cause: str | None = None
    status: IncidentStatus = IncidentStatus.open
    timeline: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    traces: list[str] = Field(default_factory=list)
    latest_action: str | None = None
    latest_action_status: ActionStatus | None = None
    rca_source: str | None = None
    remediation_source: str | None = None


class RemediationAction(BaseModel):
    action: str
    target_kind: str
    target_name: str
    namespace: str
    reason: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: ActionStatus = ActionStatus.proposed


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str
    risk_level: str = "low"
    requires_approval: bool = False
    blast_radius: int = 1
    policy_tags: list[str] = Field(default_factory=list)


class LoopResult(BaseModel):
    incident: Incident | None = None
    action: RemediationAction | None = None
    verification_passed: bool = False
    notes: list[str] = Field(default_factory=list)


class SimulationRequest(BaseModel):
    scenario: str
    service: str = "checkout"
    namespace: str = "demo"


class GeminiTestRequest(BaseModel):
    scenario: str = "dependency-down"
    service: str = "checkout"
    namespace: str = "demo"


class LiveCollectionRequest(BaseModel):
    service: str = "checkout"
    namespace: str = "demo"


class DemoFaultRequest(BaseModel):
    enabled: bool = True


class DemoAppStatus(BaseModel):
    dependency_down: bool
    inventory_down: bool = False
    auth_down: bool = False
    payment_slow: bool = False
    total_requests: int
    failed_requests: int
    successful_requests: int
    last_error: str | None = None
    last_order_status: str | None = None
    last_changed_at: str | None = None
    last_order_at: str | None = None
    fault_mode: str = "healthy"
    visible_message: str = "Checkout service is healthy."
    gemini_tokens_used: int = 0


class DemoCheckoutResponse(BaseModel):
    success: bool
    message: str
    order_id: str | None = None
    status_code: int
    status: DemoAppStatus


class ClusterWorkload(BaseModel):
    name: str
    namespace: str
    desired_replicas: int
    available_replicas: int
    updated_replicas: int
    ready_replicas: int | None = None
    conditions: list[str] = Field(default_factory=list)
    restarted_at: str | None = None


class DashboardSummary(BaseModel):
    total_incidents: int
    remediated_incidents: int
    pending_approval_incidents: int
    blocked_incidents: int
    escalated_incidents: int
    open_incidents: int
    queue_depth: int
    kubernetes_mode: str
    telemetry_mode: str
    trace_configured: bool = False
    background_monitoring_enabled: bool = False
    workloads: list[ClusterWorkload] = Field(default_factory=list)


class ScenarioMTTR(BaseModel):
    scenario: str
    resolved_incidents: int
    average_mttr_seconds: float


class MTTRReport(BaseModel):
    resolved_incidents: int
    average_mttr_seconds: float
    median_mttr_seconds: float
    p95_mttr_seconds: float
    recovered_last_24h: int
    scenarios: list[ScenarioMTTR] = Field(default_factory=list)


class ScenarioBenchmark(BaseModel):
    scenario: str
    incidents: int
    resolved_incidents: int
    average_mttr_seconds: float
    baseline_mttr_seconds: float
    improvement_percent: float
    remediation_success_rate: float


class BenchmarkReport(BaseModel):
    total_incidents: int
    resolved_incidents: int
    remediation_success_rate: float
    average_mttr_seconds: float
    baseline_mttr_seconds: float
    improvement_percent: float
    incidents_by_status: dict[str, int] = Field(default_factory=dict)
    incidents_by_scenario: dict[str, int] = Field(default_factory=dict)
    scenarios: list[ScenarioBenchmark] = Field(default_factory=list)


class AutomationStatus(BaseModel):
    provider: str
    configured: bool
    model: str | None = None
    automation_mode: str
    last_error: str | None = None
    total_ai_assisted_incidents: int = 0
    gemini_rca_incidents: int = 0
    gemini_remediation_incidents: int = 0


class ActivityEntry(BaseModel):
    timestamp: str
    level: str
    message: str


class LogEntry(BaseModel):
    timestamp: str
    level: str
    source: str
    message: str


class MonitoringStatus(BaseModel):
    enabled: bool
    running: bool
    interval_seconds: int
    last_scan_time: str | None = None
    last_remediation_time: str | None = None
    last_message: str | None = None
    targets_scanned: int = 0


class QueueEntry(BaseModel):
    id: int
    scenario: str
    service: str
    namespace: str
    source: str
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None = None
    dead_letter_reason: str | None = None
    queued_at: str | None = None
    claimed_at: str | None = None
    processed_at: str | None = None
    next_attempt_at: str | None = None


class QueueOverview(BaseModel):
    queued: int
    claimed: int
    processed: int
    dead_letter: int
    items: list[QueueEntry] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    id: int
    incident_id: str
    service: str
    namespace: str
    scenario: str
    action: str
    target_kind: str
    target_name: str
    reason: str
    risk_level: str
    blast_radius: int
    status: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    policy_tags: list[str] = Field(default_factory=list)
    reviewer_comment: str | None = None
    created_at: str
    resolved_at: str | None = None


class ApprovalDecisionRequest(BaseModel):
    comment: str | None = None


class GeminiIncidentExplanation(BaseModel):
    incident_id: str | None = None
    service: str
    scenario: str
    root_cause: str | None = None
    action: str | None = None
    source: str
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    leader_summary: str


class WorkloadEvent(BaseModel):
    timestamp: str
    type: str
    reason: str
    message: str


class ImpactView(BaseModel):
    mode: str
    simulated_incident_only: bool
    incident_id: str | None = None
    service: str | None = None
    namespace: str | None = None
    scenario: str | None = None
    latest_action: str | None = None
    latest_action_status: str | None = None
    summary: str
    workload: ClusterWorkload | None = None
    events: list[WorkloadEvent] = Field(default_factory=list)


class DependencyNode(BaseModel):
    service: str
    namespace: str
    depends_on: list[str] = Field(default_factory=list)
    impacted_services: list[str] = Field(default_factory=list)
    transitive_impacted_services: list[str] = Field(default_factory=list)
    criticality: str = "medium"
    cascading_risk_score: float = 0.0


class DemoServiceState(BaseModel):
    service: str
    status: str
    message: str
    affected: bool = False


class DemoTraceRecord(BaseModel):
    trace_id: str
    outcome: str
    services: list[str] = Field(default_factory=list)
    summary: str
    timestamp: str


class DemoTopologyStatus(BaseModel):
    services: list[DemoServiceState] = Field(default_factory=list)
    last_trace: DemoTraceRecord | None = None
    recent_traces: list[DemoTraceRecord] = Field(default_factory=list)
