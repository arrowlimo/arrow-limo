"""Employee work items and pay extras management.

Tracks non-charter payable work, reimbursements, advances, floats, loans,
and returns by employee and pay period so payroll is not solely charter-driven.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
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


ITEM_TYPES = [
    "CLEANING",
    "OFFICE",
    "BEVERAGE",
    "TRAINING",
    "STANDBY",
    "BONUS",
    "OTHER_WORK",
    "CHARTER_HOST",
    "CHARTER_CO_DRIVER",
    "REIMBURSEMENT",
    "TIP",
    "ADVANCE_ISSUED",
    "ADVANCE_RETURN",
    "FLOAT_ISSUED",
    "FLOAT_RETURN",
    "LOAN_ISSUED",
    "LOAN_RETURN",
]

PAYABLE_TYPES = {
    "CLEANING",
    "OFFICE",
    "BEVERAGE",
    "TRAINING",
    "STANDBY",
    "BONUS",
    "OTHER_WORK",
    "CHARTER_HOST",
    "CHARTER_CO_DRIVER",
    "TIP",
}


@dataclass
class WorkItemSummary:
    payable_income: float = 0.0
    reimbursements: float = 0.0
    advances_outstanding: float = 0.0
    float_outstanding: float = 0.0
    loan_outstanding: float = 0.0


def ensure_employee_work_items_table(db) -> None:
    with DatabaseContext(db, auto_commit=True) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS employee_work_items (
                work_item_id SERIAL PRIMARY KEY,
                employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
                pay_period_id INTEGER NULL REFERENCES pay_periods(pay_period_id),
                fiscal_year INTEGER NULL,
                work_date DATE NOT NULL,
                item_type VARCHAR(40) NOT NULL,
                description TEXT NULL,
                hours NUMERIC(10,2) NOT NULL DEFAULT 0,
                rate NUMERIC(10,2) NOT NULL DEFAULT 0,
                amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                receipt_ref TEXT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )



def get_work_items(db, employee_id: int, pay_period_id: int | None, fiscal_year: int | None) -> list[tuple]:
    with DatabaseContext(db, auto_commit=False) as cur:
        if pay_period_id:
            cur.execute(
                """
                SELECT work_item_id, work_date, item_type, description,
                       hours, rate, amount, receipt_ref, status
                FROM employee_work_items
                WHERE employee_id = %s
                  AND (pay_period_id = %s OR pay_period_id IS NULL)
                ORDER BY work_date DESC, work_item_id DESC
                """,
                (employee_id, pay_period_id),
            )
        elif fiscal_year:
            cur.execute(
                """
                SELECT work_item_id, work_date, item_type, description,
                       hours, rate, amount, receipt_ref, status
                FROM employee_work_items
                WHERE employee_id = %s
                  AND fiscal_year = %s
                ORDER BY work_date DESC, work_item_id DESC
                """,
                (employee_id, fiscal_year),
            )
        else:
            cur.execute(
                """
                SELECT work_item_id, work_date, item_type, description,
                       hours, rate, amount, receipt_ref, status
                FROM employee_work_items
                WHERE employee_id = %s
                ORDER BY work_date DESC, work_item_id DESC
                """,
                (employee_id,),
            )
        return cur.fetchall()



def get_work_item_summary(
    db,
    employee_id: int,
    pay_period_id: int | None = None,
    fiscal_year: int | None = None,
) -> WorkItemSummary:
    summary = WorkItemSummary()
    rows = get_work_items(db, employee_id, pay_period_id, fiscal_year)
    for _wid, _wdate, item_type, _desc, _hours, _rate, amount, _ref, status in rows:
        amt = float(amount or 0.0)
        t = (item_type or "").upper()
        s = (status or "OPEN").upper()
        if s in {"VOID", "CANCELLED"}:
            continue
        if t in PAYABLE_TYPES:
            summary.payable_income += amt
        elif t == "REIMBURSEMENT":
            summary.reimbursements += amt
        elif t == "ADVANCE_ISSUED":
            summary.advances_outstanding += amt
        elif t == "ADVANCE_RETURN":
            summary.advances_outstanding -= amt
        elif t == "FLOAT_ISSUED":
            summary.float_outstanding += amt
        elif t == "FLOAT_RETURN":
            summary.float_outstanding -= amt
        elif t == "LOAN_ISSUED":
            summary.loan_outstanding += amt
        elif t == "LOAN_RETURN":
            summary.loan_outstanding -= amt

    summary.advances_outstanding = max(0.0, summary.advances_outstanding)
    summary.float_outstanding = max(0.0, summary.float_outstanding)
    summary.loan_outstanding = max(0.0, summary.loan_outstanding)
    return summary


class EmployeeWorkItemsDialog(QDialog):
    """Manage non-charter payable work and cash movement items."""

    def __init__(
        self,
        db,
        employee_id: int,
        fiscal_year: int | None,
        pay_period_id: int | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.employee_id = int(employee_id)
        self.fiscal_year = int(fiscal_year) if fiscal_year else None
        self.pay_period_id = int(pay_period_id) if pay_period_id else None
        self.setWindowTitle("Employee Work / Advances / Reimbursements")
        self.resize(1100, 620)

        layout = QVBoxLayout(self)

        form = QGridLayout()
        self.work_date = QDateEdit()
        self.work_date.setCalendarPopup(True)
        self.work_date.setDate(QDate.currentDate())

        self.item_type = QComboBox()
        self.item_type.addItems(ITEM_TYPES)

        self.description = QLineEdit()
        self.description.setPlaceholderText("Task or payment note")

        self.hours = QDoubleSpinBox()
        self.hours.setRange(0, 1000)
        self.hours.setDecimals(2)

        self.rate = QDoubleSpinBox()
        self.rate.setRange(0, 10000)
        self.rate.setDecimals(2)

        self.amount = QDoubleSpinBox()
        self.amount.setRange(-1000000, 1000000)
        self.amount.setDecimals(2)

        self.receipt_ref = QLineEdit()
        self.receipt_ref.setPlaceholderText("Receipt # / note")

        self.status = QComboBox()
        self.status.addItems(["OPEN", "PAID", "RECEIPTED", "VOID"])

        form.addWidget(QLabel("Date"), 0, 0)
        form.addWidget(self.work_date, 0, 1)
        form.addWidget(QLabel("Type"), 0, 2)
        form.addWidget(self.item_type, 0, 3)
        form.addWidget(QLabel("Hours"), 0, 4)
        form.addWidget(self.hours, 0, 5)

        form.addWidget(QLabel("Rate"), 1, 0)
        form.addWidget(self.rate, 1, 1)
        form.addWidget(QLabel("Amount"), 1, 2)
        form.addWidget(self.amount, 1, 3)
        form.addWidget(QLabel("Status"), 1, 4)
        form.addWidget(self.status, 1, 5)

        form.addWidget(QLabel("Description"), 2, 0)
        form.addWidget(self.description, 2, 1, 1, 3)
        form.addWidget(QLabel("Receipt"), 2, 4)
        form.addWidget(self.receipt_ref, 2, 5)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Add Item")
        add_btn.clicked.connect(self._add_item)
        buttons.addWidget(add_btn)

        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._delete_selected)
        buttons.addWidget(del_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.reload)
        buttons.addWidget(refresh_btn)

        buttons.addStretch(1)
        close_btn = QPushButton("Done")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Date",
                "Type",
                "Description",
                "Hours",
                "Rate",
                "Amount",
                "Receipt",
                "Status",
            ]
        )
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        self.reload()

    def _resolved_fiscal_year(self) -> int | None:
        if self.fiscal_year:
            return self.fiscal_year
        d = self.work_date.date().toPyDate()
        return int(d.year)

    def _add_item(self) -> None:
        d = self.work_date.date().toPyDate()
        work_type = self.item_type.currentText().strip().upper()
        desc = self.description.text().strip() or None
        hours = float(self.hours.value())
        rate = float(self.rate.value())
        amount = float(self.amount.value())
        receipt = self.receipt_ref.text().strip() or None
        status = self.status.currentText().strip().upper()

        if abs(amount) < 0.005 and hours > 0 and rate > 0:
            amount = round(hours * rate, 2)

        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                INSERT INTO employee_work_items (
                    employee_id, pay_period_id, fiscal_year, work_date, item_type,
                    description, hours, rate, amount, receipt_ref, status, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, NOW()
                )
                """,
                (
                    self.employee_id,
                    self.pay_period_id,
                    self._resolved_fiscal_year(),
                    d,
                    work_type,
                    desc,
                    hours,
                    rate,
                    amount,
                    receipt,
                    status,
                ),
            )

        self.reload()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return

        item = self.table.item(row, 0)
        if not item:
            return

        work_item_id = int(item.text())
        reply = QMessageBox.question(
            self,
            "Delete Work Item",
            f"Delete work item #{work_item_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                "DELETE FROM employee_work_items WHERE work_item_id = %s",
                (work_item_id,),
            )
        self.reload()

    def reload(self) -> None:
        rows = get_work_items(
            self.db,
            self.employee_id,
            self.pay_period_id,
            self.fiscal_year,
        )
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                text = "" if value is None else str(value)
                if c == 6:
                    text = f"{float(value or 0):,.2f}"
                self.table.setItem(r, c, QTableWidgetItem(text))
