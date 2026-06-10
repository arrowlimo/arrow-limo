"""
Enhanced Banking Manager - Comprehensive banking transaction browsing
Features: Account selector, date buttons, month select, vendor/amount filters,
sorting
"""

import logging
import re
from datetime import date, datetime, timedelta

import psycopg2
from common_widgets import StandardDateEdit
from enhanced_receipts_import_export import (
    EnhancedReceiptsImportExport,
)
from print_export_helper import PrintExportHelper
from PyQt6.QtCore import QDate, Qt, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class ReplaceOnTypeLineEdit(QLineEdit):
    """Line edit that selects all on focus and replaces text on first typed"
    "character."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._replace_on_next_type = False

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.selectAll()
        self._replace_on_next_type = True

    def keyPressEvent(self, event) -> None:
        text = event.text()
        is_printable = bool(text) and text.isprintable()
        has_modifier = bool(
            event.modifiers()
            & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )

        if self._replace_on_next_type and is_printable and not has_modifier:
            self.setText(text)
            self._replace_on_next_type = False
            return

        if event.key() not in (
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
        ):
            self._replace_on_next_type = False
        super().keyPressEvent(event)


class EnhancedBankingManager(QWidget):
    """Comprehensive banking transaction management with filters and"
    "sorting."""

    def __init__(self, conn: psycopg2.extensions.connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self._is_loading_table = False
        self._receipt_viewer_dialogs = []
        self._editable_columns = {
            "account_number",
            "description",
            "transaction_date",
            "check_number",
            "debit_amount",
            "credit_amount",
            "balance",
            "reconciliation_status",
            "reconciliation_notes",
            "verified",
            "is_nsf_charge",
        }
        self.all_columns = [
            "transaction_id",
            "transaction_date",
            "account_number",
            "description",
            "debit_amount",
            "credit_amount",
            "balance",
            "check_number",
            "reconciliation_status",
            "receipt_id",
            "reconciled_receipt_id",
            "transaction_uid",
            "source_file",
            "reconciliation_notes",
            "verified",
            "is_nsf_charge",
            "verified_date",
            "verified_by",
        ]
        self.visible_columns = self.all_columns.copy()
        self._build_ui()
        self._load_accounts()
        self._load_transactions()

    def _build_ui(self) -> None:
        """Build comprehensive UI."""
        layout = QVBoxLayout(self)

        # === ACCOUNT SELECTOR ===
        account_row = QHBoxLayout()
        account_row.addWidget(QLabel("🏦 Bank Account:"))

        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(300)
        account_row.addWidget(self.account_combo)

        account_row.addStretch()
        layout.addLayout(account_row)

        # === QUICK DATE BUTTONS ===
        date_btns = QHBoxLayout()
        date_btns.addWidget(QLabel("📅 Quick Dates:"))

        btn_today = QPushButton("Today")
        btn_today.clicked.connect(lambda: self._set_date_range(0, 0))
        date_btns.addWidget(btn_today)

        btn_this_week = QPushButton("This Week")
        btn_this_week.clicked.connect(self._set_this_week)
        date_btns.addWidget(btn_this_week)

        btn_this_month = QPushButton("This Month")
        btn_this_month.clicked.connect(self._set_this_month)
        date_btns.addWidget(btn_this_month)

        btn_last_month = QPushButton("Last Month")
        btn_last_month.clicked.connect(self._set_last_month)
        date_btns.addWidget(btn_last_month)

        btn_last_3mo = QPushButton("Last 3 Months")
        btn_last_3mo.clicked.connect(lambda: self._set_date_range(90, 0))
        date_btns.addWidget(btn_last_3mo)

        btn_ytd = QPushButton("YTD")
        btn_ytd.clicked.connect(self._set_ytd)
        date_btns.addWidget(btn_ytd)

        btn_last_year = QPushButton("Last Year")
        btn_last_year.clicked.connect(self._set_last_year)
        date_btns.addWidget(btn_last_year)

        btn_all = QPushButton("All Time")
        btn_all.clicked.connect(self._set_all_time)
        date_btns.addWidget(btn_all)

        date_btns.addStretch()
        layout.addLayout(date_btns)

        # === MONTH/YEAR SELECTOR ===
        month_year = QHBoxLayout()
        month_year.addWidget(QLabel("Month/Year:"))

        self.month_combo = QComboBox()
        months = ["All"] + [
            datetime(2000, m, 1).strftime("%B") for m in range(1, 13)
        ]
        self.month_combo.addItems(months)
        month_year.addWidget(self.month_combo)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(2010, 2030)
        self.year_spin.setValue(2010)
        self.year_spin.setSpecialValueText("All Years")
        month_year.addWidget(self.year_spin)

        month_year.addStretch()
        layout.addLayout(month_year)

        # === FILTERS ===
        filters = QGroupBox("🔍 Filters")
        filter_grid = QGridLayout(filters)

        # Row 1
        filter_grid.addWidget(QLabel("Description/Vendor:"), 0, 0)
        self.vendor_filter = QLineEdit()
        self.vendor_filter.setPlaceholderText("Search description...")
        filter_grid.addWidget(self.vendor_filter, 0, 1, 1, 2)

        self.use_date_filter = QCheckBox("Date Search")
        self.use_date_filter.toggled.connect(self._toggle_date_filters)
        filter_grid.addWidget(self.use_date_filter, 0, 3)

        filter_grid.addWidget(QLabel("Date From:"), 0, 4)
        self.date_from = StandardDateEdit(allow_blank=True)
        filter_grid.addWidget(self.date_from, 0, 5)

        filter_grid.addWidget(QLabel("Date To:"), 0, 6)
        self.date_to = StandardDateEdit(allow_blank=True)
        filter_grid.addWidget(self.date_to, 0, 7)
        self._toggle_date_filters(False)

        # Row 2
        filter_grid.addWidget(QLabel("Amount:"), 1, 0)
        self.amount_filter = ReplaceOnTypeLineEdit()
        self.amount_filter.setPlaceholderText("Exact amount...")
        filter_grid.addWidget(self.amount_filter, 1, 1, 1, 3)

        filter_grid.addWidget(QLabel("Transaction Type:"), 1, 4)
        self.type_filter = QComboBox()
        self.type_filter.addItems(
            ["All", "Debit", "Credit", "Transfer", "Fee"]
        )
        filter_grid.addWidget(self.type_filter, 1, 5)

        filter_grid.addWidget(QLabel("Reference:"), 1, 6)
        self.ref_filter = QLineEdit()
        self.ref_filter.setPlaceholderText("Cheque #, ref...")
        filter_grid.addWidget(self.ref_filter, 1, 7)

        # Row 2 - Transaction ID search
        filter_grid.addWidget(QLabel("Transaction ID:"), 2, 0)
        self.transaction_id_filter = QLineEdit()
        self.transaction_id_filter.setPlaceholderText(
            "Search by transaction_id..."
        )
        filter_grid.addWidget(self.transaction_id_filter, 2, 1, 1, 2)

        # Row 3 - Checkboxes
        self.show_unmatched = QCheckBox("Unmatched Only")
        filter_grid.addWidget(self.show_unmatched, 3, 0)

        self.show_matched = QCheckBox("Matched Only")
        filter_grid.addWidget(self.show_matched, 3, 1)

        self.show_reconciled = QCheckBox("Reconciled Only")
        filter_grid.addWidget(self.show_reconciled, 3, 2)

        self.show_unreconciled = QCheckBox("Unreconciled Only")
        filter_grid.addWidget(self.show_unreconciled, 3, 3)

        layout.addWidget(filters)

        # === ACTION BUTTONS ===
        actions = QHBoxLayout()

        search_btn = QPushButton("🔍 Search")
        search_btn.setStyleSheet(
            "background-color: #2196F3; color: white; font-weight: bold;"
        )
        search_btn.clicked.connect(self._load_transactions)
        actions.addWidget(search_btn)

        clear_btn = QPushButton("Clear Filters")
        clear_btn.clicked.connect(self._clear_filters)
        actions.addWidget(clear_btn)

        # Actions
        add_btn = QPushButton("➕ Add Transaction")
        add_btn.setStyleSheet(
            "background-color: #2E7D32; color: white; font-weight: bold;"
        )
        add_btn.clicked.connect(self._add_transaction)
        actions.addWidget(add_btn)

        mark_verified_btn = QPushButton("☑ Mark Paper Verified")
        mark_verified_btn.setStyleSheet(
            "background-color: #00695C; color: white; font-weight: bold;"
        )
        mark_verified_btn.clicked.connect(
            lambda: self._set_selected_verified(True)
        )
        actions.addWidget(mark_verified_btn)

        clear_verified_btn = QPushButton("☐ Clear Paper Verified")
        clear_verified_btn.clicked.connect(
            lambda: self._set_selected_verified(False)
        )
        actions.addWidget(clear_verified_btn)

        view_receipt_btn = QPushButton("📝 View Linked Receipt")
        view_receipt_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        view_receipt_btn.clicked.connect(self._view_linked_receipt)
        actions.addWidget(view_receipt_btn)

        details_btn = QPushButton("✏️ Edit Transaction")
        details_btn.setStyleSheet(
            "background-color: #FF9800; color: white; font-weight: bold;"
        )
        details_btn.clicked.connect(self._show_transaction_details)
        actions.addWidget(details_btn)

        delete_btn = QPushButton("🗑️ Delete Transaction")
        delete_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; font-weight: bold;"
        )
        delete_btn.clicked.connect(self._delete_transaction)
        actions.addWidget(delete_btn)

        match_btn = QPushButton("🔗 Link to Receipt")
        match_btn.clicked.connect(self._link_to_receipt)
        actions.addWidget(match_btn)

        actions.addStretch()

        # Column visibility menu
        columns_btn = QPushButton("⚙️ Show/Hide Columns")
        columns_btn.clicked.connect(self._show_column_menu)
        actions.addWidget(columns_btn)

        export_btn = QPushButton("📊 Export Excel")
        export_btn.clicked.connect(
            lambda: EnhancedReceiptsImportExport.export_to_excel(
                self.conn, self.table, self
            )
        )
        actions.addWidget(export_btn)

        import_btn = QPushButton("📥 Import & Update from Excel")
        import_btn.clicked.connect(
            lambda: EnhancedReceiptsImportExport.import_from_excel(
                self.conn, self.table, self
            )
        )
        actions.addWidget(import_btn)

        csv_btn = QPushButton("💾 Export CSV")
        csv_btn.clicked.connect(
            lambda: PrintExportHelper.export_csv(
                self.table, "Banking", parent=self
            )
        )
        actions.addWidget(csv_btn)

        print_btn = QPushButton("🖨️ Print")
        print_btn.clicked.connect(
            lambda: PrintExportHelper.print_preview(
                self.table, "Banking", self
            )
        )
        actions.addWidget(print_btn)

        layout.addLayout(actions)

        # === RESULTS LABEL ===
        self.results_label = QLabel("No transactions loaded")
        layout.addWidget(self.results_label)

        # === TABLE ===
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.horizontalHeader().sectionClicked.connect(
            self._sort_by_column
        )
        self.table.itemChanged.connect(self._handle_inline_edit)
        layout.addWidget(self.table)

        self.current_sort_column = 1  # Default: transaction_date
        self.sort_ascending = False

    def _load_accounts(self) -> None:
        """Load bank account list."""
        try:
            current = self.account_combo.currentText()
            self.account_combo.clear()
            cur = self.conn.cursor()
            cur.execute("""
                SELECT DISTINCT account_number
                FROM banking_transactions
                WHERE account_number IS NOT NULL
                ORDER BY account_number
            """)
            accounts = ["All Accounts"] + [row[0] for row in cur.fetchall()]
            self.account_combo.addItems(accounts)
            if current and current in accounts:
                self.account_combo.setCurrentText(current)
            cur.close()
        except Exception as e:
            logger.error("Error loading accounts: %s", e)

    @staticmethod
    def _to_qdate(d) -> QDate:
        """Convert a Python datetime.date to QDate."""
        return QDate(d.year, d.month, d.day)

    def _set_date_range(self, days_back: int, days_forward: int = 0) -> None:
        """Set date range relative to today."""
        self.use_date_filter.setChecked(True)
        today = date.today()
        self.date_from.setDate(
            self._to_qdate(today - timedelta(days=days_back))
        )
        self.date_to.setDate(
            self._to_qdate(today + timedelta(days=days_forward))
        )

    @pyqtSlot()
    def _set_this_week(self) -> None:
        """Set to current week (Monday-Sunday)."""
        self.use_date_filter.setChecked(True)
        today = date.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        self.date_from.setDate(self._to_qdate(start))
        self.date_to.setDate(self._to_qdate(end))

    @pyqtSlot()
    def _set_this_month(self) -> None:
        """Set to current month."""
        self.use_date_filter.setChecked(True)
        today = date.today()
        self.date_from.setDate(
            self._to_qdate(date(today.year, today.month, 1))
        )
        if today.month == 12:
            self.date_to.setDate(self._to_qdate(date(today.year, 12, 31)))
        else:
            self.date_to.setDate(
                self._to_qdate(
                    date(today.year, today.month + 1, 1) - timedelta(days=1)
                )
            )

    @pyqtSlot()
    def _set_last_month(self) -> None:
        """Set to previous month."""
        self.use_date_filter.setChecked(True)
        today = date.today()
        if today.month == 1:
            self.date_from.setDate(self._to_qdate(date(today.year - 1, 12, 1)))
            self.date_to.setDate(self._to_qdate(date(today.year - 1, 12, 31)))
        else:
            self.date_from.setDate(
                self._to_qdate(date(today.year, today.month - 1, 1))
            )
            self.date_to.setDate(
                self._to_qdate(
                    date(today.year, today.month, 1) - timedelta(days=1)
                )
            )

    @pyqtSlot()
    def _set_ytd(self) -> None:
        """Set to year-to-date."""
        self.use_date_filter.setChecked(True)
        today = date.today()
        self.date_from.setDate(self._to_qdate(date(today.year, 1, 1)))
        self.date_to.setDate(self._to_qdate(today))

    @pyqtSlot()
    def _set_last_year(self) -> None:
        """Set to full previous year."""
        self.use_date_filter.setChecked(True)
        today = date.today()
        self.date_from.setDate(self._to_qdate(date(today.year - 1, 1, 1)))
        self.date_to.setDate(self._to_qdate(date(today.year - 1, 12, 31)))

    @pyqtSlot()
    def _set_all_time(self) -> None:
        """Clear date filters to show all time."""
        self.use_date_filter.setChecked(False)
        self.date_from.setDate(None)
        self.date_to.setDate(None)

    def _toggle_date_filters(self, enabled: bool) -> None:
        """Only apply date range when date search is explicitly enabled."""
        self.date_from.setEnabled(enabled)
        self.date_to.setEnabled(enabled)

    @pyqtSlot()
    def _clear_filters(self) -> None:
        """Clear all filter fields."""
        self.account_combo.setCurrentIndex(0)
        self.vendor_filter.clear()
        self.use_date_filter.setChecked(False)
        self.date_from.setDate(None)
        self.date_to.setDate(None)
        self.amount_filter.clear()
        self.type_filter.setCurrentIndex(0)
        self.ref_filter.clear()
        self.transaction_id_filter.clear()
        self.show_unmatched.setChecked(False)
        self.show_matched.setChecked(False)
        self.show_reconciled.setChecked(False)
        self.show_unreconciled.setChecked(False)
        self.month_combo.setCurrentIndex(0)
        self.year_spin.setValue(2010)

    def focus_transaction_id(self, transaction_id: int) -> bool:
        """Deep-link helper: filter table to a specific transaction id and"
        "load it."""

        try:
            txn_id = int(transaction_id)
        except (TypeError, ValueError):
            return False

        self._clear_filters()
        self.transaction_id_filter.setText(str(txn_id))
        self._load_transactions()

        if self.table.rowCount() > 0:
            self.table.setCurrentCell(0, 0)
            self.table.selectRow(0)
            return True
        return False

    @pyqtSlot()
    def _show_column_menu(self) -> None:
        """Show menu to toggle column visibility."""
        menu = QMenu(self)

        for col in self.all_columns:
            action = menu.addAction(col.replace("_", " ").title())
            action.setCheckable(True)
            action.setChecked(col in self.visible_columns)
            action.triggered.connect(
                lambda checked, c=col: self._toggle_column(c, checked)
            )

        menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))

    def _toggle_column(self, column: str, visible: bool) -> None:
        """Toggle column visibility."""
        if visible and column not in self.visible_columns:
            self.visible_columns.append(column)
        elif not visible and column in self.visible_columns:
            self.visible_columns.remove(column)
        self._load_transactions()

    def _sort_by_column(self, column_idx: int) -> None:
        """Sort table by clicked column."""
        if column_idx == self.current_sort_column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.current_sort_column = column_idx
            self.sort_ascending = True
        self._load_transactions()

    @pyqtSlot()
    def _load_transactions(self) -> None:
        """Load banking transactions with all applied filters."""
        try:
            # Build query
            allowed_columns = [
                col for col in self.visible_columns if col in self.all_columns
            ]
            if not allowed_columns:
                raise ValueError("No valid columns selected")
            select_cols = ", ".join([f"bt.{col}" for col in allowed_columns])
            sql = [
                f"SELECT {select_cols} FROM banking_transactions bt WHERE 1=1"
            ]
            params = []

            # Account filter
            account = self.account_combo.currentText()
            if account and account != "All Accounts":
                sql.append("AND bt.account_number = %s")
                params.append(account)

            # Description/Vendor filter (fuzzy)
            vendor = self.vendor_filter.text().strip()
            if vendor:
                sql.append("AND LOWER(bt.description) LIKE LOWER(%s)")
                params.append(f"%{vendor}%")

            # Transaction ID filter
            if self.transaction_id_filter.text().strip():
                try:
                    txn_id = int(self.transaction_id_filter.text().strip())
                    sql.append("AND bt.transaction_id = %s")
                    params.append(txn_id)
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Invalid Input",
                        "Transaction ID must be a number",
                    )
                    return

            # Date filters
            use_date_filter = self.use_date_filter.isChecked()
            date_from = self.date_from.getDate() if use_date_filter else None
            date_to = self.date_to.getDate() if use_date_filter else None
            if date_from:
                sql.append("AND bt.transaction_date >= %s")
                params.append(
                    date_from.toPyDate()
                    if hasattr(date_from, "toPyDate")
                    else date_from
                )
            if date_to:
                sql.append("AND bt.transaction_date <= %s")
                params.append(
                    date_to.toPyDate()
                    if hasattr(date_to, "toPyDate")
                    else date_to
                )

            # Month/Year filter (applies only when explicit date search is off)
            if not use_date_filter:
                month_idx = self.month_combo.currentIndex()
                if month_idx > 0:
                    sql.append(
                        "AND EXTRACT(MONTH FROM bt.transaction_date) = %s"
                    )
                    params.append(month_idx)

                year = self.year_spin.value()
                if year > 2010:
                    sql.append(
                        "AND EXTRACT(YEAR FROM bt.transaction_date) = %s"
                    )
                    params.append(year)

            # Partial amount search (matches debit OR credit, e.g., 4.8 ->
            # 4.80)
            amount_text = (
                self.amount_filter.text()
                .strip()
                .replace("$", "")
                .replace(",", "")
            )
            if amount_text:
                if (
                    not re.fullmatch(r"[0-9]*\.?[0-9]*", amount_text)
                    or amount_text == "."
                ):
                    QMessageBox.warning(
                        self,
                        "Invalid Input",
                        "Amount must contain only digits and decimal point",
                    )
                    return
                amount_like = f"%{amount_text}%"
                sql.append("""AND (
                    to_char(
                        COALESCE(bt.debit_amount, 0)::numeric,
                        'FM999999999990.00'
                    ) LIKE %s OR
                    to_char(
                        COALESCE(bt.credit_amount, 0)::numeric,
                        'FM999999999990.00'
                    ) LIKE %s
                )""")
                params.extend([amount_like, amount_like])

            # Transaction type
            txn_type = self.type_filter.currentText()
            if txn_type == "Debit":
                sql.append("AND bt.debit_amount > 0")
            elif txn_type == "Credit":
                sql.append("AND bt.credit_amount > 0")
            elif txn_type == "Transfer":
                sql.append("AND LOWER(bt.description) LIKE '%transfer%'")
            elif txn_type == "Fee":
                sql.append("AND LOWER(bt.description) LIKE '%fee%'")

            # Reference (check number or transaction uid)
            if self.ref_filter.text():
                sql.append(
                    "AND (LOWER(COALESCE(bt.check_number::text, '')) LIKE"
                    "LOWER(%s) "
                    "OR LOWER(COALESCE(bt.transaction_uid::text, '')) LIKE"
                    "LOWER(%s))"
                )
                params.extend(
                    [
                        f"%{self.ref_filter.text()}%",
                        f"%{self.ref_filter.text()}%",
                    ]
                )

            # Checkboxes
            if self.show_unmatched.isChecked():
                sql.append(
                    "AND bt.receipt_id IS NULL AND bt.reconciled_receipt_id"
                    "IS NULL"
                )
            if self.show_matched.isChecked():
                sql.append(
                    "AND (bt.receipt_id IS NOT NULL OR"
                    "bt.reconciled_receipt_id IS NOT NULL)"
                )
            if self.show_reconciled.isChecked():
                sql.append(
                    "AND LOWER(bt.reconciliation_status) = 'reconciled'"
                )
            if self.show_unreconciled.isChecked():
                sql.append(
                    "AND (bt.reconciliation_status IS NULL OR"
                    "LOWER(bt.reconciliation_status) != 'reconciled')"
                )

            # Sorting
            if self.current_sort_column < len(self.visible_columns):
                sort_col = self.visible_columns[self.current_sort_column]
                sort_dir = "ASC" if self.sort_ascending else "DESC"
                sql.append(f"ORDER BY bt.{sort_col} {sort_dir}")
            else:
                sql.append(
                    "ORDER BY bt.transaction_date DESC, bt.transaction_id DESC"
                )

            sql.append("LIMIT 2000")

            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()

            self._populate_table(rows)

            # Stats
            total = len(rows)
            debits = sum(
                row[self.visible_columns.index("debit_amount")] or 0
                for row in rows
                if "debit_amount" in self.visible_columns
            )
            credits = sum(
                row[self.visible_columns.index("credit_amount")] or 0
                for row in rows
                if "credit_amount" in self.visible_columns
            )
            matched = sum(
                1
                for row in rows
                if "receipt_id" in self.visible_columns
                and row[self.visible_columns.index("receipt_id")]
            )

            self.results_label.setText(
                f"📊 {total} transactions | 💸 Debits: ${debits:,.2f} | 💰"
                f"Credits: ${credits:,.2f} | 🔗 {matched} matched"
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load transactions:\n{e}"
            )
            import traceback

            traceback.print_exc()

    def _populate_table(self, rows) -> None:
        """Populate table with transaction data."""
        self._is_loading_table = True
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(self.visible_columns))

        headers = [
            col.replace("_", " ").title() for col in self.visible_columns
        ]
        self.table.setHorizontalHeaderLabels(headers)

        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                col_name = self.visible_columns[c]

                # Format based on column type
                if value is None:
                    item = QTableWidgetItem("")
                elif col_name in {"verified", "is_nsf_charge"}:
                    item = QTableWidgetItem("")
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if bool(value)
                        else Qt.CheckState.Unchecked
                    )
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif col_name in ["debit_amount", "credit_amount", "balance"]:
                    item = QTableWidgetItem(
                        f"${float(value):,.2f}" if value else ""
                    )
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                    # Color code: debits red, credits green
                    if col_name == "debit_amount" and value and value > 0:
                        item.setForeground(QColor(200, 0, 0))
                    elif col_name == "credit_amount" and value and value > 0:
                        item.setForeground(QColor(0, 150, 0))
                elif "date" in col_name:
                    item = QTableWidgetItem(str(value)[:10] if value else "")
                else:
                    item = QTableWidgetItem(str(value))

                item.setData(Qt.ItemDataRole.UserRole, value)
                if col_name in {"verified", "is_nsf_charge"}:
                    item.setFlags(
                        (
                            item.flags()
                            | Qt.ItemFlag.ItemIsUserCheckable
                            | Qt.ItemFlag.ItemIsEditable
                        )
                        & ~Qt.ItemFlag.ItemIsEditable
                    )
                elif col_name in self._editable_columns:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Highlight matched/reconciled
                if (
                    "receipt_id" in self.visible_columns
                    or "reconciled_receipt_id" in self.visible_columns
                ):
                    receipt_idx = (
                        self.visible_columns.index("receipt_id")
                        if "receipt_id" in self.visible_columns
                        else -1
                    )
                    reconciled_idx = (
                        self.visible_columns.index("reconciled_receipt_id")
                        if "reconciled_receipt_id" in self.visible_columns
                        else -1
                    )

                    if (
                        receipt_idx >= 0
                        and receipt_idx < len(row)
                        and row[receipt_idx]
                    ) or (
                        reconciled_idx >= 0
                        and reconciled_idx < len(row)
                        and row[reconciled_idx]
                    ):
                        item.setBackground(
                            QColor(220, 255, 220)
                        )  # Light green

                # Highlight reconciled status
                if "reconciliation_status" in self.visible_columns:
                    status_idx = self.visible_columns.index(
                        "reconciliation_status"
                    )
                    if (
                        status_idx < len(row)
                        and row[status_idx]
                        and row[status_idx].lower() == "reconciled"
                    ):
                        item.setBackground(QColor(200, 240, 255))  # Light blue

                self.table.setItem(r, c, item)

        self._is_loading_table = False

    def _parse_inline_value(self, column_name: str, value_text: str) -> object:
        """Parse edited text into a DB-safe value for the target column."""
        text = (value_text or "").strip()

        if column_name in {"verified", "is_nsf_charge"}:
            lowered = text.lower()
            if lowered in {"1", "true", "yes", "y", "checked"}:
                return True
            if lowered in {"0", "false", "no", "n", "unchecked", ""}:
                return False
            label = "Verified" if column_name == "verified" else "NSF"
            raise ValueError(f"{label} must be true/false")

        if text == "":
            return None

        if column_name in {"debit_amount", "credit_amount", "balance"}:
            cleaned = text.replace("$", "").replace(",", "").strip()
            return float(cleaned)

        if column_name == "transaction_date":
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
            raise ValueError("Date must be YYYY-MM-DD or MM/DD/YYYY")

        return text

    @staticmethod
    def _format_inline_display_value(column_name: str, value) -> object:
        """Format DB values for table display after an inline edit."""
        if column_name in {"verified", "is_nsf_charge"}:
            return ""

        if value is None:
            return ""

        if column_name in {"debit_amount", "credit_amount", "balance"}:
            return f"${float(value):,.2f}" if float(value) != 0 else ""

        if column_name == "transaction_date":
            return str(value)[:10]

        return str(value)

    def _handle_inline_edit(self, item: QTableWidgetItem) -> None:
        """Persist inline cell edits directly to banking_transactions."""
        if self._is_loading_table:
            return

        if not item:
            return

        row = item.row()
        col = item.column()
        if col >= len(self.visible_columns):
            return

        column_name = self.visible_columns[col]
        if column_name not in self._editable_columns:
            return

        if "transaction_id" not in self.visible_columns:
            self._is_loading_table = True
            self._load_transactions()
            self._is_loading_table = False
            QMessageBox.warning(
                self,
                "Inline Edit",
                "Show transaction_id column to use inline editing.",
            )
            return

        txn_col = self.visible_columns.index("transaction_id")
        txn_item = self.table.item(row, txn_col)
        txn_text = txn_item.text().strip() if txn_item else ""
        if not txn_text.isdigit():
            QMessageBox.warning(
                self, "Inline Edit", "Invalid transaction_id on selected row."
            )
            self._is_loading_table = True
            self._load_transactions()
            self._is_loading_table = False
            return

        txn_id = int(txn_text)
        old_value = item.data(Qt.ItemDataRole.UserRole)

        try:
            if column_name in {"verified", "is_nsf_charge"}:
                new_value = item.checkState() == Qt.CheckState.Checked
            else:
                new_value = self._parse_inline_value(column_name, item.text())
        except ValueError as e:
            self.table.blockSignals(True)
            if column_name in {"verified", "is_nsf_charge"}:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if bool(old_value)
                    else Qt.CheckState.Unchecked
                )
            else:
                item.setText(
                    self._format_inline_display_value(column_name, old_value)
                )
            self.table.blockSignals(False)
            QMessageBox.warning(self, "Invalid Value", str(e))
            return

        old_norm = "" if old_value is None else str(old_value).strip()
        new_norm = "" if new_value is None else str(new_value).strip()
        if old_norm == new_norm:
            self.table.blockSignals(True)
            if column_name in {"verified", "is_nsf_charge"}:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if bool(old_value)
                    else Qt.CheckState.Unchecked
                )
            else:
                item.setText(
                    self._format_inline_display_value(column_name, old_value)
                )
            self.table.blockSignals(False)
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                f"UPDATE banking_transactions SET {column_name} = %s "
                f"WHERE transaction_id = %s",
                (new_value, txn_id),
            )
            self.conn.commit()
            cur.close()

            self.table.blockSignals(True)
            item.setData(Qt.ItemDataRole.UserRole, new_value)
            if column_name in {"verified", "is_nsf_charge"}:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if bool(new_value)
                    else Qt.CheckState.Unchecked
                )
            else:
                item.setText(
                    self._format_inline_display_value(column_name, new_value)
                )
            if column_name in {"debit_amount", "credit_amount", "balance"}:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                if (
                    column_name == "debit_amount"
                    and new_value
                    and float(new_value) > 0
                ):
                    item.setForeground(QColor(200, 0, 0))
                elif (
                    column_name == "credit_amount"
                    and new_value
                    and float(new_value) > 0
                ):
                    item.setForeground(QColor(0, 150, 0))
            self.table.blockSignals(False)

            self.results_label.setText(
                f"Last edit saved: Transaction #{txn_id} ->"
                f"{column_name.replace('_', ' ')}"
            )
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            self.table.blockSignals(True)
            if column_name in {"verified", "is_nsf_charge"}:
                item.setCheckState(
                    Qt.CheckState.Checked
                    if bool(old_value)
                    else Qt.CheckState.Unchecked
                )
            else:
                item.setText(
                    self._format_inline_display_value(column_name, old_value)
                )
            self.table.blockSignals(False)
            QMessageBox.critical(
                self, "Save Error", f"Failed to save inline edit:\n{e}"
            )

    def _get_selected_transaction_ids(self) -> list[int]:
        """Return unique transaction_ids from currently selected table rows."""
        if "transaction_id" not in self.visible_columns:
            QMessageBox.warning(
                self,
                "Column Required",
                "Show transaction_id column to update Paper Verified for"
                "multiple rows.",
            )
            return []

        txn_col = self.visible_columns.index("transaction_id")
        rows = sorted(
            {idx.row() for idx in self.table.selectionModel().selectedRows()}
        )
        if not rows:
            rows = sorted({item.row() for item in self.table.selectedItems()})

        txn_ids: list[int] = []
        for row in rows:
            txn_item = self.table.item(row, txn_col)
            txn_text = txn_item.text().strip() if txn_item else ""
            if txn_text.isdigit():
                txn_ids.append(int(txn_text))

        return sorted(set(txn_ids))

    def _set_selected_verified(self, verified_value: bool) -> None:
        """Bulk set verified state for selected transactions."""
        txn_ids = self._get_selected_transaction_ids()
        if not txn_ids:
            QMessageBox.information(
                self, "No Selection", "Select one or more transactions first."
            )
            return

        action_text = (
            "mark as Paper Verified"
            if verified_value
            else "clear Paper Verified"
        )
        confirm = QMessageBox.question(
            self,
            "Confirm Bulk Update",
            f"{action_text} for {len(txn_ids)} selected transaction(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            cur = self.conn.cursor()
            if verified_value:
                cur.execute(
                    """
                    UPDATE banking_transactions
                    SET verified = TRUE,
                        verified_date = CURRENT_TIMESTAMP,
                        verified_by = COALESCE(verified_by, 'paper')
                    WHERE transaction_id = ANY(%s)
                    """,
                    (txn_ids,),
                )
            else:
                cur.execute(
                    """
                    UPDATE banking_transactions
                    SET verified = FALSE,
                        verified_date = NULL,
                        verified_by = NULL
                    WHERE transaction_id = ANY(%s)
                    """,
                    (txn_ids,),
                )

            updated_count = cur.rowcount
            self.conn.commit()
            cur.close()

            QMessageBox.information(
                self,
                "Updated",
                f"Updated {updated_count} transaction(s).",
            )
            self._load_transactions()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Update Error", f"Failed to update Paper Verified:\n{e}"
            )

    @pyqtSlot()
    def _view_linked_receipt(self) -> None:
        """Open the linked receipt for viewing/editing."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select a transaction to view its linked receipt.",
            )
            return

        row = selected[0].row()

        # Check for receipt_id or reconciled_receipt_id
        receipt_id = None
        if "receipt_id" in self.visible_columns:
            receipt_idx = self.visible_columns.index("receipt_id")
            val = self.table.item(row, receipt_idx).text()
            if val:
                receipt_id = int(val)

        if not receipt_id and "reconciled_receipt_id" in self.visible_columns:
            reconciled_idx = self.visible_columns.index(
                "reconciled_receipt_id"
            )
            val = self.table.item(row, reconciled_idx).text()
            if val:
                receipt_id = int(val)

        if not receipt_id:
            QMessageBox.information(
                self,
                "Not Linked",
                "This transaction is not linked to any receipt.",
            )
            return

        self._open_receipt_viewer(receipt_id)

    def _open_receipt_viewer(self, receipt_id: int) -> None:
        """Open receipt viewer dialog."""
        try:
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout
            from receipt_search_match_widget import (
                ReceiptSearchMatchWidget,
            )

            dialog = QDialog(self)
            dialog.setWindowTitle(f"Receipt #{receipt_id}")
            dialog.setGeometry(100, 100, 1200, 800)

            layout = QVBoxLayout(dialog)

            # Create receipt widget
            receipt_widget = ReceiptSearchMatchWidget(self.conn, dialog)
            layout.addWidget(receipt_widget)

            # Load the specific receipt
            receipt_widget.loaded_receipt_id = receipt_id
            receipt_widget._load_receipt_by_id(receipt_id)

            # Buttons
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Close
            )
            button_box.rejected.connect(dialog.close)
            layout.addWidget(button_box)

            # Non-modal window so users can open multiple receipt viewers at
            # once.
            dialog.setModal(False)
            self._receipt_viewer_dialogs.append(dialog)

            def _on_dialog_closed(*_) -> None:
                try:
                    if dialog in self._receipt_viewer_dialogs:
                        self._receipt_viewer_dialogs.remove(dialog)
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
                self._load_transactions()

            dialog.finished.connect(_on_dialog_closed)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to open receipt viewer:\n{e}"
            )
            import traceback

            traceback.print_exc()

    @pyqtSlot()
    def _show_transaction_details(self) -> None:
        """Show and edit transaction details in a popup form."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(
                self, "No Selection", "Please select a transaction to edit."
            )
            return

        row = selected[0].row()

        # Gather all column data into a dict
        col_data = {}
        for c, col_name in enumerate(self.visible_columns):
            col_data[col_name] = (
                self.table.item(row, c).text()
                if self.table.item(row, c)
                else ""
            )

        if "transaction_id" not in col_data or not col_data["transaction_id"]:
            QMessageBox.warning(
                self, "Error", "Cannot edit: transaction_id not available."
            )
            return

        txn_id = int(col_data["transaction_id"])

        from PyQt6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLineEdit,
            QVBoxLayout,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Transaction #{txn_id}")
        dialog.setMinimumWidth(550)

        outer_layout = QVBoxLayout(dialog)

        # Editable fields
        editable_fields = [
            "account_number",
            "description",
            "transaction_date",
            "check_number",
            "debit_amount",
            "credit_amount",
            "balance",
            "reconciliation_status",
            "reconciliation_notes",
        ]

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        inputs = {}

        # Transaction context at top
        outer_layout.addWidget(
            QLabel(
                f"<b>Transaction ID:</b> {txn_id} &nbsp;&nbsp; "
                f"<b>Source:</b> {col_data.get('source_file', '')}"
            )
        )

        for field in editable_fields:
            val = col_data.get(field, "")
            inp = QLineEdit(val)
            inp.setMinimumWidth(350)
            form.addRow(field.replace("_", " ").title() + ":", inp)
            inputs[field] = inp

        outer_layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        outer_layout.addWidget(button_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Build UPDATE statement from changed fields
        updates = {}
        for field, inp in inputs.items():
            new_val = inp.text().strip()
            old_val = col_data.get(field, "").strip()
            if new_val != old_val:
                updates[field] = new_val if new_val != "" else None

        if not updates:
            QMessageBox.information(
                self, "No Changes", "No fields were modified."
            )
            return

        try:
            set_clause = ", ".join(f"{f} = %s" for f in updates)
            values = list(updates.values()) + [txn_id]
            cur = self.conn.cursor()
            cur.execute(
                f"UPDATE banking_transactions SET {set_clause} "
                f"WHERE transaction_id = %s",
                values,
            )
            self.conn.commit()
            cur.close()
            QMessageBox.information(
                self,
                "Saved",
                f"✅ Transaction #{txn_id} updated successfully.",
            )
            self._load_transactions()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Save Error", f"Failed to save changes:\n{e}"
            )

    @pyqtSlot()
    def _add_transaction(self) -> None:
        """Add a new banking transaction for manual correction/backfill"
        "work."""

        from PyQt6.QtWidgets import (
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLineEdit,
            QVBoxLayout,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Add Banking Transaction")
        dialog.setMinimumWidth(560)

        outer_layout = QVBoxLayout(dialog)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        account_input = QComboBox()
        account_input.setEditable(True)
        accounts = [
            self.account_combo.itemText(i)
            for i in range(self.account_combo.count())
            if self.account_combo.itemText(i)
            and self.account_combo.itemText(i) != "All Accounts"
        ]
        account_input.addItems(accounts)
        if (
            self.account_combo.currentText()
            and self.account_combo.currentText() != "All Accounts"
        ):
            account_input.setCurrentText(self.account_combo.currentText())

        txn_date_input = QLineEdit(date.today().isoformat())
        txn_date_input.setPlaceholderText("YYYY-MM-DD")

        posted_date_input = QLineEdit("")
        posted_date_input.setPlaceholderText("Optional, YYYY-MM-DD")

        description_input = QLineEdit("")
        description_input.setPlaceholderText(
            "Required description from paper source"
        )

        debit_input = QLineEdit("")
        debit_input.setPlaceholderText("0.00")

        credit_input = QLineEdit("")
        credit_input.setPlaceholderText("0.00")

        balance_input = QLineEdit("")
        balance_input.setPlaceholderText("Optional running balance")

        check_number_input = QLineEdit("")
        check_number_input.setPlaceholderText("Optional cheque/reference")

        category_input = QLineEdit("")
        category_input.setPlaceholderText("Optional category")

        notes_input = QLineEdit("")
        notes_input.setPlaceholderText("Optional reconciliation notes")

        form.addRow("Account Number*:", account_input)
        form.addRow("Transaction Date*:", txn_date_input)
        form.addRow("Posted Date:", posted_date_input)
        form.addRow("Description*:", description_input)
        form.addRow("Debit Amount:", debit_input)
        form.addRow("Credit Amount:", credit_input)
        form.addRow("Balance:", balance_input)
        form.addRow("Check Number:", check_number_input)
        form.addRow("Category:", category_input)
        form.addRow("Notes:", notes_input)

        outer_layout.addLayout(form)
        outer_layout.addWidget(QLabel("* Required fields"))

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        outer_layout.addWidget(button_box)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        account_number = account_input.currentText().strip()
        description = description_input.text().strip()

        if not account_number:
            QMessageBox.warning(
                self, "Missing Data", "Account Number is required."
            )
            return

        if not description:
            QMessageBox.warning(
                self, "Missing Data", "Description is required."
            )
            return

        try:
            transaction_date = self._parse_inline_value(
                "transaction_date", txn_date_input.text()
            )
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Date", str(e))
            return

        posted_text = posted_date_input.text().strip()
        posted_date = None
        if posted_text:
            try:
                posted_date = self._parse_inline_value(
                    "transaction_date", posted_text
                )
            except ValueError as e:
                QMessageBox.warning(self, "Invalid Posted Date", str(e))
                return

        def _parse_amount_or_none(text: str) -> object:
            txt = (text or "").strip()
            if txt == "":
                return None
            return self._parse_inline_value("debit_amount", txt)

        try:
            debit_amount = _parse_amount_or_none(debit_input.text())
            credit_amount = _parse_amount_or_none(credit_input.text())
            balance = _parse_amount_or_none(balance_input.text())
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Amount",
                "Amounts must be numeric (e.g., 125.50).",
            )
            return

        debit_nonzero = debit_amount is not None and float(debit_amount) > 0
        credit_nonzero = credit_amount is not None and float(credit_amount) > 0

        if debit_nonzero and credit_nonzero:
            QMessageBox.warning(
                self,
                "Invalid Amounts",
                "Use either Debit or Credit, not both.",
            )
            return

        if not debit_nonzero and not credit_nonzero:
            QMessageBox.warning(
                self,
                "Invalid Amounts",
                "Enter a Debit or Credit amount greater than 0.",
            )
            return

        transaction_uid = f"manual_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO banking_transactions (
                    account_number,
                    transaction_date,
                    posted_date,
                    description,
                    debit_amount,
                    credit_amount,
                    balance,
                    check_number,
                    category,
                    source_file,
                    reconciliation_notes,
                    transaction_uid
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING transaction_id
                """,
                (
                    account_number,
                    transaction_date,
                    posted_date,
                    description,
                    debit_amount,
                    credit_amount,
                    balance,
                    check_number_input.text().strip() or None,
                    category_input.text().strip() or None,
                    "manual_entry",
                    notes_input.text().strip() or None,
                    transaction_uid,
                ),
            )
            txn_id = cur.fetchone()[0]
            self.conn.commit()
            cur.close()

            QMessageBox.information(
                self, "Saved", f"✅ Transaction #{txn_id} added successfully."
            )
            self._load_accounts()
            self._load_transactions()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Save Error", f"Failed to add transaction:\n{e}"
            )

    @pyqtSlot()
    def _delete_transaction(self) -> None:
        """Delete the selected banking transaction after confirmation."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(
                self, "No Selection", "Please select a transaction to delete."
            )
            return

        row = selected[0].row()

        if "transaction_id" not in self.visible_columns:
            QMessageBox.warning(
                self,
                "Error",
                "Cannot delete: transaction_id column is hidden.",
            )
            return

        txn_id_idx = self.visible_columns.index("transaction_id")
        txn_id_item = self.table.item(row, txn_id_idx)
        txn_id_text = txn_id_item.text().strip() if txn_id_item else ""
        if not txn_id_text:
            QMessageBox.warning(
                self, "Error", "Cannot delete: missing transaction_id."
            )
            return

        try:
            txn_id = int(txn_id_text)
        except ValueError:
            QMessageBox.warning(
                self, "Error", "Cannot delete: invalid transaction_id."
            )
            return

        txn_date = ""
        description = ""
        debit = ""
        credit = ""

        if "transaction_date" in self.visible_columns:
            idx = self.visible_columns.index("transaction_date")
            item = self.table.item(row, idx)
            txn_date = item.text().strip() if item else ""

        if "description" in self.visible_columns:
            idx = self.visible_columns.index("description")
            item = self.table.item(row, idx)
            description = item.text().strip() if item else ""

        if "debit_amount" in self.visible_columns:
            idx = self.visible_columns.index("debit_amount")
            item = self.table.item(row, idx)
            debit = item.text().strip() if item else ""

        if "credit_amount" in self.visible_columns:
            idx = self.visible_columns.index("credit_amount")
            item = self.table.item(row, idx)
            credit = item.text().strip() if item else ""

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            (
                f"Delete Transaction #{txn_id}?\n\n"
                f"Date: {txn_date or 'N/A'}\n"
                f"Description: {description or 'N/A'}\n"
                f"Debit: {debit or '$0.00'}\n"
                f"Credit: {credit or '$0.00'}\n\n"
                "This cannot be undone."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            cur = self.conn.cursor()
            # Clear all known FK references that can block deletion.
            cur.execute(
                "DELETE FROM receipt_banking_links WHERE transaction_id = %s",
                (txn_id,),
            )
            cur.execute(
                "UPDATE etransfer_transactions SET banking_transaction_id ="
                "NULL WHERE banking_transaction_id = %s",
                (txn_id,),
            )
            cur.execute(
                "UPDATE etransfer_banking_reconciliation SET transaction_id ="
                "NULL WHERE transaction_id = %s",
                (txn_id,),
            )
            cur.execute(
                "UPDATE square_etransfer_reconciliation SET "
                "banking_transaction_id = NULL WHERE banking_transaction_id = "
                "%s",
                (txn_id,),
            )
            cur.execute(
                "UPDATE cash_box_transactions SET banking_transaction_id ="
                "NULL WHERE banking_transaction_id = %s",
                (txn_id,),
            )
            cur.execute(
                "UPDATE chauffeur_float_tracking SET banking_transaction_id ="
                "NULL WHERE banking_transaction_id = %s",
                (txn_id,),
            )
            cur.execute(
                "UPDATE cibc_card_transactions SET banking_transaction_id ="
                "NULL WHERE banking_transaction_id = %s",
                (txn_id,),
            )
            cur.execute(
                "UPDATE owner_expense_transactions SET banking_transaction_id"
                "= NULL WHERE banking_transaction_id = %s",
                (txn_id,),
            )
            cur.execute(
                "UPDATE cheque_register SET banking_transaction_id = NULL "
                "WHERE banking_transaction_id = %s",
                (txn_id,),
            )
            cur.execute(
                "DELETE FROM banking_transactions WHERE transaction_id = %s",
                (txn_id,),
            )
            deleted = cur.rowcount

            if deleted != 1:
                self.conn.rollback()
                cur.close()
                QMessageBox.warning(
                    self,
                    "Not Deleted",
                    f"Transaction #{txn_id} was not found.",
                )
                return

            self.conn.commit()
            cur.close()
            QMessageBox.information(
                self,
                "Deleted",
                f"✅ Transaction #{txn_id} deleted successfully.",
            )
            self._load_transactions()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self,
                "Delete Error",
                (
                    f"Failed to delete transaction #{txn_id}.\n\n{e} \n\n"
                    "If this transaction is linked to other records, unlink"
                    "those records first and try again."
                ),
            )

    @pyqtSlot()
    def _link_to_receipt(self) -> None:
        """Open dialog to link this transaction to a receipt."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(
                self, "No Selection", "Please select a transaction to link."
            )
            return

        row = selected[0].row()

        if "transaction_id" not in self.visible_columns:
            QMessageBox.warning(
                self,
                "Error",
                "Cannot link: transaction_id column not visible.",
            )
            return

        txn_id_idx = self.visible_columns.index("transaction_id")
        txn_id = int(self.table.item(row, txn_id_idx).text())

        # Get transaction description for context
        desc = ""
        if "description" in self.visible_columns:
            desc_idx = self.visible_columns.index("description")
            desc = self.table.item(row, desc_idx).text()

        # Simple dialog to enter receipt ID
        from PyQt6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QLabel,
            QLineEdit,
            QVBoxLayout,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Link Transaction #{txn_id}")
        dialog.setGeometry(300, 300, 400, 200)

        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(f"Transaction: {desc}"))
        layout.addWidget(QLabel("\nEnter Receipt ID to link:"))

        receipt_id_input = QLineEdit()
        receipt_id_input.setPlaceholderText("Receipt ID")
        layout.addWidget(receipt_id_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                receipt_id = int(receipt_id_input.text())

                # Update the banking transaction
                cur = self.conn.cursor()
                cur.execute(
                    "UPDATE banking_transactions SET receipt_id = %s "
                    "WHERE transaction_id = %s",
                    (receipt_id, txn_id),
                )
                self.conn.commit()
                cur.close()

                QMessageBox.information(
                    self,
                    "Linked",
                    f"✅ Transaction #{txn_id} linked to Receipt #{receipt_id}",
                )

                # Refresh table
                self._load_transactions()

            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Please enter a valid receipt ID number.",
                )
            except Exception as e:
                try:
                    self.conn.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
                QMessageBox.critical(
                    self, "Link Error", f"Failed to link transaction:\n{e}"
                )
