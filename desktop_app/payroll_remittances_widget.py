"""
Payroll remittance reconciliation widget.

Provides a monthly CRA + WCB due/paid variance view with drill-down details
                        e.employee_id,
from employee payroll records.
"""

import logging
from datetime import date

from db_error_handling import DatabaseContext
from print_export_helper import PrintExportHelper
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class PayrollRemittancesWidget(QWidget):
    """Monthly CRA/WCB remittance dashboard with reconciliation details."""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._month_rows = {}
        self._build_ui()
        self._ensure_payroll_remittances_table()
        self._ensure_employee_flag_overrides_table()
        self.year_spin.setValue(QDate.currentDate().year())
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("<h2>Payroll Remittances (CRA + WCB)</h2>")
        title.setStyleSheet("padding: 4px; color: #1f2937;")
        layout.addWidget(title)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Year:"))

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2011, 2035)
        controls.addWidget(self.year_spin)

        controls.addWidget(QLabel("Quarter:"))
        self.quarter_combo = QComboBox()
        self.quarter_combo.addItems(["Q1", "Q2", "Q3", "Q4"])
        controls.addWidget(self.quarter_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        controls.addWidget(refresh_btn)

        quarter_btn = QPushButton("Load Quarter Verification")
        quarter_btn.setToolTip(
            "Show quarter totals + employee flags for CRA filing checks"
        )
        quarter_btn.clicked.connect(self.load_quarter_verification)
        controls.addWidget(quarter_btn)

        print_month_btn = QPushButton("Print Month Contributions")
        print_month_btn.clicked.connect(self.print_month_contributions)
        controls.addWidget(print_month_btn)

        print_quarter_btn = QPushButton("Print Quarter Contributions")
        print_quarter_btn.clicked.connect(self.print_quarter_contributions)
        controls.addWidget(print_quarter_btn)

        print_flags_btn = QPushButton("Print Employee Flags")
        print_flags_btn.clicked.connect(self.print_employee_flags)
        controls.addWidget(print_flags_btn)

        sync_btn = QPushButton("Sync Calculated Month")
        sync_btn.setToolTip(
            "Writes selected month calculated CRA totals into"
            "payroll_remittances"
        )
        sync_btn.clicked.connect(self.sync_selected_month)
        controls.addWidget(sync_btn)

        gen_year_btn = QPushButton("Generate Year Remittances")
        gen_year_btn.setToolTip(
            "Generate or refresh all 12 payroll remittance months for the"
            "selected year"
        )
        gen_year_btn.clicked.connect(self.generate_year_remittances)
        controls.addWidget(gen_year_btn)

        gen_pd7a_btn = QPushButton("Generate PD7A Returns")
        gen_pd7a_btn.setToolTip(
            "Generate monthly CRA PD7A return rows from payroll remittance"
            "totals"
        )
        gen_pd7a_btn.clicked.connect(self.generate_pd7a_returns)
        controls.addWidget(gen_pd7a_btn)

        open_payroll_btn = QPushButton("Open Payroll Entry")
        open_payroll_btn.clicked.connect(
            lambda: self._jump_to_accounting_subtab("💵 Payroll Entry")
        )
        controls.addWidget(open_payroll_btn)

        open_tax_btn = QPushButton("Open Tax")
        open_tax_btn.clicked.connect(
            lambda: self._jump_to_accounting_subtab("🏛️ Tax")
        )
        controls.addWidget(open_tax_btn)

        open_wcb_btn = QPushButton("Open WCB Rates")
        open_wcb_btn.clicked.connect(
            lambda: self._jump_to_accounting_subtab("🛡️ WCB Rates")
        )
        controls.addWidget(open_wcb_btn)

        controls.addStretch()
        layout.addLayout(controls)

        summary = QGroupBox("Year Summary")
        summary_grid = QGridLayout(summary)

        self.lbl_cra_due = QLabel("$0.00")
        self.lbl_cra_paid = QLabel("$0.00")
        self.lbl_cra_var = QLabel("$0.00")

        self.lbl_wcb_due = QLabel("$0.00")
        self.lbl_wcb_paid = QLabel("$0.00")
        self.lbl_wcb_var = QLabel("$0.00")

        for lbl in [
            self.lbl_cra_due,
            self.lbl_cra_paid,
            self.lbl_cra_var,
            self.lbl_wcb_due,
            self.lbl_wcb_paid,
            self.lbl_wcb_var,
        ]:
            lbl.setStyleSheet(
                "font-family: 'Courier New'; font-size: 11pt; font-weight:"
                "bold;"
            )

        summary_grid.addWidget(QLabel("CRA Due:"), 0, 0)
        summary_grid.addWidget(self.lbl_cra_due, 0, 1)
        summary_grid.addWidget(QLabel("CRA Paid:"), 0, 2)
        summary_grid.addWidget(self.lbl_cra_paid, 0, 3)
        summary_grid.addWidget(QLabel("CRA Variance:"), 0, 4)
        summary_grid.addWidget(self.lbl_cra_var, 0, 5)

        summary_grid.addWidget(QLabel("WCB Due:"), 1, 0)
        summary_grid.addWidget(self.lbl_wcb_due, 1, 1)
        summary_grid.addWidget(QLabel("WCB Paid:"), 1, 2)
        summary_grid.addWidget(self.lbl_wcb_paid, 1, 3)
        summary_grid.addWidget(QLabel("WCB Variance:"), 1, 4)
        summary_grid.addWidget(self.lbl_wcb_var, 1, 5)

        layout.addWidget(summary)

        self.month_table = QTableWidget()
        self.month_table.setColumnCount(9)
        self.month_table.setHorizontalHeaderLabels(
            [
                "Month",
                "CRA Due",
                "CRA Paid",
                "CRA Var",
                "WCB Due",
                "WCB Paid",
                "WCB Var",
                "Status",
                "Ref",
            ]
        )
        self.month_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.month_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.month_table.setAlternatingRowColors(True)
        self.month_table.cellClicked.connect(self._on_month_selected)
        layout.addWidget(self.month_table)

        bottom = QHBoxLayout()

        detail_group = QGroupBox("Month Detail (Employee + Pay Period)")
        detail_layout = QVBoxLayout(detail_group)
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(10)
        self.detail_table.setHorizontalHeaderLabels(
            [
                "Employee",
                "Period",
                "Gross",
                "CPP Emp",
                "EI Emp",
                "Tax",
                "CRA Due",
                "Net Pay",
                "Work Status",
                "Flags",
            ]
        )
        self.detail_table.setAlternatingRowColors(True)
        self.detail_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.detail_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        detail_layout.addWidget(self.detail_table)
        bottom.addWidget(detail_group, stretch=3)

        edit_group = QGroupBox("Selected Month Filing / Payment")
        edit_form = QFormLayout(edit_group)

        self.sel_month_label = QLabel("-")
        edit_form.addRow("Month", self.sel_month_label)

        self.payment_amount_spin = QDoubleSpinBox()
        self.payment_amount_spin.setMaximum(99999999)
        self.payment_amount_spin.setPrefix("$")
        edit_form.addRow("CRA Paid Amount", self.payment_amount_spin)

        self.payment_date_edit = QDateEdit()
        self.payment_date_edit.setCalendarPopup(True)
        self.payment_date_edit.setDate(QDate.currentDate())
        edit_form.addRow("CRA Payment Date", self.payment_date_edit)

        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItems(
            ["", "online_banking", "cheque", "wire", "other"]
        )
        edit_form.addRow("Method", self.payment_method_combo)

        self.reference_input = QLineEdit()
        edit_form.addRow("Reference", self.reference_input)

        self.pd7a_amount_spin = QDoubleSpinBox()
        self.pd7a_amount_spin.setMaximum(99999999)
        self.pd7a_amount_spin.setPrefix("$")
        edit_form.addRow("PD7A Statement", self.pd7a_amount_spin)

        self.status_combo = QComboBox()
        self.status_combo.addItems(
            ["pending", "submitted", "filed", "paid", "reconciled", "late"]
        )
        edit_form.addRow("Status", self.status_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(70)
        edit_form.addRow("Notes", self.notes_edit)

        save_btn = QPushButton("Save Selected Month")
        save_btn.clicked.connect(self.save_selected_month)
        edit_form.addRow(save_btn)

        self.override_work_status_combo = QComboBox()
        self.override_work_status_combo.addItems(
            ["(auto)", "WORKED", "NONE"]
        )
        edit_form.addRow("Override Work Status", self.override_work_status_combo)

        self.override_ei_combo = QComboBox()
        self.override_ei_combo.addItems(
            ["(auto)", "EI_EXEMPT", "NOT_EXEMPT"]
        )
        edit_form.addRow("Override EI", self.override_ei_combo)

        self.override_owner_combo = QComboBox()
        self.override_owner_combo.addItems(
            ["(auto)", "OWNER_DEFERRED", "NOT_DEFERRED"]
        )
        edit_form.addRow("Override Owner", self.override_owner_combo)

        self.override_note_input = QLineEdit()
        self.override_note_input.setPlaceholderText(
            "Audit note for override"
        )
        edit_form.addRow("Override Note", self.override_note_input)

        override_row = QHBoxLayout()
        month_override_btn = QPushButton("Apply Month Override")
        month_override_btn.clicked.connect(self.apply_month_override)
        override_row.addWidget(month_override_btn)

        quarter_override_btn = QPushButton("Apply Quarter Override")
        quarter_override_btn.clicked.connect(self.apply_quarter_override)
        override_row.addWidget(quarter_override_btn)

        clear_override_btn = QPushButton("Clear Override")
        clear_override_btn.clicked.connect(self.clear_selected_override)
        override_row.addWidget(clear_override_btn)
        edit_form.addRow(override_row)

        bottom.addWidget(edit_group, stretch=2)
        layout.addLayout(bottom)

        quarter_group = QGroupBox("Quarterly CRA Verification")
        quarter_layout = QVBoxLayout(quarter_group)

        quarter_totals = QHBoxLayout()
        self.q_cpp_total = QLabel("CPP: $0.00")
        self.q_ei_total = QLabel("EI: $0.00")
        self.q_tax_total = QLabel("Tax: $0.00")
        self.q_cra_total = QLabel("CRA Due: $0.00")
        self.q_wcb_total = QLabel("WCB Due: $0.00")
        for lbl in [
            self.q_cpp_total,
            self.q_ei_total,
            self.q_tax_total,
            self.q_cra_total,
            self.q_wcb_total,
        ]:
            lbl.setStyleSheet("font-weight: bold;")
            quarter_totals.addWidget(lbl)
        quarter_totals.addStretch(1)
        quarter_layout.addLayout(quarter_totals)

        self.quarter_table = QTableWidget()
        self.quarter_table.setColumnCount(8)
        self.quarter_table.setHorizontalHeaderLabels(
            [
                "Employee",
                "Quarter Gross",
                "CPP Emp",
                "EI Emp",
                "Tax",
                "CRA Due",
                "Work Status",
                "Flags",
            ]
        )
        self.quarter_table.setAlternatingRowColors(True)
        self.quarter_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.quarter_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        quarter_layout.addWidget(self.quarter_table)

        layout.addWidget(quarter_group)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #2563eb; font-weight: bold;")
        layout.addWidget(self.status_label)

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setStyleSheet(
            "color: #dc2626; font-weight: bold;"
            if error
            else "color: #2563eb; font-weight: bold;"
        )
        self.status_label.setText(text)

    def _jump_to_accounting_subtab(self, target_text: str) -> None:
        """Try to activate an Accounting/Finance subtab by exact visible tab"
        "text."""

        root = self.window()
        if root is None:
            QMessageBox.information(
                self, "Navigation", "Could not locate main window."
            )
            return

        tab_widgets = root.findChildren(QTabWidget)
        for tabs in tab_widgets:
            for idx in range(tabs.count()):
                if tabs.tabText(idx) != target_text:
                    continue

                tabs.setCurrentIndex(idx)
                if hasattr(root, "_on_accounting_subtab_changed"):
                    try:
                        root._on_accounting_subtab_changed(tabs, idx)
                    except Exception:
                        pass
                self._set_status(f"Opened {target_text}.")
                return

        QMessageBox.information(
            self,
            "Navigation",
            f"Could not find tab: {target_text}",
        )

    def _safe_float(self, value) -> object:
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    def _get_columns(self, table_name: str) -> object:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    """,
                    (table_name,),
                )
                return {row[0] for row in cur.fetchall()}
        except Exception:
            return set()

    def _ensure_payroll_remittances_table(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS payroll_remittances (
                        remittance_id SERIAL PRIMARY KEY,
                        fiscal_year INTEGER NOT NULL,
                        remittance_month INTEGER NOT NULL CHECK
                        (remittance_month
                        BETWEEN 1 AND 12),
                        calculated_gross DECIMAL(10,2) DEFAULT 0.00,
                        calculated_cpp_employee DECIMAL(10,2) DEFAULT 0.00,
                        calculated_cpp_employer DECIMAL(10,2) DEFAULT 0.00,
                        calculated_ei_employee DECIMAL(10,2) DEFAULT 0.00,
                        calculated_ei_employer DECIMAL(10,2) DEFAULT 0.00,
                        calculated_federal_tax DECIMAL(10,2) DEFAULT 0.00,
                        calculated_provincial_tax DECIMAL(10,2) DEFAULT 0.00,
                        calculated_total_remittance DECIMAL(10,2) DEFAULT 0.00,
                        due_date DATE,
                        payment_date DATE,
                        payment_amount DECIMAL(10,2),
                        payment_method TEXT,
                        payment_reference TEXT,
                        receipt_id INTEGER,
                        pd7a_statement_amount DECIMAL(10,2),
                        pd7a_filed_date DATE,
                        variance DECIMAL(10,2),
                        reconciled BOOLEAN DEFAULT FALSE,
                        status TEXT DEFAULT 'pending',
                        is_late BOOLEAN DEFAULT FALSE,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        created_by TEXT,
                        UNIQUE (fiscal_year, remittance_month)
                    )
                    """)
        except Exception as exc:
            logger.warning(
                f"Could not ensure payroll_remittances table: {exc}"
            )

    def _ensure_cra_pd7a_returns_table(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS cra_pd7a_returns (
                        id SERIAL PRIMARY KEY,
                        reporting_year INTEGER NOT NULL,
                        reporting_month INTEGER NOT NULL CHECK (reporting_month
                        BETWEEN 1 AND 12),
                        employee_count INTEGER DEFAULT 0,
                        total_gross_payroll DECIMAL(12,2) DEFAULT 0.00,
                        cpp_pensionable_earnings DECIMAL(12,2) DEFAULT 0.00,
                        cpp_employee_contributions DECIMAL(12,2) DEFAULT 0.00,
                        cpp_employer_contributions DECIMAL(12,2) DEFAULT 0.00,
                        cpp_total DECIMAL(12,2) DEFAULT 0.00,
                        ei_insurable_earnings DECIMAL(12,2) DEFAULT 0.00,
                        ei_employee_premiums DECIMAL(12,2) DEFAULT 0.00,
                        ei_employer_premiums DECIMAL(12,2) DEFAULT 0.00,
                        ei_total DECIMAL(12,2) DEFAULT 0.00,
                        income_tax_deducted DECIMAL(12,2) DEFAULT 0.00,
                        total_remittance_due DECIMAL(12,2) DEFAULT 0.00,
                        previous_overpayment DECIMAL(12,2) DEFAULT 0.00,
                        previous_underpayment DECIMAL(12,2) DEFAULT 0.00,
                        adjusted_remittance DECIMAL(12,2) DEFAULT 0.00,
                        is_calculated BOOLEAN DEFAULT TRUE,
                        is_submitted BOOLEAN DEFAULT FALSE,
                        submission_date DATE,
                        due_date DATE,
                        payment_id INTEGER,
                        variance_from_payment DECIMAL(12,2),
                        calculated_at TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        notes TEXT,
                        UNIQUE (reporting_year, reporting_month)
                    )
                    """)
        except Exception as exc:
            logger.warning(f"Could not ensure cra_pd7a_returns table: {exc}")

    def _ensure_employee_flag_overrides_table(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS payroll_employee_flag_overrides (
                        override_id SERIAL PRIMARY KEY,
                        fiscal_year INTEGER NOT NULL,
                        scope_kind TEXT NOT NULL CHECK (scope_kind IN ('month', 'quarter')),
                        scope_value INTEGER NOT NULL,
                        employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
                        work_status_override TEXT NULL,
                        ei_exempt_override BOOLEAN NULL,
                        owner_deferred_override BOOLEAN NULL,
                        note TEXT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        created_by TEXT,
                        UNIQUE (fiscal_year, scope_kind, scope_value, employee_id)
                    )
                    """
                )
        except Exception as exc:
            logger.warning("Could not ensure payroll employee overrides table: %s", exc)

    def _load_overrides(
        self, year: int, scope_kind: str, scope_value: int
    ) -> dict[int, dict]:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT employee_id, work_status_override,
                           ei_exempt_override, owner_deferred_override, note
                    FROM payroll_employee_flag_overrides
                    WHERE fiscal_year = %s
                      AND scope_kind = %s
                      AND scope_value = %s
                    """,
                    (year, scope_kind, scope_value),
                )
                rows = cur.fetchall()
            return {
                int(r[0]): {
                    "work_status_override": r[1],
                    "ei_exempt_override": r[2],
                    "owner_deferred_override": r[3],
                    "note": r[4] or "",
                }
                for r in rows
            }
        except Exception as exc:
            logger.error("Failed loading overrides: %s", exc)
            return {}

    def _override_values_from_inputs(self) -> tuple[str | None, bool | None, bool | None, str | None]:
        work_val = self.override_work_status_combo.currentText()
        ei_val = self.override_ei_combo.currentText()
        owner_val = self.override_owner_combo.currentText()
        note_val = self.override_note_input.text().strip() or None

        work_override = None if work_val == "(auto)" else work_val
        if ei_val == "(auto)":
            ei_override = None
        else:
            ei_override = ei_val == "EI_EXEMPT"

        if owner_val == "(auto)":
            owner_override = None
        else:
            owner_override = owner_val == "OWNER_DEFERRED"

        return work_override, ei_override, owner_override, note_val

    def _selected_employee_id_from_table(self, table: QTableWidget) -> int | None:
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if not item:
            return None
        emp_id = item.data(Qt.ItemDataRole.UserRole)
        return int(emp_id) if emp_id else None

    def _save_override(self, scope_kind: str, scope_value: int, employee_id: int) -> None:
        year = int(self.year_spin.value())
        work_override, ei_override, owner_override, note_val = self._override_values_from_inputs()

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO payroll_employee_flag_overrides (
                        fiscal_year, scope_kind, scope_value, employee_id,
                        work_status_override, ei_exempt_override,
                        owner_deferred_override, note, updated_at, created_by
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, NOW(), 'desktop_app'
                    )
                    ON CONFLICT (fiscal_year, scope_kind, scope_value, employee_id)
                    DO UPDATE SET
                        work_status_override = EXCLUDED.work_status_override,
                        ei_exempt_override = EXCLUDED.ei_exempt_override,
                        owner_deferred_override = EXCLUDED.owner_deferred_override,
                        note = EXCLUDED.note,
                        updated_at = NOW()
                    """,
                    (
                        year,
                        scope_kind,
                        scope_value,
                        employee_id,
                        work_override,
                        ei_override,
                        owner_override,
                        note_val,
                    ),
                )
            self._set_status(
                f"Saved {scope_kind} override for employee #{employee_id}."
            )
        except Exception as exc:
            logger.error("Failed to save override: %s", exc)
            QMessageBox.critical(
                self,
                "Override Save Error",
                f"Failed to save override:\n{exc}",
            )

    def apply_month_override(self) -> None:
        employee_id = self._selected_employee_id_from_table(self.detail_table)
        if not employee_id:
            QMessageBox.information(
                self,
                "Month Override",
                "Select an employee row in Month Detail first.",
            )
            return

        row = self.month_table.currentRow()
        if row < 0 or not self.month_table.item(row, 0):
            QMessageBox.information(
                self,
                "Month Override",
                "Select a month first.",
            )
            return

        month = int(self.month_table.item(row, 0).text())
        self._save_override("month", month, employee_id)
        self._load_month_employee_detail(int(self.year_spin.value()), month)
        self.load_quarter_verification()

    def apply_quarter_override(self) -> None:
        employee_id = self._selected_employee_id_from_table(self.quarter_table)
        if not employee_id:
            QMessageBox.information(
                self,
                "Quarter Override",
                "Select an employee row in Quarterly Verification first.",
            )
            return

        quarter = int(self.quarter_combo.currentIndex() + 1)
        self._save_override("quarter", quarter, employee_id)
        self.load_quarter_verification()

    def clear_selected_override(self) -> None:
        year = int(self.year_spin.value())
        month_row = self.month_table.currentRow()
        month = (
            int(self.month_table.item(month_row, 0).text())
            if month_row >= 0 and self.month_table.item(month_row, 0)
            else None
        )
        quarter = int(self.quarter_combo.currentIndex() + 1)

        employee_id = self._selected_employee_id_from_table(self.detail_table)
        scope_kind = "month"
        scope_value = month
        if not employee_id:
            employee_id = self._selected_employee_id_from_table(self.quarter_table)
            scope_kind = "quarter"
            scope_value = quarter

        if not employee_id or not scope_value:
            QMessageBox.information(
                self,
                "Clear Override",
                "Select an employee row in Month Detail or Quarter table first.",
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    DELETE FROM payroll_employee_flag_overrides
                    WHERE fiscal_year = %s
                      AND scope_kind = %s
                      AND scope_value = %s
                      AND employee_id = %s
                    """,
                    (year, scope_kind, int(scope_value), int(employee_id)),
                )
            self._set_status(
                f"Cleared {scope_kind} override for employee #{employee_id}."
            )
        except Exception as exc:
            logger.error("Failed to clear override: %s", exc)
            QMessageBox.critical(
                self,
                "Clear Override Error",
                f"Failed to clear override:\n{exc}",
            )

        if month:
            self._load_month_employee_detail(year, month)
        self.load_quarter_verification()

    def _load_cra_calculated_by_month(self, year: int) -> object:
        data = {
            m: {
                "gross": 0.0,
                "cpp_employee": 0.0,
                "cpp_employer": 0.0,
                "ei_employee": 0.0,
                "ei_employer": 0.0,
                "federal": 0.0,
                "provincial": 0.0,
                "tax": 0.0,
                "cra_due": 0.0,
            }
            for m in range(1, 13)
        }

        pay_master_cols = self._get_columns("employee_pay_master")
        if not pay_master_cols:
            return data

        cpp_employer_expr = (
            "COALESCE(epm.cpp_employer, 0)"
            if "cpp_employer" in pay_master_cols
            else "COALESCE(epm.cpp_employee, 0)"
        )
        ei_employer_expr = (
            "COALESCE(epm.ei_employer, 0)"
            if "ei_employer" in pay_master_cols
            else "ROUND(COALESCE(epm.ei_employee, 0) * 1.4, 2)"
        )
        tax_expr = (
            "COALESCE(epm.total_income_tax, 0)"
            if "total_income_tax" in pay_master_cols
            else (
                "COALESCE(epm.federal_tax, 0) + "
                "COALESCE(epm.provincial_tax, 0)"
            )
        )

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT
                        EXTRACT(MONTH FROM pp.pay_date)::int AS rem_month,
                        COALESCE(SUM(epm.gross_pay), 0) AS gross,
                        COALESCE(SUM(epm.cpp_employee), 0) AS cpp_employee,
                        COALESCE(SUM({cpp_employer_expr}), 0) AS cpp_employer,
                        COALESCE(SUM(epm.ei_employee), 0) AS ei_employee,
                        COALESCE(SUM({ei_employer_expr}), 0) AS ei_employer,
                        COALESCE(SUM(epm.federal_tax), 0) AS federal,
                        COALESCE(SUM(epm.provincial_tax), 0) AS provincial,
                        COALESCE(SUM({tax_expr}), 0) AS tax
                    FROM employee_pay_master epm
                    JOIN pay_periods pp ON pp.pay_period_id = epm.pay_period_id
                    WHERE EXTRACT(YEAR FROM pp.pay_date) = %s
                    GROUP BY EXTRACT(MONTH FROM pp.pay_date)
                    """,
                    (year,),
                )
                for row in cur.fetchall():
                    month = int(row[0])
                    gross = self._safe_float(row[1])
                    cpp_employee = self._safe_float(row[2])
                    cpp_employer = self._safe_float(row[3])
                    ei_employee = self._safe_float(row[4])
                    ei_employer = self._safe_float(row[5])
                    federal = self._safe_float(row[6])
                    provincial = self._safe_float(row[7])
                    tax = self._safe_float(row[8])
                    cra_due = (
                        cpp_employee
                        + cpp_employer
                        + ei_employee
                        + ei_employer
                        + tax
                    )
                    data[month] = {
                        "gross": gross,
                        "cpp_employee": cpp_employee,
                        "cpp_employer": cpp_employer,
                        "ei_employee": ei_employee,
                        "ei_employer": ei_employer,
                        "federal": federal,
                        "provincial": provincial,
                        "tax": tax,
                        "cra_due": cra_due,
                    }
        except Exception as exc:
            logger.error(f"Failed loading CRA monthly calculations: {exc}")

        return data

    def _load_cra_payments_by_month(self, year: int) -> object:
        data = {
            m: {"paid": 0.0, "status": "", "reference": "", "row": None}
            for m in range(1, 13)
        }
        cols = self._get_columns("payroll_remittances")
        if not cols:
            return data

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT remittance_month, payment_amount, status,
                    payment_reference,
                           pd7a_statement_amount, payment_date, payment_method,
                           notes,
                           calculated_total_remittance
                    FROM payroll_remittances
                    WHERE fiscal_year = %s
                    ORDER BY remittance_month
                    """,
                    (year,),
                )
                for row in cur.fetchall():
                    month = int(row[0])
                    data[month] = {
                        "paid": self._safe_float(row[1]),
                        "status": row[2] or "",
                        "reference": row[3] or "",
                        "row": {
                            "pd7a_statement_amount": self._safe_float(row[4]),
                            "payment_date": row[5],
                            "payment_method": row[6] or "",
                            "notes": row[7] or "",
                            "calculated_total_remittance": self._safe_float(
                                row[8]
                            ),
                        },
                    }
        except Exception as exc:
            logger.error(f"Failed loading CRA payment rows: {exc}")

        return data

    def _load_wcb_by_month(self, year: int) -> object:
        data = {m: {"due": 0.0, "paid": 0.0} for m in range(1, 13)}
        wcols = self._get_columns("wcb_summary")
        if not {"year", "month"} <= wcols:
            return data

        due_candidates = [
            "wcb_due",
            "wcb_owed",
            "premium_due",
            "assessable_premium",
            "calculated_wcb",
            "amount_due",
        ]
        paid_candidates = [
            "wcb_payment",
            "payment_amount",
            "amount_paid",
            "paid_amount",
        ]

        due_col = next((c for c in due_candidates if c in wcols), None)
        paid_col = next((c for c in paid_candidates if c in wcols), None)

        if not due_col and not paid_col:
            return data

        due_expr = f"COALESCE(SUM({due_col}), 0)" if due_col else "0"
        paid_expr = f"COALESCE(SUM({paid_col}), 0)" if paid_col else "0"

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT month, {due_expr} AS due, {paid_expr} AS paid
                    FROM wcb_summary
                    WHERE year = %s
                    GROUP BY month
                    ORDER BY month
                    """,
                    (year,),
                )
                for month, due, paid in cur.fetchall():
                    m = int(month)
                    due_f = self._safe_float(due)
                    paid_f = self._safe_float(paid)
                    if due_col is None and paid_col is not None:
                        due_f = paid_f
                    data[m] = {"due": due_f, "paid": paid_f}
        except Exception as exc:
            logger.error(f"Failed loading WCB monthly summary: {exc}")

        return data

    def refresh_data(self) -> None:
        year = int(self.year_spin.value())

        cra_calc = self._load_cra_calculated_by_month(year)
        cra_pay = self._load_cra_payments_by_month(year)
        wcb = self._load_wcb_by_month(year)

        self.month_table.setRowCount(12)
        self._month_rows = {}

        total_cra_due = 0.0
        total_cra_paid = 0.0
        total_wcb_due = 0.0
        total_wcb_paid = 0.0

        for idx, month in enumerate(range(1, 13)):
            calc = cra_calc.get(month, {})
            pay = cra_pay.get(month, {})
            wcb_row = wcb.get(month, {})

            cra_due = self._safe_float(calc.get("cra_due"))
            cra_paid = self._safe_float(pay.get("paid"))
            cra_var = cra_due - cra_paid

            wcb_due = self._safe_float(wcb_row.get("due"))
            wcb_paid = self._safe_float(wcb_row.get("paid"))
            wcb_var = wcb_due - wcb_paid

            total_cra_due += cra_due
            total_cra_paid += cra_paid
            total_wcb_due += wcb_due
            total_wcb_paid += wcb_paid

            status = pay.get("status") or (
                "pending" if abs(cra_due) > 0.009 else ""
            )
            reference = pay.get("reference") or ""

            self.month_table.setItem(idx, 0, QTableWidgetItem(f"{month:02d}"))
            self.month_table.setItem(
                idx, 1, QTableWidgetItem(f"${cra_due:,.2f}")
            )
            self.month_table.setItem(
                idx, 2, QTableWidgetItem(f"${cra_paid:,.2f}")
            )
            self.month_table.setItem(
                idx, 3, QTableWidgetItem(f"${cra_var:,.2f}")
            )
            self.month_table.setItem(
                idx, 4, QTableWidgetItem(f"${wcb_due:,.2f}")
            )
            self.month_table.setItem(
                idx, 5, QTableWidgetItem(f"${wcb_paid:,.2f}")
            )
            self.month_table.setItem(
                idx, 6, QTableWidgetItem(f"${wcb_var:,.2f}")
            )
            self.month_table.setItem(idx, 7, QTableWidgetItem(status))
            self.month_table.setItem(idx, 8, QTableWidgetItem(reference))

            self._month_rows[month] = {
                "calc": calc,
                "pay": pay,
                "wcb": wcb_row,
            }

            for col in [3, 6]:
                item = self.month_table.item(idx, col)
                val = cra_var if col == 3 else wcb_var
                if item:
                    if abs(val) < 0.01:
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    elif val > 0:
                        item.setForeground(Qt.GlobalColor.darkYellow)
                    else:
                        item.setForeground(Qt.GlobalColor.red)

        cra_var_total = total_cra_due - total_cra_paid
        wcb_var_total = total_wcb_due - total_wcb_paid

        self.lbl_cra_due.setText(f"${total_cra_due:,.2f}")
        self.lbl_cra_paid.setText(f"${total_cra_paid:,.2f}")
        self.lbl_cra_var.setText(f"${cra_var_total:,.2f}")

        self.lbl_wcb_due.setText(f"${total_wcb_due:,.2f}")
        self.lbl_wcb_paid.setText(f"${total_wcb_paid:,.2f}")
        self.lbl_wcb_var.setText(f"${wcb_var_total:,.2f}")

        self._set_status(f"Loaded remittance dashboard for {year}.")

        if self.month_table.rowCount() > 0:
            self.month_table.selectRow(0)
            self._on_month_selected(0, 0)

        self.load_quarter_verification()

    def _employee_flag_expressions(self) -> tuple[str, str]:
        """Return SQL expressions for EI exemption and owner deferred flags."""
        ecols = self._get_columns("employees")
        if "employee_number" in ecols:
            ei_exempt_expr = (
                "CASE WHEN LOWER(COALESCE(e.employee_number, '')) IN"
                " ('dr09', 'dr100') THEN TRUE ELSE FALSE END"
            )
        else:
            ei_exempt_expr = "FALSE"

        wcols = self._get_columns("employee_work_classifications")
        if {"employee_id", "is_active", "salary_deferred"} <= wcols:
            owner_deferred_expr = (
                "EXISTS ("
                " SELECT 1 FROM employee_work_classifications wc"
                " WHERE wc.employee_id = e.employee_id"
                "   AND COALESCE(wc.is_active, TRUE) = TRUE"
                "   AND COALESCE(wc.salary_deferred, 0) > 0"
                ")"
            )
        else:
            owner_deferred_expr = "FALSE"

        return ei_exempt_expr, owner_deferred_expr

    def _load_month_employee_detail(self, year: int, month: int) -> None:
        self.detail_table.setRowCount(0)
        pay_master_cols = self._get_columns("employee_pay_master")
        if not pay_master_cols:
            return

        cpp_employer_expr = (
            "COALESCE(epm.cpp_employer, 0)"
            if "cpp_employer" in pay_master_cols
            else "COALESCE(epm.cpp_employee, 0)"
        )
        ei_employer_expr = (
            "COALESCE(epm.ei_employer, 0)"
            if "ei_employer" in pay_master_cols
            else "ROUND(COALESCE(epm.ei_employee, 0) * 1.4, 2)"
        )
        tax_expr = (
            "COALESCE(epm.total_income_tax, 0)"
            if "total_income_tax" in pay_master_cols
            else (
                "COALESCE(epm.federal_tax, 0) + "
                "COALESCE(epm.provincial_tax, 0)"
            )
        )

        ecols = self._get_columns("employees")
        if "full_name" in ecols:
            name_expr = "COALESCE(e.full_name, '')"
        elif {"first_name", "last_name"} <= ecols:
            name_expr = (
                "TRIM(COALESCE(e.first_name, '') || "
                "' ' || COALESCE(e.last_name, ''))"
            )
        else:
            name_expr = "('EMP ' || e.employee_id::text)"

        ei_exempt_expr, owner_deferred_expr = self._employee_flag_expressions()

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    WITH month_pay AS (
                        SELECT
                            epm.employee_id,
                            COALESCE(MAX(pp.period_number), 0) AS period_number,
                            COALESCE(SUM(epm.gross_pay), 0) AS gross,
                            COALESCE(SUM(epm.cpp_employee), 0) AS cpp_employee,
                            COALESCE(SUM(epm.ei_employee), 0) AS ei_employee,
                            COALESCE(SUM({tax_expr}), 0) AS tax,
                            COALESCE(SUM(epm.cpp_employee), 0)
                                + COALESCE(SUM({cpp_employer_expr}), 0)
                                + COALESCE(SUM(epm.ei_employee), 0)
                                + COALESCE(SUM({ei_employer_expr}), 0)
                                + COALESCE(SUM({tax_expr}), 0) AS cra_due,
                            COALESCE(SUM(epm.net_pay), 0) AS net_pay,
                            COUNT(*) AS row_count
                        FROM employee_pay_master epm
                        JOIN pay_periods pp ON pp.pay_period_id = epm.pay_period_id
                        WHERE EXTRACT(YEAR FROM pp.pay_date) = %s
                          AND EXTRACT(MONTH FROM pp.pay_date) = %s
                        GROUP BY epm.employee_id
                    )
                    SELECT
                        e.employee_id,
                        {name_expr} AS employee_name,
                        COALESCE(mp.period_number, 0) AS period_number,
                        COALESCE(mp.gross, 0) AS gross,
                        COALESCE(mp.cpp_employee, 0) AS cpp_employee,
                        COALESCE(mp.ei_employee, 0) AS ei_employee,
                        COALESCE(mp.tax, 0) AS tax,
                        COALESCE(mp.cra_due, 0) AS cra_due,
                        COALESCE(mp.net_pay, 0) AS net_pay,
                        CASE WHEN COALESCE(mp.row_count, 0) = 0
                             THEN 'NONE'
                             ELSE 'WORKED' END AS work_status,
                        {ei_exempt_expr} AS ei_exempt,
                        {owner_deferred_expr} AS owner_deferred
                    FROM employees e
                    LEFT JOIN month_pay mp ON mp.employee_id = e.employee_id
                    WHERE COALESCE(e.employment_status, 'active') <> 'inactive'
                    ORDER BY work_status DESC, employee_name
                    """,
                    (year, month),
                )
                rows = cur.fetchall()
        except Exception as exc:
            logger.error(f"Failed loading month employee detail: {exc}")
            return

        overrides = self._load_overrides(year, "month", month)

        self.detail_table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            (
                employee_id,
                name,
                period,
                gross,
                cpp_emp,
                ei_emp,
                tax,
                cra_due,
                net_pay,
                work_status,
                ei_exempt,
                owner_deferred,
            ) = row

            override = overrides.get(int(employee_id))
            if override:
                if override.get("work_status_override"):
                    work_status = str(override["work_status_override"])
                if override.get("ei_exempt_override") is not None:
                    ei_exempt = bool(override["ei_exempt_override"])
                if override.get("owner_deferred_override") is not None:
                    owner_deferred = bool(override["owner_deferred_override"])

            gross_f = self._safe_float(gross)
            cpp_f = self._safe_float(cpp_emp)
            ei_f = self._safe_float(ei_emp)
            tax_f = self._safe_float(tax)
            cra_f = self._safe_float(cra_due)
            net_f = self._safe_float(net_pay)

            if str(work_status or "").upper() == "NONE":
                gross_f = cpp_f = ei_f = tax_f = cra_f = net_f = 0.0
            elif ei_exempt:
                cra_f = max(0.0, cra_f - (ei_f * 2.4))
                ei_f = 0.0

            flags = []
            if ei_exempt:
                flags.append("EI_EXEMPT")
            if owner_deferred:
                flags.append("OWNER_DEFERRED")
            if override:
                flags.append("OVERRIDE")
                if override.get("note"):
                    flags.append(f"NOTE:{override.get('note')}")
            name_item = QTableWidgetItem(str(name or ""))
            name_item.setData(Qt.ItemDataRole.UserRole, int(employee_id))
            self.detail_table.setItem(idx, 0, name_item)
            self.detail_table.setItem(
                idx,
                1,
                QTableWidgetItem(
                    f"P{int(period):02d}" if int(period or 0) else ""
                ),
            )
            self.detail_table.setItem(
                idx, 2, QTableWidgetItem(f"${gross_f:,.2f}")
            )
            self.detail_table.setItem(
                idx, 3, QTableWidgetItem(f"${cpp_f:,.2f}")
            )
            self.detail_table.setItem(
                idx, 4, QTableWidgetItem(f"${ei_f:,.2f}")
            )
            self.detail_table.setItem(
                idx, 5, QTableWidgetItem(f"${tax_f:,.2f}")
            )
            self.detail_table.setItem(
                idx, 6, QTableWidgetItem(f"${cra_f:,.2f}")
            )
            self.detail_table.setItem(
                idx, 7, QTableWidgetItem(f"${net_f:,.2f}")
            )
            self.detail_table.setItem(
                idx, 8, QTableWidgetItem(str(work_status or ""))
            )
            self.detail_table.setItem(
                idx, 9, QTableWidgetItem(", ".join(flags) if flags else "-")
            )

    def load_quarter_verification(self) -> None:
        year = int(self.year_spin.value())
        quarter = int(self.quarter_combo.currentIndex() + 1)
        month_start = (quarter - 1) * 3 + 1
        month_end = month_start + 2

        pay_master_cols = self._get_columns("employee_pay_master")
        if not pay_master_cols:
            self.quarter_table.setRowCount(0)
            return

        cpp_employer_expr = (
            "COALESCE(epm.cpp_employer, 0)"
            if "cpp_employer" in pay_master_cols
            else "COALESCE(epm.cpp_employee, 0)"
        )
        ei_employer_expr = (
            "COALESCE(epm.ei_employer, 0)"
            if "ei_employer" in pay_master_cols
            else "ROUND(COALESCE(epm.ei_employee, 0) * 1.4, 2)"
        )
        tax_expr = (
            "COALESCE(epm.total_income_tax, 0)"
            if "total_income_tax" in pay_master_cols
            else (
                "COALESCE(epm.federal_tax, 0) + "
                "COALESCE(epm.provincial_tax, 0)"
            )
        )

        ecols = self._get_columns("employees")
        if "full_name" in ecols:
            name_expr = "COALESCE(e.full_name, '')"
        elif {"first_name", "last_name"} <= ecols:
            name_expr = (
                "TRIM(COALESCE(e.first_name, '') || "
                "' ' || COALESCE(e.last_name, ''))"
            )
        else:
            name_expr = "('EMP ' || e.employee_id::text)"

        ei_exempt_expr, owner_deferred_expr = self._employee_flag_expressions()

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    WITH q_pay AS (
                        SELECT
                            epm.employee_id,
                            COALESCE(SUM(epm.gross_pay), 0) AS gross,
                            COALESCE(SUM(epm.cpp_employee), 0) AS cpp_employee,
                            COALESCE(SUM(epm.ei_employee), 0) AS ei_employee,
                            COALESCE(SUM({tax_expr}), 0) AS tax,
                            COALESCE(SUM(epm.cpp_employee), 0)
                                + COALESCE(SUM({cpp_employer_expr}), 0)
                                + COALESCE(SUM(epm.ei_employee), 0)
                                + COALESCE(SUM({ei_employer_expr}), 0)
                                + COALESCE(SUM({tax_expr}), 0) AS cra_due,
                            COUNT(*) AS row_count
                        FROM employee_pay_master epm
                        JOIN pay_periods pp ON pp.pay_period_id = epm.pay_period_id
                        WHERE EXTRACT(YEAR FROM pp.pay_date) = %s
                          AND EXTRACT(MONTH FROM pp.pay_date) BETWEEN %s AND %s
                        GROUP BY epm.employee_id
                    )
                    SELECT
                        e.employee_id,
                        {name_expr} AS employee_name,
                        COALESCE(q.gross, 0) AS gross,
                        COALESCE(q.cpp_employee, 0) AS cpp_employee,
                        COALESCE(q.ei_employee, 0) AS ei_employee,
                        COALESCE(q.tax, 0) AS tax,
                        COALESCE(q.cra_due, 0) AS cra_due,
                        CASE WHEN COALESCE(q.row_count, 0) = 0
                             THEN 'NONE'
                             ELSE 'WORKED' END AS work_status,
                        {ei_exempt_expr} AS ei_exempt,
                        {owner_deferred_expr} AS owner_deferred
                    FROM employees e
                    LEFT JOIN q_pay q ON q.employee_id = e.employee_id
                    WHERE COALESCE(e.employment_status, 'active') <> 'inactive'
                    ORDER BY work_status DESC, employee_name
                    """,
                    (year, month_start, month_end),
                )
                rows = cur.fetchall()
        except Exception as exc:
            logger.error(f"Failed loading quarterly verification: {exc}")
            self.quarter_table.setRowCount(0)
            return

        overrides = self._load_overrides(year, "quarter", quarter)

        self.quarter_table.setRowCount(len(rows))

        q_cpp = 0.0
        q_ei = 0.0
        q_tax = 0.0
        q_cra = 0.0
        for idx, row in enumerate(rows):
            (
                employee_id,
                name,
                gross,
                cpp_emp,
                ei_emp,
                tax,
                cra_due,
                work_status,
                ei_exempt,
                owner_deferred,
            ) = row

            override = overrides.get(int(employee_id))
            if override:
                if override.get("work_status_override"):
                    work_status = str(override["work_status_override"])
                if override.get("ei_exempt_override") is not None:
                    ei_exempt = bool(override["ei_exempt_override"])
                if override.get("owner_deferred_override") is not None:
                    owner_deferred = bool(override["owner_deferred_override"])

            gross_f = self._safe_float(gross)
            cpp_f = self._safe_float(cpp_emp)
            ei_f = self._safe_float(ei_emp)
            tax_f = self._safe_float(tax)
            cra_f = self._safe_float(cra_due)

            if str(work_status or "").upper() == "NONE":
                gross_f = cpp_f = ei_f = tax_f = cra_f = 0.0
            elif ei_exempt:
                cra_f = max(0.0, cra_f - (ei_f * 2.4))
                ei_f = 0.0

            flags = []
            if ei_exempt:
                flags.append("EI_EXEMPT")
            if owner_deferred:
                flags.append("OWNER_DEFERRED")
            if override:
                flags.append("OVERRIDE")
                if override.get("note"):
                    flags.append(f"NOTE:{override.get('note')}")

            q_cpp += cpp_f
            q_ei += ei_f
            q_tax += tax_f
            q_cra += cra_f

            q_name_item = QTableWidgetItem(str(name or ""))
            q_name_item.setData(Qt.ItemDataRole.UserRole, int(employee_id))
            self.quarter_table.setItem(idx, 0, q_name_item)
            self.quarter_table.setItem(idx, 1, QTableWidgetItem(f"${gross_f:,.2f}"))
            self.quarter_table.setItem(idx, 2, QTableWidgetItem(f"${cpp_f:,.2f}"))
            self.quarter_table.setItem(idx, 3, QTableWidgetItem(f"${ei_f:,.2f}"))
            self.quarter_table.setItem(idx, 4, QTableWidgetItem(f"${tax_f:,.2f}"))
            self.quarter_table.setItem(idx, 5, QTableWidgetItem(f"${cra_f:,.2f}"))
            self.quarter_table.setItem(idx, 6, QTableWidgetItem(str(work_status or "")))
            self.quarter_table.setItem(
                idx,
                7,
                QTableWidgetItem(", ".join(flags) if flags else "-"),
            )

        # Quarter WCB derived from the already-loaded monthly map.
        q_wcb = 0.0
        for m in range(month_start, month_end + 1):
            q_wcb += self._safe_float(
                self._month_rows.get(m, {}).get("wcb", {}).get("due")
            )

        self.q_cpp_total.setText(f"CPP: ${q_cpp:,.2f}")
        self.q_ei_total.setText(f"EI: ${q_ei:,.2f}")
        self.q_tax_total.setText(f"Tax: ${q_tax:,.2f}")
        self.q_cra_total.setText(f"CRA Due: ${q_cra:,.2f}")
        self.q_wcb_total.setText(f"WCB Due: ${q_wcb:,.2f}")

    def print_month_contributions(self) -> None:
        month_row = self.month_table.currentRow()
        month_text = "All Months"
        if month_row >= 0 and self.month_table.item(month_row, 0):
            month_text = f"Month {self.month_table.item(month_row, 0).text()}"
        title = (
            f"Payroll Contribution Summary {self.year_spin.value()} - {month_text}"
        )
        PrintExportHelper.print_table(self.detail_table, title, self)

    def print_quarter_contributions(self) -> None:
        quarter = self.quarter_combo.currentIndex() + 1
        title = f"Payroll Contribution Summary {self.year_spin.value()} - Q{quarter}"
        PrintExportHelper.print_table(self.quarter_table, title, self)

    def print_employee_flags(self) -> None:
        quarter = self.quarter_combo.currentIndex() + 1
        title = f"Employee Status Flags {self.year_spin.value()} - Q{quarter}"
        PrintExportHelper.print_table(self.quarter_table, title, self)

    def _on_month_selected(self, row: int, _column: int) -> None:
        month_item = self.month_table.item(row, 0)
        if not month_item:
            return
        try:
            month = int((month_item.text() or "0").strip())
        except ValueError:
            return

        year = int(self.year_spin.value())
        self.sel_month_label.setText(f"{year}-{month:02d}")

        month_data = self._month_rows.get(month, {})
        calc = month_data.get("calc", {})
        pay = month_data.get("pay", {})
        row_data = pay.get("row") if isinstance(pay, dict) else None

        self.payment_amount_spin.setValue(
            self._safe_float(pay.get("paid") if isinstance(pay, dict) else 0.0)
        )
        if row_data and row_data.get("payment_date"):
            dt = row_data["payment_date"]
            self.payment_date_edit.setDate(QDate(dt.year, dt.month, dt.day))
        else:
            # CRA due date is 15th of following month
            due_year = year + 1 if month == 12 else year
            due_month = 1 if month == 12 else month + 1
            self.payment_date_edit.setDate(QDate(due_year, due_month, 15))

        method = row_data.get("payment_method") if row_data else ""
        method_idx = self.payment_method_combo.findText(method or "")
        self.payment_method_combo.setCurrentIndex(
            method_idx if method_idx >= 0 else 0
        )

        self.reference_input.setText(
            pay.get("reference") if isinstance(pay, dict) else ""
        )
        self.pd7a_amount_spin.setValue(
            self._safe_float(
                row_data.get("pd7a_statement_amount")
                if row_data
                else calc.get("cra_due")
            )
        )

        status = pay.get("status") if isinstance(pay, dict) else ""
        status_idx = self.status_combo.findText(status or "pending")
        self.status_combo.setCurrentIndex(status_idx if status_idx >= 0 else 0)
        self.notes_edit.setPlainText(
            (row_data.get("notes") if row_data else "") or ""
        )

        self._load_month_employee_detail(year, month)

    def focus_remittance_id(self, remittance_id: int) -> bool:
        """Deep-link helper: jump to a remittance record by id."""
        try:
            rid = int(remittance_id)
        except (TypeError, ValueError):
            return False

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT fiscal_year, remittance_month
                    FROM payroll_remittances
                    WHERE remittance_id = %s
                    LIMIT 1
                    """,
                    (rid,),
                )
                row = cur.fetchone()
            if not row:
                return False

            fiscal_year, rem_month = int(row[0]), int(row[1])
            self.year_spin.setValue(fiscal_year)
            self.refresh_data()

            for i in range(self.month_table.rowCount()):
                month_item = self.month_table.item(i, 0)
                if not month_item:
                    continue
                try:
                    table_month = int((month_item.text() or "0").strip())
                except ValueError:
                    continue
                if table_month == rem_month:
                    self.month_table.setCurrentCell(i, 0)
                    self.month_table.selectRow(i)
                    self._on_month_selected(i, 0)
                    self._set_status(
                        f"Opened remittance #{rid}"
                        f"({fiscal_year}-{rem_month:02d})."
                    )
                    return True
        except Exception as exc:
            logger.error(f"Failed to focus remittance_id {rid}: {exc}")

        return False

    def sync_selected_month(self) -> None:
        row = self.month_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Sync", "Select a month first.")
            return

        month_item = self.month_table.item(row, 0)
        if not month_item:
            return

        month = int(month_item.text())
        year = int(self.year_spin.value())
        calc = self._month_rows.get(month, {}).get("calc", {})

        due_date = (
            date(year + 1, 1, 15) if month == 12 else date(year, month + 1, 15)
        )

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO payroll_remittances (
                        fiscal_year, remittance_month,
                        calculated_gross, calculated_cpp_employee,
                        calculated_cpp_employer,
                        calculated_ei_employee, calculated_ei_employer,
                        calculated_federal_tax, calculated_provincial_tax,
                        calculated_total_remittance, due_date, variance,
                        updated_at, created_by
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, NOW(), 'desktop_app'
                    )
                    ON CONFLICT (fiscal_year, remittance_month) DO UPDATE SET
                        calculated_gross = EXCLUDED.calculated_gross,
                        calculated_cpp_employee =
                        EXCLUDED.calculated_cpp_employee,
                        calculated_cpp_employer =
                        EXCLUDED.calculated_cpp_employer,
                        calculated_ei_employee =
                        EXCLUDED.calculated_ei_employee,
                        calculated_ei_employer =
                        EXCLUDED.calculated_ei_employer,
                        calculated_federal_tax =
                        EXCLUDED.calculated_federal_tax,
                        calculated_provincial_tax =
                        EXCLUDED.calculated_provincial_tax,
                        calculated_total_remittance =
                        EXCLUDED.calculated_total_remittance,
                        due_date = EXCLUDED.due_date,
                        variance = EXCLUDED.variance,
                        updated_at = NOW()
                    """,
                    (
                        year,
                        month,
                        self._safe_float(calc.get("gross")),
                        self._safe_float(calc.get("cpp_employee")),
                        self._safe_float(calc.get("cpp_employer")),
                        self._safe_float(calc.get("ei_employee")),
                        self._safe_float(calc.get("ei_employer")),
                        self._safe_float(calc.get("federal")),
                        self._safe_float(calc.get("provincial")),
                        self._safe_float(calc.get("cra_due")),
                        due_date,
                        self._safe_float(calc.get("cra_due")),
                    ),
                )
            self.refresh_data()
            self._set_status(
                f"Synced calculated totals for {year}-{month:02d}."
            )
        except Exception as exc:
            logger.error(f"Failed to sync selected month: {exc}")
            QMessageBox.critical(
                self, "Sync Error", f"Failed to sync month:\n{exc}"
            )

    def generate_year_remittances(self) -> None:
        year = int(self.year_spin.value())
        cra_calc = self._load_cra_calculated_by_month(year)

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                upserted = 0
                for month in range(1, 13):
                    calc = cra_calc.get(month, {})
                    due_date = (
                        date(year + 1, 1, 15)
                        if month == 12
                        else date(year, month + 1, 15)
                    )
                    cra_due = self._safe_float(calc.get("cra_due"))

                    cur.execute(
                        """
                        INSERT INTO payroll_remittances (
                            fiscal_year, remittance_month,
                            calculated_gross, calculated_cpp_employee,
                            calculated_cpp_employer,
                            calculated_ei_employee, calculated_ei_employer,
                            calculated_federal_tax, calculated_provincial_tax,
                            calculated_total_remittance, due_date, variance,
                            updated_at, created_by
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s,
                            NOW(), 'desktop_app'
                        )
                        ON CONFLICT (fiscal_year,
                        remittance_month) DO UPDATE SET
                            calculated_gross = EXCLUDED.calculated_gross,
                            calculated_cpp_employee =
                            EXCLUDED.calculated_cpp_employee,
                            calculated_cpp_employer =
                            EXCLUDED.calculated_cpp_employer,
                            calculated_ei_employee =
                            EXCLUDED.calculated_ei_employee,
                            calculated_ei_employer =
                            EXCLUDED.calculated_ei_employer,
                            calculated_federal_tax =
                            EXCLUDED.calculated_federal_tax,
                            calculated_provincial_tax =
                            EXCLUDED.calculated_provincial_tax,
                            calculated_total_remittance =
                            EXCLUDED.calculated_total_remittance,
                            due_date = EXCLUDED.due_date,
                            variance = EXCLUDED.calculated_total_remittance -
                            COALESCE(payroll_remittances.payment_amount, 0),
                            updated_at = NOW()
                        """,
                        (
                            year,
                            month,
                            self._safe_float(calc.get("gross")),
                            self._safe_float(calc.get("cpp_employee")),
                            self._safe_float(calc.get("cpp_employer")),
                            self._safe_float(calc.get("ei_employee")),
                            self._safe_float(calc.get("ei_employer")),
                            self._safe_float(calc.get("federal")),
                            self._safe_float(calc.get("provincial")),
                            cra_due,
                            due_date,
                            cra_due,
                        ),
                    )
                    upserted += 1

            self.refresh_data()
            self._set_status(
                f"Generated payroll remittances for {year} ({upserted}"
                f"months)."
            )
        except Exception as exc:
            logger.error(f"Failed to generate year remittances: {exc}")
            QMessageBox.critical(
                self,
                "Generate Error",
                f"Failed to generate remittances:\n{exc}",
            )

    def _count_month_employees(self, year: int, month: int) -> int:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT epm.employee_id)
                    FROM employee_pay_master epm
                    JOIN pay_periods pp ON pp.pay_period_id = epm.pay_period_id
                    WHERE EXTRACT(YEAR FROM pp.pay_date) = %s
                      AND EXTRACT(MONTH FROM pp.pay_date) = %s
                    """,
                    (year, month),
                )
                row = cur.fetchone()
                return int(row[0] or 0) if row else 0
        except Exception:
            return 0

    def generate_pd7a_returns(self) -> None:
        year = int(self.year_spin.value())
        self._ensure_cra_pd7a_returns_table()

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    SELECT
                        remittance_month,
                        calculated_gross,
                        calculated_cpp_employee,
                        calculated_cpp_employer,
                        calculated_ei_employee,
                        calculated_ei_employer,
                        calculated_federal_tax,
                        calculated_provincial_tax,
                        calculated_total_remittance,
                        due_date,
                        payment_amount,
                        payment_date,
                        variance,
                        status,
                        notes,
                        pd7a_statement_amount
                    FROM payroll_remittances
                    WHERE fiscal_year = %s
                    ORDER BY remittance_month
                    """,
                    (year,),
                )
                rows = cur.fetchall()

                if not rows:
                    QMessageBox.information(
                        self,
                        "Generate PD7A",
                        f"No payroll remittance rows found for {year}."
                        f"Generate remittances first.",
                    )
                    return

                upserted = 0
                for row in rows:
                    month = int(row[0])
                    gross = self._safe_float(row[1])
                    cpp_emp = self._safe_float(row[2])
                    cpp_empr = self._safe_float(row[3])
                    ei_emp = self._safe_float(row[4])
                    ei_empr = self._safe_float(row[5])
                    tax_fed = self._safe_float(row[6])
                    tax_prov = self._safe_float(row[7])
                    total_due = self._safe_float(row[8])
                    due_dt = row[9]
                    payment_amount = self._safe_float(row[10])
                    payment_date = row[11]
                    variance = self._safe_float(row[12])
                    status = (row[13] or "").strip().lower()
                    notes = row[14] or ""
                    pd7a_amount = self._safe_float(row[15])

                    adjusted = pd7a_amount if pd7a_amount > 0 else total_due
                    employee_count = self._count_month_employees(year, month)

                    cur.execute(
                        """
                        INSERT INTO cra_pd7a_returns (
                            reporting_year, reporting_month,
                            employee_count,
                            total_gross_payroll,
                            cpp_pensionable_earnings,
                            cpp_employee_contributions,
                            cpp_employer_contributions,
                            cpp_total,
                            ei_insurable_earnings,
                            ei_employee_premiums,
                            ei_employer_premiums,
                            ei_total,
                            income_tax_deducted,
                            total_remittance_due,
                            previous_overpayment,
                            previous_underpayment,
                            adjusted_remittance,
                            is_calculated,
                            is_submitted,
                            submission_date,
                            due_date,
                            variance_from_payment,
                            calculated_at,
                            updated_at,
                            notes
                        ) VALUES (
                            %s, %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            TRUE,
                            %s,
                            %s,
                            %s,
                            %s,
                            NOW(),
                            NOW(),
                            %s
                        )
                        ON CONFLICT (reporting_year,
                        reporting_month) DO UPDATE SET
                            employee_count = EXCLUDED.employee_count,
                            total_gross_payroll = EXCLUDED.total_gross_payroll,
                            cpp_pensionable_earnings =
                            EXCLUDED.cpp_pensionable_earnings,
                            cpp_employee_contributions =
                            EXCLUDED.cpp_employee_contributions,
                            cpp_employer_contributions =
                            EXCLUDED.cpp_employer_contributions,
                            cpp_total = EXCLUDED.cpp_total,
                            ei_insurable_earnings =
                            EXCLUDED.ei_insurable_earnings,
                            ei_employee_premiums =
                            EXCLUDED.ei_employee_premiums,
                            ei_employer_premiums =
                            EXCLUDED.ei_employer_premiums,
                            ei_total = EXCLUDED.ei_total,
                            income_tax_deducted = EXCLUDED.income_tax_deducted,
                            total_remittance_due =
                            EXCLUDED.total_remittance_due,
                            adjusted_remittance = EXCLUDED.adjusted_remittance,
                            is_calculated = TRUE,
                            is_submitted = EXCLUDED.is_submitted,
                            submission_date = EXCLUDED.submission_date,
                            due_date = EXCLUDED.due_date,
                            variance_from_payment =
                            EXCLUDED.variance_from_payment,
                            updated_at = NOW(),
                            notes = EXCLUDED.notes
                        """,
                        (
                            year,
                            month,
                            employee_count,
                            gross,
                            gross,
                            cpp_emp,
                            cpp_empr,
                            cpp_emp + cpp_empr,
                            gross,
                            ei_emp,
                            ei_empr,
                            ei_emp + ei_empr,
                            tax_fed + tax_prov,
                            total_due,
                            0.0,
                            0.0,
                            adjusted,
                            status
                            in {"submitted", "filed", "paid", "reconciled"},
                            payment_date,
                            due_dt,
                            (
                                variance
                                if abs(variance) > 0.0001
                                else (total_due - payment_amount)
                            ),
                            notes,
                        ),
                    )
                    upserted += 1

            self._set_status(
                f"Generated PD7A returns for {year} ({upserted} months)."
            )
            QMessageBox.information(
                self,
                "PD7A Generated",
                f"Generated/updated {upserted} PD7A month rows for {year}.",
            )
        except Exception as exc:
            logger.error(f"Failed to generate PD7A returns: {exc}")
            QMessageBox.critical(
                self,
                "Generate PD7A Error",
                f"Failed to generate PD7A returns:\n{exc}",
            )

    def save_selected_month(self) -> None:
        row = self.month_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Save", "Select a month first.")
            return

        month_item = self.month_table.item(row, 0)
        if not month_item:
            return

        month = int(month_item.text())
        year = int(self.year_spin.value())
        calc = self._month_rows.get(month, {}).get("calc", {})
        calc_due = self._safe_float(calc.get("cra_due"))

        pay_date = self.payment_date_edit.date().toPyDate()
        payment_amount = float(self.payment_amount_spin.value())
        pd7a_amount = float(self.pd7a_amount_spin.value())
        status = self.status_combo.currentText().strip() or "pending"
        reference = self.reference_input.text().strip()
        method = self.payment_method_combo.currentText().strip()
        notes = self.notes_edit.toPlainText().strip()

        due_date = (
            date(year + 1, 1, 15) if month == 12 else date(year, month + 1, 15)
        )
        variance = calc_due - payment_amount
        is_late = bool(pay_date and pay_date > due_date)
        reconciled = abs(variance) < 0.01 and pd7a_amount > 0

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO payroll_remittances (
                        fiscal_year, remittance_month,
                        calculated_gross, calculated_cpp_employee,
                        calculated_cpp_employer,
                        calculated_ei_employee, calculated_ei_employer,
                        calculated_federal_tax, calculated_provincial_tax,
                        calculated_total_remittance,
                        due_date, payment_date, payment_amount,
                        payment_method, payment_reference,
                        pd7a_statement_amount, variance, reconciled,
                        status, is_late, notes, updated_at, created_by
                    ) VALUES (
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, NOW(), 'desktop_app'
                    )
                    ON CONFLICT (fiscal_year, remittance_month) DO UPDATE SET
                        calculated_gross = EXCLUDED.calculated_gross,
                        calculated_cpp_employee =
                        EXCLUDED.calculated_cpp_employee,
                        calculated_cpp_employer =
                        EXCLUDED.calculated_cpp_employer,
                        calculated_ei_employee =
                        EXCLUDED.calculated_ei_employee,
                        calculated_ei_employer =
                        EXCLUDED.calculated_ei_employer,
                        calculated_federal_tax =
                        EXCLUDED.calculated_federal_tax,
                        calculated_provincial_tax =
                        EXCLUDED.calculated_provincial_tax,
                        calculated_total_remittance =
                        EXCLUDED.calculated_total_remittance,
                        due_date = EXCLUDED.due_date,
                        payment_date = EXCLUDED.payment_date,
                        payment_amount = EXCLUDED.payment_amount,
                        payment_method = EXCLUDED.payment_method,
                        payment_reference = EXCLUDED.payment_reference,
                        pd7a_statement_amount = EXCLUDED.pd7a_statement_amount,
                        variance = EXCLUDED.variance,
                        reconciled = EXCLUDED.reconciled,
                        status = EXCLUDED.status,
                        is_late = EXCLUDED.is_late,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                    """,
                    (
                        year,
                        month,
                        self._safe_float(calc.get("gross")),
                        self._safe_float(calc.get("cpp_employee")),
                        self._safe_float(calc.get("cpp_employer")),
                        self._safe_float(calc.get("ei_employee")),
                        self._safe_float(calc.get("ei_employer")),
                        self._safe_float(calc.get("federal")),
                        self._safe_float(calc.get("provincial")),
                        calc_due,
                        due_date,
                        pay_date,
                        payment_amount,
                        method or None,
                        reference or None,
                        pd7a_amount,
                        variance,
                        reconciled,
                        status,
                        is_late,
                        notes or None,
                    ),
                )

            self.refresh_data()
            self._set_status(
                f"Saved remittance record for {year}-{month:02d}."
            )
        except Exception as exc:
            logger.error(f"Failed saving remittance month: {exc}")
            QMessageBox.critical(
                self, "Save Error", f"Failed to save remittance:\n{exc}"
            )
