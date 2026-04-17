from __future__ import annotations

import logging

from app.state import state


class DashboardLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            state.add_log(
                message=message,
                level=record.levelname,
                source=record.name,
            )
        except Exception:
            return


def configure_dashboard_logging() -> None:
    root_logger = logging.getLogger()
    if any(isinstance(handler, DashboardLogHandler) for handler in root_logger.handlers):
        return

    handler = DashboardLogHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
