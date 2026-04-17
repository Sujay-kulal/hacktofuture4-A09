from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import TelemetryEvent
from app.telemetry_queue import TelemetryQueueStore


def test_telemetry_queue_persists_and_marks_processed() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True)
    queue = TelemetryQueueStore(session_factory)

    queue.enqueue(
        TelemetryEvent(
            scenario="dependency-down",
            service="checkout",
            namespace="demo",
            symptoms=["customer errors"],
            metadata={"source": "demo-app"},
        )
    )

    assert queue.depth() == 1

    event = queue.dequeue()

    assert event is not None
    assert event.service == "checkout"
    assert "_queue_record_id" in event.metadata

    queue.mark_processed(int(event.metadata["_queue_record_id"]))

    assert queue.depth() == 0
    assert queue.overview().processed == 1


def test_telemetry_queue_dead_letters_after_max_attempts() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True)
    queue = TelemetryQueueStore(session_factory)

    queue.enqueue(
        TelemetryEvent(
            scenario="dependency-down",
            service="checkout",
            namespace="demo",
            symptoms=["customer errors"],
            metadata={"source": "demo-app"},
        ),
        max_attempts=1,
    )

    event = queue.dequeue()

    assert event is not None
    result = queue.mark_failed(int(event.metadata["_queue_record_id"]), "simulated failure")

    assert result == "dead_letter"
    assert queue.overview().dead_letter == 1
