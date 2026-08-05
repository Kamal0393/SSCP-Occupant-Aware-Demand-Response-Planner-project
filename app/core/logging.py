"""
Module: logging.py

Purpose:
    Configures structured (JSON) logging for the application. Since this
    project's core theme is explainability, system-level observability is
    treated with the same seriousness: every log line should be machine
    parseable so we can later correlate a Decision with the request that
    produced it.

Inputs:
    app.core.config.settings (for LOG_LEVEL).

Outputs:
    A configured root logger; call `configure_logging()` once at app startup.

Design decisions:
    - Plain stdlib `logging` + a custom JSON formatter, avoiding an extra
      dependency for something this small. If log aggregation (e.g. ELK)
      is added later, this formatter's output is already compatible.
"""

import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL)

    # Avoid duplicate handlers if configure_logging() is called more than once
    # (e.g. under test runners that import the app module multiple times).
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
