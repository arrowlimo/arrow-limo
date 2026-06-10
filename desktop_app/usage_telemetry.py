"""Lightweight usage telemetry helper for local JSONL and daily summary export."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class UsageTelemetry:
    """Record UI events to newline-delimited JSON and daily summary files."""

    def __init__(self, app_name: str = "alms_desktop") -> None:
        base_dir = Path.home() / ".limo_telemetry"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.app_name = app_name
        self.events_file = base_dir / "events.jsonl"
        self.summary_file = base_dir / "daily_summary.json"

    def track(self, event_name: str, payload: dict | None = None) -> None:
        payload = payload or {}
        ts = datetime.utcnow().isoformat() + "Z"
        event = {
            "timestamp": ts,
            "app": self.app_name,
            "event": event_name,
            "payload": payload,
        }
        self._append_event(event)
        self._increment_daily(event_name)

    def _append_event(self, event: dict) -> None:
        try:
            with open(self.events_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=True) + "\n")
        except Exception as exc:
            logger.warning("Usage telemetry append failed: %s", exc)

    def _increment_daily(self, event_name: str) -> None:
        day_key = datetime.utcnow().strftime("%Y-%m-%d")
        try:
            summary = {}
            if self.summary_file.exists():
                with open(self.summary_file, encoding="utf-8") as handle:
                    summary = json.load(handle)
            day_entry = summary.get(day_key, {})
            day_entry[event_name] = int(day_entry.get(event_name, 0)) + 1
            summary[day_key] = day_entry
            with open(self.summary_file, "w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2)
        except Exception as exc:
            logger.warning("Usage telemetry summary update failed: %s", exc)
