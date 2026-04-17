from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import Base, engine


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "incidents" in inspector.get_table_names():
            column_names = {column["name"] for column in inspector.get_columns("incidents")}
            dialect = connection.dialect.name

            if "traces" not in column_names:
                if dialect == "postgresql":
                    connection.execute(text("ALTER TABLE incidents ADD COLUMN traces JSON"))
                    connection.execute(text("UPDATE incidents SET traces = '[]'::json WHERE traces IS NULL"))
                else:
                    connection.execute(text("ALTER TABLE incidents ADD COLUMN traces JSON"))

            if "resolved_at" not in column_names:
                if dialect == "postgresql":
                    connection.execute(text("ALTER TABLE incidents ADD COLUMN resolved_at TIMESTAMPTZ"))
                else:
                    connection.execute(text("ALTER TABLE incidents ADD COLUMN resolved_at DATETIME"))

            if "rca_source" not in column_names:
                connection.execute(text("ALTER TABLE incidents ADD COLUMN rca_source VARCHAR(64)"))

            if "remediation_source" not in column_names:
                connection.execute(text("ALTER TABLE incidents ADD COLUMN remediation_source VARCHAR(64)"))

        if "telemetry_events" in inspector.get_table_names():
            telemetry_columns = {column["name"] for column in inspector.get_columns("telemetry_events")}
            dialect = connection.dialect.name

            if "attempts" not in telemetry_columns:
                connection.execute(text("ALTER TABLE telemetry_events ADD COLUMN attempts INTEGER DEFAULT 0"))
            if "max_attempts" not in telemetry_columns:
                connection.execute(text("ALTER TABLE telemetry_events ADD COLUMN max_attempts INTEGER DEFAULT 3"))
            if "last_error" not in telemetry_columns:
                connection.execute(text("ALTER TABLE telemetry_events ADD COLUMN last_error TEXT"))
            if "dead_letter_reason" not in telemetry_columns:
                connection.execute(text("ALTER TABLE telemetry_events ADD COLUMN dead_letter_reason TEXT"))
            if "next_attempt_at" not in telemetry_columns:
                if dialect == "postgresql":
                    connection.execute(text("ALTER TABLE telemetry_events ADD COLUMN next_attempt_at TIMESTAMPTZ"))
                else:
                    connection.execute(text("ALTER TABLE telemetry_events ADD COLUMN next_attempt_at DATETIME"))
