"""Persistent month-end and year-end close management checklists."""

import calendar
from dataclasses import dataclass
from datetime import date

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class CloseTask:
    key: str
    area: str
    question: str
    domain: str
    target: str
    secondary_target: str = ""


MONTH_END_TASKS = (
    CloseTask(
        "charters_closed",
        "Operations",
        "Are all charters for this month completed, reviewed, and closed?",
        "operations",
        "📡 Dispatch",
        "📝 Run Charter",
    ),
    CloseTask(
        "receipts_entered",
        "Revenue",
        "Are all client receipts for the month entered and verified?",
        "accounting",
        "🧾 Enhanced Receipts",
    ),
    CloseTask(
        "client_invoices_reviewed",
        "Receivables",
        "Are client invoices complete and unpaid balances reviewed?",
        "accounting",
        "💰 Receipts & Invoices",
    ),
    CloseTask(
        "payments_linked",
        "Receivables",
        "Are receipts and client payments linked to the correct invoices?",
        "accounting",
        "💳 Payment Linker",
    ),
    CloseTask(
        "vendor_invoices_entered",
        "Payables",
        "Are all vendor invoices and month-end charges entered?",
        "accounting",
        "📋 Vendor Invoices",
    ),
    CloseTask(
        "vendor_payables_reviewed",
        "Payables",
        "Are unpaid vendor invoices reviewed and payment decisions recorded?",
        "accounting",
        "📋 Vendor Invoices",
    ),
    CloseTask(
        "banking_reconciled",
        "Banking",
        "Are bank, cash, card, deposit, and transfer transactions reconciled?",
        "accounting",
        "🏦 Enhanced Banking",
    ),
    CloseTask(
        "nsf_refunds_resolved",
        "Banking",
        "Are NSF items, refunds, chargebacks, and unmatched deposits resolved?",
        "accounting",
        "🧩 NSF Pairs",
    ),
    CloseTask(
        "employee_pay_complete",
        "Payroll",
        "Is employee pay for this month calculated, reviewed, and posted?",
        "accounting",
        "💵 Payroll Entry",
    ),
    CloseTask(
        "reimbursements_complete",
        "Payroll",
        "Are employee reimbursements, advances, and expense repayments complete?",
        "fleet",
        "👔 Employees",
    ),
    CloseTask(
        "cra_payroll_complete",
        "CRA",
        "Are payroll deductions, employer contributions, and CRA payments complete?",
        "accounting",
        "🧮 Payroll Remittances",
    ),
    CloseTask(
        "gst_complete",
        "GST",
        "Is GST collected/ITC reviewed and the remittance or payment recorded?",
        "accounting",
        "🏛️ Tax",
    ),
    CloseTask(
        "wcb_complete",
        "Compliance",
        "Are WCB, benefits, and other statutory month obligations reviewed?",
        "accounting",
        "🛡️ WCB Rates",
    ),
    CloseTask(
        "staff_loans_reconciled",
        "Employees",
        "Are employee loans, floats, and advances reconciled?",
        "accounting",
        "🏦 Staff Loan Account",
    ),
    CloseTask(
        "close_exceptions_reviewed",
        "Control",
        "Are all close-control exceptions cleared or documented?",
        "operations",
        "✅ Close Control Center",
    ),
    CloseTask(
        "financials_reviewed",
        "Review",
        "Have monthly financial reports and unusual balances been reviewed?",
        "accounting",
        "📊 Financial Reports",
    ),
    CloseTask(
        "support_saved",
        "Sign-off",
        "Are supporting documents, notes, and final reviewer sign-off complete?",
        "accounting",
        "📝 Accountant Notes",
    ),
)


YEAR_END_TASKS = (
    CloseTask(
        "all_months_closed",
        "Close",
        "Are all twelve month-end checklists complete?",
        "accounting",
        "📆 Month-End Close",
    ),
    CloseTask(
        "cutoff_complete",
        "Cut-off",
        "Are year-end charters, receipts, and invoices posted in the correct year?",
        "accounting",
        "💰 Receipts & Invoices",
    ),
    CloseTask(
        "banking_year_reconciled",
        "Banking",
        "Are all bank, card, cash, loan, and transfer accounts reconciled?",
        "accounting",
        "🏦 Enhanced Banking",
    ),
    CloseTask(
        "ar_collectability",
        "Receivables",
        "Are unpaid client invoices, credits, and collectability adjustments reviewed?",
        "accounting",
        "💰 Receipts & Invoices",
    ),
    CloseTask(
        "ap_accruals",
        "Payables",
        "Are unpaid vendor invoices, accruals, and cut-off liabilities complete?",
        "accounting",
        "📋 Vendor Invoices",
    ),
    CloseTask(
        "payroll_year_complete",
        "Payroll",
        "Are annual payroll, employee earnings, reimbursements, and benefits complete?",
        "accounting",
        "💵 Payroll Entry",
    ),
    CloseTask(
        "t4_t4a_complete",
        "Payroll",
        "Are T4/T4A data, employee information, and annual payroll totals reviewed?",
        "year_end",
        "🧮 Year-End Audit",
    ),
    CloseTask(
        "cra_year_reconciled",
        "CRA",
        "Are CRA payroll remittances and employer contributions reconciled?",
        "accounting",
        "🧮 Payroll Remittances",
    ),
    CloseTask(
        "gst_year_reconciled",
        "GST",
        "Are all GST returns, ITCs, payments, and the annual balance reconciled?",
        "accounting",
        "🏛️ Tax",
    ),
    CloseTask(
        "wcb_annual_complete",
        "Compliance",
        "Is the WCB annual return and assessable payroll review complete?",
        "accounting",
        "🛡️ WCB Rates",
    ),
    CloseTask(
        "assets_depreciation",
        "Assets",
        "Are asset additions, disposals, and depreciation schedules complete?",
        "accounting",
        "📦 Asset Inventory",
    ),
    CloseTask(
        "loans_related_parties",
        "Balance Sheet",
        "Are loans, shareholder/related-party, staff-loan, and advance balances reviewed?",
        "accounting",
        "🏢 Business Entity",
    ),
    CloseTask(
        "inventory_complete",
        "Inventory",
        "Are beverage and other inventory balances counted and adjusted?",
        "accounting",
        "🍷 Beverage Revenue",
    ),
    CloseTask(
        "t2_gifi_ready",
        "Corporate Tax",
        "Are T2/GIFI working papers and corporate tax adjustments ready?",
        "accounting",
        "📋 T2 Corporate Tax",
    ),
    CloseTask(
        "financial_statements_reviewed",
        "Review",
        "Are year-end financial statements and unusual balances reviewed?",
        "accounting",
        "📊 Financial Reports",
    ),
    CloseTask(
        "year_end_wizard_complete",
        "Sign-off",
        "Is the existing Year-End Wizard, evidence package, backup, and sign-off complete?",
        "year_end",
        "🧮 Year-End Audit",
    ),
)


class PeriodCloseManagementWidget(QWidget):
    """Persistent Yes/No/Later close checklist with module handoffs."""

    def __init__(
        self,
        db,
        period_type: str,
        main_window=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if period_type not in {"month", "year"}:
            raise ValueError(f"Unsupported close period type: {period_type}")
        self.db = db
        self.period_type = period_type
        self.main_window = main_window
        self.tasks = MONTH_END_TASKS if period_type == "month" else YEAR_END_TASKS
        self.answer_combos: dict[str, QComboBox] = {}
        self.go_buttons: dict[str, QPushButton] = {}
        self.note_edits: dict[str, QLineEdit] = {}
        self._loading = False
        self._ensure_status_table()
        self._build_ui()
        self.refresh_statuses()

    def _ensure_status_table(self) -> None:
        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS period_close_checklist (
                    period_type VARCHAR(10) NOT NULL,
                    period_key VARCHAR(7) NOT NULL,
                    task_key VARCHAR(80) NOT NULL,
                    answer VARCHAR(20) NOT NULL DEFAULT 'Later',
                    notes TEXT,
                    updated_by VARCHAR(120),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (period_type, period_key, task_key),
                    CHECK (answer IN ('Yes', 'No', 'Later'))
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS period_close_signoff (
                    period_type VARCHAR(10) NOT NULL,
                    period_key VARCHAR(7) NOT NULL,
                    closed_by VARCHAR(120),
                    closed_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (period_type, period_key)
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE period_close_checklist
                ALTER COLUMN answer TYPE VARCHAR(20)
                """
            )
            cur.execute(
                """
                ALTER TABLE period_close_checklist
                DROP CONSTRAINT IF EXISTS period_close_checklist_answer_check
                """
            )
            cur.execute(
                """
                ALTER TABLE period_close_checklist
                ADD CONSTRAINT period_close_checklist_answer_check
                CHECK (answer IN ('Yes', 'No', 'Later', 'In Progress'))
                """
            )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        title = "Month-End Close" if self.period_type == "month" else "Year-End Close"
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        toolbar.addWidget(title_label)

        if self.period_type == "month":
            self.month_combo = QComboBox()
            for month in range(1, 13):
                self.month_combo.addItem(calendar.month_name[month], month)
            self.month_combo.setCurrentIndex(date.today().month - 1)
            self.month_combo.currentIndexChanged.connect(self.refresh_statuses)
            toolbar.addWidget(self.month_combo)
        else:
            self.month_combo = None

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, date.today().year + 5)
        self.year_spin.setValue(date.today().year)
        self.year_spin.valueChanged.connect(self.refresh_statuses)
        toolbar.addWidget(self.year_spin)

        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self.progress_label)
        toolbar.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_statuses)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        guidance = QLabel(
            "Answer Yes when complete, No when work has not started, In Progress "
            "while the accountant is working on it, or Later to defer it. No "
            "highlights Go Fix; In Progress shows Continue. Use the Return button "
            "in the status bar when the module work is finished."
        )
        guidance.setWordWrap(True)
        guidance.setStyleSheet(
            "background: #e8f2fb; border: 1px solid #a8c5dd; padding: 5px;"
        )
        layout.addWidget(guidance)

        self.table = QTableWidget(len(self.tasks), 5)
        self.table.setHorizontalHeaderLabels(
            ["Area", "Required Close Check", "Answer", "Go", "Notes"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        for row, task in enumerate(self.tasks):
            self.table.setRowHeight(row, 38)
            area_item = QTableWidgetItem(task.area)
            question_item = QTableWidgetItem(task.question)
            question_item.setToolTip(task.question)
            self.table.setItem(row, 0, area_item)
            self.table.setItem(row, 1, question_item)

            answer = QComboBox()
            answer.addItems(["Later", "No", "In Progress", "Yes"])
            answer.currentTextChanged.connect(
                lambda value, t=task, r=row: self._answer_changed(t, r, value)
            )
            self.answer_combos[task.key] = answer
            self.table.setCellWidget(row, 2, answer)

            go_btn = QPushButton("Go")
            go_btn.clicked.connect(lambda _checked=False, t=task: self._go_to_task(t))
            self.go_buttons[task.key] = go_btn
            self.table.setCellWidget(row, 3, go_btn)

            notes = QLineEdit()
            notes.setPlaceholderText("Optional note")
            notes.editingFinished.connect(
                lambda t=task: self._save_task(t)
            )
            self.note_edits[task.key] = notes
            self.table.setCellWidget(row, 4, notes)

        layout.addWidget(self.table)
        QTimer.singleShot(0, lambda: self.table.setSortingEnabled(False))

        footer = QHBoxLayout()
        self.close_status_label = QLabel()
        footer.addWidget(self.close_status_label)
        footer.addStretch()
        self.complete_btn = QPushButton("Mark Period Closed")
        self.complete_btn.clicked.connect(self._mark_period_closed)
        footer.addWidget(self.complete_btn)
        layout.addLayout(footer)

    def period_key(self) -> str:
        year = self.year_spin.value()
        if self.period_type == "year":
            return str(year)
        return f"{year:04d}-{self.month_combo.currentData():02d}"

    def set_period_key(self, period_key: str) -> None:
        parts = period_key.split("-")
        self.year_spin.setValue(int(parts[0]))
        if self.period_type == "month" and len(parts) == 2:
            index = self.month_combo.findData(int(parts[1]))
            if index >= 0:
                self.month_combo.setCurrentIndex(index)
        self.refresh_statuses()

    def refresh_statuses(self, *_args) -> None:
        period_key = self.period_key()
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT task_key, answer, COALESCE(notes, '')
                FROM period_close_checklist
                WHERE period_type = %s AND period_key = %s
                """,
                (self.period_type, period_key),
            )
            saved = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
            cur.execute(
                """
                SELECT COALESCE(closed_by, ''), closed_at
                FROM period_close_signoff
                WHERE period_type = %s AND period_key = %s
                """,
                (self.period_type, period_key),
            )
            self._closed_info = cur.fetchone()

        self._loading = True
        try:
            for row, task in enumerate(self.tasks):
                answer, notes = saved.get(task.key, ("Later", ""))
                combo = self.answer_combos[task.key]
                combo.setCurrentText(answer)
                self.note_edits[task.key].setText(notes)
                self._style_row(row, task, answer)
        finally:
            self._loading = False
        self._update_progress()

    def _answer_changed(self, task: CloseTask, row: int, answer: str) -> None:
        if self._loading:
            return
        self._save_task(task)
        self._style_row(row, task, answer)
        self._update_progress()

        context = getattr(self.main_window, "_close_return_context", None)
        if (
            context
            and context.get("period_type") == self.period_type
            and context.get("period_key") == self.period_key()
            and context.get("task_key") == task.key
            and answer in {"Yes", "Later"}
        ):
            self.main_window.clear_close_return_context()

    def _save_task(self, task: CloseTask) -> None:
        if self._loading:
            return
        answer = self.answer_combos[task.key].currentText()
        notes = self.note_edits[task.key].text().strip()
        user_name = ""
        if self.main_window is not None:
            user_name = self.main_window.auth_user.get("username", "")
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO period_close_checklist (
                        period_type, period_key, task_key, answer,
                        notes, updated_by, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (period_type, period_key, task_key)
                    DO UPDATE SET
                        answer = EXCLUDED.answer,
                        notes = EXCLUDED.notes,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = NOW()
                    """,
                    (
                        self.period_type,
                        self.period_key(),
                        task.key,
                        answer,
                        notes,
                        user_name,
                    ),
                )
                if answer != "Yes":
                    cur.execute(
                        """
                        DELETE FROM period_close_signoff
                        WHERE period_type = %s AND period_key = %s
                        """,
                        (self.period_type, self.period_key()),
                    )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Close Checklist Save Error",
                f"Could not save {task.question}\n\n{exc}",
            )
            self.refresh_statuses()

    def _style_row(self, row: int, task: CloseTask, answer: str) -> None:
        colors = {
            "Yes": QColor("#dcfce7"),
            "No": QColor("#fee2e2"),
            "Later": QColor("#fef3c7"),
            "In Progress": QColor("#dbeafe"),
        }
        for column in (0, 1):
            item = self.table.item(row, column)
            if item is not None:
                item.setBackground(colors[answer])

        button = self.go_buttons[task.key]
        if answer == "No":
            button.setText("Go Fix")
            button.setStyleSheet(
                "background: #dc2626; color: white; font-weight: bold; padding: 5px;"
            )
        elif answer == "In Progress":
            button.setText("Continue")
            button.setStyleSheet(
                "background: #2563eb; color: white; font-weight: bold; padding: 5px;"
            )
            self.note_edits[task.key].setPlaceholderText(
                "Current work or next step"
            )
        else:
            button.setText("Go")
            button.setStyleSheet("")
            self.note_edits[task.key].setPlaceholderText("Optional note")

    def _update_progress(self) -> None:
        answers = [combo.currentText() for combo in self.answer_combos.values()]
        completed = answers.count("Yes")
        in_progress = answers.count("In Progress")
        total = len(answers)
        remaining = total - completed
        self.progress_label.setText(
            f"{completed}/{total} complete"
            + (f" • {in_progress} in progress" if in_progress else "")
        )
        self.complete_btn.setEnabled(remaining == 0)
        if remaining:
            self.complete_btn.setText("Mark Period Closed")
            self.close_status_label.setText(
                f"{remaining} close checks still require completion or review."
            )
            self.close_status_label.setStyleSheet(
                "color: #b45309; font-weight: bold;"
            )
        else:
            if self._closed_info:
                closed_by, closed_at = self._closed_info
                self.close_status_label.setText(
                    f"{self.period_key()} closed by {closed_by or 'unknown'} "
                    f"on {closed_at:%Y-%m-%d %H:%M}."
                )
                self.complete_btn.setText("Period Closed ✓")
                self.complete_btn.setEnabled(False)
            else:
                self.close_status_label.setText(
                    f"{self.period_key()} is ready to close."
                )
                self.complete_btn.setText("Mark Period Closed")
            self.close_status_label.setStyleSheet(
                "color: #15803d; font-weight: bold;"
            )

    def _go_to_task(self, task: CloseTask) -> None:
        main = self.main_window or self.window()
        if main is None:
            QMessageBox.warning(self, "Open Module", "Main window is unavailable.")
            return

        if self.answer_combos[task.key].currentText() == "Later":
            self.answer_combos[task.key].setCurrentText("No")

        period_type = self.period_type
        period_key = self.period_key()

        def navigate() -> None:
            opened = False
            if task.domain == "accounting":
                opened = bool(main.navigate_to_accounting_subtab(task.target))
            elif task.domain == "operations":
                opened = bool(main.navigate_to_operations_subtab(task.target))
                if opened and task.secondary_target:
                    main._navigate_to_dispatch_subtab(task.secondary_target)
            elif task.domain == "fleet":
                opened = bool(main.navigate_to_fleet_subtab(task.target))
            elif task.domain == "year_end":
                opened = bool(main.navigate_to_top_tab(task.target))

            if opened:
                if hasattr(main, "set_close_return_context"):
                    main.set_close_return_context(
                        period_type,
                        period_key,
                        task.key,
                    )
            else:
                QMessageBox.warning(
                    main,
                    "Open Module",
                    f"Could not open the module for:\n{task.question}",
                )

        QTimer.singleShot(0, navigate)

    def _mark_period_closed(self) -> None:
        if any(
            combo.currentText() != "Yes"
            for combo in self.answer_combos.values()
        ):
            QMessageBox.warning(
                self,
                "Close Not Ready",
                "Every close check must be answered Yes before closing the period.",
            )
            return
        user_name = ""
        if self.main_window is not None:
            user_name = self.main_window.auth_user.get("username", "")
        with DatabaseContext(self.db, auto_commit=True) as cur:
            cur.execute(
                """
                INSERT INTO period_close_signoff (
                    period_type, period_key, closed_by, closed_at
                )
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (period_type, period_key)
                DO UPDATE SET
                    closed_by = EXCLUDED.closed_by,
                    closed_at = NOW()
                """,
                (
                    self.period_type,
                    self.period_key(),
                    user_name,
                ),
            )
        self.refresh_statuses()
        QMessageBox.information(
            self,
            "Period Closed",
            f"{self.period_key()} close checklist is complete and signed off.",
        )
