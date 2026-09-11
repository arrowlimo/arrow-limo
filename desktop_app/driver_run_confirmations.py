"""Dispatcher confirmation queue for driver-submitted run details.

A driver entering hours, odometer or notes in the web portal does not make
those values live. The submission is stamped on the charter and a dispatcher
must confirm it here before the run details are treated as verified.
"""

import logging

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)

COL_SELECT = 0
COLUMNS = [
    "Confirm",
    "Date",
    "Reserve #",
    "Driver",
    "Hours",
    "Odo Start",
    "Odo End",
    "Fuel (L)",
    "Status",
    "Submitted",
]


class DriverRunConfirmationsDialog(QDialog):
    """Runs where a driver submitted details that nobody has verified yet."""

    confirmed = pyqtSignal()

    def __init__(self, db, auth_user=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._dispatcher = (
            auth_user.get("username", "dispatcher") if auth_user else "dispatcher"
        )
        self._rows = []

        self.setWindowTitle("Confirm Driver-Submitted Run Details")
        self.resize(1150, 600)
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()

        header = QLabel("🚦 Driver-Submitted Run Details Awaiting Dispatcher Confirmation")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(COL_SELECT, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_SELECT, 70)
        for column in range(1, len(COLUMNS)):
            header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        select_all = QPushButton("☑️ Select All")
        select_all.clicked.connect(lambda: self._set_all_checked(True))
        buttons.addWidget(select_all)

        select_none = QPushButton("☐ Select None")
        select_none.clicked.connect(lambda: self._set_all_checked(False))
        buttons.addWidget(select_none)

        buttons.addStretch()

        self.confirm_selected_btn = QPushButton("✅ Confirm Selected")
        self.confirm_selected_btn.clicked.connect(self.confirm_selected)
        buttons.addWidget(self.confirm_selected_btn)

        self.confirm_all_btn = QPushButton("✅ Confirm All")
        self.confirm_all_btn.clicked.connect(self.confirm_all)
        buttons.addWidget(self.confirm_all_btn)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh)
        buttons.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        buttons.addWidget(close_btn)

        layout.addLayout(buttons)
        self.setLayout(layout)

    def refresh(self) -> None:
        rows = []
        try:
            with DatabaseContext(self.db) as cur:
                cur.execute(
                    """
                    SELECT c.charter_id, c.charter_date, c.reserve_number,
                           COALESCE(e.first_name || ' ' || e.last_name, '') AS driver,
                           c.actual_hours, c.odometer_start, c.odometer_end,
                           c.fuel_added_liters, c.status,
                           c.driver_details_submitted_at
                    FROM charters c
                    LEFT JOIN employees e
                        ON e.employee_id = COALESCE(c.assigned_driver_id, c.employee_id)
                    WHERE c.driver_details_submitted_at IS NOT NULL
                      AND c.dispatcher_confirmed_at IS NULL
                    ORDER BY c.driver_details_submitted_at DESC
                    LIMIT 500
                    """
                )
                rows = cur.fetchall() or []
        except Exception as exc:
            logger.exception("Failed to load driver run submissions")
            self.summary_label.setText(f"⚠️ Could not load submissions: {exc}")
            return

        self._rows = rows
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            (
                _charter_id,
                charter_date,
                reserve_number,
                driver,
                actual_hours,
                odo_start,
                odo_end,
                fuel,
                status,
                submitted_at,
            ) = row

            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
            )
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row_index, COL_SELECT, checkbox_item)

            values = [
                charter_date.strftime("%Y-%m-%d") if charter_date else "",
                str(reserve_number or ""),
                driver or "(unassigned)",
                "" if actual_hours is None else f"{actual_hours:g}",
                "" if odo_start is None else f"{odo_start:g}",
                "" if odo_end is None else f"{odo_end:g}",
                "" if fuel is None else f"{fuel:g}",
                status or "",
                submitted_at.strftime("%Y-%m-%d %H:%M") if submitted_at else "",
            ]
            for offset, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if not value and offset in (4, 5, 6):
                    item.setText("missing")
                    item.setForeground(QBrush(QColor("#b91c1c")))
                self.table.setItem(row_index, offset, item)

        if rows:
            self.summary_label.setText(
                f"{len(rows)} run(s) have driver-entered details that are not yet "
                "confirmed. Confirming marks the details verified and records who "
                "confirmed them."
            )
        else:
            self.summary_label.setText(
                "✅ Every driver-submitted run detail has been confirmed."
            )
        self.confirm_selected_btn.setEnabled(bool(rows))
        self.confirm_all_btn.setEnabled(bool(rows))

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, COL_SELECT)
            if item is not None:
                item.setCheckState(state)

    def confirm_all(self) -> None:
        if self._rows:
            self._confirm(list(self._rows))

    def confirm_selected(self) -> None:
        selected = []
        for row_index, row in enumerate(self._rows):
            item = self.table.item(row_index, COL_SELECT)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(row)
        if not selected:
            QMessageBox.information(
                self,
                "Nothing Selected",
                "Tick the Confirm box on the runs you have verified.",
            )
            return
        self._confirm(selected)

    def _confirm(self, rows) -> None:
        confirm = QMessageBox.question(
            self,
            "Confirm Run Details",
            f"Mark {len(rows)} run(s) as confirmed by {self._dispatcher}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        charter_ids = [row[0] for row in rows]
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    UPDATE charters
                    SET dispatcher_confirmed_at = NOW(),
                        dispatcher_confirmed_by = %s
                    WHERE charter_id = ANY(%s)
                      AND dispatcher_confirmed_at IS NULL
                    """,
                    (self._dispatcher, charter_ids),
                )
                updated = cur.rowcount
        except Exception as exc:
            logger.exception("Failed to confirm driver run details")
            QMessageBox.critical(self, "Confirmation Failed", str(exc))
            return

        QMessageBox.information(
            self, "Confirmed", f"{updated} run(s) confirmed by {self._dispatcher}."
        )
        self.refresh()
        self.confirmed.emit()
