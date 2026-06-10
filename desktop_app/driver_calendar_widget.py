"""
Driver Calendar Widget
Monthly calendar with drill-down: charters per day, vehicle/driver assignment,
yard depart time, pickup time,
customer info, customer notes,
dispatch-only notes. Includes buttons to print charter documentation and open a
simple driver entry form (times, odometer, fuel receipts, floats, HOS).

Note: This implementation reads common columns if present and safely skips
missing ones using information_schema.
It does not alter database schema. Driver entry form currently saves to JSON
under reports/driver_logs_submissions/.
"""

import json
import logging
import os
from datetime import datetime
from glob import glob

from db_error_handling import DatabaseContext
from psycopg2 import sql
from psycopg2.errors import UndefinedTable
from PyQt6.QtCore import QDate, QLocale, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCalendarWidget,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

DEPART_YARD_LABEL = "Depart Yard"
NO_DRIVER_LOG_MESSAGE = "⏳ No driver log submitted yet"
DRIVER_ASSIGNED_CONDITION = "c.employee_id IS NOT NULL"


class DriverCalendarWidget(QWidget):
    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self._charter_columns = None
        self._init_ui()
        self._ensure_submission_dir()
        self.load_day_events(QDate.currentDate())

    def _driver_logs_table_exists(self) -> bool:
        """Check if the driver logs table exists in the current database."""
        return bool(self._get_columns("charter_driver_logs"))

    def _format_driver_log_from_backup(self, backup: dict) -> str:
        """Build display text for a JSON-backed driver log."""
        driver_log_text = "✅ Driver Log Found (JSON backup)\n"
        driver_log_text += "\nTimes:\n"
        driver_log_text += (
            f"  {DEPART_YARD_LABEL}: {backup.get('depart_yard') or 'N/A'}\n"
        )
        driver_log_text += (
            f"  Pickup Time: {backup.get('pickup_time') or 'N/A'}\n"
        )
        driver_log_text += "\nOdometer:\n"
        driver_log_text += (
            "  Start: " f"{backup.get('start_odometer') or 'N/A'} km\n"
        )
        driver_log_text += f"  End: {backup.get('end_odometer') or 'N/A'} km\n"
        driver_log_text += "\nFuel & Float:\n"
        driver_log_text += f"  Fuel: {backup.get('fuel_liters') or 'N/A'} L\n"
        driver_log_text += (
            "  Float Used: "
            f"${float(backup.get('float_amount') or 0):.2f}\n"
        )
        hos_notes = backup.get("hos_notes")
        driver_notes = backup.get("driver_notes")
        if hos_notes:
            driver_log_text += f"\nHOS Notes:\n{hos_notes}\n"
        if driver_notes:
            driver_log_text += f"\nDriver Notes:\n{driver_notes}\n"
        return driver_log_text

    def _format_driver_log_from_row(self, row: tuple) -> str:
        """Build display text for a DB-backed driver log row."""
        (
            depart_time,
            pickup_time,
            start_odo,
            end_odo,
            fuel_liters,
            fuel_amt,
            float_amt,
            hos_notes,
            driver_notes,
            submitted_at,
        ) = row

        driver_log_text = f"✅ Driver Log Found (Submitted: {submitted_at})\n"
        driver_log_text += "\nTimes:\n"
        driver_log_text += f"  {DEPART_YARD_LABEL}: {depart_time or 'N/A'}\n"
        driver_log_text += f"  Pickup Time: {pickup_time or 'N/A'}\n"
        driver_log_text += "\nOdometer:\n"
        driver_log_text += f"  Start: {start_odo or 'N/A'} km\n"
        driver_log_text += f"  End: {end_odo or 'N/A'} km\n"
        if start_odo and end_odo:
            distance = end_odo - start_odo
            driver_log_text += f"  Distance: {distance} km\n"
        driver_log_text += "\nFuel & Float:\n"
        driver_log_text += f"  Fuel: {fuel_liters or 'N/A'}  L @ ${fuel_amt or 0:.2f}\n"
        driver_log_text += f"  Float Used: ${float_amt or 0:.2f}\n"
        if hos_notes:
            driver_log_text += f"\nHOS Notes:\n{hos_notes}\n"
        if driver_notes:
            driver_log_text += f"\nDriver Notes:\n{driver_notes}\n"
        return driver_log_text

    def _load_latest_driver_log_json(self, reserve_number: str) -> object:
        """Load latest JSON backup for a reserve number if available."""
        pattern = os.path.join(
            self.submission_dir, f"driver_log_{reserve_number}_*.json"
        )
        files = sorted(glob(pattern), reverse=True)
        for path in files:
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
        return None

    def _ensure_submission_dir(self) -> None:
        try:
            base = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "reports",
                "driver_logs_submissions",
            )
            os.makedirs(base, exist_ok=True)
            self.submission_dir = base
        except Exception:
            self.submission_dir = os.path.join(
                os.getcwd(), "driver_logs_submissions"
            )
            os.makedirs(self.submission_dir, exist_ok=True)

    def _init_ui(self) -> None:
        layout = QVBoxLayout()

        # Header with title and filters
        header_layout = QHBoxLayout()
        title = QLabel("🗓️ Driver Calendar")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Filter checkboxes
        filter_label = QLabel("Show:")
        filter_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(filter_label)

        from PyQt6.QtWidgets import QCheckBox

        self.filter_my_charters = QCheckBox("My Charters Only")
        self.filter_my_charters.setChecked(False)
        self.filter_my_charters.toggled.connect(
            lambda: self.load_day_events(self.calendar.selectedDate())
        )
        header_layout.addWidget(self.filter_my_charters)

        self.filter_unassigned = QCheckBox("Unassigned")
        self.filter_unassigned.setChecked(True)
        self.filter_unassigned.toggled.connect(
            lambda: self.load_day_events(self.calendar.selectedDate())
        )
        header_layout.addWidget(self.filter_unassigned)

        self.filter_all = QCheckBox("All Drivers")
        self.filter_all.setChecked(True)
        self.filter_all.toggled.connect(
            lambda: self.load_day_events(self.calendar.selectedDate())
        )
        header_layout.addWidget(self.filter_all)

        layout.addLayout(header_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: month calendar
        left = QWidget()
        left_layout = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self._on_date_changed)
        left_layout.addWidget(self.calendar)
        left.setLayout(left_layout)
        splitter.addWidget(left)

        # Right: day details
        right = QWidget()
        right_layout = QVBoxLayout()

        # Day summary table
        self.day_table = QTableWidget()
        self.day_table.setColumnCount(10)
        self.day_table.setHorizontalHeaderLabels(
            [
                "Reserve #",
                "Charter ID",
                "Client",
                "Pickup",
                "Do Time",
                "Span",
                "Depart Yard",
                "Vehicle",
                "Driver",
                "Status",
            ]
        )
        self.day_table.itemSelectionChanged.connect(
            self._load_selected_charter
        )
        right_layout.addWidget(self.day_table)

        # Charter details + actions
        box = QGroupBox("Charter Details")
        form = QFormLayout()
        self.detail_reserve = QLineEdit()
        self.detail_reserve.setReadOnly(True)
        self.detail_charter_id = QLineEdit()
        self.detail_charter_id.setReadOnly(True)
        self.detail_pickup_time = QLineEdit()
        self.detail_pickup_time.setReadOnly(True)
        self.detail_depart_yard = QLineEdit()
        self.detail_depart_yard.setReadOnly(True)
        self.detail_vehicle = QLineEdit()
        self.detail_vehicle.setReadOnly(True)
        self.detail_driver = QLineEdit()
        self.detail_driver.setReadOnly(True)
        self.detail_customer = QLineEdit()
        self.detail_customer.setReadOnly(True)
        self.detail_customer_notes = QTextEdit()
        self.detail_customer_notes.setReadOnly(True)
        self.detail_dispatch_notes = QTextEdit()
        self.detail_dispatch_notes.setReadOnly(True)
        form.addRow("Reserve #", self.detail_reserve)
        form.addRow("Charter ID", self.detail_charter_id)
        form.addRow("Pickup Time", self.detail_pickup_time)
        form.addRow(DEPART_YARD_LABEL, self.detail_depart_yard)
        form.addRow("Vehicle", self.detail_vehicle)
        form.addRow("Driver", self.detail_driver)
        form.addRow("Customer", self.detail_customer)
        form.addRow("Customer Notes", self.detail_customer_notes)
        form.addRow("Dispatch Notes", self.detail_dispatch_notes)

        action_layout = QHBoxLayout()
        self.print_btn = QPushButton("🖨️ Print Charter")
        self.print_btn.clicked.connect(self._print_charter)
        self.driver_form_btn = QPushButton("✍️ Driver Entry Form")
        self.driver_form_btn.clicked.connect(self._open_driver_form)
        action_layout.addWidget(self.print_btn)
        action_layout.addWidget(self.driver_form_btn)
        form.addRow(action_layout)

        box.setLayout(form)
        right_layout.addWidget(box)

        right.setLayout(right_layout)
        splitter.addWidget(right)

        splitter.setSizes([400, 600])
        layout.addWidget(splitter)
        self.setLayout(layout)

    def _on_date_changed(self) -> None:
        self.load_day_events(self.calendar.selectedDate())

    def _resolve_do_time_expr(self) -> str:
        """Resolve the SQL expression used for Do Time based on schema."""
        if "do_time" in self._charter_columns:
            return "COALESCE(c.do_time, c.dropoff_time)"
        if "dropoff_time" in self._charter_columns:
            return "c.dropoff_time"
        return "NULL::time"

    def _build_day_where_clause(self, date_py) -> object:
        """Build WHERE clause and parameters for day event query."""
        where_conditions = ["c.charter_date = %s"]
        where_params = [date_py]

        restrict_to_assigned = (
            (
                hasattr(self, "filter_my_charters")
                and self.filter_my_charters.isChecked()
            )
            or (
                hasattr(self, "filter_unassigned")
                and not self.filter_unassigned.isChecked()
            )
            or (
                hasattr(self, "filter_all")
                and not self.filter_all.isChecked()
            )
        )
        if restrict_to_assigned:
            where_conditions.append(DRIVER_ASSIGNED_CONDITION)

        # Always exclude cancelled/no-show
        where_conditions.append(
            "(c.status IS NULL OR c.status NOT IN ('cancelled','no-show'))"
        )
        return " AND ".join(where_conditions), where_params

    def _fetch_day_events(self, qdate: QDate) -> object:
        """Fetch day events from database for the selected calendar date."""
        date_py = qdate.toPyDate()
        where_clause, where_params = self._build_day_where_clause(date_py)
        do_time_expr = self._resolve_do_time_expr()

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                f"""
                SELECT c.charter_id,
                       c.reserve_number,
                       COALESCE(c.client_display_name, '') AS client,
                       c.pickup_time,
                       {do_time_expr} AS do_time,
                       NULL::time AS depart_yard_time,
                       COALESCE(v.vehicle_number, c.vehicle, '') AS vehicle_number,
                       COALESCE(e.full_name, c.driver, '') AS driver_name,
                       c.status
                FROM charters c
                LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
                LEFT JOIN employees e ON c.employee_id = e.employee_id
                WHERE {where_clause}
                ORDER BY c.pickup_time NULLS LAST
                """,
                where_params,
            )
            return cur.fetchall()

    def _populate_day_table(self, rows) -> None:
        """Populate the day summary grid from query rows."""
        col_names = [
            "charter_id",
            "reserve_number",
            "client",
            "pickup_time",
            "do_time",
            "depart_yard_time",
            "vehicle_number",
            "driver_name",
            "status",
        ]
        self.day_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            data = dict(zip(col_names, row))
            reserve = str(data.get("reserve_number") or "")
            charter_id = str(data.get("charter_id") or "")
            client = str(data.get("client") or "")
            pickup = str(data.get("pickup_time") or "")
            do_time = str(data.get("do_time") or "")
            span = f"{pickup} -> {do_time}" if pickup and do_time else ""
            depart = str(data.get("depart_yard_time") or "")
            vehicle = str(data.get("vehicle_number") or "")
            driver = str(data.get("driver_name") or "")
            status = str(data.get("status") or "")
            items = [
                QTableWidgetItem(reserve),  # 0: Reserve #
                QTableWidgetItem(charter_id),  # 1: Charter ID
                QTableWidgetItem(client),  # 2: Client
                QTableWidgetItem(pickup),  # 3: Pickup
                QTableWidgetItem(do_time),  # 4: Do Time
                QTableWidgetItem(span),  # 5: Span
                QTableWidgetItem(depart),  # 6: Depart Yard
                QTableWidgetItem(vehicle),  # 7: Vehicle
                QTableWidgetItem(driver),  # 8: Driver
                QTableWidgetItem(status),  # 9: Status
            ]
            for c, it in enumerate(items):
                self.day_table.setItem(r, c, it)

    def _get_columns(self, table_name) -> object:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name=%s
                    """,
                    (table_name,),
                )
                cols = {r[0] for r in cur.fetchall()}
                return cols
        except Exception as e:
            logger.error(f"Failed to get columns for {table_name}: {e}")
            return set()

    def load_day_events(self, qdate: QDate) -> None:
        try:
            if self._charter_columns is None:
                self._charter_columns = self._get_columns("charters")
            rows = self._fetch_day_events(qdate)
            self._populate_day_table(rows)
        except Exception as e:
            logger.error(f"Failed to load day events: {e}")
            QMessageBox.warning(
                self, "Load Error", f"Failed to load day events: {e}"
            )

    def _lookup_vehicle(self, vcols, vehicle_id) -> object:
        if not vehicle_id or "vehicle_id" not in vcols:
            return ""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT vehicle_number FROM vehicles WHERE vehicle_id=%s "
                    "LIMIT 1",
                    (vehicle_id,),
                )
                r = cur.fetchone()
                if not r:
                    return ""
                parts = [str(x) for x in r if x]
                return " / ".join(parts)
        except Exception as e:
            logger.error(f"Failed to lookup vehicle {vehicle_id}: {e}")
            return ""

    def _lookup_driver(self, ecols, employee_id) -> object:
        if not employee_id or "employee_id" not in ecols:
            return ""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                allowed_driver_cols = ["full_name", "phone_number"]
                selected_cols = [c for c in allowed_driver_cols if c in ecols]
                if not selected_cols:
                    selected_cols = ["full_name"]
                select_clause = sql.SQL(", ").join(
                    sql.Identifier(c) for c in selected_cols
                )
                cur.execute(
                    sql.SQL(
                        "SELECT {} FROM employees WHERE employee_id=%s LIMIT 1"
                    ).format(select_clause),
                    (employee_id,),
                )
                r = cur.fetchone()
                if not r:
                    return ""
                parts = [str(x) for x in r if x]
                return " / ".join(parts)
        except Exception as e:
            logger.error(f"Failed to lookup driver {employee_id}: {e}")
            return ""

    def _load_selected_charter(self) -> None:
        items = self.day_table.selectedItems()
        if not items:
            return
        row = self.day_table.row(items[0])
        reserve = self.day_table.item(row, 0).text()
        charter_id = self.day_table.item(row, 1).text()
        self.detail_reserve.setText(reserve)
        self.detail_charter_id.setText(charter_id)
        # Fill the rest from table directly
        self.detail_customer.setText(
            self.day_table.item(row, 2).text()
        )  # Client
        self.detail_pickup_time.setText(self.day_table.item(row, 3).text())
        self.detail_depart_yard.setText(self.day_table.item(row, 6).text())
        self.detail_vehicle.setText(self.day_table.item(row, 7).text())
        self.detail_driver.setText(self.day_table.item(row, 8).text())
        # Load notes if available
        try:
            ccols = self._get_columns("charters")
            if {"customer_notes", "dispatch_notes"} & ccols:
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    allowed_note_fields = ["customer_notes", "dispatch_notes"]
                    fields = [f for f in allowed_note_fields if f in ccols]
                    select_clause = sql.SQL(", ").join(
                        sql.Identifier(f) for f in fields
                    )
                    cur.execute(
                        sql.SQL(
                            "SELECT {} FROM charters WHERE reserve_number=%s "
                            "LIMIT 1"
                        ).format(select_clause),
                        (reserve,),
                    )
                    r = cur.fetchone()
                    vals = dict(zip(fields, r)) if r else {}
                    self.detail_customer_notes.setPlainText(
                        str(vals.get("customer_notes") or "")
                    )
                    self.detail_dispatch_notes.setPlainText(
                        str(vals.get("dispatch_notes") or "")
                    )
        except Exception as e:
            logger.error(f"Failed to load charter notes: {e}")

        # Load driver logs if available
        self._load_and_display_driver_logs(reserve)

    def _load_and_display_driver_logs(self, reserve_number: str) -> None:
        """Load and display driver logs for the selected charter"""
        if not self._driver_logs_table_exists():
            backup = self._load_latest_driver_log_json(reserve_number)
            if backup:
                self.detail_dispatch_notes.setPlainText(
                    self._format_driver_log_from_backup(backup)
                )
            else:
                self.detail_dispatch_notes.setPlainText(NO_DRIVER_LOG_MESSAGE)
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT depart_time, pickup_time, start_odometer,
                    end_odometer,
                           fuel_liters, fuel_amount, float_amount, hos_notes,
                           driver_notes, submitted_at
                    FROM charter_driver_logs
                    WHERE reserve_number = %s
                    ORDER BY submitted_at DESC
                    LIMIT 1
                """,
                    (reserve_number,),
                )

                row = cur.fetchone()
            if row:
                self.detail_dispatch_notes.setPlainText(
                    self._format_driver_log_from_row(row)
                )
            else:
                # No driver logs yet
                self.detail_dispatch_notes.setPlainText(NO_DRIVER_LOG_MESSAGE)

        except UndefinedTable:
            # Avoid showing raw SQL errors to end users.
            self.detail_dispatch_notes.setPlainText(NO_DRIVER_LOG_MESSAGE)
        except Exception as e:
            logger.error(
                f"Could not load driver logs for {reserve_number}: {e}"
            )
            self.detail_dispatch_notes.setPlainText(
                "⏳ Driver logs unavailable right now"
            )

    def _print_charter(self) -> None:
        reserve = self.detail_reserve.text().strip()
        if not reserve:
            QMessageBox.information(self, "Print", "Select a charter first")
            return
        # Placeholder: emit JSON for now; integrate PDF generator later
        out = {
            "reserve_number": reserve,
            "charter_id": self.detail_charter_id.text(),
            "vehicle": self.detail_vehicle.text(),
            "driver": self.detail_driver.text(),
            "pickup_time": self.detail_pickup_time.text(),
            "depart_yard": self.detail_depart_yard.text(),
            "customer": self.detail_customer.text(),
            "notes": {
                "customer": self.detail_customer_notes.toPlainText(),
                "dispatch": self.detail_dispatch_notes.toPlainText(),
            },
        }
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(
            self.submission_dir, f"charter_print_{reserve}_{ts}.json"
        )
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
            QMessageBox.information(
                self, "Print", f"Saved charter doc to {path}"
            )
        except Exception as e:
            QMessageBox.warning(self, "Print", f"Failed to save: {e}")

    def _open_driver_form(self) -> None:
        reserve = self.detail_reserve.text().strip()
        if not reserve:
            QMessageBox.information(
                self, "Driver Form", "Select a charter first"
            )
            return
        dlg = DriverEntryDialog(reserve, self.submission_dir, self.db, self)
        dlg.exec()


class DriverEntryDialog(QDialog):
    def __init__(
        self, reserve_number: str, submission_dir: str, db=None, parent=None
    ) -> None:
        super().__init__(parent)
        self.reserve_number = reserve_number
        self.submission_dir = submission_dir
        self.db = db
        self.setWindowTitle(f"Driver Entry - {reserve_number}")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QFormLayout(self)
        self.depart_time = QTimeEdit()
        self.depart_time.setLocale(QLocale(QLocale.Language.English,
                                           QLocale.Country.UnitedKingdom))
        self.depart_time.setDisplayFormat("HH:mm")
        self.depart_time.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.depart_time.setReadOnly(False)
        self.pickup_time = QTimeEdit()
        self.pickup_time.setLocale(QLocale(QLocale.Language.English,
                                           QLocale.Country.UnitedKingdom))
        self.pickup_time.setDisplayFormat("HH:mm")
        self.pickup_time.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.pickup_time.setReadOnly(False)
        self.start_odometer = QSpinBox()
        self.start_odometer.setMaximum(9999999)
        self.end_odometer = QSpinBox()
        self.end_odometer.setMaximum(9999999)
        self.fuel_liters = QSpinBox()
        self.fuel_liters.setMaximum(2000)
        self.fuel_amount = QSpinBox()
        self.fuel_amount.setMaximum(100000)
        self.float_amount = QSpinBox()
        self.float_amount.setMaximum(100000)
        self.hos_notes = QTextEdit()
        self.driver_notes = QTextEdit()

        # Add HOS warning label
        from PyQt6.QtWidgets import QLabel

        self.hos_warning = QLabel(
            "⏰ HOS Regulations: Max 14 hrs driving, 11 hrs on duty per day"
        )
        self.hos_warning.setStyleSheet("color: #FF8C00; font-weight: bold;")

        layout.addRow(DEPART_YARD_LABEL, self.depart_time)
        layout.addRow("Pickup Time", self.pickup_time)
        layout.addRow("", self.hos_warning)
        layout.addRow("Start Odometer", self.start_odometer)
        layout.addRow("End Odometer", self.end_odometer)
        layout.addRow("Fuel Liters", self.fuel_liters)
        layout.addRow("Fuel Amount", self.fuel_amount)
        layout.addRow("Float Used", self.float_amount)
        layout.addRow("HOS Notes", self.hos_notes)
        layout.addRow("Driver Notes", self.driver_notes)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _driver_logs_table_exists(self) -> bool:
        """Check if the driver logs table exists in the current database."""
        if not self.db:
            return False
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema='public'
                      AND table_name='charter_driver_logs'
                    LIMIT 1
                    """
                )
                return bool(cur.fetchone())
        except Exception:
            return False

    @staticmethod
    def _time_or_none(time_edit: QTimeEdit) -> object:
        time_value = time_edit.time()
        if time_value.hour() > 0 or time_value.minute() > 0:
            return time_value.isoformat()
        return None

    @staticmethod
    def _spin_int_or_none(spin: QSpinBox) -> object:
        return spin.value() if spin.value() > 0 else None

    @staticmethod
    def _spin_float_or_none(spin: QSpinBox) -> object:
        return float(spin.value()) if spin.value() > 0 else None

    def _build_payload(self, hos_warnings: str) -> dict:
        """Build driver entry payload to store in DB/JSON."""
        return {
            "reserve_number": self.reserve_number,
            "depart_yard": self.depart_time.text(),
            "pickup_time": self.pickup_time.text(),
            "start_odometer": self.start_odometer.value(),
            "end_odometer": self.end_odometer.value(),
            "fuel_liters": self.fuel_liters.value(),
            "fuel_amount": self.fuel_amount.value(),
            "float_amount": self.float_amount.value(),
            "hos_notes": self.hos_notes.toPlainText(),
            "driver_notes": self.driver_notes.toPlainText(),
            "submitted_at": datetime.now().isoformat(),
            "hos_warnings": hos_warnings,
        }

    def _save_payload_to_db(self, payload: dict) -> bool:
        """Save payload to DB if available; returns True when DB save succeeds."""
        if not self.db:
            return False
        try:
            if not self._driver_logs_table_exists():
                raise UndefinedTable("charter_driver_logs does not exist")
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO charter_driver_logs (
                        reserve_number, depart_time, pickup_time,
                        start_odometer, end_odometer, fuel_liters,
                        fuel_amount, float_amount, hos_notes, driver_notes,
                        json_backup
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (reserve_number, submitted_at) DO UPDATE SET
                        depart_time = EXCLUDED.depart_time,
                        pickup_time = EXCLUDED.pickup_time,
                        start_odometer = EXCLUDED.start_odometer,
                        end_odometer = EXCLUDED.end_odometer,
                        fuel_liters = EXCLUDED.fuel_liters,
                        fuel_amount = EXCLUDED.fuel_amount,
                        float_amount = EXCLUDED.float_amount,
                        hos_notes = EXCLUDED.hos_notes,
                        driver_notes = EXCLUDED.driver_notes,
                        json_backup = EXCLUDED.json_backup,
                        updated_at = NOW()
                    """,
                    (
                        self.reserve_number,
                        self._time_or_none(self.depart_time),
                        self._time_or_none(self.pickup_time),
                        self._spin_int_or_none(self.start_odometer),
                        self._spin_int_or_none(self.end_odometer),
                        self._spin_int_or_none(self.fuel_liters),
                        self._spin_float_or_none(self.fuel_amount),
                        self._spin_float_or_none(self.float_amount),
                        self.hos_notes.toPlainText() or None,
                        self.driver_notes.toPlainText() or None,
                        json.dumps(payload),
                    ),
                )
            return True
        except UndefinedTable:
            logger.warning(
                "charter_driver_logs table missing; saving JSON backup only"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to save driver entry to database: {e}")
            QMessageBox.warning(
                self,
                "Database Error",
                f"Failed to save to database:\n\n{e!s}\n\nWill save to JSON only.",
            )
            return False

    def _save_payload_to_json(self, payload: dict, ts: str) -> str:
        """Save payload JSON backup and return saved file path."""
        path = os.path.join(
            self.submission_dir, f"driver_log_{self.reserve_number}_{ts}.json"
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return path

    def _show_save_success(self, db_saved: bool, path: str) -> None:
        """Show success message after save operations complete."""
        if db_saved:
            QMessageBox.information(
                self,
                "Saved",
                "✅ Driver entry saved to database and JSON backup",
            )
        else:
            QMessageBox.information(
                self, "Saved", f"Driver entry saved to {path}"
            )

    def _save(self) -> None:
        # Calculate HOS (Hours of Service) and warn if violations
        depart_time = self.depart_time.time()
        pickup_time = self.pickup_time.time()

        hos_warnings = self._validate_hos(depart_time, pickup_time)

        if hos_warnings:
            reply = QMessageBox.warning(
                self,
                "HOS Violation Warning",
                f"Hours of Service violations"
                f"detected:\n\n{hos_warnings}\n\nContinue saving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        payload = self._build_payload(hos_warnings)
        db_saved = self._save_payload_to_db(payload)

        try:
            path = self._save_payload_to_json(payload, ts)
            self._show_save_success(db_saved, path)
            self.accept()
        except Exception as e:
            QMessageBox.warning(
                self, "Error", f"Failed to save JSON backup: {e}"
            )

    def _validate_hos(self, depart_time, pickup_time) -> object:
        """
        Validate Hours of Service (HOS) regulations.
        Returns warning string if violations detected, empty string if OK.

        HOS Regulations (Canadian/Alberta):
        - Max 14 hours on duty per day (includes driving + other work)
        - Max 11 hours continuous driving per day
        - Minimum 8 hours off-duty between shifts
        """
        warnings = []

        # Calculate hours between depart and pickup
        if depart_time.hour() > 0 or depart_time.minute() > 0:
            if pickup_time.hour() > 0 or pickup_time.minute() > 0:
                # Calculate time difference
                depart_minutes = depart_time.hour() * 60 + depart_time.minute()
                pickup_minutes = pickup_time.hour() * 60 + pickup_time.minute()

                # Handle day boundary (e.g., 22:00 to 06:00 next day)
                if pickup_minutes < depart_minutes:
                    pickup_minutes += 24 * 60

                hours_worked = (pickup_minutes - depart_minutes) / 60.0

                if hours_worked > 14:
                    warnings.append(
                        f"⚠️ On-duty time: {hours_worked:.1f} hours (max 14"
                        f"allowed)"
                    )

                if hours_worked > 11:
                    warnings.append(
                        f"⚠️ Driving time: {hours_worked:.1f} hours (max 11"
                        f"continuous allowed)"
                    )

        return "\n".join(warnings) if warnings else ""
