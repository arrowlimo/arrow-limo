import logging

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from db_error_handling import DatabaseContext

logger = logging.getLogger(__name__)


class DuplicateRecordDialog(QDialog):
    """Generic dialog for duplicating a record."""

    def __init__(self, record_type, record_data, parent=None) -> None:
        super().__init__(parent)
        self.record_type = record_type
        self.record_data = record_data
        self.new_identifier = None

        self.setWindowTitle(f"Duplicate {record_type}")
        self.setGeometry(100, 100, 500, 200)

        layout = QVBoxLayout()

        title = QLabel(f"Duplicate {record_type} Record")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)

        info = QLabel(
            f"Enter a new name or identifier for the duplicate"
            f"{record_type.lower()} record:"
        )
        layout.addWidget(info)

        form = QFormLayout()
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText(
            f"New {record_type.lower()} name..."
        )
        form.addRow(f"New {record_type.lower()} name:", self.identifier_input)
        layout.addLayout(form)

        button_layout = QHBoxLayout()
        ok_btn = QPushButton("✓ Duplicate")
        ok_btn.clicked.connect(self.accept_duplicate)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def accept_duplicate(self) -> None:
        new_name = self.identifier_input.text().strip()
        if not new_name:
            QMessageBox.warning(
                self,
                "Warning",
                "Please enter a name for the duplicate record.",
            )
            return

        self.new_identifier = new_name
        self.accept()


class RoutingStopDialog(QDialog):
    """Dialog for adding or editing a single routing stop."""

    def __init__(self, parent=None, stop_data=None) -> None:
        super().__init__(parent)
        self.stop_data = stop_data or {}
        self.setWindowTitle("Add/Edit Routing Stop")
        self.setMinimumWidth(500)
        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QFormLayout()

        self.stop_type = QComboBox()
        self.stop_type.addItems(
            [
                "PICKUP AT",
                "DROP OFF AT",
                "LEAVE RED DEER FOR",
                "DROP OFF FOR SPLIT RUN AT",
                "PICK UP AT",
                "RETURN TO RED DEER AT",
                "EXTRA TIME ADDED",
                "WAYPOINT / STOP",
            ]
        )
        if "type" in self.stop_data:
            self.stop_type.setCurrentText(self.stop_data["type"])
        layout.addRow("Stop Type:", self.stop_type)

        self.location = QLineEdit()
        self.location.setPlaceholderText("Enter address or location name")
        if "location" in self.stop_data:
            self.location.setText(self.stop_data["location"])
        layout.addRow("Details:", self.location)

        self.time = QLineEdit()
        self.time.setPlaceholderText("HH:MM (e.g. 14:30)")
        if "time" in self.stop_data:
            self.time.setText(self.stop_data["time"])
        layout.addRow("Time:", self.time)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setPlaceholderText(
            "Driver notes, special instructions, gate codes, etc."
        )
        if "notes" in self.stop_data:
            self.notes.setPlainText(self.stop_data["notes"])
        layout.addRow("Driver Notes:", self.notes)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setLayout(layout)

    def validate_and_accept(self) -> None:
        if not self.location.text().strip():
            QMessageBox.warning(
                self, "Validation Error", "Location is required."
            )
            return

        self.accept()

    def get_stop_data(self) -> dict:
        return {
            "type": self.stop_type.currentText(),
            "location": self.location.text().strip(),
            "time": self.time.text().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


class PreRunChecklistDialog(QDialog):
    """Checklist popup shown for Booked charters within 48 hours of departure."""

    ITEMS = [
        ("driver_confirmed", "Driver confirmed"),
        ("vehicle_confirmed", "Vehicle confirmed"),
        ("client_contacted", "Client contacted"),
        ("deposit_received", "Deposit / payment received"),
    ]

    def __init__(self, db, charter_id: int, reserve_number: str = "", parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.charter_id = charter_id
        self.reserve_number = reserve_number
        self.setWindowTitle(f"Pre-Run Checklist — {reserve_number}")
        self.setMinimumWidth(360)
        self._ensure_table()
        self._setup_ui()
        self._load_state()

    def _ensure_table(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS charter_checklists (
                        charter_id        INTEGER PRIMARY KEY,
                        driver_confirmed  BOOLEAN DEFAULT FALSE,
                        vehicle_confirmed BOOLEAN DEFAULT FALSE,
                        client_contacted  BOOLEAN DEFAULT FALSE,
                        deposit_received  BOOLEAN DEFAULT FALSE,
                        updated_at        TIMESTAMP DEFAULT NOW()
                    )
                    """
                )
        except Exception as e:
            logger.error(f"charter_checklists create failed: {e}")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        header = QLabel(f"<b>Pre-run checklist for {self.reserve_number}</b>")
        layout.addWidget(header)
        layout.addWidget(QLabel("Confirm all items before the run departs:"))

        self._checks: dict = {}
        for key, label in self.ITEMS:
            cb = QCheckBox(label)
            self._checks[key] = cb
            layout.addWidget(cb)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Close
        )
        btn_box.accepted.connect(self._save_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_state(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT driver_confirmed, vehicle_confirmed, client_contacted, deposit_received "
                    "FROM charter_checklists WHERE charter_id=%s",
                    (self.charter_id,),
                )
                row = cur.fetchone()
                if row:
                    keys = [k for k, _ in self.ITEMS]
                    for key, val in zip(keys, row):
                        if key in self._checks:
                            self._checks[key].setChecked(bool(val))
        except Exception as _e:
            logger.debug("Suppressed: %s", _e)

    def _save_and_accept(self) -> None:
        vals = {k: self._checks[k].isChecked() for k, _ in self.ITEMS}
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO charter_checklists
                        (charter_id, driver_confirmed, vehicle_confirmed, client_contacted, deposit_received, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (charter_id) DO UPDATE SET
                        driver_confirmed  = EXCLUDED.driver_confirmed,
                        vehicle_confirmed = EXCLUDED.vehicle_confirmed,
                        client_contacted  = EXCLUDED.client_contacted,
                        deposit_received  = EXCLUDED.deposit_received,
                        updated_at        = NOW()
                    """,
                    (
                        self.charter_id,
                        vals["driver_confirmed"],
                        vals["vehicle_confirmed"],
                        vals["client_contacted"],
                        vals["deposit_received"],
                    ),
                )
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))
        self.accept()
