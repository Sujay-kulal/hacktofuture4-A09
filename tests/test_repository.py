from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ActionStatus, Incident, IncidentStatus, PolicyDecision, RemediationAction
from app.repository import IncidentRepository


def test_repository_persists_incident_and_action() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, future=True)()
    repo = IncidentRepository(session)

    incident = Incident(
        id="incident-1",
        scenario="crashloop",
        service="checkout",
        namespace="demo",
        symptoms=["CrashLoopBackOff"],
        metrics={"restarts": 5},
        status=IncidentStatus.remediated,
        timeline=["detected", "fixed"],
        root_cause="bad config",
        rca_source="gemini",
        remediation_source="playbook",
    )
    action = RemediationAction(
        action="restart_deployment",
        target_kind="Deployment",
        target_name="checkout",
        namespace="demo",
        reason="bad config",
        status=ActionStatus.verified,
    )

    repo.save_incident(incident, action)
    incidents = repo.list_incidents()

    assert len(incidents) == 1
    assert incidents[0].service == "checkout"
    assert incidents[0].latest_action == "restart_deployment"
    assert incidents[0].latest_action_status == ActionStatus.verified
    assert incidents[0].rca_source == "gemini"
    assert incidents[0].remediation_source == "playbook"

    status = repo.automation_status(
        configured=True,
        provider="gemini",
        model="gemini-2.5-flash",
        automation_mode="hybrid",
        last_error=None,
    )
    assert status.total_ai_assisted_incidents == 1
    assert status.gemini_rca_incidents == 1
    assert status.gemini_remediation_incidents == 0

    approval = repo.create_approval_request(
        incident=incident,
        action=action,
        policy_decision=PolicyDecision(
            allowed=False,
            reason="human approval required",
            risk_level="high",
            requires_approval=True,
            blast_radius=4,
            policy_tags=["rollback-approval"],
        ),
    )
    assert approval.status == "pending"

    benchmark = repo.benchmark_report()
    assert benchmark.total_incidents == 1
    assert benchmark.remediation_success_rate == 100.0
