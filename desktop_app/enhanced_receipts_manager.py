"""
Enhanced Receipts Manager - Comprehensive receipt browsing with full editing
Features: All fields, fuzzy lookup, column toggles, splits, direct editing
"""

import logging
from datetime import date, datetime, timedelta

import psycopg2
from common_widgets import StandardDateEdit
from enhanced_receipts_import_export import (
    EnhancedReceiptsImportExport,
)
from print_export_helper import PrintExportHelper
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
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


class SortableTableWidgetItem(QTableWidgetItem):
    """Table item with explicit sort value so date/amount sorting is"
    "reliable."""

    def __init__(self, text: str, sort_value=None) -> None:
        super().__init__(text)
        self.sort_value = sort_value if sort_value is not None else text

    def __lt__(self, other) -> object:
        if isinstance(other, SortableTableWidgetItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class EnhancedReceiptsManager(QWidget):
    """Comprehensive receipts management with all fields and direct editing."""

    def __init__(self, conn: psycopg2.extensions.connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self._last_loaded_count = 0
        self._report_presets = {
            "custom": None,
            "vendor_month": {
                "columns": [
                    "receipt_id",
                    "receipt_date",
                    "vendor_name",
                    "description",
                    "gross_amount",
                    "gst_amount",
                    "net_amount",
                    "gl_account_code",
                    "payment_method",
                    "verified_by_edit",
                    "comment",
                ],
                "group_by": "receipt_date",
            },
            "vendor_year": {
                "columns": [
                    "receipt_id",
                    "receipt_date",
                    "vendor_name",
                    "description",
                    "gross_amount",
                    "gst_amount",
                    "net_amount",
                    "gl_account_code",
                    "payment_method",
                    "verified_by_edit",
                    "receipt_review_status",
                    "comment",
                ],
                "group_by": "receipt_date",
                "month_index": 0,
            },
            "unverified_queue": {
                "columns": [
                    "receipt_id",
                    "receipt_date",
                    "vendor_name",
                    "description",
                    "gross_amount",
                    "gl_account_code",
                    "payment_method",
                    "banking_transaction_id",
                    "verified_by_edit",
                    "receipt_review_status",
                    "comment",
                ],
                "show_unverified": True,
                "show_verified": False,
                "review_status": "UNREVIEWED",
                "group_by": "vendor_name",
            },
            "investigation_queue": {
                "columns": [
                    "receipt_id",
                    "receipt_date",
                    "vendor_name",
                    "description",
                    "gross_amount",
                    "gl_account_code",
                    "payment_method",
                    "banking_transaction_id",
                    "receipt_review_status",
                    "comment",
                ],
                "review_status": "INVESTIGATE",
                "group_by": "vendor_name",
            },
            "double_verified_audit": {
                "columns": [
                    "receipt_id",
                    "receipt_date",
                    "vendor_name",
                    "description",
                    "gross_amount",
                    "gst_amount",
                    "gl_account_code",
                    "payment_method",
                    "verified_by_edit",
                    "verified_at",
                    "receipt_review_status",
                    "comment",
                ],
                "review_status": "DOUBLE_VERIFIED",
                "group_by": "vendor_name",
            },
        }
        self.all_columns = [
            "receipt_id",
            "receipt_date",
            "vendor_name",
            "gross_amount",
            "gst_amount",
            "net_amount",
            "description",
            "category",
            "gl_account_code",
            "gl_account_name",
            "payment_method",
            "banking_transaction_id",
            "charter_id",
            "vehicle_number",
            "employee_id",
            "fuel_amount",
            "business_personal",
            "verified_by_edit",
            "verified_at",
            "fiscal_year",
            "split_group_id",
            "comment",
        ]
        self.visible_columns = self.all_columns.copy()
        self._build_ui()
        self._load_vendors()
        self._load_receipts()

    def _build_ui(self) -> None:
        """Build comprehensive UI."""
        layout = QVBoxLayout(self)

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

        btn_ytd = QPushButton("YTD")
        btn_ytd.clicked.connect(self._set_ytd)
        date_btns.addWidget(btn_ytd)

        btn_last_year = QPushButton("Last Year")
        btn_last_year.clicked.connect(self._set_last_year)
        date_btns.addWidget(btn_last_year)

        date_btns.addStretch()
        layout.addLayout(date_btns)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("📄 Report Preset:"))

        self.report_preset_combo = QComboBox()
        self.report_preset_combo.addItem("Custom View", "custom")
        self.report_preset_combo.addItem(
            "Vendor Month Printout", "vendor_month"
        )
        self.report_preset_combo.addItem("Vendor Year Printout", "vendor_year")
        self.report_preset_combo.addItem(
            "Unverified Review Queue", "unverified_queue"
        )
        self.report_preset_combo.addItem(
            "Investigation Queue", "investigation_queue"
        )
        self.report_preset_combo.addItem(
            "Double Verified Audit", "double_verified_audit"
        )
        preset_row.addWidget(self.report_preset_combo)

        apply_preset_btn = QPushButton("Apply Preset")
        apply_preset_btn.clicked.connect(self._apply_report_preset)
        preset_row.addWidget(apply_preset_btn)
        preset_row.addStretch()
        layout.addLayout(preset_row)

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
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.setSpecialValueText("All Years")
        month_year.addWidget(self.year_spin)

        month_year.addStretch()
        layout.addLayout(month_year)

        # === FILTERS ===
        filters = QGroupBox("🔍 Filters")
        filter_grid = QGridLayout(filters)

        # Row 1
        filter_grid.addWidget(QLabel("Vendor:"), 0, 0)
        self.vendor_filter = QComboBox()
        self.vendor_filter.setEditable(True)
        self.vendor_filter.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        filter_grid.addWidget(self.vendor_filter, 0, 1)

        filter_grid.addWidget(QLabel("Date From:"), 0, 2)
        self.date_from = StandardDateEdit(allow_blank=True)
        filter_grid.addWidget(self.date_from, 0, 3)

        filter_grid.addWidget(QLabel("Date To:"), 0, 4)
        self.date_to = StandardDateEdit(allow_blank=True)
        filter_grid.addWidget(self.date_to, 0, 5)

        # Row 2
        filter_grid.addWidget(QLabel("Amount Min:"), 1, 0)
        self.amount_min = QDoubleSpinBox()
        self.amount_min.setRange(0, 999999)
        self.amount_min.setPrefix("$")
        filter_grid.addWidget(self.amount_min, 1, 1)

        filter_grid.addWidget(QLabel("Amount Max:"), 1, 2)
        self.amount_max = QDoubleSpinBox()
        self.amount_max.setRange(0, 999999)
        self.amount_max.setValue(999999)
        self.amount_max.setPrefix("$")
        filter_grid.addWidget(self.amount_max, 1, 3)

        filter_grid.addWidget(QLabel("Category:"), 1, 4)
        self.category_filter = QLineEdit()
        filter_grid.addWidget(self.category_filter, 1, 5)

        # Row 3
        filter_grid.addWidget(QLabel("GL Code:"), 2, 0)
        self.gl_filter = QLineEdit()
        filter_grid.addWidget(self.gl_filter, 2, 1)

        filter_grid.addWidget(QLabel("Vehicle:"), 2, 2)
        self.vehicle_filter = QLineEdit()
        filter_grid.addWidget(self.vehicle_filter, 2, 3)

        filter_grid.addWidget(QLabel("Driver:"), 2, 4)
        self.driver_filter = QLineEdit()
        filter_grid.addWidget(self.driver_filter, 2, 5)

        # Row 3b - Banking Transaction ID
        filter_grid.addWidget(QLabel("Banking Txn ID:"), 2, 6)
        self.banking_txn_id_filter = QLineEdit()
        self.banking_txn_id_filter.setPlaceholderText(
            "Search by banking_transaction_id..."
        )
        filter_grid.addWidget(self.banking_txn_id_filter, 2, 7)

        # Row 4 - Checkboxes
        self.show_verified = QCheckBox("Verified Only")
        filter_grid.addWidget(self.show_verified, 3, 0)

        self.show_unverified = QCheckBox("Unverified Only")
        filter_grid.addWidget(self.show_unverified, 3, 1)

        self.bp_filter = QComboBox()
        self.bp_filter.addItems(
            ["🏢 Bus/Personal: All", "Business Only", "Personal Only"]
        )
        self.bp_filter.setToolTip("Filter by Business/Personal flag")
        self.bp_filter.currentIndexChanged.connect(self._load_receipts)
        self.bp_filter.setMinimumWidth(160)
        filter_grid.addWidget(self.bp_filter, 3, 2, 1, 2)

        self.show_splits = QCheckBox("Split Receipts Only")
        filter_grid.addWidget(self.show_splits, 3, 4)

        self.show_with_banking = QCheckBox("With Banking Link")
        filter_grid.addWidget(self.show_with_banking, 3, 5)

        self.show_no_banking = QCheckBox("No Banking Link")
        filter_grid.addWidget(self.show_no_banking, 3, 6)

        self.show_cash = QCheckBox("Cash Purchases")
        filter_grid.addWidget(self.show_cash, 3, 7)

        self.show_cheque = QCheckBox("Cheque Payments")
        filter_grid.addWidget(self.show_cheque, 3, 8)

        filter_grid.addWidget(QLabel("Review Status:"), 4, 0)
        self.review_status_filter = QComboBox()
        self.review_status_filter.addItem("All Review Statuses", "ALL")
        self.review_status_filter.addItem("Unreviewed", "UNREVIEWED")
        self.review_status_filter.addItem("Double Verified", "DOUBLE_VERIFIED")
        self.review_status_filter.addItem("Investigate", "INVESTIGATE")
        self.review_status_filter.addItem(
            "Review Mismatch High", "REVIEW_MISM_HI"
        )
        self.review_status_filter.addItem(
            "Review Mismatch Low", "REVIEW_MISM_LO"
        )
        self.review_status_filter.addItem(
            "Cross-Account Review", "XACC_REVIEW"
        )
        self.review_status_filter.addItem(
            "Auto Cross-Account Dup", "XACC_DUP_AUTO"
        )
        self.review_status_filter.addItem(
            "Duplicate Same Banking", "DUP_SAME_BANKING"
        )
        self.review_status_filter.addItem(
            "Non Expense Reversal", "NON_EXPENSE_REV"
        )
        filter_grid.addWidget(self.review_status_filter, 4, 1, 1, 2)

        layout.addWidget(filters)

        # === ACTION BUTTONS ===
        actions = QHBoxLayout()

        search_btn = QPushButton("🔍 Search")
        search_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        search_btn.clicked.connect(self._load_receipts)
        actions.addWidget(search_btn)

        clear_btn = QPushButton("Clear Filters")
        clear_btn.clicked.connect(self._clear_filters)
        actions.addWidget(clear_btn)

        select_all_btn = QPushButton("☑ Select Filtered")
        select_all_btn.clicked.connect(self._select_all_filtered)
        actions.addWidget(select_all_btn)

        clear_selected_btn = QPushButton("☐ Clear Checks")
        clear_selected_btn.clicked.connect(self._clear_checked)
        actions.addWidget(clear_selected_btn)

        mark_verified_btn = QPushButton("✅ Mark Verified")
        mark_verified_btn.clicked.connect(self._bulk_mark_verified)
        actions.addWidget(mark_verified_btn)

        double_verify_btn = QPushButton("✅✅ Double Verify")
        double_verify_btn.clicked.connect(self._bulk_mark_double_verified)
        actions.addWidget(double_verify_btn)

        investigate_btn = QPushButton("🔎 Investigate")
        investigate_btn.clicked.connect(self._bulk_mark_investigate)
        actions.addWidget(investigate_btn)

        # CRUD Actions
        add_btn = QPushButton("➕ Add Receipt")
        add_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        add_btn.clicked.connect(self._add_receipt)
        actions.addWidget(add_btn)

        edit_btn = QPushButton("✏️ Edit Selected")
        edit_btn.setStyleSheet(
            "background-color: #2196F3; color: white; font-weight: bold;"
        )
        edit_btn.clicked.connect(lambda: self._edit_selected_receipt())
        actions.addWidget(edit_btn)

        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.setStyleSheet("background-color: #f44336; color: white;")
        delete_btn.clicked.connect(self._delete_receipt)
        actions.addWidget(delete_btn)

        actions.addStretch()

        # Group-by selector for printing
        actions.addWidget(QLabel("📊 Group by:"))
        self.print_group_by = QComboBox()
        self.print_group_by.addItem("None", None)
        self.print_group_by.addItem("Vendor", "vendor_name")
        self.print_group_by.addItem("Category", "category")
        self.print_group_by.addItem("GL Code", "gl_account_code")
        self.print_group_by.addItem("Date", "receipt_date")
        self.print_group_by.setMaximumWidth(120)
        actions.addWidget(self.print_group_by)

        # Column visibility menu
        columns_btn = QPushButton("⚙️ Show/Hide Columns")
        columns_btn.clicked.connect(self._show_column_menu)
        actions.addWidget(columns_btn)

        export_btn = QPushButton("📊 Export Excel")
        export_btn.clicked.connect(self._export_filtered_excel)
        actions.addWidget(export_btn)

        export_checked_btn = QPushButton("☑📊 Export Checked")
        export_checked_btn.clicked.connect(self._export_checked_excel)
        actions.addWidget(export_checked_btn)

        import_btn = QPushButton("📥 Import & Update from Excel")
        import_btn.clicked.connect(
            lambda: EnhancedReceiptsImportExport.import_from_excel(
                self.conn, self.table, self
            )
        )
        actions.addWidget(import_btn)

        print_btn = QPushButton("🖨️ Print Preview")
        print_btn.clicked.connect(self._print_receipts)
        actions.addWidget(print_btn)

        print_checked_btn = QPushButton("☑🖨️ Print Checked")
        print_checked_btn.clicked.connect(self._print_checked_receipts)
        actions.addWidget(print_checked_btn)

        layout.addLayout(actions)

        # === RESULTS LABEL ===
        self.results_label = QLabel("No receipts loaded")
        layout.addWidget(self.results_label)

        self.report_hint_label = QLabel(
            "Print/Export uses the current filtered and sorted view. Use"
            "checkboxes for bulk review actions."
        )
        self.report_hint_label.setStyleSheet(
            "color: #4b5563; font-style: italic;"
        )
        layout.addWidget(self.report_hint_label)

        # === TABLE ===
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        # Enable click-to-sort on column headers
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.table.itemDoubleClicked.connect(self._edit_receipt)
        layout.addWidget(self.table)

    def _load_vendors(self) -> None:
        """Load vendor list for fuzzy autocomplete."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT DISTINCT vendor_name
                FROM receipts
                WHERE vendor_name IS NOT NULL
                ORDER BY vendor_name
            """)
            vendors = ["All"] + [row[0] for row in cur.fetchall()]
            self.vendor_filter.addItems(vendors)
            cur.close()
        except Exception as e:
            logger.error("Error loading vendors: %s", e)

    def _set_date_range(self, days_back: int, days_forward: int = 0) -> None:
        """Set date range relative to today."""
        today = date.today()
        self.date_from.setDate(today - timedelta(days=days_back))
        self.date_to.setDate(today + timedelta(days=days_forward))

    @pyqtSlot()
    def _set_this_week(self) -> None:
        """Set to current week (Monday-Sunday)."""
        today = date.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        self.date_from.setDate(start)
        self.date_to.setDate(end)

    @pyqtSlot()
    def _set_this_month(self) -> None:
        """Set to current month."""
        today = date.today()
        self.date_from.setDate(date(today.year, today.month, 1))
        if today.month == 12:
            self.date_to.setDate(date(today.year, 12, 31))
        else:
            self.date_to.setDate(
                date(today.year, today.month + 1, 1) - timedelta(days=1)
            )

    @pyqtSlot()
    def _set_last_month(self) -> None:
        """Set to previous month."""
        today = date.today()
        if today.month == 1:
            self.date_from.setDate(date(today.year - 1, 12, 1))
            self.date_to.setDate(date(today.year - 1, 12, 31))
        else:
            self.date_from.setDate(date(today.year, today.month - 1, 1))
            self.date_to.setDate(
                date(today.year, today.month, 1) - timedelta(days=1)
            )

    @pyqtSlot()
    def _set_ytd(self) -> None:
        """Set to year-to-date."""
        today = date.today()
        self.date_from.setDate(date(today.year, 1, 1))
        self.date_to.setDate(today)

    @pyqtSlot()
    def _set_last_year(self) -> None:
        """Set to full previous year."""
        today = date.today()
        self.date_from.setDate(date(today.year - 1, 1, 1))
        self.date_to.setDate(date(today.year - 1, 12, 31))

    @pyqtSlot()
    def _clear_filters(self) -> None:
        """Clear all filter fields."""
        self.vendor_filter.setCurrentIndex(0)
        self.date_from.setDate(None)
        self.date_to.setDate(None)
        self.amount_min.setValue(0)
        self.amount_max.setValue(999999)
        self.category_filter.clear()
        self.gl_filter.clear()
        self.vehicle_filter.clear()
        self.driver_filter.clear()
        self.banking_txn_id_filter.clear()
        self.show_verified.setChecked(False)
        self.show_unverified.setChecked(False)
        self.bp_filter.setCurrentIndex(0)
        self.show_splits.setChecked(False)
        self.show_with_banking.setChecked(False)
        self.show_no_banking.setChecked(False)
        self.show_cash.setChecked(False)
        self.show_cheque.setChecked(False)
        self.month_combo.setCurrentIndex(0)
        self.year_spin.setValue(datetime.now().year)
        self.review_status_filter.setCurrentIndex(0)
        self.report_preset_combo.setCurrentIndex(0)

    @pyqtSlot()
    def _apply_report_preset(self) -> None:
        """Apply a predefined report layout/filter preset."""
        preset_key = self.report_preset_combo.currentData()
        preset = self._report_presets.get(preset_key)
        if not preset:
            return

        if "columns" in preset:
            self.visible_columns = [
                col for col in self.all_columns if col in preset["columns"]
            ]

        if "show_verified" in preset:
            self.show_verified.setChecked(bool(preset["show_verified"]))
        if "show_unverified" in preset:
            self.show_unverified.setChecked(bool(preset["show_unverified"]))
        if "month_index" in preset:
            self.month_combo.setCurrentIndex(preset["month_index"])
        if "review_status" in preset:
            idx = self.review_status_filter.findData(preset["review_status"])
            if idx >= 0:
                self.review_status_filter.setCurrentIndex(idx)
        if "group_by" in preset:
            idx = self.print_group_by.findData(preset["group_by"])
            if idx >= 0:
                self.print_group_by.setCurrentIndex(idx)

        self._load_receipts()

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
            # Add column and maintain original order from all_columns
            self.visible_columns = [
                col
                for col in self.all_columns
                if col in self.visible_columns or col == column
            ]
        elif not visible and column in self.visible_columns:
            self.visible_columns.remove(column)
        self._load_receipts()

    def _table_column_index(self, column_name: str) -> int:
        """Return table column index accounting for leading checkbox column."""
        return 1 + self.visible_columns.index(column_name)

    def _current_report_title(self, checked_only: bool = False) -> str:
        """Build report title from active filters."""
        parts = ["Receipts Report"]

        preset_text = self.report_preset_combo.currentText()
        if preset_text and preset_text != "Custom View":
            parts.append(preset_text)

        vendor = (self.vendor_filter.currentText() or "").strip()
        if vendor and vendor != "All":
            parts.append(f"Vendor: {vendor}")

        month_idx = self.month_combo.currentIndex()
        year = self.year_spin.value()
        if month_idx > 0 and year > 2010:
            parts.append(f"{self.month_combo.currentText()} {year}")
        elif month_idx > 0:
            parts.append(self.month_combo.currentText())
        elif year > 2010:
            parts.append(str(year))

        review_status = self.review_status_filter.currentData()
        if review_status == "UNREVIEWED":
            parts.append("Unreviewed")
        elif review_status and review_status != "ALL":
            parts.append(review_status)

        if checked_only:
            parts.append("Checked Rows")

        return " - ".join(parts)

    def _build_report_table(self, checked_only: bool = False) -> QTableWidget:
        """Create a print/export-safe copy of the current table without"
        "checkbox column."""

        report_table = QTableWidget()
        report_table.setColumnCount(len(self.visible_columns))
        report_table.setHorizontalHeaderLabels(
            [col.replace("_", " ").title() for col in self.visible_columns]
        )

        rows_to_copy = []
        checked_receipt_ids = (
            set(self._get_checked_receipt_ids()) if checked_only else set()
        )
        receipt_idx = (
            self._table_column_index("receipt_id")
            if "receipt_id" in self.visible_columns
            else None
        )

        for row in range(self.table.rowCount()):
            if checked_only and receipt_idx is not None:
                receipt_item = self.table.item(row, receipt_idx)
                if (
                    not receipt_item
                    or int(receipt_item.text()) not in checked_receipt_ids
                ):
                    continue
            rows_to_copy.append(row)

        report_table.setRowCount(len(rows_to_copy))

        for report_row, row in enumerate(rows_to_copy):
            for col in range(len(self.visible_columns)):
                source_item = self.table.item(row, col + 1)
                cloned = QTableWidgetItem(
                    source_item.text() if source_item else ""
                )
                if source_item:
                    cloned.setBackground(source_item.background())
                    cloned.setForeground(source_item.foreground())
                    cloned.setTextAlignment(source_item.textAlignment())
                report_table.setItem(report_row, col, cloned)

        return report_table

    def _get_checked_receipt_ids(self) -> list[int]:
        """Return receipt IDs for rows checked in the filtered view."""
        checked_ids = []
        if "receipt_id" not in self.visible_columns:
            return checked_ids

        receipt_idx = self._table_column_index("receipt_id")
        for row in range(self.table.rowCount()):
            checkbox_item = self.table.item(row, 0)
            if (
                checkbox_item
                and checkbox_item.checkState() == Qt.CheckState.Checked
            ):
                receipt_item = self.table.item(row, receipt_idx)
                if receipt_item and receipt_item.text().strip():
                    checked_ids.append(int(receipt_item.text()))
        return checked_ids

    @pyqtSlot()
    def _select_all_filtered(self) -> None:
        """Check all currently filtered rows."""
        for row in range(self.table.rowCount()):
            checkbox_item = self.table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.CheckState.Checked)

    @pyqtSlot()
    def _clear_checked(self) -> None:
        """Clear checked rows in the current filtered view."""
        for row in range(self.table.rowCount()):
            checkbox_item = self.table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(Qt.CheckState.Unchecked)

    def _bulk_update_receipts(
        self,
        title: str,
        sql: str,
        extra_params_func=None,
        success_message=None,
    ) -> None:
        """Apply a bulk update to checked receipts in the current filtered"
        "view."""

        receipt_ids = self._get_checked_receipt_ids()
        if not receipt_ids:
            QMessageBox.information(
                self,
                title,
                "No checked receipts in the current filtered view.",
            )
            return

        try:
            cur = self.conn.cursor()
            updated = 0
            for receipt_id in receipt_ids:
                params = (
                    extra_params_func(receipt_id)
                    if extra_params_func
                    else (receipt_id,)
                )
                cur.execute(sql, params)
                updated += cur.rowcount
            self.conn.commit()
            cur.close()
            QMessageBox.information(
                self,
                title,
                success_message
                or (
                    f"Updated {updated} receipt(s) from the "
                    "filtered result set."
                ),
            )
            self._load_receipts()
        except Exception as e:
            logger.error("Bulk update failed: %s", e)
            QMessageBox.critical(self, title, f"Bulk update failed:\n{e}")

    @pyqtSlot()
    def _bulk_mark_verified(self) -> None:
        """Mark checked filtered receipts as manually verified."""
        self._bulk_update_receipts(
            "Bulk Verify",
            """
            UPDATE receipts
            SET verified_by_edit = TRUE,
                verified_at = NOW(),
                receipt_review_status = 'VERIFIED',
                receipt_review_notes = COALESCE(receipt_review_notes, '') ||
                    CASE
                        WHEN COALESCE(receipt_review_notes, '') = ''
                        THEN ''
                        ELSE E'\n'
                    END ||
                    'Manual verification marked from Enhanced Receipts Manager.',
                receipt_reviewed_at = NOW()
            WHERE receipt_id = %s
            """,
            success_message="Marked checked filtered receipts as verified.",
        )

    @pyqtSlot()
    def _bulk_mark_double_verified(self) -> None:
        """Mark checked filtered receipts as manual double verification"
        "complete."""

        self._bulk_update_receipts(
            "Double Verification",
            """
            UPDATE receipts
            SET verified_by_edit = TRUE,
                verified_at = NOW(),
                receipt_review_status = 'DOUBLE_VERIFIED',
                receipt_review_notes = COALESCE(receipt_review_notes, '') ||
                    CASE
                        WHEN COALESCE(receipt_review_notes, '') = ''
                        THEN ''
                        ELSE E'\n'
                    END ||
                    'Manual double verification marked from Enhanced Receipts'
                    'Manager.',

                receipt_reviewed_at = NOW()
            WHERE receipt_id = %s
            """,
            success_message=(
                "Marked checked filtered receipts as "
                "double verified."
            ),
        )

    @pyqtSlot()
    def _bulk_mark_investigate(self) -> None:
        """Mark checked filtered receipts for manual investigation."""
        note, ok = QInputDialog.getText(
            self,
            "Investigate Receipts",
            "Optional note for investigation status:",
        )
        if not ok:
            return

        self._bulk_update_receipts(
            "Investigate Receipts",
            """
            UPDATE receipts
            SET receipt_review_status = 'INVESTIGATE',
                receipt_review_notes = COALESCE(receipt_review_notes, '') ||
                    CASE
                        WHEN COALESCE(receipt_review_notes, '') = ''
                        THEN ''
                        ELSE E'\n'
                    END ||
                    %s,
                receipt_reviewed_at = NOW()
            WHERE receipt_id = %s
            """,
            extra_params_func=lambda receipt_id: (
                note.strip()
                or (
                    "Flagged for manual investigation from "
                    "Enhanced Receipts Manager."
                ),
                receipt_id,
            ),
            success_message=(
                "Marked checked filtered receipts "
                "for investigation."
            ),
        )

    @pyqtSlot()
    def _export_filtered_excel(self) -> None:
        """Export filtered report view without checkbox column."""

        report_table = self._build_report_table(checked_only=False)
        EnhancedReceiptsImportExport.export_to_excel(
            self.conn, report_table, self
        )

    @pyqtSlot()
    def _export_checked_excel(self) -> None:
        """Export only checked rows from the current filtered view."""
        if not self._get_checked_receipt_ids():
            QMessageBox.information(
                self,
                "Export Checked",
                "No checked receipts in the current filtered view.",
            )
            return

        report_table = self._build_report_table(checked_only=True)
        EnhancedReceiptsImportExport.export_to_excel(
            self.conn, report_table, self
        )

    def _load_receipts(self) -> None:
        """Load receipts with all applied filters."""
        try:
            # Build query
            allowed_columns = [
                col for col in self.visible_columns if col in self.all_columns
            ]
            if not allowed_columns:
                raise ValueError("No valid columns selected")
            select_cols = ", ".join([f"r.{col}" for col in allowed_columns])
            sql = [f"SELECT {select_cols} FROM receipts r WHERE 1=1"]
            params = []

            # Vendor filter (fuzzy)
            vendor = self.vendor_filter.currentText()
            if vendor and vendor != "All":
                sql.append("AND LOWER(r.vendor_name) LIKE LOWER(%s)")
                params.append(f"%{vendor}%")

            # Date filters
            date_from = self.date_from.getDate()
            date_to = self.date_to.getDate()
            if date_from:
                sql.append("AND r.receipt_date >= %s")
                params.append(date_from)
            if date_to:
                sql.append("AND r.receipt_date <= %s")
                params.append(date_to)

            # Month/Year filter
            month_idx = self.month_combo.currentIndex()
            if month_idx > 0:
                sql.append("AND EXTRACT(MONTH FROM r.receipt_date) = %s")
                params.append(month_idx)

            year = self.year_spin.value()
            if year > 2010:
                sql.append("AND EXTRACT(YEAR FROM r.receipt_date) = %s")
                params.append(year)

            # Amount range
            if self.amount_min.value() > 0 or self.amount_max.value() < 999999:
                sql.append("AND r.gross_amount BETWEEN %s AND %s")
                params.extend(
                    [self.amount_min.value(), self.amount_max.value()]
                )

            # Category
            if self.category_filter.text():
                sql.append("AND LOWER(r.category) LIKE LOWER(%s)")
                params.append(f"%{self.category_filter.text()}%")

            # GL Code
            if self.gl_filter.text():
                sql.append(
                    "AND (LOWER(r.gl_account_code) LIKE LOWER(%s) OR"
                    "LOWER(r.gl_account_name) LIKE LOWER(%s))"
                )
                params.extend(
                    [
                        f"%{self.gl_filter.text()}%",
                        f"%{self.gl_filter.text()}%",
                    ]
                )

            # Vehicle
            if self.vehicle_filter.text():
                sql.append("AND LOWER(r.vehicle_number) LIKE LOWER(%s)")
                params.append(f"%{self.vehicle_filter.text()}%")

            # Driver
            if self.driver_filter.text():
                sql.append("AND LOWER(r.driver_name) LIKE LOWER(%s)")
                params.append(f"%{self.driver_filter.text()}%")

            # Banking Transaction ID
            if self.banking_txn_id_filter.text():
                try:
                    banking_txn_id = int(self.banking_txn_id_filter.text())
                    sql.append("AND r.banking_transaction_id = %s")
                    params.append(banking_txn_id)
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Invalid Input",
                        "Banking Transaction ID must be a number",
                    )
                    return

            # Checkboxes
            if self.show_verified.isChecked():
                sql.append("AND r.verified_by_edit = TRUE")
            if self.show_unverified.isChecked():
                sql.append(
                    "AND (r.verified_by_edit = FALSE OR r.verified_by_edit IS"
                    "NULL)"
                )
            review_status = self.review_status_filter.currentData()
            if review_status == "UNREVIEWED":
                sql.append(
                    "AND (r.receipt_review_status IS NULL OR"
                    "TRIM(r.receipt_review_status) = '')"
                )
            elif review_status and review_status != "ALL":
                sql.append("AND r.receipt_review_status = %s")
                params.append(review_status)
            bp_sel = self.bp_filter.currentText()
            if bp_sel == "Business Only":
                sql.append("AND r.business_personal = 'Business'")
            elif bp_sel == "Personal Only":
                sql.append("AND r.business_personal = 'Personal'")
            if self.show_splits.isChecked():
                sql.append("AND r.split_group_id IS NOT NULL")
            if (
                self.show_with_banking.isChecked()
                and not self.show_no_banking.isChecked()
            ):
                sql.append("AND r.banking_transaction_id IS NOT NULL")
            elif (
                self.show_no_banking.isChecked()
                and not self.show_with_banking.isChecked()
            ):
                sql.append("AND r.banking_transaction_id IS NULL")

            payment_methods = []
            if self.show_cash.isChecked():
                payment_methods.append("cash")
            if self.show_cheque.isChecked():
                payment_methods.extend(["check", "cheque"])
            if payment_methods:
                sql.append(
                    "AND LOWER(COALESCE(r.payment_method, '')) = ANY(%s)"
                )
                params.append(payment_methods)

            # CRITICAL: Group split receipts together by split_group_id
            # This ensures splits are always visible together regardless of
            # filters
            # Using CASE to sort splits together: receipts with same
            # split_group_id stay adjacent
            # Sort DESC (newest first) so newly-added backfill receipts are
            # visible at the top
            sql.append("""
            ORDER BY
              COALESCE(r.split_group_id, r.receipt_id) DESC,
              CASE WHEN r.split_group_id IS NOT NULL THEN r.receipt_date END
              DESC,
              r.receipt_id DESC
            LIMIT 5000
            """)

            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()

            rows = self._augment_split_group_rows(rows, allowed_columns)

            self._populate_table(rows)
            self._last_loaded_count = len(rows)

            # Stats - check if columns are visible before calculating
            total = len(rows)

            # Verified count
            if "verified_by_edit" in self.visible_columns:
                verified_idx = self.visible_columns.index("verified_by_edit")
                verified = sum(
                    1
                    for row in rows
                    if verified_idx < len(row) and row[verified_idx]
                )
            else:
                verified = 0

            # Splits count
            if "split_group_id" in self.visible_columns:
                splits_idx = self.visible_columns.index("split_group_id")
                splits = sum(
                    1
                    for row in rows
                    if splits_idx < len(row) and row[splits_idx]
                )
            else:
                splits = 0

            # Total amount
            if "gross_amount" in self.visible_columns:
                amount_idx = self.visible_columns.index("gross_amount")
                total_amount = sum(row[amount_idx] or 0 for row in rows)
            else:
                total_amount = 0

            self.results_label.setText(
                f"📊 {total} receipts | ✅ {verified} verified | ✂️ {splits}"
                f"splits | 💰 ${total_amount:,.2f}"
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load receipts:\n{e}"
            )
            import traceback

            traceback.print_exc()

    def _populate_table(self, rows) -> None:
        """Populate table with receipt data."""
        # Disable sorting while populating to prevent conflicts
        self.table.setSortingEnabled(False)

        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(self.visible_columns) + 1)
        self.table.setHorizontalHeaderLabels(
            ["Select"]
            + [col.replace("_", " ").title() for col in self.visible_columns]
        )

        for r, row in enumerate(rows):
            checkbox_item = QTableWidgetItem("")
            checkbox_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(r, 0, checkbox_item)

            for c, value in enumerate(row):
                col_name = self.visible_columns[c]

                # Format based on column type
                if value is None:
                    item = SortableTableWidgetItem("", "")
                elif "amount" in col_name:
                    item = SortableTableWidgetItem(
                        f"${float(value):,.2f}", float(value)
                    )
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                elif "date" in col_name:
                    item = SortableTableWidgetItem(
                        str(value)[:10] if value else "",
                        str(value)[:10] if value else "",
                    )
                elif col_name == "business_personal":
                    item = SortableTableWidgetItem(
                        str(value) if value else "",
                        str(value) if value else "",
                    )
                    if value and str(value).lower() == "personal":
                        # Red tint for personal
                        item.setBackground(QColor(255, 200, 200))
                    elif value and str(value).lower() == "business":
                        # Green tint for business
                        item.setBackground(QColor(200, 255, 200))
                elif col_name == "verified_by_edit":
                    item = SortableTableWidgetItem(
                        "✅" if value else "", 1 if value else 0
                    )
                    if value:
                        item.setBackground(QColor(200, 255, 200))
                else:
                    item = SortableTableWidgetItem(str(value), str(value))

                # Highlight splits
                if "split_group_id" in self.visible_columns:
                    split_idx = self.visible_columns.index("split_group_id")
                    if split_idx < len(row) and row[split_idx]:
                        item.setBackground(QColor(255, 240, 200))

                self.table.setItem(r, c + 1, item)

        # Re-enable sorting after population is complete
        self.table.setSortingEnabled(True)

    def _augment_split_group_rows(self, rows, allowed_columns) -> object:
        """Include sibling rows for split groups so pairs stay visible together."""
        if not rows or "split_group_id" not in allowed_columns:
            return rows

        split_idx = allowed_columns.index("split_group_id")
        split_group_ids = sorted(
            {
                row[split_idx]
                for row in rows
                if split_idx < len(row) and row[split_idx] is not None
            }
        )
        if not split_group_ids:
            return rows

        select_cols = ", ".join([f"r.{col}" for col in allowed_columns])
        placeholders = ", ".join(["%s"] * len(split_group_ids))

        existing_ids = set()
        receipt_idx = allowed_columns.index("receipt_id") if "receipt_id" in allowed_columns else None
        if receipt_idx is not None:
            for row in rows:
                if receipt_idx < len(row) and row[receipt_idx] is not None:
                    existing_ids.add(int(row[receipt_idx]))

        try:
            cur = self.conn.cursor()
            cur.execute(
                f"""
                SELECT {select_cols}
                FROM receipts r
                WHERE r.split_group_id IN ({placeholders})
                ORDER BY COALESCE(r.split_group_id, r.receipt_id) DESC,
                         r.receipt_date DESC,
                         r.receipt_id DESC
                """,
                split_group_ids,
            )
            sibling_rows = cur.fetchall() or []
            cur.close()
        except Exception:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            return rows

        merged = list(rows)
        for sibling in sibling_rows:
            if receipt_idx is None:
                if sibling not in merged:
                    merged.append(sibling)
                continue
            if receipt_idx >= len(sibling) or sibling[receipt_idx] is None:
                continue
            sibling_id = int(sibling[receipt_idx])
            if sibling_id in existing_ids:
                continue
            merged.append(sibling)
            existing_ids.add(sibling_id)

        return merged

    def _edit_receipt(self, item) -> None:
        """Open receipt for editing in drill-down popup."""
        row = item.row()
        if "receipt_id" in self.visible_columns:
            receipt_id_idx = self._table_column_index("receipt_id")
            receipt_id = int(self.table.item(row, receipt_id_idx).text())
            self._open_receipt_editor(receipt_id)

    def _edit_selected_receipt(self) -> None:
        """Edit the currently selected receipt."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(
                self, "No Selection", "Please select a receipt to edit."
            )
            return

        row = selected[0].row()
        if "receipt_id" in self.visible_columns:
            receipt_id_idx = self._table_column_index("receipt_id")
            receipt_id = int(self.table.item(row, receipt_id_idx).text())
            self._open_receipt_editor(receipt_id)

    def _open_receipt_editor(self, receipt_id: int) -> None:
        """Open receipt editor dialog."""
        try:
            from simple_receipt_editor import SimpleReceiptEditor

            dialog = SimpleReceiptEditor(self.conn, receipt_id, self)
            if dialog.exec():
                # Reload receipts after successful edit
                self._load_receipts()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to open receipt editor:\n{e}"
            )
            import traceback

            traceback.print_exc()

    @pyqtSlot()
    def _add_receipt(self) -> None:
        """Open receipt editor to add new receipt."""
        try:
            from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout
            from receipt_search_match_widget import (
                ReceiptSearchMatchWidget,
            )

            dialog = QDialog(self)
            dialog.setWindowTitle("Add New Receipt")
            dialog.setGeometry(100, 100, 1200, 800)

            layout = QVBoxLayout(dialog)

            # Create receipt widget
            receipt_widget = ReceiptSearchMatchWidget(self.conn, dialog)
            layout.addWidget(receipt_widget)

            # Clear form for new entry
            receipt_widget._clear_form()

            # Buttons
            button_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Close
            )
            button_box.rejected.connect(dialog.close)
            layout.addWidget(button_box)

            dialog.exec()

            # Refresh table after adding
            self._load_receipts()

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to open add receipt dialog:\n{e}"
            )
            import traceback

            traceback.print_exc()

    @pyqtSlot()
    def _print_receipts(self) -> None:
        """Print receipts with optional grouping."""
        report_table = self._build_report_table(checked_only=False)
        report_title = self._current_report_title(checked_only=False)
        group_col = self.print_group_by.currentData()
        group_idx = (
            self.visible_columns.index(group_col)
            if group_col in self.visible_columns
            else -1
        )

        if group_idx == -1 or report_table.rowCount() == 0:
            # No grouping - use regular print
            PrintExportHelper.print_preview(report_table, report_title, self)
        else:
            # Grouped print
            PrintExportHelper.print_grouped_preview(
                report_table, report_title, group_idx, self
            )

    @pyqtSlot()
    def _print_checked_receipts(self) -> None:
        """Print only checked rows from the current filtered view."""
        if not self._get_checked_receipt_ids():
            QMessageBox.information(
                self,
                "Print Checked",
                "No checked receipts in the current filtered view.",
            )
            return

        report_table = self._build_report_table(checked_only=True)
        report_title = self._current_report_title(checked_only=True)
        group_col = self.print_group_by.currentData()
        group_idx = (
            self.visible_columns.index(group_col)
            if group_col in self.visible_columns
            else -1
        )

        if group_idx == -1 or report_table.rowCount() == 0:
            PrintExportHelper.print_preview(report_table, report_title, self)
        else:
            PrintExportHelper.print_grouped_preview(
                report_table, report_title, group_idx, self
            )

    @pyqtSlot()
    def _delete_receipt(self) -> None:
        """Delete the selected receipt."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.information(
                self, "No Selection", "Please select a receipt to delete."
            )
            return

        row = selected[0].row()
        if "receipt_id" not in self.visible_columns:
            QMessageBox.warning(
                self, "Error", "Cannot delete: receipt_id column not visible."
            )
            return

        receipt_id = int(
            self.table.item(row, self._table_column_index("receipt_id")).text()
        )

        # Get vendor name for confirmation
        vendor = ""
        if "vendor_name" in self.visible_columns:
            vendor_idx = self._table_column_index("vendor_name")
            vendor = self.table.item(row, vendor_idx).text()

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete Receipt #{receipt_id}?\nVendor: {vendor}\n\nThis will"
            f"unlink from banking transactions.\nThis cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            cur = self.conn.cursor()

            # Clear banking transaction links (if columns exist in local DB)
            try:
                cur.execute(
                    "UPDATE banking_transactions SET receipt_id = NULL "
                    "WHERE receipt_id = %s",
                    (receipt_id,),
                )
            except Exception as e:
                logger.info(
                    f"Info: banking_transactions.receipt_id column not"
                    f"available: {e}"
                )
            try:
                cur.execute(
                    "UPDATE banking_transactions SET reconciled_receipt_id = "
                    "NULL WHERE reconciled_receipt_id = %s",
                    (receipt_id,),
                )
            except Exception as e:
                logger.info(
                    f"Info: banking_transactions.reconciled_receipt_id column"
                    f"not available: {e}"
                )

            # Delete from matching ledger if exists
            try:
                cur.execute(
                    "DELETE FROM banking_receipt_matching_ledger "
                    "WHERE receipt_id = %s",
                    (receipt_id,),
                )
            except Exception as e:
                logger.info(
                    "banking_receipt_matching_ledger not available: %s",
                    e,
                )

            # Delete the receipt (use correct primary key column 'receipt_id')
            cur.execute(
                "DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,)
            )

            self.conn.commit()
            cur.close()

            QMessageBox.information(
                self,
                "Deleted",
                f"✅ Receipt #{receipt_id} deleted successfully.",
            )

            # Refresh table
            self._load_receipts()

        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            QMessageBox.critical(
                self, "Delete Error", f"Failed to delete receipt:\n{e}"
            )
            import traceback

            traceback.print_exc()
