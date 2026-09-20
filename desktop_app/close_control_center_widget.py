"""
Close Control Center Widget
Operational daily/month-end control checks for limousine + employee workflows.
"""

import logging
from datetime import date

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class CloseControlCenterWidget(QWidget):
    """Daily/month-end operational controls dashboard."""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self.refresh_checks()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Close Control Center")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Daily/month-end exceptions for payroll, receipts, banking, and remittances"
        )
        subtitle.setStyleSheet("color: #475569;")
        layout.addWidget(subtitle)

        top_row = QHBoxLayout()
        self.summary_label = QLabel("Loading checks...")
        self.summary_label.setStyleSheet("font-weight: bold;")

        refresh_btn = QPushButton("Refresh Checks")
        refresh_btn.clicked.connect(self.refresh_checks)

        top_row.addWidget(self.summary_label)
        top_row.addStretch(1)
        top_row.addWidget(refresh_btn)
        layout.addLayout(top_row)

        action_row = QHBoxLayout()
        self.open_source_btn = QPushButton("Open Source For Selected Check")
        self.open_source_btn.clicked.connect(self.open_selected_check_source)
        action_row.addWidget(self.open_source_btn)

        self.auto_fix_btn = QPushButton("Run Auto-Fix (Selected)")
        self.auto_fix_btn.setToolTip(
            "Runs safe automatic fixes where supported for the selected check."
        )
        self.auto_fix_btn.clicked.connect(self.run_selected_check_auto_fix)
        action_row.addWidget(self.auto_fix_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Check", "Status", "Count", "Exposure", "Details"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(lambda _r, _c: self.open_selected_check_source())
        layout.addWidget(self.table)

    def _main_window(self):
        w = self.window()
        return w if w is not None else self.parent()

    def _find_child_widget_by_class_name(self, root, class_name: str):
        if root is None:
            return None
        for child in root.findChildren(QWidget):
            if type(child).__name__ == class_name:
                return child
        return None

    def _apply_source_handoff(self, check_name: str, main) -> None:
        """Apply check-specific filters in the destination tab when possible."""
        try:
            if check_name == "Staff Work Completed Not Posted":
                w = getattr(main, "employee_work_schedule_widget", None)
                if w is not None:
                    if hasattr(w, "filter_unposted_only"):
                        w.filter_unposted_only.setChecked(True)
                    if hasattr(w, "filter_completed_only"):
                        w.filter_completed_only.setChecked(True)
                    if hasattr(w, "_load_rows"):
                        w._load_rows()
                return

            if check_name == "Receipts Review Queue":
                tab = getattr(main, "accounting_parent_tabs", None)
                current = tab.currentWidget() if tab is not None else None
                w = self._find_child_widget_by_class_name(current, "EnhancedReceiptsManager")
                if w is not None:
                    if hasattr(w, "show_unverified"):
                        w.show_unverified.setChecked(True)
                    if hasattr(w, "review_status_filter"):
                        idx = w.review_status_filter.findData("UNREVIEWED")
                        if idx >= 0:
                            w.review_status_filter.setCurrentIndex(idx)
                    if hasattr(w, "_load_receipts"):
                        w._load_receipts()
                return

            if check_name == "Unreconciled Banking Transactions":
                w = getattr(main, "enhanced_banking_manager", None)
                if w is not None:
                    if hasattr(w, "_clear_filters"):
                        w._clear_filters()
                    if hasattr(w, "show_unreconciled"):
                        w.show_unreconciled.setChecked(True)
                    if hasattr(w, "_load_transactions"):
                        w._load_transactions()
                return

            if check_name == "Orphaned Client Payments":
                tab = getattr(main, "accounting_parent_tabs", None)
                current = tab.currentWidget() if tab is not None else None
                w = self._find_child_widget_by_class_name(current, "PaymentLinkerWidget")
                if w is not None and hasattr(w, "load_orphaned_payments"):
                    w.load_orphaned_payments()
                return

            if check_name == "Overdue Vendor Payables":
                tab = getattr(main, "accounting_parent_tabs", None)
                current = tab.currentWidget() if tab is not None else None
                w = self._find_child_widget_by_class_name(current, "VendorInvoiceManager")
                if w is not None:
                    if hasattr(w, "filter_status"):
                        idx = w.filter_status.findText("Unpaid")
                        if idx >= 0:
                            w.filter_status.setCurrentIndex(idx)
                    if hasattr(w, "_apply_invoice_filters"):
                        w._apply_invoice_filters()
                return

            if check_name == "CRA/WCB Remittance Variances":
                w = getattr(main, "payroll_remittances_widget", None)
                if w is not None and hasattr(w, "refresh_data"):
                    w.refresh_data()
                return
        except Exception as exc:
            logger.debug("Source handoff failed for %s: %s", check_name, exc)

    def _open_check_source(self, check_name: str) -> bool:
        main = self._main_window()
        if main is None:
            return False

        # Route each exception check to its primary operational tab.
        if check_name == "Staff Work Completed Not Posted":
            ok = hasattr(main, "navigate_to_operations_subtab") and main.navigate_to_operations_subtab("📡 Dispatch")
            if ok and hasattr(main, "_navigate_to_dispatch_subtab"):
                ok = bool(main._navigate_to_dispatch_subtab("👷 Staff Work Schedule"))
            if ok:
                self._apply_source_handoff(check_name, main)
            return bool(ok)

        if check_name == "Receipts Review Queue":
            ok = bool(
                hasattr(main, "navigate_to_accounting_subtab")
                and main.navigate_to_accounting_subtab("🧾 Enhanced Receipts")
            )
            if ok:
                self._apply_source_handoff(check_name, main)
            return ok

        if check_name == "Unreconciled Banking Transactions":
            ok = bool(
                hasattr(main, "navigate_to_accounting_subtab")
                and main.navigate_to_accounting_subtab("🏦 Enhanced Banking")
            )
            if ok:
                self._apply_source_handoff(check_name, main)
            return ok

        if check_name == "Orphaned Client Payments":
            ok = bool(
                hasattr(main, "navigate_to_accounting_subtab")
                and main.navigate_to_accounting_subtab("💳 Payment Linker")
            )
            if ok:
                self._apply_source_handoff(check_name, main)
            return ok

        if check_name == "Overdue Vendor Payables":
            ok = bool(
                hasattr(main, "navigate_to_accounting_subtab")
                and main.navigate_to_accounting_subtab("📋 Vendor Invoices")
            )
            if ok:
                self._apply_source_handoff(check_name, main)
            return ok

        if check_name == "Payroll Gross With Zero Deductions":
            return bool(
                hasattr(main, "navigate_to_accounting_subtab")
                and main.navigate_to_accounting_subtab("💵 Payroll Entry")
            )

        if check_name == "CRA/WCB Remittance Variances":
            ok = bool(
                hasattr(main, "navigate_to_accounting_subtab")
                and main.navigate_to_accounting_subtab("🧮 Payroll Remittances")
            )
            if ok:
                self._apply_source_handoff(check_name, main)
            return ok

        return False

    def open_selected_check_source(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Open Source",
                "Select a check row first.",
            )
            return

        check_item = self.table.item(row, 0)
        status_item = self.table.item(row, 1)
        check_name = (check_item.text() if check_item else "").strip()
        status = (status_item.text() if status_item else "").strip().upper()

        if not check_name:
            QMessageBox.warning(self, "Open Source", "Invalid check row.")
            return

        if status == "SKIP":
            QMessageBox.information(
                self,
                "Open Source",
                "This check is skipped in current schema state.",
            )
            return

        if not self._open_check_source(check_name):
            QMessageBox.warning(
                self,
                "Open Source",
                "Could not navigate to source tab for this check.",
            )

    def run_selected_check_auto_fix(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Auto-Fix",
                "Select a check row first.",
            )
            return

        check_item = self.table.item(row, 0)
        status_item = self.table.item(row, 1)
        check_name = (check_item.text() if check_item else "").strip()
        status = (status_item.text() if status_item else "").strip().upper()

        if not check_name:
            QMessageBox.warning(self, "Auto-Fix", "Invalid check row.")
            return

        if status == "PASS":
            QMessageBox.information(
                self,
                "Auto-Fix",
                "Selected check already passes.",
            )
            return

        main = self._main_window()
        if main is None:
            QMessageBox.warning(self, "Auto-Fix", "Main window not available.")
            return

        if check_name == "Staff Work Completed Not Posted":
            ok = False
            if hasattr(main, "navigate_to_operations_subtab"):
                ok = bool(main.navigate_to_operations_subtab("📡 Dispatch"))
            if ok and hasattr(main, "_navigate_to_dispatch_subtab"):
                ok = bool(main._navigate_to_dispatch_subtab("👷 Staff Work Schedule"))

            widget = getattr(main, "employee_work_schedule_widget", None)
            if widget is None:
                QMessageBox.warning(
                    self,
                    "Auto-Fix",
                    "Could not open Staff Work Schedule widget.",
                )
                return

            if hasattr(widget, "_post_ready_to_payroll"):
                widget._post_ready_to_payroll()
                self.refresh_checks()
                QMessageBox.information(
                    self,
                    "Auto-Fix",
                    "Auto-fix executed: posted ready completed staff work rows.",
                )
                return

        QMessageBox.information(
            self,
            "Auto-Fix",
            "No safe auto-fix is implemented for this check yet."
            " Use Open Source For Selected Check.",
        )

    def _table_exists(self, table_name: str) -> bool:
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
            row = cur.fetchone()
            return bool(row and row[0])

    def _cols(self, table_name: str) -> set[str]:
        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
                """,
                (table_name,),
            )
            return {r[0] for r in cur.fetchall()}

    def _check_staff_completed_unposted(self) -> tuple[str, int, float, str]:
        if not self._table_exists("employee_work_schedule"):
            return "SKIP", 0, 0.0, "employee_work_schedule table missing"

        cols = self._cols("employee_work_schedule")
        required = {
            "work_date",
            "status",
            "payroll_posted_work_item_id",
            "pay_type",
            "scheduled_hours",
            "rate_amount",
        }
        if not required <= cols:
            return "SKIP", 0, 0.0, "employee_work_schedule missing required columns"

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*),
                    COALESCE(SUM(
                        CASE
                            WHEN UPPER(COALESCE(pay_type, 'HOURLY')) = 'HOURLY'
                                THEN COALESCE(scheduled_hours, 0) * COALESCE(rate_amount, 0)
                            ELSE COALESCE(rate_amount, 0)
                        END
                    ), 0)
                FROM employee_work_schedule
                WHERE work_date <= %s
                  AND COALESCE(status, 'SCHEDULED') = 'COMPLETED'
                  AND payroll_posted_work_item_id IS NULL
                """,
                (date.today(),),
            )
            count_val, amount_val = cur.fetchone() or (0, 0)

        status = "PASS" if int(count_val or 0) == 0 else "WARN"
        return status, int(count_val or 0), float(amount_val or 0), "Completed shifts not posted to payroll"

    def _check_unreviewed_receipts(self) -> tuple[str, int, float, str]:
        if not self._table_exists("receipts"):
            return "SKIP", 0, 0.0, "receipts table missing"

        cols = self._cols("receipts")
        gross_expr = "COALESCE(gross_amount, 0)" if "gross_amount" in cols else "0"
        if "receipt_review_status" in cols:
            where = "COALESCE(receipt_review_status, 'UNREVIEWED') IN ('UNREVIEWED', 'INVESTIGATE')"
            detail = "Receipts not review-complete"
        elif "verified_by_edit" in cols:
            where = "COALESCE(verified_by_edit, '') = ''"
            detail = "Receipts missing verifier"
        else:
            return "SKIP", 0, 0.0, "No receipt review status columns"

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                f"""
                SELECT COUNT(*), COALESCE(SUM({gross_expr}), 0)
                FROM receipts
                WHERE {where}
                """
            )
            count_val, amount_val = cur.fetchone() or (0, 0)

        status = "PASS" if int(count_val or 0) == 0 else "WARN"
        return status, int(count_val or 0), float(amount_val or 0), detail

    def _check_unreconciled_bank_txns(self) -> tuple[str, int, float, str]:
        if not self._table_exists("banking_transactions"):
            return "SKIP", 0, 0.0, "banking_transactions table missing"

        cols = self._cols("banking_transactions")
        if "reconciliation_status" not in cols:
            return "SKIP", 0, 0.0, "reconciliation_status column missing"

        debit_expr = "COALESCE(debit_amount, 0)" if "debit_amount" in cols else "0"
        credit_expr = "COALESCE(credit_amount, 0)" if "credit_amount" in cols else "0"

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*),
                    COALESCE(SUM(ABS({debit_expr} - {credit_expr})), 0)
                FROM banking_transactions
                WHERE LOWER(COALESCE(reconciliation_status, '')) NOT IN ('reconciled', 'matched', 'cleared')
                """
            )
            count_val, amount_val = cur.fetchone() or (0, 0)

        status = "PASS" if int(count_val or 0) == 0 else "WARN"
        return status, int(count_val or 0), float(amount_val or 0), "Bank transactions not reconciled"

    def _check_orphaned_client_payments(self) -> tuple[str, int, float, str]:
        """Payments with value but no charter linkage."""
        if not self._table_exists("payments"):
            return "SKIP", 0, 0.0, "payments table missing"

        cols = self._cols("payments")
        if "charter_id" not in cols or "reserve_number" not in cols:
            return "SKIP", 0, 0.0, "payments missing charter/reserve columns"

        amount_col = None
        for candidate in ("amount", "payment_amount", "paid_amount"):
            if candidate in cols:
                amount_col = candidate
                break
        if not amount_col:
            return "SKIP", 0, 0.0, "payments amount column missing"

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*),
                    COALESCE(SUM(COALESCE({amount_col}, 0)), 0)
                FROM payments
                WHERE COALESCE({amount_col}, 0) > 0
                  AND charter_id IS NULL
                  AND NULLIF(BTRIM(COALESCE(reserve_number::text, '')), '') IS NULL
                """
            )
            count_val, amount_val = cur.fetchone() or (0, 0)

        status = "PASS" if int(count_val or 0) == 0 else "WARN"
        return status, int(count_val or 0), float(amount_val or 0), "Payments without charter linkage"

    def _check_overdue_vendor_payables(self) -> tuple[str, int, float, str]:
        """Vendor invoices overdue and still outstanding."""
        if not self._table_exists("vendor_invoices"):
            return "SKIP", 0, 0.0, "vendor_invoices table missing"

        cols = self._cols("vendor_invoices")
        if "due_date" not in cols:
            return "SKIP", 0, 0.0, "vendor_invoices due_date missing"

        if "balance_due" in cols:
            outstanding_expr = "COALESCE(balance_due, 0)"
        elif "amount_due" in cols:
            outstanding_expr = "COALESCE(amount_due, 0)"
        elif "total_amount" in cols and "amount_paid" in cols:
            outstanding_expr = "COALESCE(total_amount, 0) - COALESCE(amount_paid, 0)"
        else:
            return "SKIP", 0, 0.0, "vendor_invoices outstanding amount columns missing"

        status_col = "status" if "status" in cols else "invoice_status" if "invoice_status" in cols else None
        status_filter = ""
        if status_col:
            status_filter = (
                f"AND LOWER(COALESCE({status_col}, '')) NOT IN "
                "('paid', 'closed', 'cancelled', 'void')"
            )

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*),
                    COALESCE(SUM(GREATEST({outstanding_expr}, 0)), 0)
                FROM vendor_invoices
                WHERE due_date < %s
                  AND GREATEST({outstanding_expr}, 0) > 0.01
                  {status_filter}
                """,
                (date.today(),),
            )
            count_val, amount_val = cur.fetchone() or (0, 0)

        status = "PASS" if int(count_val or 0) == 0 else "WARN"
        return status, int(count_val or 0), float(amount_val or 0), "Overdue vendor payables"

    def _check_payroll_zero_deductions(self) -> tuple[str, int, float, str]:
        if not self._table_exists("employee_pay_master"):
            return "SKIP", 0, 0.0, "employee_pay_master table missing"

        cols = self._cols("employee_pay_master")
        if not {"gross_pay", "total_deductions"} <= cols:
            return "SKIP", 0, 0.0, "Payroll deductions columns missing"

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(gross_pay), 0)
                FROM employee_pay_master
                WHERE COALESCE(gross_pay, 0) > 0
                  AND COALESCE(total_deductions, 0) = 0
                """
            )
            count_val, amount_val = cur.fetchone() or (0, 0)

        status = "PASS" if int(count_val or 0) == 0 else "WARN"
        return status, int(count_val or 0), float(amount_val or 0), "Payroll rows with gross pay but zero deductions"

    def _check_remittance_variances(self) -> tuple[str, int, float, str]:
        if not self._table_exists("payroll_remittances"):
            return "SKIP", 0, 0.0, "payroll_remittances table missing"

        cols = self._cols("payroll_remittances")
        if not {"calculated_total_remittance", "payment_amount"} <= cols:
            return "SKIP", 0, 0.0, "Remittance due/paid columns missing"

        with DatabaseContext(self.db, auto_commit=False) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*),
                    COALESCE(SUM(ABS(
                        COALESCE(calculated_total_remittance, 0)
                        - COALESCE(payment_amount, 0)
                    )), 0)
                FROM payroll_remittances
                WHERE ABS(
                    COALESCE(calculated_total_remittance, 0)
                    - COALESCE(payment_amount, 0)
                ) > 0.01
                """
            )
            count_val, amount_val = cur.fetchone() or (0, 0)

        status = "PASS" if int(count_val or 0) == 0 else "WARN"
        return (
            status,
            int(count_val or 0),
            float(amount_val or 0),
            "Months with CRA calculated-versus-paid variance",
        )

    def refresh_checks(self) -> None:
        """Run controls and update dashboard."""

        checks = [
            (
                "Staff Work Completed Not Posted",
                self._check_staff_completed_unposted,
            ),
            ("Receipts Review Queue", self._check_unreviewed_receipts),
            ("Unreconciled Banking Transactions", self._check_unreconciled_bank_txns),
            ("Orphaned Client Payments", self._check_orphaned_client_payments),
            ("Overdue Vendor Payables", self._check_overdue_vendor_payables),
            ("Payroll Gross With Zero Deductions", self._check_payroll_zero_deductions),
            ("CRA/WCB Remittance Variances", self._check_remittance_variances),
        ]

        rows = []
        pass_count = 0
        warn_count = 0
        skip_count = 0

        for check_name, fn in checks:
            try:
                status, count_val, exposure, detail = fn()
            except Exception as exc:
                logger.error("Close control check failed (%s): %s", check_name, exc)
                status, count_val, exposure, detail = (
                    "ERROR",
                    0,
                    0.0,
                    f"Error: {exc}",
                )

            if status == "PASS":
                pass_count += 1
            elif status == "WARN":
                warn_count += 1
            elif status == "SKIP":
                skip_count += 1
            else:
                warn_count += 1

            rows.append((check_name, status, count_val, exposure, detail))

        self.table.setRowCount(len(rows))
        first_warn_row = -1
        for r, (check_name, status, count_val, exposure, detail) in enumerate(rows):
            vals = [
                check_name,
                status,
                str(int(count_val or 0)),
                f"${float(exposure or 0.0):,.2f}",
                detail,
            ]
            for c, val in enumerate(vals):
                item = QTableWidgetItem(str(val))
                self.table.setItem(r, c, item)

            color = None
            if status == "PASS":
                color = QColor("#dcfce7")
            elif status == "WARN":
                color = QColor("#fee2e2")
                if first_warn_row < 0:
                    first_warn_row = r
            elif status == "SKIP":
                color = QColor("#e5e7eb")

            if color is not None:
                for c in range(self.table.columnCount()):
                    cell = self.table.item(r, c)
                    if cell is not None:
                        cell.setBackground(color)

        self.table.resizeColumnsToContents()
        if first_warn_row >= 0:
            self.table.selectRow(first_warn_row)
        elif self.table.rowCount() > 0:
            self.table.selectRow(0)
        self.summary_label.setText(
            f"PASS: {pass_count}  |  WARN: {warn_count}  |  SKIP: {skip_count}"
        )
