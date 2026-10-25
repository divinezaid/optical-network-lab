"""Structured (JSON lines) event log for a node.

Every state change is one JSON object per line, so the Stage 3 log parser
can read it without regexes:

    {"ts": "...", "level": "WARNING", "node": "node-a", "event": "ALARM_RAISED", ...}
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "node": record.node,
            "event": record.getMessage(),
            **record.fields,
        }
        return json.dumps(entry, default=str)


class EventLog:
    def __init__(self, node_id: str, log_dir: Path | None = None) -> None:
        self.node_id = node_id
        self._logger = logging.getLogger(f"ne.{node_id}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._logger.handlers.clear()

        handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_dir / f"{node_id}.log", encoding="utf-8"))
        for handler in handlers:
            handler.setFormatter(_JsonFormatter())
            self._logger.addHandler(handler)

    def emit(self, level: int, event: str, **fields) -> None:
        self._logger.log(level, event, extra={"node": self.node_id, "fields": fields})
