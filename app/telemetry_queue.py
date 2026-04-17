from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import asc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db_models import TelemetryEventRecord
from app.models import QueueEntry, QueueOverview, TelemetryEvent


class TelemetryQueueStore:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def enqueue(self, event: TelemetryEvent, *, max_attempts: int = 3) -> int:
        payload = event.model_dump()
        source = str(event.metadata.get("source", "manual"))
        with self.session_factory() as session:
            record = TelemetryEventRecord(
                scenario=event.scenario,
                service=event.service,
                namespace=event.namespace,
                source=source,
                payload=payload,
                status="queued",
                max_attempts=max_attempts,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return int(record.id)

    def dequeue(self) -> TelemetryEvent | None:
        with self.session_factory() as session:
            claim_cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.telemetry_claim_timeout_seconds)
            stale_stmt = select(TelemetryEventRecord).where(
                TelemetryEventRecord.status == "claimed",
                TelemetryEventRecord.claimed_at.is_not(None),
                TelemetryEventRecord.claimed_at < claim_cutoff,
            )
            for stale_record in session.execute(stale_stmt).scalars().all():
                stale_record.status = "queued"
                stale_record.claimed_at = None

            stmt = (
                select(TelemetryEventRecord)
                .where(
                    TelemetryEventRecord.status == "queued",
                    (
                        (TelemetryEventRecord.next_attempt_at.is_(None))
                        | (TelemetryEventRecord.next_attempt_at <= datetime.now(timezone.utc))
                    ),
                )
                .order_by(asc(TelemetryEventRecord.queued_at), asc(TelemetryEventRecord.id))
                .limit(1)
            )
            record = session.execute(stmt).scalars().first()
            if record is None:
                return None

            record.status = "claimed"
            record.claimed_at = datetime.now(timezone.utc)
            payload = dict(record.payload or {})
            metadata = dict(payload.get("metadata") or {})
            metadata["_queue_record_id"] = int(record.id)
            payload["metadata"] = metadata
            session.commit()
            return TelemetryEvent(**payload)

    def mark_processed(self, queue_record_id: int | None) -> None:
        if queue_record_id is None:
            return
        with self.session_factory() as session:
            record = session.get(TelemetryEventRecord, queue_record_id)
            if record is None:
                return
            record.status = "processed"
            record.processed_at = datetime.now(timezone.utc)
            session.commit()

    def mark_failed(self, queue_record_id: int | None, error: str) -> str:
        if queue_record_id is None:
            return "missing"
        with self.session_factory() as session:
            record = session.get(TelemetryEventRecord, queue_record_id)
            if record is None:
                return "missing"

            record.attempts = int(record.attempts or 0) + 1
            record.last_error = error
            record.claimed_at = None

            if record.attempts >= int(record.max_attempts or 3):
                record.status = "dead_letter"
                record.dead_letter_reason = error
                record.processed_at = datetime.now(timezone.utc)
                session.commit()
                return "dead_letter"

            backoff_seconds = min(30 * max(record.attempts, 1), 300)
            record.status = "queued"
            record.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
            session.commit()
            return "requeued"

    def depth(self) -> int:
        with self.session_factory() as session:
            return int(
                session.scalar(
                    select(func.count()).select_from(TelemetryEventRecord).where(TelemetryEventRecord.status == "queued")
                )
                or 0
            )

    def overview(self, limit: int = 30) -> QueueOverview:
        with self.session_factory() as session:
            counts = {
                status: int(
                    session.scalar(
                        select(func.count()).select_from(TelemetryEventRecord).where(TelemetryEventRecord.status == status)
                    )
                    or 0
                )
                for status in ("queued", "claimed", "processed", "dead_letter")
            }
            records = (
                session.execute(
                    select(TelemetryEventRecord)
                    .order_by(asc(TelemetryEventRecord.status), asc(TelemetryEventRecord.queued_at))
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return QueueOverview(
                queued=counts["queued"],
                claimed=counts["claimed"],
                processed=counts["processed"],
                dead_letter=counts["dead_letter"],
                items=[self._to_entry(record) for record in records],
            )

    def requeue(self, queue_record_id: int) -> bool:
        with self.session_factory() as session:
            record = session.get(TelemetryEventRecord, queue_record_id)
            if record is None:
                return False
            record.status = "queued"
            record.claimed_at = None
            record.processed_at = None
            record.dead_letter_reason = None
            record.next_attempt_at = None
            session.commit()
            return True

    def _to_entry(self, record: TelemetryEventRecord) -> QueueEntry:
        return QueueEntry(
            id=int(record.id),
            scenario=record.scenario,
            service=record.service,
            namespace=record.namespace,
            source=record.source,
            status=record.status,
            attempts=int(record.attempts or 0),
            max_attempts=int(record.max_attempts or 3),
            last_error=record.last_error,
            dead_letter_reason=record.dead_letter_reason,
            queued_at=record.queued_at.isoformat() if record.queued_at else None,
            claimed_at=record.claimed_at.isoformat() if record.claimed_at else None,
            processed_at=record.processed_at.isoformat() if record.processed_at else None,
            next_attempt_at=record.next_attempt_at.isoformat() if record.next_attempt_at else None,
        )
