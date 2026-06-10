"""
Accounting Receipts Widget - Receipt entry with GST + GL code selection

This module provides a comprehensive interface for managing receipts
and invoices with support for:
- Receipt entry with GST calculation
- GL account code selection
- Vehicle assignment
- Personal/business classification
- Recent receipts list
- Search and filter functionality
"""

import logging
from datetime import datetime
from decimal import Decimal

from db_connection import DatabaseConnection
from form_widgets import CurrencyInput, DateInput, VendorSelector
from multi_date_filter_builder import MultiDateFilterBuilder
from PyQt6.QtCore import QDate, QSettings, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QKeySequence, QUndoStack
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from receipt_search_match_widget import ReceiptSearchMatchWidget

logger = logging.getLogger(__name__)


class AccountingReceiptsWidget(QWidget):
    """Receipts entry with GST + GL code selection, recent list,
    and search/match."""

    def __init__(self, db: DatabaseConnection, parent_tab_widget=None) -> None:
        super().__init__()
        self.db = db
        self.parent_tab_widget = parent_tab_widget
        self.gl_accounts: dict[str, str] = {}
        self.vehicles: dict[int, str] = {}
        # Initialize combo boxes early to prevent errors in load methods
        self.gl_combo = QComboBox()
        self.gl_combo.addItem("", "")
        self.vehicle_combo = QComboBox()
        self.vehicle_combo.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        self.vehicle_combo.setMaximumWidth(200)
        self.vehicle_combo.addItem("", None)

        # Create error label in case init fails
        self.error_label = None

        try:
            self.init_ui()
        except Exception as e:
            self._safe_rollback("init_ui")
            error_msg = f"Error in AccountingReceiptsWidget.init_ui(): {e}"
            logger.warning(error_msg)
            import traceback

            traceback.print_exc()
            # Show error in UI instead of blank page
            self._show_error(error_msg)
            return

        try:
            self.load_chart_accounts()
        except Exception as e:
            self._safe_rollback("load_chart_accounts")
            logger.warning(f"Error in load_chart_accounts(): {e}")
        try:
            self.load_vehicles()
        except Exception as e:
            self._safe_rollback("load_vehicles")
            logger.warning(f"Error in load_vehicles(): {e}")
        try:
            self.load_receipts()
        except Exception as e:
            self._safe_rollback("load_receipts")
            logger.warning(f"Error in load_receipts(): {e}")

    def _safe_rollback(self, context: str) -> None:
        """Attempt rollback while preserving the original exception flow."""
        try:
            self.db.rollback()
        except Exception as rollback_error:
            logger.warning(
                "Rollback failed in %s: %s", context, rollback_error
            )

    def _show_error(self, error_msg: str) -> None:
        """Display error message in the widget instead of showing blank page"""
        layout = QVBoxLayout()

        error_display = QLabel(
            f"❌ Error Loading Receipts Module\n\n{error_msg}")
        error_display.setStyleSheet("""
            QLabel {
                color: #c0392b;
                background-color: #fadbd8;
                padding: 20px;
                border: 2px solid #e74c3c;
                border-radius: 5px;
                font-size: 12px;
            }
        """)
        error_display.setWordWrap(True)
        error_display.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(error_display)
        layout.addStretch()
        self.setLayout(layout)

    def _create_simplified_receipts_tab(self) -> QWidget:
        """Create a simplified receipts interface without the crashing
        ReceiptSearchMatchWidget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Header
        header = QLabel("💰 Receipts & Invoices")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Search area
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        search_input = QLineEdit()
        search_input.setPlaceholderText("Vendor name or amount...")
        search_layout.addWidget(search_input)
        add_btn = QPushButton("➕ Add Receipt")
        search_layout.addWidget(add_btn)
        layout.addLayout(search_layout)

        # Receipts table
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Date", "Vendor", "Amount", "GST", "GL Code", "ID"]
        )

        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT receipt_date, vendor_name, gross_amount,
                       gst_amount, pay_account, receipt_id
                FROM receipts
                ORDER BY receipt_date DESC
                LIMIT 200
            """)
            rows = cur.fetchall()
            cur.close()

            table.setRowCount(len(rows))
            for i, row in enumerate(rows):
                for j, value in enumerate(row):
                    item = QTableWidgetItem(
                        str(value) if value is not None else "")
                    if j in [2, 3]:  # Amount columns - right align
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                    table.setItem(i, j, item)

            table.resizeColumnsToContents()
            table.horizontalHeader().setStretchLastSection(False)
        except Exception as e:
            self._safe_rollback("_create_simplified_receipts_tab")
            logger.warning(f"Error loading receipts: {e}")

        layout.addWidget(table)
        return widget

    def init_ui(self) -> None:
        # Single comprehensive Search & Match widget handles all
        # receipt/invoice operations
        main_layout = QVBoxLayout()

        tabs = QTabWidget()

        # Store tab reference for cross-tab navigation
        self.accounting_tabs = tabs

        logger.debug("    >> [init_ui] Creating ReceiptSearchMatchWidget...")
        # Tab 1: Search & Match (comprehensive - search, add receipts/invoices,
        # edit, match to banking)
        logger.debug("    >> [init_ui] Passing db connection...")
        try:
            search_match_widget = ReceiptSearchMatchWidget(self.db.conn)
            self.search_match_widget = search_match_widget
        except Exception as e:
            self._safe_rollback("init_ui.ReceiptSearchMatchWidget")
            import traceback

            logger.warning(f"    >> ❌ ReceiptSearchMatchWidget failed to init: {e}")
            traceback.print_exc()
            raise
        logger.warning("    >> [init_ui] ReceiptSearchMatchWidget created,"
            " setting parent_tab_widget...")
        search_match_widget.parent_tab_widget = self.parent_tab_widget
        logger.warning("    >> [init_ui] Adding to tabs...")
        tabs.addTab(search_match_widget, "🔍 Search, Match & Add")
        logger.warning("    >> [init_ui] ReceiptSearchMatchWidget tab added OK")

        try:
            # Tab 2: Recent Receipts (quick view/edit table)
            recent_tab = self._create_recent_receipts_tab()
            tabs.addTab(recent_tab, "📋 Recent List")
        except Exception as e:
            self._safe_rollback("init_ui.recent_tab")
            logger.warning(f"Error creating recent receipts tab: {e}")
            import traceback

            traceback.print_exc()
            error_label = QLabel(f"Error loading Recent Receipts: {e}")
            error_label.setStyleSheet("color: red;")
            tabs.addTab(error_label, "📋 Recent List")

        main_layout.addWidget(tabs)
        self.setLayout(main_layout)

    def open_receipt_by_id(self, receipt_id: int) -> object:
        """Deep-link helper: open/search a specific receipt id
        in Search, Match & Add tab."""
        try:
            rid = int(receipt_id)
        except (TypeError, ValueError):
            QMessageBox.warning(self, "Invalid Receipt",
                                f"Invalid receipt id: {receipt_id}")
            return False

        try:
            if (hasattr(self, "accounting_tabs")
                    and self.accounting_tabs.count() > 0):
                self.accounting_tabs.setCurrentIndex(0)
            if (hasattr(self, "search_match_widget")
                    and self.search_match_widget):
                self.search_match_widget._load_receipt_by_id(rid)
                return True
        except Exception as e:
            QMessageBox.warning(
                self,
                "Open Receipt",
                f"Could not open receipt {rid} in Receipts widget:\n{e}",
            )
        return False

    def _create_add_receipt_tab(self) -> object:
        """Create the add receipt form tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        form_box = QGroupBox("Add New Receipt")
        form_layout = QFormLayout()

        # ============================================================================
        # PHASE 3: UNDO/REDO SUPPORT
        # ============================================================================
        self.undo_stack = QUndoStack(self)

        # Keypad-friendly date input
        self.date_edit = DateInput()

        # Smart vendor selector with historical lookup
        self.vendor_input = VendorSelector(self.db.conn)
        self.vendor_input.currentTextChanged.connect(self._on_vendor_selected)

        # Currency input field - works with numeric keypad and keyboard
        self.amount_input = CurrencyInput()
        self.amount_input.textChanged.connect(self._on_amount_changed)

        self.gst_display = QLabel("$0.00")
        self.gst_display.setToolTip(
            "GST amount (auto-calculated, 5% of amount - tax inclusive)"
        )

        # Tax Jurisdiction selector for out-of-province/US purchases
        self.tax_jurisdiction = QComboBox()
        self.tax_jurisdiction.addItems(
            [
                "AB (GST 5%)",  # Alberta - default
                "BC (GST 5% + PST 7%)",  # British Columbia
                "SK (GST 5% + PST 6%)",  # Saskatchewan
                "MB (GST 5% + PST 7%)",  # Manitoba
                "ON (HST 13%)",  # Ontario
                "QC (GST 5% + PST 9.975%)",  # Quebec
                "NB (HST 15%)",  # New Brunswick
                "NS (HST 15%)",  # Nova Scotia
                "PE (HST 15%)",  # Prince Edward Island
                "NL (HST 15%)",  # Newfoundland & Labrador
                "YT (GST 5%)",  # Yukon
                "NT (GST 5%)",  # Northwest Territories
                "NU (GST 5%)",  # Nunavut
                "US (varies by state)",  # United States
                "Other (manual entry)",  # Manual override
            ]
        )
        self.tax_jurisdiction.setToolTip(
            "<b>Tax Jurisdiction</b><br>Select province/state"
            " for automatic tax calculation.<br>Default: AB (GST 5%)"
        )
        self.tax_jurisdiction.currentTextChanged.connect(self.auto_calc_gst)

        # PST/Additional Sales Tax input (for US or other provinces)
        self.pst_input = CurrencyInput()
        self.pst_input.setMaximumWidth(150)
        self.pst_input.setText("0.00")
        self.pst_input.setToolTip(
            "<b>PST / Additional Sales Tax</b><br>Enter PST"
            " (BC, SK, MB, QC) or US state sales tax."
            "<br>Auto-calculated for Canadian provinces."
        )
        self.pst_input.textChanged.connect(self.auto_calc_gst)
        self.pst_input.setEnabled(False)  # Auto-calculated by default

        # ============================================================================
        # PHASE 3: RECENT ITEMS TRACKING
        # ============================================================================
        self.settings = QSettings("ArrowLimo", "Desktop")

        self.gl_combo = QComboBox()
        self.gl_combo.addItem("", "")
        self.gl_combo.setToolTip(
            "<b>GL Account Code</b><br>General Ledger account for accounting."
            "<br>Auto-filled from vendor history if available."
        )
        self.gl_combo.currentIndexChanged.connect(
            self._maybe_set_gst_exempt_from_gl)

        self.vehicle_combo = QComboBox()
        self.vehicle_combo.addItem("", None)
        self.vehicle_combo.setToolTip(
            "<b>Vehicle</b><br>Optional: Link expense to specific vehicle"
            "<br>(e.g., for fuel or maintenance)"
        )

        self.fuel_amount_input = QDoubleSpinBox()
        self.fuel_amount_input.setRange(0, 999999.999)
        self.fuel_amount_input.setDecimals(3)
        self.fuel_amount_input.setSuffix(" L")
        self.fuel_amount_input.setMaximumWidth(120)
        self.fuel_amount_input.setToolTip("Fuel amount in liters (optional).")

        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(60)
        self.description_input.setToolTip(
            "Enter details about this receipt."
            "\nExample: 'Diesel fuel for vehicles 1-3'"
        )

        self.personal_check = QCheckBox("Personal / owner draw")
        self.personal_check.setToolTip(
            "Check if this is a personal expense or owner withdrawal"
        )
        self.personal_check.stateChanged.connect(self.auto_calc_gst)

        self.driver_personal_check = QCheckBox("Driver personal (exclude GST)")
        self.driver_personal_check.setToolTip(
            "Check if this is a driver's personal expense (no GST calculation)"
        )
        self.driver_personal_check.stateChanged.connect(self.auto_calc_gst)

        self.gst_exempt_check = QCheckBox("GST Exempt")
        self.gst_exempt_check.setToolTip(
            "Check for GST-exempt items"
            " (e.g., WCB, government services, basic groceries)"
        )
        self.gst_exempt_check.stateChanged.connect(self.auto_calc_gst)

        self.save_btn = QPushButton("💾 Save Receipt")
        self.save_btn.setToolTip("Save receipt to database [Ctrl+S]")
        self.save_btn.clicked.connect(self.save_receipt)

        # Add format indicators for date
        date_layout = QVBoxLayout()
        date_layout.addWidget(self.date_edit)
        date_hint = QLabel("📅 Format: MM/dd/yyyy, MM-dd-yyyy, or yyyymmdd")
        date_hint.setStyleSheet(
            "font-size: 9px; color: #666; margin-top: -5px;")
        date_layout.addWidget(date_hint)
        date_layout.setContentsMargins(0, 0, 0, 5)

        # Add format indicators for amount
        amount_layout = QVBoxLayout()
        amount_layout.addWidget(self.amount_input)
        amount_hint = QLabel("💵 Format: 10 (=10.00), 10.50, or .50 (=0.50)")
        amount_hint.setStyleSheet(
            "font-size: 9px; color: #666; margin-top: -5px;")
        amount_layout.addWidget(amount_hint)
        amount_layout.setContentsMargins(0, 0, 0, 5)

        form_layout.addRow("Date", date_layout)
        form_layout.addRow("Vendor", self.vendor_input)
        form_layout.addRow("Amount (tax incl)", amount_layout)
        form_layout.addRow("Tax Jurisdiction", self.tax_jurisdiction)
        form_layout.addRow("GST (auto)", self.gst_display)
        form_layout.addRow("PST / Sales Tax", self.pst_input)
        form_layout.addRow("GL Account", self.gl_combo)
        # Vehicle field with type display
        try:
            self.vehicle_combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToContents
            )
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
        self.vehicle_combo.setMinimumContentsLength(4)
        self.vehicle_combo.setMaximumWidth(140)
        self.receipt_vehicle_type_label = QLabel("")
        self.receipt_vehicle_type_label.setStyleSheet(
            "color:#555; padding-left:6px;")
        rv_row = QHBoxLayout()
        rv_row.setContentsMargins(0, 0, 0, 0)
        rv_row.setSpacing(6)
        rv_row.addWidget(self.vehicle_combo)
        rv_row.addWidget(QLabel("Fuel:"))
        rv_row.addWidget(self.fuel_amount_input)
        rv_row.addWidget(QLabel("Type:"))
        rv_row.addWidget(self.receipt_vehicle_type_label)
        rv_row.addStretch(1)
        rv_widget = QWidget()
        rv_widget.setLayout(rv_row)
        form_layout.addRow("Vehicle", rv_widget)
        form_layout.addRow("Description", self.description_input)
        form_layout.addRow(self.personal_check)
        form_layout.addRow(self.driver_personal_check)
        form_layout.addRow(self.gst_exempt_check)

        # Undo/Redo buttons
        undo_redo_layout = QHBoxLayout()
        undo_btn = QPushButton("⎌ Undo (Ctrl+Z)")
        undo_btn.clicked.connect(self.undo_stack.undo)
        undo_btn.setShortcut(QKeySequence.StandardKey.Undo)
        redo_btn = QPushButton("⎌ Redo (Ctrl+Y)")
        redo_btn.clicked.connect(self.undo_stack.redo)
        redo_btn.setShortcut(QKeySequence.StandardKey.Redo)
        undo_redo_layout.addWidget(undo_btn)
        undo_redo_layout.addWidget(redo_btn)
        undo_redo_layout.addStretch()
        undo_redo_layout.addWidget(self.save_btn)
        form_layout.addRow(undo_redo_layout)

        form_box.setLayout(form_layout)
        layout.addWidget(form_box)

        widget.setLayout(layout)

        # ============================================================================
        # PHASE 1 UX UPGRADE - TAB ORDER OPTIMIZATION
        # ============================================================================
        # Optimize form navigation: Date → Vendor → Amount → GL → Save
        self.date_edit.setFocus()
        QWidget.setTabOrder(self.date_edit, self.vendor_input)
        QWidget.setTabOrder(self.vendor_input, self.amount_input)
        QWidget.setTabOrder(self.amount_input, self.gl_combo)
        QWidget.setTabOrder(self.gl_combo, self.vehicle_combo)
        QWidget.setTabOrder(self.vehicle_combo, self.fuel_amount_input)
        QWidget.setTabOrder(self.fuel_amount_input, self.description_input)
        QWidget.setTabOrder(self.description_input, self.personal_check)
        QWidget.setTabOrder(self.personal_check, self.driver_personal_check)
        QWidget.setTabOrder(self.driver_personal_check, self.gst_exempt_check)
        QWidget.setTabOrder(self.gst_exempt_check, self.save_btn)

        return widget

    def _create_recent_receipts_tab(self) -> object:
        """Create the recent receipts table tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Bulk operations toolbar
        bulk_toolbar = QHBoxLayout()
        bulk_toolbar.setSpacing(6)
        self.bulk_select_all_btn = QPushButton("☑ Select All")
        self.bulk_clear_selection_btn = QPushButton("☐ Clear")
        self.bulk_verify_btn = QPushButton("✅ Mark Verified")
        self.bulk_delete_btn = QPushButton("🗑️ Delete Selected")
        self.bulk_select_all_btn.clicked.connect(self._bulk_select_all)
        self.bulk_clear_selection_btn.clicked.connect(
            self._bulk_clear_selection)
        self.bulk_verify_btn.clicked.connect(self._bulk_mark_verified)
        self.bulk_delete_btn.clicked.connect(self._bulk_delete)
        bulk_toolbar.addWidget(QLabel("Bulk Actions:"))
        bulk_toolbar.addWidget(self.bulk_select_all_btn)
        bulk_toolbar.addWidget(self.bulk_clear_selection_btn)
        bulk_toolbar.addWidget(self.bulk_verify_btn)
        bulk_toolbar.addWidget(self.bulk_delete_btn)
        bulk_toolbar.addStretch()
        layout.addLayout(bulk_toolbar)

        # Quick filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(6)
        self.filter_vendor = QLineEdit()
        self.filter_vendor.setPlaceholderText("Vendor contains...")
        self.filter_gl = QComboBox()
        self.filter_gl.setEditable(False)
        self.filter_gl.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.filter_gl.setToolTip("Filter by GL Account Code")
        # Load GL accounts from database
        gl_accounts = [
            "",
            "6000 - Advertising",
            "6005 - Donations",
            "6100 - Office Rent",
            "6101 - Interest & Late Chgs Expense",
            "6200 - Utilities",
            "6300 - Repairs & Maintenance",
            "6350 - Equipment Repairs",
            "6400 - Insurance",
            "6480 - Membership",
            "6500 - Bank Fees",
            "6500 - Meals and Entertainment",
            "6550 - Office Supplies",
            "6610 - Wages/Salaries",
            "6625 - Professional Fees",
            "6751 - Hospitality Supplies",
            "6750 - Supplies",
            "6800 - Telephone",
            "6826 - Parking & Misc. Ticket Expenses",
            "6900 - Vehicle R&M",
            "6925 - Fuel",
            "6950 - WCB",
            "Administrative",
            "ADVERTISING",
            "Bank Charges",
            "Bank Charges & Interest",
            "Bank Fees",
            "Business expense",
            "Client Entertainment",
            "communication",
            "entertainment_beverages",
            "equipment_lease",
            "fuel",
            "Fuel",
            "FUEL",
            "Government Fees",
            "government_fees",
            "hospitality_supplies",
            "insurance",
            "Insurance",
            "Insurance - Vehicle Liability",
            "licenses",
            "Liquor/Entertainment",
            "maintenance",
            "meals_entertainment",
            "mixed_use",
            "office rent",
            "office_supplies",
            "owner_draws",
            "petty_cash",
            "rent",
            "Supplies",
            "uncategorized_expenses",
            "utilities",
            "Vehicle Maintenance",
            "Vehicle Rental",
        ]
        for account in gl_accounts:
            self.filter_gl.addItem(account, account)
        self.filter_amount_min = QLineEdit()
        self.filter_amount_min.setPlaceholderText("Min $")
        self.filter_amount_max = QLineEdit()
        self.filter_amount_max.setPlaceholderText("Max $")

        # Advanced date period picker (replaces simple from/to text fields)
        self.filter_amount_min = QLineEdit()
        self.filter_amount_min.setPlaceholderText("Min $")
        self.filter_amount_max = QLineEdit()
        self.filter_amount_max.setPlaceholderText("Max $")

        # Multi-date filter builder
        self.date_filter_builder = MultiDateFilterBuilder()
        self.date_filter_builder.filters_changed.connect(
            self._on_receipt_filters_changed
        )

        self.filter_apply_btn = QPushButton("Apply Filters")
        self.filter_clear_btn = QPushButton("Clear")
        self.filter_apply_btn.clicked.connect(self.apply_receipt_filters)
        self.filter_clear_btn.clicked.connect(self.clear_receipt_filters)

        # Filter toolbar - basic filters
        filter_layout.addWidget(QLabel("Vendor"))
        filter_layout.addWidget(self.filter_vendor)
        filter_layout.addWidget(QLabel("GL Account"))
        filter_layout.addWidget(self.filter_gl)
        filter_layout.addWidget(QLabel("Amount"))
        filter_layout.addWidget(self.filter_amount_min)
        filter_layout.addWidget(QLabel("to"))
        filter_layout.addWidget(self.filter_amount_max)
        filter_layout.addWidget(self.filter_apply_btn)
        filter_layout.addWidget(self.filter_clear_btn)
        layout.addLayout(filter_layout)

        # Multi-date filter builder as its own section
        date_filter_group = QGroupBox(
            "📅 Add Date Range Filters (e.g., '2022 Mar-Apr' OR '2021 Jan')"
        )
        date_filter_layout = QVBoxLayout(date_filter_group)
        date_filter_layout.addWidget(self.date_filter_builder)
        layout.addWidget(date_filter_group)

        # Recent receipts table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["☑", "Date", "Vendor", "GL Account", "Amount", "GST", "Type"]
        )
        self._expanded_rows = (
            set()
        )  # Track expanded receipt IDs for detail view (NOT row indices)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setMinimumHeight(500)  # Show at least 12-15 rows
        self.table.setAlternatingRowColors(True)  # Better visibility

        # ============================================================================
        # PHASE 1 UX UPGRADE - CONTEXT MENUS (RIGHT-CLICK)
        # ============================================================================
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(
            self._show_receipt_context_menu)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.cellDoubleClicked.connect(self._toggle_row_expansion)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.cellChanged.connect(self._on_receipt_cell_changed)
        # Keyboard helpers for navigation
        self.table.keyPressEvent = lambda event: self._receipt_table_keypress(
            event)

        layout.addWidget(self.table)

        widget.setLayout(layout)
        return widget

    # ============================================================================
    # CONTEXT MENU HANDLERS
    # ============================================================================
    def _show_receipt_context_menu(self, position) -> None:
        """Show right-click context menu for receipt table"""
        item = self.table.itemAt(position)
        if not item:
            return

        row = item.row()
        menu = QMenu(self)

        # Context menu actions
        expand_action = menu.addAction("📂 Expand/Collapse Details")
        menu.addSeparator()
        link_action = menu.addAction("🔗 Link to Payment")
        dup_action = menu.addAction("📋 Duplicate Receipt")
        verify_action = menu.addAction("✅ Mark as Verified")
        menu.addSeparator()
        view_action = menu.addAction("📄 View Original")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Delete Receipt")

        action = menu.exec(self.table.mapToGlobal(position))

        if action == expand_action:
            self._toggle_row_expansion(row, 0)
        elif action == link_action:
            QMessageBox.information(
                self,
                "Link Payment",
                f"Linking receipt from row {row}...\n"
                "[Full implementation pending]",
            )
        elif action == dup_action:
            self._duplicate_receipt(row)
        elif action == verify_action:
            self._mark_receipt_verified(row)
        elif action == view_action:
            QMessageBox.information(
                self,
                "View Document",
                f"Opening original document for receipt {row}...\n"
                "[PDF viewer pending]",
            )
        elif action == delete_action:
            self._delete_receipt_row(row)

    def _on_vendor_selected(self, vendor_name) -> None:
        """When vendor selected, auto-populate GL code from history"""
        if not vendor_name:
            return

        # Get suggested GL code from VendorSelector
        suggested_gl_code = self.vendor_input.get_suggested_gl_code()

        # Auto-populate GL code if found
        if suggested_gl_code:
            index = self.gl_combo.findData(suggested_gl_code)
            if index >= 0:
                self.gl_combo.setCurrentIndex(index)

    def _maybe_set_gst_exempt_from_gl(self) -> None:
        """Auto-mark GST exempt for Shareholder Loan GL accounts."""
        try:
            gl_code = self.gl_combo.currentData()
            gl_name = self.gl_accounts.get(gl_code, "") if gl_code else ""
            if "shareholder loan" in str(gl_name).lower():
                self.gst_exempt_check.setChecked(True)
                self.auto_calc_gst()
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
    def _on_amount_changed(self, text) -> None:
        """Handle amount field changes - convert to float
        and recalculate GST"""
        # Delegate to auto_calc_gst which now handles PST too
        self.auto_calc_gst()

    def auto_calc_gst(self) -> None:
        """Calculate GST and PST based on jurisdiction"""
        try:
            # Get amount
            amount_text = self.amount_input.text()
            if not amount_text or amount_text == "":
                self.gst_display.setText("$0.00")
                self.pst_input.setText("0.00")
                return

            amount = float(amount_text)

            # Check if GST/PST should be excluded
            if (
                self.driver_personal_check.isChecked()
                or self.gst_exempt_check.isChecked()
            ):
                self.gst_display.setText("$0.00")
                self.pst_input.setText("0.00")
                self.pst_input.setEnabled(False)
                return

            # Get jurisdiction
            jurisdiction = self.tax_jurisdiction.currentText()

            # Calculate based on jurisdiction (tax-inclusive)
            if (
                "AB" in jurisdiction
                or "YT" in jurisdiction
                or "NT" in jurisdiction
                or "NU" in jurisdiction
            ):
                # Alberta/Territories: GST 5% only
                gst = amount * 0.05 / 1.05
                pst = 0.0
                self.pst_input.setEnabled(False)
            elif "BC" in jurisdiction:
                # BC: GST 5% + PST 7% = 12% total (tax-inclusive)
                total_tax_rate = 0.12
                total_tax = amount * total_tax_rate / (1 + total_tax_rate)
                gst = amount * 0.05 / (1 + total_tax_rate)
                pst = total_tax - gst
                self.pst_input.setEnabled(False)
            elif "SK" in jurisdiction:
                # Saskatchewan: GST 5% + PST 6% = 11% total
                total_tax_rate = 0.11
                total_tax = amount * total_tax_rate / (1 + total_tax_rate)
                gst = amount * 0.05 / (1 + total_tax_rate)
                pst = total_tax - gst
                self.pst_input.setEnabled(False)
            elif "MB" in jurisdiction:
                # Manitoba: GST 5% + PST 7% = 12% total
                total_tax_rate = 0.12
                total_tax = amount * total_tax_rate / (1 + total_tax_rate)
                gst = amount * 0.05 / (1 + total_tax_rate)
                pst = total_tax - gst
                self.pst_input.setEnabled(False)
            elif "QC" in jurisdiction:
                # Quebec: GST 5% + QST 9.975% = 14.975% total
                total_tax_rate = 0.14975
                total_tax = amount * total_tax_rate / (1 + total_tax_rate)
                gst = amount * 0.05 / (1 + total_tax_rate)
                pst = total_tax - gst
                self.pst_input.setEnabled(False)
            elif "HST" in jurisdiction:
                # HST provinces (ON 13%, NB/NS/PE/NL 15%)
                if "ON" in jurisdiction:
                    hst_rate = 0.13
                else:
                    hst_rate = 0.15
                # HST = combined GST+PST
                gst = amount * hst_rate / (1 + hst_rate)
                pst = 0.0
                self.pst_input.setEnabled(False)
            elif "US" in jurisdiction:
                # US: Manual entry (rates vary by state)
                gst = 0.0  # No Canadian GST on US purchases
                self.pst_input.setEnabled(True)  # Manual sales tax entry
                # Keep current PST value (user enters US sales tax)
                pst_str = (
                    self.pst_input.get_value()
                    if hasattr(self.pst_input, "get_value")
                    else "0.00"
                )
                pst = float(pst_str) if pst_str else 0.0
            elif "Other" in jurisdiction:
                # Manual entry
                gst = 0.0
                self.pst_input.setEnabled(True)
                pst_str = (
                    self.pst_input.get_value()
                    if hasattr(self.pst_input, "get_value")
                    else "0.00"
                )
                pst = float(pst_str) if pst_str else 0.0
            else:
                # Default to Alberta
                gst = amount * 0.05 / 1.05
                pst = 0.0
                self.pst_input.setEnabled(False)

            self.gst_display.setText(f"${gst:.2f}")
            if not self.pst_input.isEnabled():
                self.pst_input.setText(f"{pst:.2f}")

        except (ValueError, AttributeError):
            # Not a valid number yet, ignore
            pass

    def load_chart_accounts(self) -> None:
        try:
            # Rollback any failed transactions first
            self._safe_rollback("load_chart_accounts")

            cur = self.db.get_cursor()
            cur.execute("""
                SELECT account_code, account_name
                FROM chart_of_accounts
                ORDER BY account_code
                """)
            rows = cur.fetchall()
            self.gl_accounts = {r[0]: r[1] for r in rows if r[0]}
            self.gl_combo.clear()
            self.gl_combo.addItem("", "")
            for code, name in self.gl_accounts.items():
                self.gl_combo.addItem(f"{code} — {name}", code)
        except Exception as e:
            QMessageBox.warning(
                self, "Chart of Accounts", f"Failed to load accounts: {e}"
            )

    def load_vehicles(self) -> None:
        try:
            self._safe_rollback("load_vehicles")

            cur = self.db.get_cursor()
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'vehicles'
                """)
            vehicle_columns = {row[0] for row in cur.fetchall()}

            status_column = (
                "status"
                if "status" in vehicle_columns
                else "operational_status"
            )
            if status_column not in vehicle_columns:
                status_column = "status"

            cur.execute(rf"""
                SELECT vehicle_id, vehicle_number, {status_column} AS status,
                       COALESCE(vehicle_type, '') as vehicle_type
                FROM vehicles
                ORDER BY
                    CASE WHEN LOWER(COALESCE({status_column}, ''))
                        = 'active' THEN 0 ELSE 1 END,
                    CASE
                        WHEN vehicle_number ~ '^[Ll]-?\d+$'
                        THEN CAST(regexp_replace(
                            vehicle_number, '[^0-9]', '', 'g') AS INT)
                        ELSE 9999
                    END,
                    vehicle_number
                """)
            rows = cur.fetchall()
            self.vehicles = {
                r[0]: str(r[1] or f"Vehicle {r[0]}")
                for r in rows
            }
            self._receipt_vehicle_types = {r[0]: (r[3] or "") for r in rows}
            self.vehicle_combo.clear()
            self.vehicle_combo.addItem("", None)
            for vid, label in self.vehicles.items():
                self.vehicle_combo.addItem(label, vid)
            try:
                self.vehicle_combo.currentIndexChanged.connect(
                    self._update_receipt_vehicle_type_display
                )
            except Exception:
                logger.debug(
                    "Vehicle type display signal connection failed",
                    exc_info=True,
                )
            self._update_receipt_vehicle_type_display()
        except Exception as e:
            self._safe_rollback("load_vehicles.failure")
            QMessageBox.warning(
                self, "Vehicles", f"Failed to load vehicles: {e}")

    def _update_receipt_vehicle_type_display(self) -> None:
        try:
            vid = self.vehicle_combo.currentData()
            vtype = ""
            if (
                hasattr(self, "_receipt_vehicle_types")
                and vid in self._receipt_vehicle_types
            ):
                vtype = self._receipt_vehicle_types.get(vid) or ""
            self.receipt_vehicle_type_label.setText(str(vtype))
        except Exception:
            try:
                self.receipt_vehicle_type_label.setText("")
            except Exception:
                logger.debug(
                    "Receipt vehicle type label unavailable during refresh",
                    exc_info=True,
                )

    def load_receipts(self, filters=None) -> None:
        """Load receipts with optional filters, multiple date ranges (OR),
        and optional year grouping"""
        if filters is None:
            filters = self._get_default_receipt_filters()
        self._current_receipt_filters = filters
        self._loading_receipts = True
        try:
            # Rollback any failed transactions first
            self._safe_rollback("load_receipts")

            cur = self.db.get_cursor()
            base_query = (
                "SELECT receipt_id, receipt_date, vendor_name, category, "
                "gl_account_code, gross_amount, "
                "gst_amount, gst_code "
                "FROM receipts "
            )
            conditions = []
            params = []

            if filters:
                # Standard filters
                vendor = filters.get("vendor")
                if vendor:
                    conditions.append("vendor_name ILIKE %s")
                    params.append(f"%{vendor}%")

                gl_code = filters.get("gl_code")
                if gl_code:
                    conditions.append("gl_account_code = %s")
                    params.append(gl_code)

                amt_min = filters.get("amount_min")
                if amt_min is not None:
                    conditions.append("gross_amount >= %s")
                    params.append(amt_min)

                amt_max = filters.get("amount_max")
                if amt_max is not None:
                    conditions.append("gross_amount <= %s")
                    params.append(amt_max)

                # Multiple date ranges (OR logic)
                date_ranges = filters.get("date_ranges", [])
                if date_ranges:
                    date_conditions = []
                    for from_date, to_date in date_ranges:
                        if from_date and to_date:
                            date_conditions.append(
                                "(receipt_date >= %s AND receipt_date <= %s)"
                            )
                            params.append(from_date)
                            params.append(to_date)
                        elif from_date:
                            date_conditions.append("(receipt_date >= %s)")
                            params.append(from_date)
                        elif to_date:
                            date_conditions.append("(receipt_date <= %s)")
                            params.append(to_date)

                    if date_conditions:
                        conditions.append(f"({' OR '.join(date_conditions)})")

            if conditions:
                base_query += "WHERE " + " AND ".join(conditions) + " "

            # Check if grouping by year is enabled
            should_group_by_year = (
                filters.get("group_by_year", False) if filters else False
            )

            base_query += (
                "ORDER BY receipt_date DESC, receipt_id DESC LIMIT 500"
            )
            cur.execute(base_query, params)
            rows = cur.fetchall()

            # If grouping by year, organize rows
            if should_group_by_year:
                rows_by_year = {}
                for row in rows:
                    year = row[1].year if row[1] else None
                    if year not in rows_by_year:
                        rows_by_year[year] = []
                    rows_by_year[year].append(row)

                # Flatten with year separators
                display_rows = []
                for year in sorted(rows_by_year.keys(), reverse=True):
                    # Add year header row
                    display_rows.append(
                        (None, None, f"═══ {year} ═══",
                         None, None, None, None, None)
                    )
                    display_rows.extend(rows_by_year[year])
                rows = display_rows

            self.table.blockSignals(True)
            # Row positions are about to change - clear all expanded state
            self._expanded_rows.clear()
            self.table.setRowCount(len(rows))

            for i, r in enumerate(rows):
                # Check if this is a year separator
                if r[0] is None and r[1] is None:
                    # Year separator row
                    item = QTableWidgetItem(r[2])  # Year text
                    # Light blue background
                    item.setBackground(QColor(200, 220, 240))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    self.table.setItem(i, 2, item)
                    continue

                receipt_id = r[0]
                receipt_date = r[1]
                vendor = r[2]
                category = r[3]
                gl_code = r[4]
                amt = float(r[5]) if r[5] else 0
                gst = float(r[6]) if r[6] else 0
                r[7]

                # Checkbox column
                checkbox = QTableWidgetItem()
                checkbox.setCheckState(Qt.CheckState.Unchecked)
                checkbox.setData(Qt.ItemDataRole.UserRole, receipt_id)
                self.table.setItem(i, 0, checkbox)

                date_item = QTableWidgetItem(
                    receipt_date.strftime("%Y-%m-%d") if receipt_date else ""
                )
                self.table.setItem(i, 1, date_item)
                self.table.setItem(i, 2, QTableWidgetItem(vendor or ""))
                self.table.setItem(i, 3, QTableWidgetItem(category or ""))
                self.table.setItem(i, 4, QTableWidgetItem(gl_code or ""))
                self.table.setItem(i, 5, QTableWidgetItem(f"${amt:.2f}"))
                self.table.setItem(i, 6, QTableWidgetItem(f"${gst:.2f}"))

            self.table.blockSignals(False)
        except Exception as e:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            self.table.blockSignals(False)
            QMessageBox.warning(
                self, "Receipts", f"Failed to load receipts: {e}")
        finally:
            self._loading_receipts = False

    def clear_receipt_filters(self) -> None:
        """Clear all receipt filters"""
        self.filter_vendor.clear()
        self.filter_gl.setCurrentIndex(0)
        self.filter_amount_min.clear()
        self.filter_amount_max.clear()
        self.date_filter_builder._clear_all_filters()
        self.load_receipts(self._get_default_receipt_filters())

    def _get_default_receipt_filters(self) -> object:
        """Get default filters (365 days back)"""
        today = QDate.currentDate()
        return {
            "date_ranges": [
                # 365 days back with no upper limit
                (today.addDays(-365).toPyDate(), None)
            ]
        }

    def _on_receipt_filters_changed(self, filters_list) -> None:
        """Handle date filter builder changes"""
        # Store filters for later use
        self._active_receipt_date_filters = filters_list

    def apply_receipt_filters(self) -> None:
        """Gather all filter inputs and reload receipts"""
        filters = {}

        # Vendor filter
        vendor = self.filter_vendor.text().strip()
        if vendor:
            filters["vendor"] = vendor

        # GL filter
        gl_code = self.filter_gl.currentText()
        if gl_code and gl_code != "":
            filters["gl_code"] = gl_code

        # Amount filters
        amount_min_text = self.filter_amount_min.text().strip()
        if amount_min_text:
            try:
                filters["amount_min"] = Decimal(
                    amount_min_text.replace("$", "").replace(",", "")
                )
            except Exception:
                QMessageBox.warning(self, "Filter", "Min amount is invalid")
                return

        amount_max_text = self.filter_amount_max.text().strip()
        if amount_max_text:
            try:
                filters["amount_max"] = Decimal(
                    amount_max_text.replace("$", "").replace(",", "")
                )
            except Exception:
                QMessageBox.warning(self, "Filter", "Max amount is invalid")
                return

        # Multiple date range filters (OR logic)
        date_ranges = self.date_filter_builder.calculate_date_ranges()
        if date_ranges:
            filters["date_ranges"] = [
                (from_date.toPyDate(), to_date.toPyDate())
                for from_date, to_date in date_ranges
            ]

        # Group by year option
        filters["group_by_year"] = (
            self.date_filter_builder.should_group_by_year()
        )

        self.load_receipts(filters)

    def _get_receipt_id(self, row) -> object:
        item = self.table.item(row, 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _parse_date_value(self, text) -> object:
        text = text.strip()
        if not text:
            return None
        fmts = ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y",
                "%m%d%Y", "%m%d%y", "%Y/%m/%d"]
        for fmt in fmts:
            try:
                return datetime.strptime(text, fmt).date()
            except Exception:
                continue
        return None

    def _parse_amount_value(self, text) -> object:
        cleaned = text.replace("$", "").replace(",", "").strip()
        if not cleaned:
            return Decimal("0")
        return Decimal(cleaned)

    def _reload_receipts(self) -> None:
        self._expanded_rows.clear()  # row indices become invalid after reload
        self.load_receipts(self._current_receipt_filters)

    def _on_receipt_cell_changed(self, row, column) -> None:
        if self._loading_receipts:
            return
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return
        column_map = {
            1: ("receipt_date", self._parse_date_value),
            2: ("vendor_name", lambda v: v.strip().upper() if v else None),
            3: ("gl_account_code", lambda v: v.strip() if v else None),
            4: ("gross_amount", self._parse_amount_value),
            5: ("gst_amount", self._parse_amount_value),
        }
        if column not in column_map:
            return
        field, parser = column_map[column]
        value_text = (
            self.table.item(row, column).text(
            ) if self.table.item(row, column) else ""
        )
        try:
            parsed_value = parser(value_text)
        except Exception:
            QMessageBox.warning(self, "Update", "Invalid value")
            self._reload_receipts()
            return
        if field == "receipt_date" and not parsed_value:
            QMessageBox.warning(self, "Update", "Invalid date format")
            self._reload_receipts()
            return
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            cur = self.db.get_cursor()
            update_queries = {
                "receipt_date": (
                    "UPDATE receipts SET receipt_date = %s,"
                    " is_paper_verified = TRUE WHERE receipt_id = %s"
                ),
                "vendor_name": (
                    "UPDATE receipts SET vendor_name = %s,"
                    " is_paper_verified = TRUE WHERE receipt_id = %s"
                ),
                "gl_account_code": (
                    "UPDATE receipts SET gl_account_code = %s,"
                    " is_paper_verified = TRUE WHERE receipt_id = %s"
                ),
                "gross_amount": (
                    "UPDATE receipts SET gross_amount = %s,"
                    " net_amount = gross_amount - COALESCE(gst_amount, 0),"
                    " is_paper_verified = TRUE WHERE receipt_id = %s"
                ),
                "gst_amount": (
                    "UPDATE receipts SET gst_amount = %s,"
                    " net_amount = COALESCE(gross_amount, 0) - %s,"
                    " is_paper_verified = TRUE WHERE receipt_id = %s"
                ),
            }
            if field not in update_queries:
                raise ValueError(f"Unsupported field: {field}")
            # gst_amount SQL uses parsed_value twice (SET and net subtraction)
            if field == "gst_amount":
                params = (parsed_value, parsed_value, receipt_id)
            else:
                params = (parsed_value, receipt_id)
            cur.execute(update_queries[field], params)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(
                self, "Update Failed", f"Could not update receipt: {e}"
            )
        self._reload_receipts()

    def _receipt_table_keypress(self, event) -> None:
        key = event.key()
        mods = event.modifiers()
        current = self.table.currentItem()
        if current:
            row = current.row()
            col = current.column()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.table.editItem(current)
                return
            if key == Qt.Key.Key_Space:
                self.table.selectRow(row)
                return
            if mods & Qt.KeyboardModifier.ControlModifier:
                if key == Qt.Key.Key_Down:
                    self.table.setCurrentCell(self.table.rowCount() - 1, col)
                    return
                if key == Qt.Key.Key_Up:
                    self.table.setCurrentCell(0, col)
                    return
        QTableWidget.keyPressEvent(self.table, event)

    # ============================================================================
    # PHASE 3: BULK OPERATIONS
    # ============================================================================
    def _bulk_select_all(self) -> None:
        """Select all receipts in table"""
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if isinstance(checkbox, QTableWidgetItem):
                checkbox.setCheckState(Qt.CheckState.Checked)

    def _bulk_clear_selection(self) -> None:
        """Clear all selections"""
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if isinstance(checkbox, QTableWidgetItem):
                checkbox.setCheckState(Qt.CheckState.Unchecked)

    def _get_selected_receipt_rows(self) -> object:
        """Get rows with checkboxes checked"""
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if (
                isinstance(checkbox, QTableWidgetItem)
                and checkbox.checkState() == Qt.CheckState.Checked
            ):
                selected.append(row)
        return selected

    def _bulk_change_category(self) -> None:
        """Change category for multiple receipts"""
        rows = self._get_selected_receipt_rows()
        if not rows:
            QMessageBox.information(
                self, "Bulk Category", "No receipts selected")
            return

        categories = ["fuel", "maintenance",
                      "insurance", "office", "meals", "other"]
        category, ok = QInputDialog.getItem(
            self, "Batch Category", "Select new category:",
            categories, 0, False
        )
        if not ok or not category:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            cur = self.db.get_cursor()
            for row in rows:
                receipt_id = self._get_receipt_id(row)
                if receipt_id:
                    cur.execute(
                        "UPDATE receipts SET category = %s"
                        " WHERE receipt_id = %s",
                        (category, receipt_id),
                    )
            self.db.commit()
            QMessageBox.information(
                self, "Success", f"Updated {len(rows)} receipts")
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Batch update failed: {e}")

    def _bulk_mark_verified(self) -> None:
        """Mark multiple receipts as verified"""
        rows = self._get_selected_receipt_rows()
        if not rows:
            QMessageBox.information(
                self, "Bulk Verify", "No receipts selected")
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            cur = self.db.get_cursor()
            for row in rows:
                receipt_id = self._get_receipt_id(row)
                if receipt_id:
                    cur.execute(
                        "UPDATE receipts SET verified_by_edit = TRUE,"
                        " verified_at = NOW() WHERE receipt_id = %s",
                        (receipt_id,),
                    )
                    # Visual feedback
                    for col in range(1, self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            item.setBackground(QBrush(QColor(200, 255, 200)))
            self.db.commit()
            QMessageBox.information(
                self, "Success", f"Marked {len(rows)} receipts as verified"
            )
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Batch verify failed: {e}")

    def _bulk_delete(self) -> None:
        """Delete multiple receipts"""
        rows = self._get_selected_receipt_rows()
        if not rows:
            QMessageBox.information(
                self, "Bulk Delete", "No receipts selected")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(rows)} selected receipts? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            cur = self.db.get_cursor()
            for row in rows:
                receipt_id = self._get_receipt_id(row)
                if receipt_id:
                    cur.execute(
                        "DELETE FROM receipts WHERE receipt_id = %s", (
                            receipt_id,)
                    )
            self.db.commit()
            QMessageBox.information(
                self, "Success", f"Deleted {len(rows)} receipts")
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Batch delete failed: {e}")

    # ============================================================================
    # PHASE 3: ROW EXPANSION / DETAIL VIEW
    # ============================================================================
    def _toggle_row_expansion(self, row, column) -> None:
        """Expand or collapse row to show full details"""
        # Get the receipt_id for this row first - skip detail/separator rows
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return  # Clicked on a detail row or year separator - ignore

        if receipt_id in self._expanded_rows:
            # Collapse: remove detail row immediately below this row
            self._expanded_rows.discard(receipt_id)
            if row + 1 < self.table.rowCount():
                detail_item = self.table.item(row + 1, 0)
                if (detail_item
                        and detail_item.text().startswith("  [Details]")):
                    self.table.removeRow(row + 1)
        else:
            # Expand: insert detail row below this receipt row
            self._expanded_rows.add(receipt_id)

            try:
                # Rollback any failed transactions first
                try:
                    self.db.rollback()
                except Exception:
                    try:
                        self.db.rollback()
                    except Exception as _e:
                        logger.debug('Suppressed: %s', _e)
                cur = self.db.get_cursor()
                cur.execute(
                    """
                    SELECT description, gl_account_code, gl_account_name,
                           source_system, is_verified_banking,
                           created_from_banking, banking_transaction_id,
                           is_paper_verified, verified_by_edit
                    FROM receipts
                    WHERE receipt_id = %s
                    """,
                    (receipt_id,),
                )
                result = cur.fetchone()
                if not result:
                    return

                desc = result[0] or "N/A"
                gl_code = result[1] or "N/A"
                gl_name = result[2] or "N/A"
                source = result[3] or "Manual Entry"
                verified_banking = result[4]
                from_banking = result[5]
                bank_tx = result[6]
                paper_verified = result[7]
                edit_verified = result[8]

                # Determine verification status
                if verified_banking or paper_verified or edit_verified:
                    reviewed = "✅ Verified"
                else:
                    reviewed = "⚠️ Unverified"

                banking = "🏦 From Banking" if from_banking else "Manual"

                detail_text = (
                    f"  [Details] Description: {desc}"
                    f" | GL Account: {gl_code} - {gl_name} | "
                    f"Source: {source} | Status: {reviewed} | Type: {banking}"
                )
                if bank_tx:
                    detail_text += f" | Bank TX: {bank_tx}"

                # Insert new row below current
                self.table.insertRow(row + 1)
                detail_item = QTableWidgetItem(detail_text)
                detail_item.setBackground(QBrush(QColor(240, 240, 240)))
                self.table.setItem(row + 1, 0, detail_item)
                self.table.setSpan(row + 1, 0, 1, self.table.columnCount())

            except Exception as e:
                QMessageBox.warning(
                    self, "Expand", f"Failed to load details: {e}")

    # ============================================================================
    # PHASE 3: CONTEXT MENU HELPER ACTIONS
    # ============================================================================
    def _duplicate_receipt(self, row) -> None:
        """Duplicate a receipt (copy values to new row)"""
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            cur = self.db.get_cursor()
            cur.execute(
                """
                INSERT INTO receipts (
                    receipt_date, vendor_name, canonical_vendor,
                    gross_amount, gst_amount,
                    category, description, gl_account_code, gl_account_name)
                SELECT receipt_date, vendor_name, canonical_vendor,
                       gross_amount, gst_amount,
                       category, description, gl_account_code, gl_account_name
                FROM receipts
                WHERE receipt_id = %s
                RETURNING receipt_id
                """,
                (receipt_id,),
            )
            new_id = cur.fetchone()[0]
            self.db.commit()
            QMessageBox.information(
                self, "Duplicated", f"Receipt duplicated as ID {new_id}"
            )
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Duplicate failed: {e}")

    def _change_receipt_category(self, row) -> None:
        """Change category for a single receipt"""
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return

        categories = ["fuel", "maintenance",
                      "insurance", "office", "meals", "other"]
        category, ok = QInputDialog.getItem(
            self, "Change Category", "Select category:", categories, 0, False
        )
        if not ok or not category:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            cur = self.db.get_cursor()
            cur.execute(
                "UPDATE receipts SET category = %s WHERE receipt_id = %s",
                (category, receipt_id),
            )
            self.db.commit()
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Update failed: {e}")

    def _mark_receipt_verified(self, row) -> None:
        """Mark single receipt as verified"""
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return

        try:
            cur = self.db.get_cursor()
            cur.execute(
                "UPDATE receipts SET verified_by_edit = TRUE,"
                " verified_at = NOW() WHERE receipt_id = %s",
                (receipt_id,),
            )
            self.db.commit()
            # Visual feedback
            for col in range(1, self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QBrush(QColor(200, 255, 200)))
            QMessageBox.information(
                self, "Verified", "Receipt marked as verified")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Verify failed: {e}")

    def _delete_receipt_row(self, row) -> None:
        """Delete single receipt"""
        receipt_id = self._get_receipt_id(row)
        if not receipt_id:
            return

        reply = QMessageBox.question(
            self,
            "Delete",
            f"Delete receipt ID {receipt_id}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            cur = self.db.get_cursor()
            cur.execute(
                "DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
            self.db.commit()
            QMessageBox.information(self, "Deleted", "Receipt deleted")
            self._reload_receipts()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Failed", f"Delete failed: {e}")

    def save_receipt(self) -> None:
        # Show progress indicator
        progress = QMessageBox(self)
        progress.setWindowTitle("Saving...")
        progress.setText("Saving receipt to database...")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.show()
        QApplication.processEvents()

        # Get vendor in UPPERCASE from VendorSelector
        vendor = self.vendor_input.get_vendor()
        if not vendor:
            progress.close()
            QMessageBox.warning(self, "Validation", "Vendor is required")
            return

        # Parse amount from currency input field
        try:
            amount = Decimal(str(self.amount_input.get_value()))
        except Exception:
            try:
                self.db.rollback()
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            progress.close()
            QMessageBox.warning(self, "Validation",
                                "Amount must be a valid number")
            return

        gst_val = Decimal(
            str(self.gst_display.text().replace(
                "$", "").replace(",", "") or "0")
        )
        pst_val = (
            Decimal(str(self.pst_input.get_value()))
            if hasattr(self.pst_input, "get_value")
            else Decimal("0")
        )
        gl_code = self.gl_combo.currentData()
        gl_name = self.gl_accounts.get(gl_code, None) if gl_code else None
        vehicle_id = self.vehicle_combo.currentData()
        vehicle_id = int(vehicle_id) if vehicle_id else None
        fuel_amount = (
            self.fuel_amount_input.value()
            if hasattr(self, "fuel_amount_input") else 0
        )
        fuel_amount = Decimal(str(fuel_amount)) if fuel_amount else None
        is_driver_personal = self.driver_personal_check.isChecked()
        is_gst_exempt = self.gst_exempt_check.isChecked()
        is_personal = self.personal_check.isChecked()

        tax_jurisdiction = (
            self.tax_jurisdiction.currentText()
            if hasattr(self, "tax_jurisdiction")
            else None
        )
        category = None
        if hasattr(self.vendor_input, "get_suggested_category"):
            category = self.vendor_input.get_suggested_category()

        canonical_vendor = vendor.upper()
        owner_personal_amount = (
            amount if is_personal and not is_driver_personal else Decimal("0")
        )

        # Determine GST code based on checkboxes
        if is_driver_personal:
            gst_code = "DRIVER_PERSONAL"
        elif is_gst_exempt:
            gst_code = "GST_EXEMPT"
        else:
            gst_code = "GST_INCL_5"

        if is_driver_personal or is_gst_exempt:
            gst_val = Decimal("0")

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except Exception:
                try:
                    self.db.rollback()
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            cur = self.db.get_cursor()
            cur.execute(
                """
                INSERT INTO receipts (
                    receipt_date, vendor_name, canonical_vendor,
                    gross_amount, gst_amount, net_amount, gst_code, sales_tax,
                    tax_jurisdiction, category, description, vehicle_id,
                    fuel_amount, owner_personal_amount, gl_account_code,
                    gl_account_name, is_paper_verified)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING receipt_id
                """,
                (
                    self.date_edit.getDate().toPyDate(),
                    vendor,
                    canonical_vendor,
                    amount,
                    gst_val,
                    round(amount - gst_val, 2),  # net_amount
                    gst_code,
                    pst_val,
                    tax_jurisdiction,
                    category,
                    self.description_input.toPlainText().strip() or None,
                    vehicle_id,
                    fuel_amount,
                    owner_personal_amount,
                    gl_code,
                    gl_name,
                ),
            )
            receipt_id = cur.fetchone()[0]
            self.db.commit()
            progress.close()
            QMessageBox.information(
                self, "Saved", f"Receipt #{receipt_id} saved")
            self._track_category_usage(category)
            self.undo_stack.clear()
            self.reset_form()
            self.load_receipts()
        except Exception as e:
            self.db.rollback()
            progress.close()
            QMessageBox.critical(self, "Save Failed",
                                 f"Could not save receipt:\n{e}")

    def reset_form(self) -> None:
        self.date_edit.setDate(QDate.currentDate())
        self.vendor_input.clear()
        self.amount_input.setValue(0.0)
        self.gst_display.setText("$0.00")
        self.pst_input.setText("0.00")
        self.tax_jurisdiction.setCurrentIndex(0)  # Reset to AB (GST 5%)
        self.gl_combo.setCurrentIndex(0)
        if hasattr(self, "fuel_amount_input"):
            self.fuel_amount_input.setValue(0)
        self.vehicle_combo.setCurrentIndex(0)
        self.description_input.clear()
        self.personal_check.setChecked(False)
        self.driver_personal_check.setChecked(False)
        self.gst_exempt_check.setChecked(False)
