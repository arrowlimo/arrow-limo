"""
Employee Work Schedule Widget
Non-charter staff scheduling for dispatch (cleaners, dispatchers, office, etc.).
"""

import logging
from datetime import date

from db_error_handling import DatabaseContext
from employee_work_items import ensure_employee_work_items_table
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class EmployeeWorkScheduleWidget(QWidget):
    """Dispatch-facing scheduler for non-charter employee work."""

    ROLE_TYPES = [
        "CLEANER",
        "DISPATCHER",
        "OFFICE",
        "ADMIN",
        "MAINTENANCE",
        "WAREHOUSE",
        "OTHER",
    ]

    PAY_TYPES = ["HOURLY", "SALARY", "FIXED_JOB"]
    STATUSES = ["SCHEDULED", "COMPLETED", "CANCELLED"]
    ROLE_TO_WORK_ITEM = {
        "CLEANER": "CLEANING",
        "DISPATCHER": "OFFICE",
        "OFFICE": "OFFICE",
        "ADMIN": "OFFICE",
        "MAINTENANCE": "OTHER_WORK",
        "WAREHOUSE": "OTHER_WORK",
        "OTHER": "OTHER_WORK",
    }

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._selected_schedule_id = None
        self._selected_employee_id = None
        self._employee_lookup = {}

        self._ensure_table()
        ensure_employee_work_items_table(self.db)
        self._build_ui()
        self._load_employees()
        self._load_rows()

    def _ensure_table(self) -> None:
        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS employee_work_schedule (
                    schedule_id SERIAL PRIMARY KEY,
                    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
                    work_date DATE NOT NULL,
                    role_type VARCHAR(40) NOT NULL DEFAULT 'OTHER',
                    task_name TEXT NOT NULL DEFAULT '',
                    start_time TIME NULL,
                    end_time TIME NULL,
                    scheduled_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
                    pay_type VARCHAR(20) NOT NULL DEFAULT 'HOURLY',
                    rate_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                    status VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED',
                    notes TEXT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_employee_work_schedule_date
                ON employee_work_schedule(work_date)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_employee_work_schedule_employee
                ON employee_work_schedule(employee_id)
                """
            )
            cur.execute(
                """
                ALTER TABLE employee_work_schedule
                ADD COLUMN IF NOT EXISTS payroll_posted_work_item_id INTEGER NULL
                """
            )
            cur.execute(
                """
                ALTER TABLE employee_work_schedule
                ADD COLUMN IF NOT EXISTS payroll_posted_at TIMESTAMP NULL
                """
            )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Schedule Employee Work (Non-Charter)")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(title)

        filter_row = QHBoxLayout()
        self.filter_from = QDateEdit()
        self.filter_from.setCalendarPopup(True)
        self.filter_from.setDate(QDate.currentDate().addDays(-7))
        self.filter_to = QDateEdit()
        self.filter_to.setCalendarPopup(True)
        self.filter_to.setDate(QDate.currentDate().addDays(14))
        self.filter_employee = QComboBox()
        self.filter_employee.addItem("All Employees", None)
        self.filter_unposted_only = QCheckBox("Unposted Only")
        self.filter_completed_only = QCheckBox("Completed Only")
        self.filter_unposted_only.stateChanged.connect(lambda _s: self._load_rows())
        self.filter_completed_only.stateChanged.connect(lambda _s: self._load_rows())

        filter_apply_btn = QPushButton("Apply Filter")
        filter_apply_btn.clicked.connect(self._load_rows)
        filter_clear_btn = QPushButton("Today +/- 2 Weeks")
        filter_clear_btn.clicked.connect(self._reset_filters)

        filter_row.addWidget(QLabel("From:"))
        filter_row.addWidget(self.filter_from)
        filter_row.addWidget(QLabel("To:"))
        filter_row.addWidget(self.filter_to)
        filter_row.addWidget(QLabel("Employee:"))
        filter_row.addWidget(self.filter_employee, stretch=1)
        filter_row.addWidget(self.filter_unposted_only)
        filter_row.addWidget(self.filter_completed_only)
        filter_row.addWidget(filter_apply_btn)
        filter_row.addWidget(filter_clear_btn)
        root.addLayout(filter_row)

        summary_row = QHBoxLayout()
        self.pending_summary_label = QLabel("Pending Payroll (<= Today): 0 row(s) | $0.00")
        self.pending_summary_label.setStyleSheet("font-weight: bold; color: #92400e;")
        self.post_pending_btn = QPushButton("Post Pending Payroll (<= Today)")
        self.post_pending_btn.setToolTip(
            "Post all COMPLETED and unposted rows due through today"
            " (respects Employee filter)."
        )
        self.post_pending_btn.clicked.connect(self._post_ready_to_payroll)
        summary_row.addWidget(self.pending_summary_label)
        summary_row.addStretch(1)
        summary_row.addWidget(self.post_pending_btn)
        root.addLayout(summary_row)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.work_date = QDateEdit()
        self.work_date.setCalendarPopup(True)
        self.work_date.setDate(QDate.currentDate())

        self.employee_combo = QComboBox()

        self.role_combo = QComboBox()
        self.role_combo.addItems(self.ROLE_TYPES)

        self.task_name = QLineEdit()
        self.task_name.setPlaceholderText("Example: Office opening / inventory / calls")

        self.start_time = QLineEdit()
        self.start_time.setPlaceholderText("08:00")
        self.end_time = QLineEdit()
        self.end_time.setPlaceholderText("16:00")

        self.hours = QDoubleSpinBox()
        self.hours.setRange(0, 24)
        self.hours.setDecimals(2)
        self.hours.setSingleStep(0.25)
        self.hours.valueChanged.connect(self._refresh_estimate_preview)

        self.pay_type = QComboBox()
        self.pay_type.addItems(self.PAY_TYPES)
        self.pay_type.currentTextChanged.connect(self._refresh_estimate_preview)

        self.rate_amount = QDoubleSpinBox()
        self.rate_amount.setRange(0, 1000000)
        self.rate_amount.setDecimals(2)
        self.rate_amount.setPrefix("$")
        self.rate_amount.valueChanged.connect(self._refresh_estimate_preview)

        self.status_combo = QComboBox()
        self.status_combo.addItems(self.STATUSES)
        self.auto_post_on_save = QCheckBox("Auto-post to payroll when COMPLETED")
        self.auto_post_on_save.setChecked(True)

        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional notes for dispatch/payroll")

        self.estimate_preview = QLabel("Estimated Pay: $0.00")
        self.estimate_preview.setStyleSheet("font-weight: bold; color: #1d4ed8;")

        form.addWidget(QLabel("Date"), 0, 0)
        form.addWidget(self.work_date, 0, 1)
        form.addWidget(QLabel("Employee"), 0, 2)
        form.addWidget(self.employee_combo, 0, 3)
        form.addWidget(QLabel("Role"), 0, 4)
        form.addWidget(self.role_combo, 0, 5)

        form.addWidget(QLabel("Task"), 1, 0)
        form.addWidget(self.task_name, 1, 1, 1, 3)
        form.addWidget(QLabel("Status"), 1, 4)
        form.addWidget(self.status_combo, 1, 5)

        form.addWidget(QLabel("Start"), 2, 0)
        form.addWidget(self.start_time, 2, 1)
        form.addWidget(QLabel("End"), 2, 2)
        form.addWidget(self.end_time, 2, 3)
        form.addWidget(QLabel("Hours"), 2, 4)
        form.addWidget(self.hours, 2, 5)

        form.addWidget(QLabel("Pay Type"), 3, 0)
        form.addWidget(self.pay_type, 3, 1)
        form.addWidget(QLabel("Rate / Amount"), 3, 2)
        form.addWidget(self.rate_amount, 3, 3)
        form.addWidget(self.estimate_preview, 3, 4, 1, 2)

        form.addWidget(QLabel("Notes"), 4, 0)
        form.addWidget(self.notes, 4, 1, 1, 5)
        form.addWidget(self.auto_post_on_save, 5, 0, 1, 3)

        root.addLayout(form)

        button_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Entry")
        self.save_btn.setStyleSheet("background-color: #2563eb; color: white;")
        self.save_btn.clicked.connect(self._save_entry)

        clear_btn = QPushButton("Clear Form")
        clear_btn.clicked.connect(self._clear_form)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_selected)

        post_selected_btn = QPushButton("Post Selected To Payroll")
        post_selected_btn.setToolTip(
            "Create a non-charter payroll work-item from selected schedule row."
        )
        post_selected_btn.clicked.connect(self._post_selected_to_payroll)

        post_completed_btn = QPushButton("Post Completed (Filtered)")
        post_completed_btn.setToolTip(
            "Post all COMPLETED rows in current filter that are not posted yet."
        )
        post_completed_btn.clicked.connect(self._post_completed_filtered_to_payroll)

        post_ready_btn = QPushButton("Auto-Post Ready (<= Today)")
        post_ready_btn.setToolTip(
            "Post COMPLETED rows with work date up to today that are not posted yet."
        )
        post_ready_btn.clicked.connect(self._post_ready_to_payroll)

        post_visible_btn = QPushButton("Post Visible Rows")
        post_visible_btn.setToolTip(
            "Post all rows currently visible in the list (after filters/sorting)."
        )
        post_visible_btn.clicked.connect(self._post_visible_rows_to_payroll)

        refresh_btn = QPushButton("Refresh List")
        refresh_btn.clicked.connect(self._load_rows)

        button_row.addWidget(self.save_btn)
        button_row.addWidget(clear_btn)
        button_row.addWidget(delete_btn)
        button_row.addWidget(post_selected_btn)
        button_row.addWidget(post_completed_btn)
        button_row.addWidget(post_ready_btn)
        button_row.addWidget(post_visible_btn)
        button_row.addWidget(refresh_btn)
        button_row.addStretch(1)
        root.addLayout(button_row)

        self.table = QTableWidget()
        self.table.setColumnCount(15)
        self.table.setHorizontalHeaderLabels(
            [
                "Date",
                "Employee",
                "Role",
                "Task",
                "Start",
                "End",
                "Hours",
                "Pay Type",
                "Rate/Amount",
                "Est Pay",
                "Status",
                "Notes",
                "Posted",
                "Work-Item ID",
                "Posted At",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemDoubleClicked.connect(self._load_selected_row_to_form)
        self.table.setSortingEnabled(True)
        root.addWidget(self.table)

        totals_row = QHBoxLayout()
        self.total_hours_label = QLabel("Scheduled Hours: 0.00")
        self.total_pay_label = QLabel("Estimated Payroll: $0.00")
        self.total_hours_label.setStyleSheet("font-weight: bold;")
        self.total_pay_label.setStyleSheet("font-weight: bold;")
        totals_row.addWidget(self.total_hours_label)
        totals_row.addSpacing(20)
        totals_row.addWidget(self.total_pay_label)
        totals_row.addStretch(1)
        root.addLayout(totals_row)

        self._refresh_estimate_preview()

    def _load_employees(self) -> None:
        self.employee_combo.clear()
        self.filter_employee.clear()
        self.filter_employee.addItem("All Employees", None)
        self._employee_lookup.clear()

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        employee_id,
                        COALESCE(full_name, '') AS full_name,
                        COALESCE(employee_number::text, '') AS employee_number
                    FROM employees
                    ORDER BY full_name
                    """
                )
                rows = cur.fetchall()

            for employee_id, full_name, employee_number in rows:
                label = full_name or f"EMP_{employee_id}"
                if employee_number:
                    label = f"{label} ({employee_number})"
                self.employee_combo.addItem(label, int(employee_id))
                self.filter_employee.addItem(label, int(employee_id))
                self._employee_lookup[int(employee_id)] = label
        except Exception as exc:
            logger.error("Failed loading employees for work schedule: %s", exc)
            QMessageBox.warning(self, "Employees", f"Failed to load employees: {exc}")

    def _reset_filters(self) -> None:
        self.filter_from.setDate(QDate.currentDate().addDays(-14))
        self.filter_to.setDate(QDate.currentDate().addDays(14))
        self.filter_employee.setCurrentIndex(0)
        self.filter_unposted_only.setChecked(False)
        self.filter_completed_only.setChecked(False)
        self._load_rows()

    def _estimate_pay(self, hours: float, pay_type: str, rate_amount: float) -> float:
        t = (pay_type or "HOURLY").upper()
        if t == "HOURLY":
            return max(0.0, float(hours)) * max(0.0, float(rate_amount))
        return max(0.0, float(rate_amount))

    def _refresh_estimate_preview(self) -> None:
        est = self._estimate_pay(
            self.hours.value(),
            self.pay_type.currentText(),
            self.rate_amount.value(),
        )
        self.estimate_preview.setText(f"Estimated Pay: ${est:,.2f}")

    def _parse_time_text(self, value: str) -> str | None:
        text = (value or "").strip()
        if not text:
            return None
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError("Time must be HH:MM")
        hh = int(parts[0])
        mm = int(parts[1])
        if hh < 0 or hh > 23 or mm < 0 or mm > 59:
            raise ValueError("Time must be within 00:00 to 23:59")
        return f"{hh:02d}:{mm:02d}"

    def _save_entry(self) -> None:
        employee_id = self.employee_combo.currentData()
        if not employee_id:
            QMessageBox.warning(self, "Missing Employee", "Select an employee.")
            return

        try:
            start_time = self._parse_time_text(self.start_time.text())
            end_time = self._parse_time_text(self.end_time.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Time", str(exc))
            return

        work_date = self.work_date.date().toPyDate()
        role_type = self.role_combo.currentText().strip() or "OTHER"
        task_name = (self.task_name.text() or "").strip()
        scheduled_hours = float(self.hours.value())
        pay_type = self.pay_type.currentText().strip() or "HOURLY"
        rate_amount = float(self.rate_amount.value())
        status = self.status_combo.currentText().strip() or "SCHEDULED"
        notes = (self.notes.text() or "").strip()
        saved_schedule_id = None
        auto_post_message = ""

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                if self._selected_schedule_id:
                    saved_schedule_id = int(self._selected_schedule_id)
                    cur.execute(
                        """
                        UPDATE employee_work_schedule
                        SET
                            employee_id = %s,
                            work_date = %s,
                            role_type = %s,
                            task_name = %s,
                            start_time = %s,
                            end_time = %s,
                            scheduled_hours = %s,
                            pay_type = %s,
                            rate_amount = %s,
                            status = %s,
                            notes = %s,
                            updated_at = NOW()
                        WHERE schedule_id = %s
                        """,
                        (
                            int(employee_id),
                            work_date,
                            role_type,
                            task_name,
                            start_time,
                            end_time,
                            scheduled_hours,
                            pay_type,
                            rate_amount,
                            status,
                            notes,
                            int(self._selected_schedule_id),
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO employee_work_schedule (
                            employee_id,
                            work_date,
                            role_type,
                            task_name,
                            start_time,
                            end_time,
                            scheduled_hours,
                            pay_type,
                            rate_amount,
                            status,
                            notes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING schedule_id
                        """,
                        (
                            int(employee_id),
                            work_date,
                            role_type,
                            task_name,
                            start_time,
                            end_time,
                            scheduled_hours,
                            pay_type,
                            rate_amount,
                            status,
                            notes,
                        ),
                    )
                    saved_schedule_id = int(cur.fetchone()[0])
        except Exception as exc:
            logger.error("Failed saving work schedule: %s", exc)
            QMessageBox.critical(self, "Save Failed", f"Could not save entry: {exc}")
            return

        if (
            saved_schedule_id
            and self.auto_post_on_save.isChecked()
            and status.upper() == "COMPLETED"
        ):
            ok, msg = self._post_schedule_row_to_payroll(int(saved_schedule_id))
            if ok:
                auto_post_message = msg
            elif "Already posted" not in str(msg):
                auto_post_message = f"Auto-post skipped: {msg}"

        self._clear_form()
        self._load_rows()
        if auto_post_message:
            QMessageBox.information(self, "Payroll Posting", auto_post_message)

    def _load_rows(self) -> None:
        self._refresh_pending_summary()
        from_date = self.filter_from.date().toPyDate()
        to_date = self.filter_to.date().toPyDate()
        employee_id = self.filter_employee.currentData()

        where = ["s.work_date BETWEEN %s AND %s"]
        params = [from_date, to_date]
        if employee_id:
            where.append("s.employee_id = %s")
            params.append(int(employee_id))
        if self.filter_unposted_only.isChecked():
            where.append("s.payroll_posted_work_item_id IS NULL")
        if self.filter_completed_only.isChecked():
            where.append("COALESCE(s.status, 'SCHEDULED') = 'COMPLETED'")

        where_sql = " AND ".join(where)

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT
                        s.schedule_id,
                        s.employee_id,
                        s.work_date::date,
                        COALESCE(e.full_name, ''),
                        COALESCE(e.employee_number::text, ''),
                        COALESCE(s.role_type, ''),
                        COALESCE(s.task_name, ''),
                        TO_CHAR(s.start_time, 'HH24:MI'),
                        TO_CHAR(s.end_time, 'HH24:MI'),
                        COALESCE(s.scheduled_hours, 0),
                        COALESCE(s.pay_type, 'HOURLY'),
                        COALESCE(s.rate_amount, 0),
                        COALESCE(s.status, 'SCHEDULED'),
                        COALESCE(s.notes, ''),
                        s.payroll_posted_work_item_id,
                        TO_CHAR(s.payroll_posted_at, 'YYYY-MM-DD HH24:MI'),
                        CASE
                            WHEN UPPER(COALESCE(s.pay_type, 'HOURLY')) = 'HOURLY'
                                THEN COALESCE(s.scheduled_hours, 0) * COALESCE(s.rate_amount, 0)
                            ELSE COALESCE(s.rate_amount, 0)
                        END AS est_pay
                    FROM employee_work_schedule s
                    LEFT JOIN employees e ON s.employee_id = e.employee_id
                    WHERE {where_sql}
                    ORDER BY s.work_date DESC, s.schedule_id DESC
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()
        except Exception as exc:
            logger.error("Failed loading work schedule rows: %s", exc)
            QMessageBox.warning(self, "Load Failed", f"Could not load schedule rows: {exc}")
            return

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))

        total_hours = 0.0
        total_pay = 0.0

        for r, row in enumerate(rows):
            (
                schedule_id,
                row_employee_id,
                work_date,
                full_name,
                employee_number,
                role_type,
                task_name,
                start_time,
                end_time,
                scheduled_hours,
                pay_type,
                rate_amount,
                status,
                notes,
                posted_work_item_id,
                payroll_posted_at,
                est_pay,
            ) = row

            employee_label = full_name or f"EMP_{row_employee_id}"
            if employee_number:
                employee_label = f"{employee_label} ({employee_number})"

            date_item = QTableWidgetItem(str(work_date or ""))
            date_item.setData(Qt.ItemDataRole.UserRole, int(schedule_id))
            date_item.setData(Qt.ItemDataRole.UserRole + 1, int(row_employee_id))
            self.table.setItem(r, 0, date_item)
            self.table.setItem(r, 1, QTableWidgetItem(employee_label))
            self.table.setItem(r, 2, QTableWidgetItem(str(role_type or "")))
            self.table.setItem(r, 3, QTableWidgetItem(str(task_name or "")))
            self.table.setItem(r, 4, QTableWidgetItem(str(start_time or "")))
            self.table.setItem(r, 5, QTableWidgetItem(str(end_time or "")))
            self.table.setItem(r, 6, QTableWidgetItem(f"{float(scheduled_hours or 0):.2f}"))
            self.table.setItem(r, 7, QTableWidgetItem(str(pay_type or "")))
            self.table.setItem(r, 8, QTableWidgetItem(f"${float(rate_amount or 0):,.2f}"))
            self.table.setItem(r, 9, QTableWidgetItem(f"${float(est_pay or 0):,.2f}"))
            self.table.setItem(r, 10, QTableWidgetItem(str(status or "")))
            self.table.setItem(r, 11, QTableWidgetItem(str(notes or "")))
            posted_text = "YES" if posted_work_item_id else "NO"
            self.table.setItem(r, 12, QTableWidgetItem(posted_text))
            self.table.setItem(
                r,
                13,
                QTableWidgetItem(
                    str(int(posted_work_item_id)) if posted_work_item_id else ""
                ),
            )
            self.table.setItem(
                r,
                14,
                QTableWidgetItem(str(payroll_posted_at or "")),
            )

            total_hours += float(scheduled_hours or 0)
            total_pay += float(est_pay or 0)

        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

        self.total_hours_label.setText(f"Scheduled Hours: {total_hours:,.2f}")
        self.total_pay_label.setText(f"Estimated Payroll: ${total_pay:,.2f}")

    def _refresh_pending_summary(self) -> None:
        """Show count/value of completed, unposted rows due through today."""

        employee_id = self.filter_employee.currentData()
        where = [
            "work_date <= %s",
            "COALESCE(status, 'SCHEDULED') = 'COMPLETED'",
            "payroll_posted_work_item_id IS NULL",
        ]
        params = [date.today()]
        if employee_id:
            where.append("employee_id = %s")
            params.append(int(employee_id))

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*),
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN UPPER(COALESCE(pay_type, 'HOURLY')) = 'HOURLY'
                                        THEN COALESCE(scheduled_hours, 0) * COALESCE(rate_amount, 0)
                                    ELSE COALESCE(rate_amount, 0)
                                END
                            ),
                            0
                        )
                    FROM employee_work_schedule
                    WHERE {' AND '.join(where)}
                    """,
                    tuple(params),
                )
                row = cur.fetchone() or (0, 0)
            due_count = int(row[0] or 0)
            due_amount = float(row[1] or 0.0)
            self.pending_summary_label.setText(
                f"Pending Payroll (<= Today): {due_count} row(s) | ${due_amount:,.2f}"
            )
        except Exception as exc:
            logger.warning("Pending payroll summary refresh failed: %s", exc)
            self.pending_summary_label.setText("Pending Payroll (<= Today): unavailable")

    def _load_selected_row_to_form(self, *_args) -> None:
        row = self.table.currentRow()
        if row < 0:
            return

        date_item = self.table.item(row, 0)
        if not date_item:
            return

        schedule_id = date_item.data(Qt.ItemDataRole.UserRole)
        employee_id = date_item.data(Qt.ItemDataRole.UserRole + 1)

        date_text = (self.table.item(row, 0).text() if self.table.item(row, 0) else "").strip()
        role_type = (self.table.item(row, 2).text() if self.table.item(row, 2) else "OTHER").strip()
        task_name = (self.table.item(row, 3).text() if self.table.item(row, 3) else "").strip()
        start_time = (self.table.item(row, 4).text() if self.table.item(row, 4) else "").strip()
        end_time = (self.table.item(row, 5).text() if self.table.item(row, 5) else "").strip()
        hours_text = (self.table.item(row, 6).text() if self.table.item(row, 6) else "0").strip()
        pay_type = (self.table.item(row, 7).text() if self.table.item(row, 7) else "HOURLY").strip()
        rate_text = (self.table.item(row, 8).text() if self.table.item(row, 8) else "$0").replace("$", "").replace(",", "").strip()
        status = (self.table.item(row, 10).text() if self.table.item(row, 10) else "SCHEDULED").strip()
        notes = (self.table.item(row, 11).text() if self.table.item(row, 11) else "").strip()

        if date_text:
            parsed = QDate.fromString(date_text, "yyyy-MM-dd")
            if parsed.isValid():
                self.work_date.setDate(parsed)

        idx_emp = self.employee_combo.findData(int(employee_id)) if employee_id is not None else -1
        if idx_emp >= 0:
            self.employee_combo.setCurrentIndex(idx_emp)

        idx_role = self.role_combo.findText(role_type)
        self.role_combo.setCurrentIndex(idx_role if idx_role >= 0 else self.role_combo.findText("OTHER"))

        self.task_name.setText(task_name)
        self.start_time.setText(start_time)
        self.end_time.setText(end_time)

        try:
            self.hours.setValue(float(hours_text or 0))
        except Exception:
            self.hours.setValue(0)

        idx_pay = self.pay_type.findText(pay_type)
        self.pay_type.setCurrentIndex(idx_pay if idx_pay >= 0 else 0)

        try:
            self.rate_amount.setValue(float(rate_text or 0))
        except Exception:
            self.rate_amount.setValue(0)

        idx_status = self.status_combo.findText(status)
        self.status_combo.setCurrentIndex(idx_status if idx_status >= 0 else 0)
        self.notes.setText(notes)

        self._selected_schedule_id = int(schedule_id) if schedule_id is not None else None
        self._selected_employee_id = int(employee_id) if employee_id is not None else None
        self.save_btn.setText("Update Entry")
        self._refresh_estimate_preview()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Delete", "Select a schedule row first.")
            return

        date_item = self.table.item(row, 0)
        if not date_item:
            return

        schedule_id = date_item.data(Qt.ItemDataRole.UserRole)
        if schedule_id is None:
            return

        if (
            QMessageBox.question(
                self,
                "Delete Entry",
                "Delete selected work schedule entry?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM employee_work_schedule WHERE schedule_id = %s",
                    (int(schedule_id),),
                )
        except Exception as exc:
            logger.error("Failed deleting work schedule row: %s", exc)
            QMessageBox.critical(self, "Delete Failed", f"Could not delete row: {exc}")
            return

        self._clear_form()
        self._load_rows()

    def _clear_form(self) -> None:
        self._selected_schedule_id = None
        self._selected_employee_id = None
        self.work_date.setDate(QDate.currentDate())
        self.role_combo.setCurrentIndex(self.role_combo.findText("OTHER"))
        self.task_name.clear()
        self.start_time.clear()
        self.end_time.clear()
        self.hours.setValue(0)
        self.pay_type.setCurrentIndex(0)
        self.rate_amount.setValue(0)
        self.status_combo.setCurrentIndex(0)
        self.notes.clear()
        self.save_btn.setText("Save Entry")
        self._refresh_estimate_preview()

    def _selected_schedule_id_from_table(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        date_item = self.table.item(row, 0)
        if not date_item:
            return None
        schedule_id = date_item.data(Qt.ItemDataRole.UserRole)
        return int(schedule_id) if schedule_id is not None else None

    def _resolve_pay_period_for_date(self, work_date: date) -> tuple[int | None, int]:
        fiscal_year = int(work_date.year)
        pay_period_id = None
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT pay_period_id, fiscal_year
                    FROM pay_periods
                    WHERE period_start_date <= %s AND period_end_date >= %s
                    ORDER BY period_number
                    LIMIT 1
                    """,
                    (work_date, work_date),
                )
                row = cur.fetchone()
                if row:
                    pay_period_id = int(row[0]) if row[0] is not None else None
                    fiscal_year = int(row[1] or fiscal_year)
        except Exception as exc:
            logger.warning("Pay period resolution failed for %s: %s", work_date, exc)
        return pay_period_id, fiscal_year

    def _work_item_type_for_role(self, role_type: str) -> str:
        return self.ROLE_TO_WORK_ITEM.get((role_type or "OTHER").upper(), "OTHER_WORK")

    def _post_schedule_row_to_payroll(self, schedule_id: int) -> tuple[bool, str]:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    SELECT
                        schedule_id,
                        employee_id,
                        work_date,
                        role_type,
                        task_name,
                        scheduled_hours,
                        pay_type,
                        rate_amount,
                        status,
                        notes,
                        payroll_posted_work_item_id
                    FROM employee_work_schedule
                    WHERE schedule_id = %s
                    """,
                    (int(schedule_id),),
                )
                row = cur.fetchone()
                if not row:
                    return False, "Schedule row not found."

                (
                    _sid,
                    employee_id,
                    work_date,
                    role_type,
                    task_name,
                    scheduled_hours,
                    pay_type,
                    rate_amount,
                    status,
                    notes,
                    posted_work_item_id,
                ) = row

                if posted_work_item_id:
                    return False, "Already posted to payroll."

                if str(status or "").upper() == "CANCELLED":
                    return False, "Cancelled rows are not posted."

                hours_val = float(scheduled_hours or 0.0)
                rate_val = float(rate_amount or 0.0)
                if str(pay_type or "").upper() == "HOURLY":
                    amount_val = hours_val * rate_val
                else:
                    amount_val = rate_val

                pay_period_id, fiscal_year = self._resolve_pay_period_for_date(work_date)
                work_item_type = self._work_item_type_for_role(str(role_type or ""))
                description = (
                    f"{str(task_name or '').strip()}"
                    f" [schedule #{int(schedule_id)} | {str(role_type or 'OTHER')}]"
                ).strip()

                cur.execute(
                    """
                    INSERT INTO employee_work_items (
                        employee_id,
                        pay_period_id,
                        fiscal_year,
                        work_date,
                        item_type,
                        description,
                        hours,
                        rate,
                        amount,
                        receipt_ref,
                        status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING work_item_id
                    """,
                    (
                        int(employee_id),
                        int(pay_period_id) if pay_period_id else None,
                        int(fiscal_year),
                        work_date,
                        work_item_type,
                        description,
                        hours_val,
                        rate_val,
                        amount_val,
                        f"schedule:{int(schedule_id)}",
                        "OPEN",
                    ),
                )
                work_item_id = cur.fetchone()[0]

                cur.execute(
                    """
                    UPDATE employee_work_schedule
                    SET payroll_posted_work_item_id = %s,
                        payroll_posted_at = NOW(),
                        updated_at = NOW()
                    WHERE schedule_id = %s
                    """,
                    (int(work_item_id), int(schedule_id)),
                )

            return True, f"Posted to payroll work-item #{int(work_item_id)}."
        except Exception as exc:
            logger.error("Failed posting schedule row to payroll: %s", exc)
            return False, f"Post failed: {exc}"

    def _post_selected_to_payroll(self) -> None:
        schedule_id = self._selected_schedule_id_from_table()
        if not schedule_id:
            QMessageBox.information(self, "Post To Payroll", "Select a schedule row first.")
            return
        ok, msg = self._post_schedule_row_to_payroll(schedule_id)
        if ok:
            QMessageBox.information(self, "Post To Payroll", msg)
            self._load_rows()
        else:
            QMessageBox.warning(self, "Post To Payroll", msg)

    def _post_completed_filtered_to_payroll(self) -> None:
        from_date = self.filter_from.date().toPyDate()
        to_date = self.filter_to.date().toPyDate()
        employee_id = self.filter_employee.currentData()

        where = [
            "work_date BETWEEN %s AND %s",
            "COALESCE(status, 'SCHEDULED') = 'COMPLETED'",
            "payroll_posted_work_item_id IS NULL",
        ]
        params = [from_date, to_date]
        if employee_id:
            where.append("employee_id = %s")
            params.append(int(employee_id))

        schedule_ids = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT schedule_id
                    FROM employee_work_schedule
                    WHERE {' AND '.join(where)}
                    ORDER BY work_date, schedule_id
                    """,
                    tuple(params),
                )
                schedule_ids = [int(r[0]) for r in cur.fetchall()]
        except Exception as exc:
            QMessageBox.warning(self, "Post To Payroll", f"Load failed: {exc}")
            return

        if not schedule_ids:
            QMessageBox.information(
                self,
                "Post To Payroll",
                "No unposted COMPLETED rows found in the current filter.",
            )
            return

        success_count = 0
        fail_count = 0
        for sid in schedule_ids:
            ok, _msg = self._post_schedule_row_to_payroll(sid)
            if ok:
                success_count += 1
            else:
                fail_count += 1

        self._load_rows()
        QMessageBox.information(
            self,
            "Post To Payroll",
            f"Posted: {success_count} | Skipped/Failed: {fail_count}",
        )

    def _post_ready_to_payroll(self) -> None:
        """Post completed/unposted rows due through today.

        Uses employee filter only, so payroll can be posted regardless of
        current date-range window in the table.
        """

        employee_id = self.filter_employee.currentData()
        where = [
            "work_date <= %s",
            "COALESCE(status, 'SCHEDULED') = 'COMPLETED'",
            "payroll_posted_work_item_id IS NULL",
        ]
        params = [date.today()]
        if employee_id:
            where.append("employee_id = %s")
            params.append(int(employee_id))

        schedule_ids = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT schedule_id
                    FROM employee_work_schedule
                    WHERE {' AND '.join(where)}
                    ORDER BY work_date, schedule_id
                    """,
                    tuple(params),
                )
                schedule_ids = [int(r[0]) for r in cur.fetchall()]
        except Exception as exc:
            QMessageBox.warning(self, "Post To Payroll", f"Load failed: {exc}")
            return

        if not schedule_ids:
            QMessageBox.information(
                self,
                "Post To Payroll",
                "No ready rows found (COMPLETED, unposted, date <= today).",
            )
            return

        success_count = 0
        fail_count = 0
        for sid in schedule_ids:
            ok, _msg = self._post_schedule_row_to_payroll(sid)
            if ok:
                success_count += 1
            else:
                fail_count += 1

        self._load_rows()
        QMessageBox.information(
            self,
            "Post To Payroll",
            f"Ready-post complete. Posted: {success_count} | Skipped/Failed: {fail_count}",
        )

    def _post_visible_rows_to_payroll(self) -> None:
        """Post all rows currently shown in the schedule table."""

        schedule_ids = []
        for row in range(self.table.rowCount()):
            date_item = self.table.item(row, 0)
            if not date_item:
                continue
            schedule_id = date_item.data(Qt.ItemDataRole.UserRole)
            if schedule_id is None:
                continue
            schedule_ids.append(int(schedule_id))

        if not schedule_ids:
            QMessageBox.information(
                self,
                "Post To Payroll",
                "No visible rows to post.",
            )
            return

        if (
            QMessageBox.question(
                self,
                "Post Visible Rows",
                f"Post {len(schedule_ids)} visible row(s) to payroll now?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        success_count = 0
        fail_count = 0
        fail_examples = []
        for sid in schedule_ids:
            ok, msg = self._post_schedule_row_to_payroll(sid)
            if ok:
                success_count += 1
            else:
                fail_count += 1
                if msg and msg not in fail_examples and len(fail_examples) < 3:
                    fail_examples.append(msg)

        self._load_rows()
        extra = ""
        if fail_examples:
            extra = "\n\nExamples:\n- " + "\n- ".join(fail_examples)
        QMessageBox.information(
            self,
            "Post To Payroll",
            (
                f"Visible-post complete. Posted: {success_count} | "
                f"Skipped/Failed: {fail_count}{extra}"
            ),
        )
