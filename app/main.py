from __future__ import annotations

import logging
from pathlib import Path
import time

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry.trace import get_current_span
from opentelemetry.trace.status import Status, StatusCode
from sqlalchemy.orm import Session

from agents import MonitorAgent, RCAAgent, RemediationAgent, VerificationAgent
from app.background_monitor import BackgroundMonitor
from app.bootstrap import init_database
from app.config import settings
from app.database import get_db
from app.logging_config import configure_dashboard_logging
from app.models import (
    ActionStatus,
    ApprovalDecisionRequest,
    ApprovalRequest,
    AutomationStatus,
    BenchmarkReport,
    DashboardSummary,
    DemoAppStatus,
    DemoFaultRequest,
    DemoTopologyStatus,
    DependencyNode,
    GeminiIncidentExplanation,
    GeminiTestRequest,
    IncidentStatus,
    ImpactView,
    LiveCollectionRequest,
    LoopResult,
    MTTRReport,
    MonitoringStatus,
    RemediationAction,
    SimulationRequest,
    TelemetryEvent,
)
from app.orchestrator import SelfHealingOrchestrator
from app.policy_engine import PolicyEngine
from app.repository import IncidentRepository
from app.state import state
from app.telemetry_queue import TelemetryQueueStore
from app.tracing_setup import configure_tracing, get_tracer
from app.database import SessionLocal
from integrations.kubernetes.client import KubernetesExecutor
from integrations.llm.gemini_client import GeminiAutomationClient
from integrations.telemetry.provider import TelemetryProvider


app = FastAPI(title="Agentic Self-Healing Cloud", version="0.1.0")
configure_tracing(app)
logger = logging.getLogger("selfheal")
tracer = get_tracer("selfheal.api")

automation_client = None
if settings.gemini_api_key:
    automation_client = GeminiAutomationClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        base_url=settings.gemini_base_url,
        fallback_models=settings.gemini_fallback_models,
        max_retries=settings.gemini_max_retries,
        cache_seconds=settings.gemini_cache_seconds,
        rate_limit_cooldown_seconds=settings.gemini_rate_limit_cooldown_seconds,
    )

queue_store = TelemetryQueueStore(SessionLocal)
telemetry = TelemetryProvider(queue_store=queue_store)
policy_engine = PolicyEngine(settings.policies_file)
executor = KubernetesExecutor(mode=settings.kube_mode)
dependency_graph = telemetry.dependency_graph
orchestrator = SelfHealingOrchestrator(
    telemetry=telemetry,
    monitor=MonitorAgent(),
    rca=RCAAgent(
        automation_client=automation_client,
        automation_mode=settings.automation_mode,
    ),
    remediator=RemediationAgent(
        settings.playbooks_file,
        automation_client=automation_client,
        automation_mode=settings.automation_mode,
    ),
    verifier=VerificationAgent(),
    policies=policy_engine,
    executor=executor,
    event_logger=state.log,
    automation_mode=settings.automation_mode,
)
background_monitor = BackgroundMonitor(
    enabled=settings.background_monitoring_enabled,
    interval_seconds=settings.background_monitoring_interval_seconds,
    max_events_per_scan=settings.background_monitoring_max_events_per_scan,
    max_queue_depth=settings.background_monitoring_max_queue_depth,
    namespaces=settings.background_monitor_namespaces,
    state=state,
    executor=executor,
    telemetry=telemetry,
    orchestrator=orchestrator,
)

frontend_dir = Path(settings.static_dir)
app.mount("/assets", StaticFiles(directory=frontend_dir), name="assets")


def _rebuild_event_from_incident(incident) -> TelemetryEvent:
    return TelemetryEvent(
        scenario=incident.scenario,
        service=incident.service,
        namespace=incident.namespace,
        symptoms=incident.symptoms,
        metrics=incident.metrics,
        traces=incident.traces,
        metadata={"source": "approval"},
    )


@app.on_event("startup")
def startup() -> None:
    configure_dashboard_logging()
    init_database()
    background_monitor.start()
    state.log("Application startup completed", "success")
    logger.info("Backend startup completed")


@app.on_event("shutdown")
def shutdown() -> None:
    background_monitor.stop()
    logger.info("Backend shutdown requested")


@app.middleware("http")
async def request_logging_middleware(request, call_next):
    logger.info("HTTP %s %s started", request.method, request.url.path)
    response = await call_next(request)
    logger.info("HTTP %s %s completed with %s", request.method, request.url.path, response.status_code)
    return response


@app.get("/")
def root() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/dashboard")
def dashboard() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/demo-app")
def demo_app() -> FileResponse:
    return FileResponse(frontend_dir / "demo.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "kubernetes_mode": settings.kube_mode,
        "telemetry_mode": settings.telemetry_mode,
        "prometheus_configured": str(bool(settings.prometheus_url)).lower(),
        "loki_configured": str(bool(settings.loki_url)).lower(),
        "trace_configured": str(bool(settings.trace_url)).lower(),
        "trace_backend": settings.trace_backend,
        "tracing_enabled": str(settings.tracing_enabled).lower(),
        "queue_backend": "postgresql",
        "gemini_configured": str(bool(settings.gemini_api_key)).lower(),
        "gemini_model": settings.gemini_model if settings.gemini_api_key else "not-configured",
        "automation_mode": settings.automation_mode,
        "background_monitoring_enabled": str(settings.background_monitoring_enabled).lower(),
    }


@app.get("/activity")
def activity() -> list[dict]:
    return [entry.model_dump() for entry in state.activity_feed]


@app.get("/logs")
def logs() -> list[dict]:
    return [entry.model_dump() for entry in state.log_feed]


@app.get("/automation/status", response_model=AutomationStatus)
def automation_status(db: Session = Depends(get_db)) -> AutomationStatus:
    repo = IncidentRepository(db)
    return repo.automation_status(
        configured=bool(settings.gemini_api_key),
        provider="gemini",
        model=settings.gemini_model if settings.gemini_api_key else None,
        automation_mode=settings.automation_mode,
        last_error=automation_client.last_error if automation_client is not None else None,
    )


@app.get("/demo/status", response_model=DemoAppStatus)
def demo_status() -> DemoAppStatus:
    return state.demo_status()


@app.get("/demo/topology", response_model=DemoTopologyStatus)
def demo_topology() -> DemoTopologyStatus:
    return state.demo_topology_status()


@app.post("/demo/faults/dependency-down", response_model=DemoAppStatus)
def toggle_demo_dependency(request: DemoFaultRequest) -> DemoAppStatus:
    return state.set_demo_dependency(request.enabled, "demo control panel")


@app.post("/demo/faults/{fault_name}", response_model=DemoAppStatus)
def toggle_demo_fault(fault_name: str, request: DemoFaultRequest) -> DemoAppStatus:
    valid_faults = {"payment", "inventory", "auth", "payment_slow"}
    if fault_name not in valid_faults:
        raise HTTPException(status_code=404, detail=f"Unknown demo fault '{fault_name}'")
    return state.set_demo_fault(fault_name, request.enabled, "demo control panel")


@app.post("/demo/checkout")
def demo_checkout() -> JSONResponse:
    services = ["storefront", "checkout", "auth", "inventory", "payment"]
    with tracer.start_as_current_span("storefront.checkout") as root_span:
        status_before = state.demo_status()
        root_span.set_attribute("demo.workflow", "storefront-checkout")
        root_span.set_attribute("demo.namespace", "demo")

        with tracer.start_as_current_span("auth.authorize") as auth_span:
            auth_span.set_attribute("demo.service", "auth")
            if status_before.auth_down:
                auth_span.set_status(Status(StatusCode.ERROR, "auth unavailable"))

        if not status_before.auth_down:
            with tracer.start_as_current_span("inventory.reserve") as inventory_span:
                inventory_span.set_attribute("demo.service", "inventory")
                if status_before.inventory_down:
                    inventory_span.set_status(Status(StatusCode.ERROR, "inventory unavailable"))

        if not status_before.auth_down and not status_before.inventory_down:
            with tracer.start_as_current_span("payment.charge") as payment_span:
                payment_span.set_attribute("demo.service", "payment")
                if status_before.payment_slow:
                    time.sleep(0.15)
                    payment_span.set_attribute("demo.latency_ms", 150)
                if status_before.dependency_down:
                    payment_span.set_status(Status(StatusCode.ERROR, "payment unavailable"))

        result = state.process_demo_checkout()
        root_span.set_attribute("demo.dependency_down", result.status.dependency_down)
        root_span.set_attribute("demo.inventory_down", result.status.inventory_down)
        root_span.set_attribute("demo.auth_down", result.status.auth_down)
        root_span.set_attribute("demo.payment_slow", result.status.payment_slow)
        root_span.set_attribute("demo.checkout.success", result.success)
        root_span.set_attribute("demo.checkout.status_code", result.status_code)
        if not result.success:
            root_span.set_status(Status(StatusCode.ERROR, result.message))

        trace_id = format(get_current_span().get_span_context().trace_id, "032x")
        state.record_demo_trace(
            trace_id=trace_id,
            services=services,
            outcome="success" if result.success else "failure",
            summary=result.message,
        )
    return JSONResponse(status_code=result.status_code, content=result.model_dump())


@app.post("/telemetry/collect/demo")
def collect_demo_telemetry() -> dict[str, str | float]:
    with tracer.start_as_current_span("demo.collect_telemetry") as span:
        status = state.demo_status()
        span.set_attribute("demo.failed_requests", status.failed_requests)
        span.set_attribute("demo.total_requests", status.total_requests)
    if not any([status.dependency_down, status.inventory_down, status.auth_down, status.payment_slow]) and status.failed_requests == 0:
        raise HTTPException(status_code=404, detail="Demo app is healthy. Break the dependency first.")

    traces = [f"{record.trace_id} | {' -> '.join(record.services)} | {record.summary}" for record in state.recent_demo_traces()[:5]]
    scenario = "dependency-down"
    suspected_dependency = "payment"
    if status.auth_down:
        scenario = "failed-rollout"
        suspected_dependency = "auth"
    elif status.inventory_down:
        scenario = "dependency-down"
        suspected_dependency = "inventory"
    elif status.payment_slow:
        scenario = "high-latency"
        suspected_dependency = "payment"

    event = TelemetryEvent(
        scenario=scenario,
        service="checkout",
        namespace="demo",
        symptoms=[
            "customer checkout errors" if status.failed_requests else "latency budget exceeded",
            f"{suspected_dependency} dependency impacted the checkout path",
        ],
        metrics={
            "failed_requests": float(status.failed_requests),
            "successful_requests": float(status.successful_requests),
            "error_rate": (status.failed_requests / status.total_requests) if status.total_requests else 0.0,
            "demo_trace_count": float(len(traces)),
        },
        logs=[
            status.last_error or "payment dependency unreachable",
            "storefront checkout returned HTTP 503",
        ],
        traces=traces or ["storefront -> checkout -> payment dependency timeout"],
        metadata={
            "source": "demo-app",
            "suspected_dependency": suspected_dependency,
            "impacted_services": ["checkout", "storefront"],
            "transitive_impacted_services": [service.service for service in state.demo_topology_status().services if service.affected],
        },
    )
    telemetry.push(event)
    state.log("Queued real demo storefront failure for self-healing", "warning")
    logger.warning("Demo storefront failure queued: service=checkout namespace=demo")
    return {
        "queued": event.scenario,
        "service": event.service,
        "namespace": event.namespace,
        "queue_depth": telemetry.depth(),
    }


@app.post("/automation/test/gemini")
def test_gemini(request: GeminiTestRequest) -> dict:
    if automation_client is None:
        raise HTTPException(status_code=400, detail="Gemini is not configured")

    event = TelemetryEvent(
        scenario=request.scenario,
        service=request.service,
        namespace=request.namespace,
        symptoms=["manual gemini test"],
        metrics={"error_rate": 0.35, "ready_replicas": 0},
        logs=["connection refused from dependency", "readiness probe failed"],
        traces=["checkout -> payment timeout"],
        metadata={"suspected_dependency": "payment", "impacted_services": ["checkout"]},
    )
    rca_result = automation_client.analyze_event(event)
    remediation_result = automation_client.recommend_action(
        event,
        str(rca_result.get("root_cause")) if rca_result else "unknown",
        "restart_deployment",
    )
    return {
        "gemini_configured": True,
        "input": event.model_dump(),
        "rca_result": rca_result,
        "remediation_result": remediation_result,
        "last_error": automation_client.last_error,
    }


@app.post("/automation/explain-last-incident", response_model=GeminiIncidentExplanation)
def explain_last_incident() -> GeminiIncidentExplanation:
    if automation_client is None:
        raise HTTPException(status_code=400, detail="Gemini is not configured")

    event = state.last_processed_event
    incident = state.last_processed_incident
    action = state.last_processed_action
    if event is None or incident is None:
        raise HTTPException(status_code=404, detail="No processed incident is available yet")

    explanation = automation_client.explain_decision(
        event,
        incident_id=incident.id,
        root_cause=incident.root_cause,
        action=action.action if action else incident.latest_action,
    )
    if explanation is None:
        raise HTTPException(
            status_code=502,
            detail=automation_client.last_error or "Gemini explanation failed",
        )

    response = GeminiIncidentExplanation(
        incident_id=incident.id,
        service=incident.service,
        scenario=incident.scenario,
        root_cause=incident.root_cause,
        action=action.action if action else incident.latest_action,
        source="last_processed_incident",
        explanation=str(explanation.get("explanation", "")),
        evidence=[str(item) for item in explanation.get("evidence", []) if item],
        leader_summary=str(explanation.get("leader_summary", "")),
    )
    state.set_gemini_explanation(response)
    return response


@app.get("/dependencies", response_model=list[DependencyNode])
def dependencies() -> list[DependencyNode]:
    return dependency_graph.all_nodes()


@app.get("/monitoring/status", response_model=MonitoringStatus)
def monitoring_status() -> MonitoringStatus:
    return state.monitoring_status


@app.get("/impact", response_model=ImpactView)
def impact_view() -> ImpactView:
    incident = state.last_processed_incident
    if incident is None:
        return executor.impact_view(
            service=None,
            namespace=None,
            scenario=None,
            latest_action=None,
            latest_action_status=None,
            incident_id=None,
            simulated_incident_only=False,
        )

    simulated_only = state.last_processed_event is not None and state.last_processed_event.metadata.get("source") != "live"
    latest_action_status = incident.latest_action_status.value if incident.latest_action_status else None
    return executor.impact_view(
        service=incident.service,
        namespace=incident.namespace,
        scenario=incident.scenario,
        latest_action=incident.latest_action,
        latest_action_status=latest_action_status,
        incident_id=incident.id,
        simulated_incident_only=simulated_only,
    )


@app.get("/incidents")
def list_incidents(db: Session = Depends(get_db)) -> list[dict]:
    repo = IncidentRepository(db)
    return [incident.model_dump() for incident in repo.list_incidents()]


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db)) -> dict:
    repo = IncidentRepository(db)
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
    return incident.model_dump()


@app.patch("/incidents/{incident_id}")
def update_incident(
    incident_id: str,
    updates: dict,
    db: Session = Depends(get_db),
) -> dict:
    """Update an incident's status, root_cause, or add a timeline note.
    
    Accepted fields in the body:
      - status: one of open, pending_approval, remediated, blocked, escalated
      - root_cause: string describing the root cause
      - timeline_note: a string to append to the incident timeline
    """
    repo = IncidentRepository(db)
    incident = repo.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")

    changed = []

    if "status" in updates:
        new_status_value = updates["status"]
        valid_statuses = {s.value for s in IncidentStatus}
        if new_status_value not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{new_status_value}'. Must be one of: {', '.join(valid_statuses)}",
            )
        incident.status = IncidentStatus(new_status_value)
        incident.timeline.append(f"Status changed to '{new_status_value}' by AI agent")
        changed.append(f"status={new_status_value}")

    if "root_cause" in updates:
        incident.root_cause = updates["root_cause"]
        incident.timeline.append(f"Root cause updated by AI agent: {updates['root_cause']}")
        changed.append("root_cause")

    if "timeline_note" in updates:
        incident.timeline.append(updates["timeline_note"])
        changed.append("timeline_note")

    repo.save_incident(incident)
    state.log(f"Incident {incident_id} updated by AI agent: {', '.join(changed)}", "info")
    logger.info("Incident %s updated: %s", incident_id, ", ".join(changed))
    return incident.model_dump()


@app.get("/queue")
def queue_overview() -> dict:
    return queue_store.overview().model_dump()


@app.post("/queue/{queue_id}/requeue")
def requeue_queue_item(queue_id: int) -> dict[str, str | int]:
    if not queue_store.requeue(queue_id):
        raise HTTPException(status_code=404, detail="Queue item not found")
    state.log(f"Queue item #{queue_id} requeued for processing", "info")
    return {"status": "requeued", "queue_id": queue_id}


@app.get("/approvals", response_model=list[ApprovalRequest])
def list_approvals(status: str | None = None, db: Session = Depends(get_db)) -> list[ApprovalRequest]:
    repo = IncidentRepository(db)
    return repo.list_approvals(status=status)


def _execute_approval(
    *,
    approval_id: int,
    decision: str,
    comment: str | None,
    db: Session,
) -> ApprovalRequest:
    repo = IncidentRepository(db)
    approval = repo.get_approval(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Approval request is already resolved")

    incident = repo.get_incident(approval.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident for approval request was not found")

    if decision == "approve":
        action = RemediationAction(
            action=approval.action,
            target_kind=approval.target_kind,
            target_name=approval.target_name,
            namespace=approval.namespace,
            reason=approval.reason,
            parameters=approval.parameters,
            status=ActionStatus.approved,
        )
        executed = executor.execute(action)
        event = _rebuild_event_from_incident(incident)
        verified = VerificationAgent().verify(event, executed)
        incident.timeline.append(f"Approval #{approval.id} approved manually")
        incident.timeline.append(f"Executor result after approval: {executed.status.value}")
        incident.latest_action = executed.action
        incident.latest_action_status = executed.status
        if verified:
            executed.status = ActionStatus.verified
            incident.latest_action_status = executed.status
            incident.status = IncidentStatus.remediated
            incident.timeline.append("Verification passed after approval")
        else:
            incident.status = IncidentStatus.escalated
            incident.timeline.append("Verification failed after approval")
        repo.save_incident(incident, executed)
        state.record_last_run(event=event, incident=incident, action=executed)
        state.log(f"Approval #{approval.id} approved and executed", "success")
        return repo.resolve_approval(approval_id, "approved", comment) or approval

    if decision == "reject":
        incident.status = IncidentStatus.blocked
        incident.timeline.append(f"Approval #{approval.id} rejected manually")
        repo.save_incident(incident)
        state.log(f"Approval #{approval.id} rejected", "warning")
        return repo.resolve_approval(approval_id, "rejected", comment) or approval

    if decision == "escalate":
        incident.status = IncidentStatus.escalated
        incident.timeline.append(f"Approval #{approval.id} escalated to human response")
        repo.save_incident(incident)
        state.log(f"Approval #{approval.id} escalated", "warning")
        return repo.resolve_approval(approval_id, "escalated", comment) or approval

    if decision == "retry":
        action = RemediationAction(
            action=approval.action,
            target_kind=approval.target_kind,
            target_name=approval.target_name,
            namespace=approval.namespace,
            reason=approval.reason,
            parameters=approval.parameters,
            status=ActionStatus.proposed,
        )
        incident.timeline.append(f"Approval #{approval.id} requested a retry of the remediation plan")
        telemetry.push(_rebuild_event_from_incident(incident))
        repo.save_incident(incident, action)
        state.log(f"Approval #{approval.id} sent the incident back for retry", "info")
        return repo.resolve_approval(approval_id, "retried", comment) or approval

    raise HTTPException(status_code=400, detail="Unknown approval decision")


@app.post("/approvals/{approval_id}/approve", response_model=ApprovalRequest)
def approve_request(approval_id: int, request: ApprovalDecisionRequest, db: Session = Depends(get_db)) -> ApprovalRequest:
    return _execute_approval(approval_id=approval_id, decision="approve", comment=request.comment, db=db)


@app.post("/approvals/{approval_id}/reject", response_model=ApprovalRequest)
def reject_request(approval_id: int, request: ApprovalDecisionRequest, db: Session = Depends(get_db)) -> ApprovalRequest:
    return _execute_approval(approval_id=approval_id, decision="reject", comment=request.comment, db=db)


@app.post("/approvals/{approval_id}/escalate", response_model=ApprovalRequest)
def escalate_request(approval_id: int, request: ApprovalDecisionRequest, db: Session = Depends(get_db)) -> ApprovalRequest:
    return _execute_approval(approval_id=approval_id, decision="escalate", comment=request.comment, db=db)


@app.post("/approvals/{approval_id}/retry", response_model=ApprovalRequest)
def retry_request(approval_id: int, request: ApprovalDecisionRequest, db: Session = Depends(get_db)) -> ApprovalRequest:
    return _execute_approval(approval_id=approval_id, decision="retry", comment=request.comment, db=db)


@app.get("/reports/mttr", response_model=MTTRReport)
def mttr_report(db: Session = Depends(get_db)) -> MTTRReport:
    repo = IncidentRepository(db)
    return repo.mttr_report()


@app.get("/reports/benchmark", response_model=BenchmarkReport)
def benchmark_report(db: Session = Depends(get_db)) -> BenchmarkReport:
    repo = IncidentRepository(db)
    return repo.benchmark_report()


@app.post("/incidents/simulate")
def simulate_incident(request: SimulationRequest) -> dict[str, str]:
    scenario_map = {
        "crashloop": TelemetryEvent(
            scenario="crashloop",
            service=request.service,
            namespace=request.namespace,
            symptoms=["CrashLoopBackOff", "restarts > 5"],
            metrics={"restarts": 8, "error_rate": 0.72},
            logs=["application failed to boot due to invalid startup flag"],
            traces=["frontend -> checkout -> failed startup"],
        ),
        "oomkill": TelemetryEvent(
            scenario="oomkill",
            service=request.service,
            namespace=request.namespace,
            symptoms=["OOMKilled", "memory saturation"],
            metrics={"memory_utilization": 0.98, "restarts": 4},
            logs=["container terminated with exit code 137"],
            traces=["worker -> checkout -> memory spike"],
        ),
        "high-latency": TelemetryEvent(
            scenario="high-latency",
            service=request.service,
            namespace=request.namespace,
            symptoms=["p95 latency spike", "5xx increase"],
            metrics={"p95_latency_ms": 2200, "error_rate": 0.23},
            logs=["upstream dependency timed out"],
            traces=["api -> checkout -> inventory timeout"],
        ),
        "dependency-down": TelemetryEvent(
            scenario="dependency-down",
            service=request.service,
            namespace=request.namespace,
            symptoms=["dependency failures", "connection refused"],
            metrics={"dependency_errors": 18, "availability": 0.55},
            logs=["redis connection refused"],
            traces=["checkout -> redis connection failed"],
        ),
        "failed-rollout": TelemetryEvent(
            scenario="failed-rollout",
            service=request.service,
            namespace=request.namespace,
            symptoms=["post deploy errors", "readiness failures"],
            metrics={"error_rate": 0.65, "ready_replicas": 0},
            logs=["readiness probe failed after deployment revision update"],
            traces=["gateway -> checkout -> readiness failure"],
        ),
    }

    if request.scenario not in scenario_map:
        raise HTTPException(status_code=400, detail=f"Unknown scenario '{request.scenario}'")

    event = scenario_map[request.scenario]
    telemetry.push(event)
    state.log(
        f"Queued simulated incident '{request.scenario}' for service '{request.service}'",
        "info",
    )
    logger.info("Simulated incident queued: scenario=%s service=%s namespace=%s", request.scenario, request.service, request.namespace)
    return {"queued": request.scenario, "service": request.service}


@app.post("/telemetry/collect/live")
def collect_live(request: LiveCollectionRequest) -> dict[str, str | float]:
    event = telemetry.collect_live(service=request.service, namespace=request.namespace)
    if event is None:
        state.log(
            f"No live anomaly detected for service '{request.service}' in namespace '{request.namespace}'",
            "warning",
        )
        logger.warning(
            "No live anomaly detected: service=%s namespace=%s",
            request.service,
            request.namespace,
        )
        raise HTTPException(
            status_code=404,
            detail="No anomaly detected or Prometheus is not configured",
        )

    telemetry.push(event)
    state.log(
        f"Queued live telemetry anomaly '{event.scenario}' for service '{event.service}'",
        "info",
    )
    logger.info(
        "Live anomaly queued: scenario=%s service=%s namespace=%s",
        event.scenario,
        event.service,
        event.namespace,
    )
    return {
        "queued": event.scenario,
        "service": event.service,
        "namespace": event.namespace,
        "queue_depth": telemetry.depth(),
    }


@app.post("/loop/run-once", response_model=LoopResult)
def run_once(db: Session = Depends(get_db)) -> LoopResult:
    repo = IncidentRepository(db)
    result = orchestrator.run_once(repo)
    state.record_last_run(
        event=orchestrator.last_event,
        incident=result.incident,
        action=result.action,
    )
    if result.incident is None:
        state.log("Run loop completed with no incident to process", "warning")
        logger.warning("Run loop completed with no queued telemetry event")
    else:
        state.log(
            f"Run loop completed for service '{result.incident.service}' with status '{result.incident.status.value}'",
            "success" if result.verification_passed else "warning",
        )
        logger.info(
            "Run loop completed: service=%s scenario=%s status=%s verification=%s",
            result.incident.service,
            result.incident.scenario,
            result.incident.status.value,
            result.verification_passed,
        )
    return result


@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    namespace: str | None = None,
    db: Session = Depends(get_db),
) -> DashboardSummary:
    repo = IncidentRepository(db)
    summary = repo.summary(
        queue_depth=telemetry.depth(),
        kubernetes_mode=executor.mode,
        telemetry_mode=settings.telemetry_mode,
    )
    summary.trace_configured = bool(settings.trace_url)
    summary.background_monitoring_enabled = settings.background_monitoring_enabled
    summary.workloads = executor.list_workloads(namespace=namespace)
    return summary
