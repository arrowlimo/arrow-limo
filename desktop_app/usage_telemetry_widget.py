"""UI widget to inspect ALMS usage telemetry in-app."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class UsageTelemetryWidget(QWidget):
    """Read-only dashboard for local telemetry events and daily summary."""

    def __init__(self, db=None) -> None:
        super().__init__()
        self.db = db
        self.telemetry_dir = Path.home() / ".limo_telemetry"
        self.events_file = self.telemetry_dir / "events.jsonl"
        self.summary_file = self.telemetry_dir / "daily_summary.json"

        self.metric_total_events = QLabel("0")
        self.metric_today_events = QLabel("0")
        self.metric_top_event = QLabel("-")
        self.metric_last_seen = QLabel("-")

        self.events_table = QTableWidget()
        self.status_label = QLabel("")

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("Usage Telemetry Snapshot")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0f172a;")
        subtitle = QLabel(
            "Operational usage metrics for menu/dispatch flows (local machine)."
        )
        subtitle.setStyleSheet("color: #475569;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        cards = QHBoxLayout()
        cards.setSpacing(8)
        cards.addWidget(self._make_card("Total Events", self.metric_total_events))
        cards.addWidget(self._make_card("Today", self.metric_today_events))
        cards.addWidget(self._make_card("Top Event", self.metric_top_event))
        cards.addWidget(self._make_card("Last Event", self.metric_last_seen))
        layout.addLayout(cards)

        actions = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        actions.addWidget(refresh_btn)
        actions.addStretch()
        layout.addLayout(actions)

        self.events_table.setColumnCount(4)
        self.events_table.setHorizontalHeaderLabels(
            ["Timestamp", "App", "Event", "Payload"]
        )
        self.events_table.horizontalHeader().setStretchLastSection(True)
        self.events_table.verticalHeader().setVisible(False)
        self.events_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.events_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self.events_table)

        self.status_label.setStyleSheet("color: #64748b;")
        layout.addWidget(self.status_label)

        self.setStyleSheet(
            """
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #dbe3ee;
                border-radius: 8px;
                padding: 8px;
            }
            QPushButton {
                background-color: #0ea5e9;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 5px 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
            QTableWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background: white;
                gridline-color: #e2e8f0;
            }
            QHeaderView::section {
                background-color: #e2e8f0;
                color: #0f172a;
                border: none;
                padding: 4px;
                font-weight: 600;
            }
            """
        )

    def _make_card(self, title: str, value_label: QLabel) -> QFrame:
        frame = QFrame()
        card_layout = QVBoxLayout(frame)
        card_layout.setContentsMargins(10, 8, 10, 8)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: #475569; font-size: 11px;")
        value_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #0f172a;")

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return frame

    def _read_events(self) -> list[dict]:
        if not self.events_file.exists():
            return []

        events = []
        with open(self.events_file, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events

    def _read_summary(self) -> dict:
        if not self.summary_file.exists():
            return {}
        try:
            with open(self.summary_file, encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {}

    def refresh_data(self) -> None:
        events = self._read_events()
        summary = self._read_summary()

        today = datetime.now().strftime("%Y-%m-%d")
        today_events = [e for e in events if str(e.get("timestamp", "")).startswith(today)]

        self.metric_total_events.setText(str(len(events)))
        self.metric_today_events.setText(str(len(today_events)))

        event_counter = Counter(e.get("event", "") for e in events if e.get("event"))
        top_event = event_counter.most_common(1)[0][0] if event_counter else "-"
        self.metric_top_event.setText(top_event)

        last_ts = events[-1].get("timestamp", "-") if events else "-"
        self.metric_last_seen.setText(last_ts)

        self._populate_table(events[-100:])

        today_summary = summary.get(today, {})
        summary_text = ", ".join(
            f"{k}={v}" for k, v in sorted(today_summary.items())
        )
        if not summary_text:
            summary_text = "No daily summary values yet."
        self.status_label.setText(
            f"Source: {self.telemetry_dir} | Today summary: {summary_text}"
        )

    def _populate_table(self, events: list[dict]) -> None:
        self.events_table.setRowCount(len(events))

        for row_idx, event in enumerate(reversed(events)):
            ts_item = QTableWidgetItem(str(event.get("timestamp", "")))
            app_item = QTableWidgetItem(str(event.get("app", "")))
            event_item = QTableWidgetItem(str(event.get("event", "")))
            payload = event.get("payload", {})
            payload_text = json.dumps(payload, ensure_ascii=True)
            payload_item = QTableWidgetItem(payload_text)

            ts_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            app_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            event_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            payload_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            self.events_table.setItem(row_idx, 0, ts_item)
            self.events_table.setItem(row_idx, 1, app_item)
            self.events_table.setItem(row_idx, 2, event_item)
            self.events_table.setItem(row_idx, 3, payload_item)

        self.events_table.resizeColumnsToContents()
