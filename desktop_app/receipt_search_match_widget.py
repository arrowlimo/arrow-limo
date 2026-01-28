"""
Receipt Search & Match Widget (restored minimal version)
Provides a stable search + view interface for receipts and a placeholder for add/update.
Original file was corrupted; this version prioritizes loading without crashes.
"""

import os
from decimal import Decimal
from typing import List

import psycopg2
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QDoubleValidator, QColor, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QDoubleSpinBox,
    QGroupBox,
    QFormLayout,
    QCheckBox,
    QMessageBox,
    QSplitter,
    QHeaderView,
    QTabWidget,
    QComboBox,
    QSizePolicy,
    QCompleter,
    QDialog,
    QScrollArea,
)

from desktop_app.common_widgets import StandardDateEdit
from desktop_app.split_receipt_manager_dialog import SplitReceiptManagerDialog
from desktop_app.banking_transaction_picker_dialog import BankingTransactionPickerDialog
from desktop_app.split_receipt_details_widget import SplitReceiptDetailsWidget


class DateInput(StandardDateEdit):
    """Keep legacy name used elsewhere; StandardDateEdit already handles parsing."""

    def __init__(self, parent=None):
        # allow_blank=True so the field can start empty instead of auto-filling today
        super().__init__(parent, allow_blank=True)

    def date(self):
        # Preserve compatibility with QDateEdit API
        return super().date()


class CurrencyInput(QLineEdit):
    """Simple currency field with 2-decimal validation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        validator = QDoubleValidator(0.0, 1_000_000_000.0, 2, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(validator)
        self.setPlaceholderText("0.00")
        self.setMaxLength(20)

    def value(self) -> Decimal:
        text = (self.text() or "0").replace(",", "").strip()
        try:
            return Decimal(text)
        except Exception:
            return Decimal("0")


class ReceiptSearchMatchWidget(QWidget):
    """Lightweight, crash-safe rebuild of the receipt search/match UI."""

    def __init__(self, conn: psycopg2.extensions.connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._column_cache = {}
        self.last_results: List[tuple] = []
        self.skip_recent = str(os.environ.get("RECEIPT_WIDGET_SKIP_RECENT", "true")).lower() in ("1", "true", "yes")
        self.write_enabled = str(os.environ.get("RECEIPT_WIDGET_WRITE_ENABLED", "false")).lower() in ("1", "true", "yes")
        self._build_ui()
        if self.skip_recent:
            self.results_label.setText("(recent load skipped; click Search)")
        if not self.skip_recent:
            self._load_recent()
        # Connect duplicate check button (deferred via lambda)
        self.dup_check_btn.clicked.connect(lambda: self._check_duplicates())

    def _normalize_date_param(self, d):
        """Convert QDate/QDateTime to Python date; return None if unset."""
        try:
            if d is None:
                return None
            # QDate from PyQt
            if hasattr(d, 'toPyDate'):
                return d.toPyDate()
            # QDateTime -> QDate -> Python date
            if hasattr(d, 'date'):
                qd = d.date()
                if hasattr(qd, 'toPyDate'):
                    return qd.toPyDate()
        except Exception:
            pass
        return d

    def _receipts_has_column(self, column_name: str) -> bool:
        """Check once if receipts has the given column; cache the result."""
        try:
            key = f"receipts.{column_name}"
            if key in self._column_cache:
                return self._column_cache[key]
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema='public'
                          AND table_name='receipts'
                          AND column_name=%s
                    )
                    """,
                    (column_name,)
                )
                exists = bool(cur.fetchone()[0])
            self._column_cache[key] = exists
            return exists
        except Exception:
            # If check fails, be conservative and return False
            return False

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        """Build main layout: Left side has Search, Banking, Charter (scrollable); Right side has Receipt Details (scrollable)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Build sections
        self.search_panel = self._build_search_panel()
        self.receipt_detail_panel = self._build_receipt_detail_panel()
        self.banking_match_panel = self._build_banking_match_panel()
        self.charter_lookup_panel = self._build_charter_lookup_panel()

        # Main splitter: left side has search/banking/charter; right side has receipts
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: vertical stack of search, banking, charter with scroll area
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(3)

        # Search section
        left_layout.addWidget(self.search_panel)

        # Banking match section
        banking_group = QGroupBox("🏦 Banking Match")
        banking_group_layout = QVBoxLayout(banking_group)
        banking_group_layout.setContentsMargins(5, 5, 5, 5)
        banking_group_layout.addWidget(self.banking_match_panel)
        left_layout.addWidget(banking_group)

        # Charter lookup section
        charter_group = QGroupBox("📍 Charter Lookup")
        charter_group_layout = QVBoxLayout(charter_group)
        charter_group_layout.setContentsMargins(5, 5, 5, 5)
        charter_group_layout.addWidget(self.charter_lookup_panel)
        left_layout.addWidget(charter_group)

        left_layout.addStretch()

        # Wrap left side in scroll area
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_container)
        left_scroll.setWidgetResizable(True)
        main_splitter.addWidget(left_scroll)

        # Right side: Receipt Details with scroll area
        receipt_group = QGroupBox("📋 Receipt Details")
        receipt_group_layout = QVBoxLayout(receipt_group)
        receipt_group_layout.setContentsMargins(5, 5, 5, 5)
        receipt_group_layout.addWidget(self.receipt_detail_panel)

        # Wrap right side in scroll area
        right_scroll = QScrollArea()
        right_scroll.setWidget(receipt_group)
        right_scroll.setWidgetResizable(True)
        main_splitter.addWidget(right_scroll)

        main_splitter.setSizes([400, 600])

        layout.addWidget(main_splitter)

    def _build_search_panel(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)

        # Row 1: Date range + Vendor
        self.date_from = StandardDateEdit(allow_blank=True)
        self.date_to = StandardDateEdit(allow_blank=True)
        self.vendor_filter = QLineEdit()
        self.vendor_filter.setPlaceholderText("Vendor contains...")
        self.vendor_filter.returnPressed.connect(self._do_search)
        
        row1 = QHBoxLayout()
        row1.addWidget(self.date_from)
        row1.addWidget(QLabel("to"))
        row1.addWidget(self.date_to)
        row1.addWidget(QLabel("Vendor:"))
        row1.addWidget(self.vendor_filter)
        row1.addStretch()
        form.addRow("Date & Vendor", row1)

        # Row 2: Charter + Description
        self.charter_filter = QLineEdit()
        self.charter_filter.setPlaceholderText("Reserve # / Charter...")
        self.charter_filter.returnPressed.connect(self._do_search)
        self.include_desc_chk = QCheckBox("Search Description")
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Charter:"))
        row2.addWidget(self.charter_filter)
        row2.addWidget(self.include_desc_chk)
        row2.addStretch()
        form.addRow("Charter & Options", row2)

        # Row 3: Amount + Receipt ID
        self.amount_filter = CurrencyInput()
        self.amount_filter.setMaximumWidth(120)
        self.amount_filter.returnPressed.connect(self._do_search)
        self.amount_range = QDoubleSpinBox()
        self.amount_range.setRange(0, 10000)
        self.amount_range.setDecimals(2)
        self.amount_range.setSingleStep(0.01)
        self.amount_range.setPrefix("±$")
        self.amount_range.setValue(0.0)
        self.amount_range.setMaximumWidth(80)
        
        # Amount checkbox - to filter by total amounts
        self.amount_check = QCheckBox("Match Total")
        self.amount_check.setMaximumWidth(100)
        self.amount_check.setChecked(False)
        
        self.receipt_id_filter = QLineEdit()
        self.receipt_id_filter.setPlaceholderText("ID")
        self.receipt_id_filter.setMaximumWidth(80)
        self.receipt_id_filter.returnPressed.connect(self._do_search)
        
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Amount:"))
        row3.addWidget(self.amount_filter)
        row3.addWidget(self.amount_range)
        row3.addWidget(self.amount_check)
        row3.addWidget(QLabel("ID:"))
        row3.addWidget(self.receipt_id_filter)
        row3.addStretch()
        form.addRow("Amount & ID", row3)

        # Row 4: Buttons
        btn_row = QHBoxLayout()
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self._do_search)
        btn_row.addWidget(self.search_btn)

        self.clear_btn = QPushButton("✕ Clear")
        self.clear_btn.clicked.connect(self._clear_filters)
        btn_row.addWidget(self.clear_btn)

        self.results_label = QLabel("")
        btn_row.addWidget(self.results_label)
        btn_row.addStretch()
        form.addRow("", btn_row)

        return panel


    def _build_receipt_detail_panel(self) -> QWidget:
        panel = QWidget()
        vbox = QVBoxLayout(panel)

        self.results_table = QTableWidget(0, 10)
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Date", "Vendor", "Amount", "GL/Category", "Charter", "Banking ID", "Matched", "Reserve #", "Driver"]
        )
        header: QHeaderView = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        
        # Make table auto-expand to fit content (up to max height)
        self.results_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.results_table.setMaximumHeight(600)  # Cap at 600px to prevent taking over window
        
        self.results_table.itemSelectionChanged.connect(self._populate_form_from_selection)
        self.results_table.doubleClicked.connect(self._on_receipt_double_clicked)
        
        # Add action buttons above table
        table_actions_layout = QHBoxLayout()
        self.delete_selected_btn = QPushButton("🗑️ Delete Selected")
        self.delete_selected_btn.clicked.connect(self._delete_selected_receipts)
        self.delete_selected_btn.setToolTip("Delete selected receipt(s) from the table")
        table_actions_layout.addWidget(self.delete_selected_btn)
        table_actions_layout.addStretch()
        vbox.addLayout(table_actions_layout)
        
        vbox.addWidget(self.results_table)
        
        # Split receipt details (will show if receipt is split)
        self.split_details_widget = SplitReceiptDetailsWidget(self.conn)
        vbox.addWidget(self.split_details_widget)

        add_box = QGroupBox("Add / Update (temporarily read-only)")
        vbox_form = QVBoxLayout(add_box)
        vbox_form.setSpacing(3)
        vbox_form.setContentsMargins(5, 5, 5, 5)

        # Row 1: Date + Vendor + Invoice
        form_row1 = QHBoxLayout()
        form_row1.addWidget(QLabel("Date:"))
        self.new_date = DateInput()
        self.new_date.setDate(None)
        self.new_date.setMaximumWidth(110)
        form_row1.addWidget(self.new_date)
        
        form_row1.addWidget(QLabel("Vendor:"))
        self.new_vendor = QLineEdit()
        self.new_vendor.setMaximumWidth(150)
        form_row1.addWidget(self.new_vendor)
        
        form_row1.addWidget(QLabel("Invoice #:"))
        self.new_invoice = QLineEdit()
        self.new_invoice.setMaximumWidth(80)
        form_row1.addWidget(self.new_invoice)
        form_row1.addStretch()
        vbox_form.addLayout(form_row1)

        # Row 2: Amount + GST + PST
        form_row2 = QHBoxLayout()
        form_row2.addWidget(QLabel("Amount:"))
        self.new_amount = CurrencyInput()
        self.new_amount.setMaximumWidth(100)
        form_row2.addWidget(self.new_amount)
        # Connect amount field change to auto-calculate GST
        self.new_amount.textChanged.connect(self._auto_calculate_gst)

        self.calc_btn = QPushButton("Calc")
        self.calc_btn.setMaximumWidth(50)
        self.calc_btn.clicked.connect(self._open_calculator)
        form_row2.addWidget(self.calc_btn)
        
        form_row2.addWidget(QLabel("GST (auto):"))
        self.new_gst = CurrencyInput()
        self.new_gst.setMaximumWidth(80)
        form_row2.addWidget(self.new_gst)
        
        self.gst_exempt_chk = QCheckBox("Exempt")
        self.gst_exempt_chk.setMaximumWidth(70)
        form_row2.addWidget(self.gst_exempt_chk)
        
        form_row2.addWidget(QLabel("PST:"))
        self.new_pst = CurrencyInput()
        self.new_pst.setMaximumWidth(80)
        form_row2.addWidget(self.new_pst)
        form_row2.addStretch()
        vbox_form.addLayout(form_row2)
        
        # Row 2b: Tax Jurisdiction + Reason
        form_row2b = QHBoxLayout()
        form_row2b.addWidget(QLabel("Tax Jurisdiction:"))
        self.tax_jurisdiction = QComboBox()
        self.tax_jurisdiction.addItems([
            "AB (GST 5%)", "BC (GST 5% + PST 7%)", "SK (GST 5%)", "MB (GST 5%)",
            "ON (HST 13%)", "QC (GST 5% + PST 9.975%)", "NB (HST 15%)", "NS (HST 15%)",
            "PE (HST 15%)", "NL (HST 15%)", "VT (GST 5%)", "NT (GST 5%)", "NU (GST 5%)",
            "US (varies)", "Other (manual entry)"
        ])
        self.tax_jurisdiction.setCurrentIndex(0)  # Default to AB
        self.tax_jurisdiction.setMaximumWidth(180)
        # Connect jurisdiction change to recalculate GST
        self.tax_jurisdiction.currentTextChanged.connect(self._auto_calculate_gst)
        form_row2b.addWidget(self.tax_jurisdiction)
        
        form_row2b.addWidget(QLabel("Reason:"))
        self.tax_reason = QComboBox()
        self.tax_reason.addItems([
            "Standard purchase",
            "Manual - Government fee",
            "Manual - Adjustment",
            "Manual - Correction",
            "Manual - Write-off",
            "Other (see notes)"
        ])
        self.tax_reason.setCurrentIndex(0)
        self.tax_reason.setMaximumWidth(150)
        form_row2b.addWidget(self.tax_reason)
        form_row2b.addStretch()
        vbox_form.addLayout(form_row2b)

        form_row3 = QHBoxLayout()
        form_row3.addWidget(QLabel("GL:"))
        self.new_gl = QComboBox()
        self.new_gl.setEditable(True)
        self.new_gl.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.new_gl.setPlaceholderText("Type GL code or category...")
        self.new_gl.setMinimumWidth(200)
        self.new_gl.setMaximumWidth(300)
        self._load_gl_accounts()
        form_row3.addWidget(self.new_gl)
        
        form_row3.addWidget(QLabel("Charter:"))
        charter_box = QHBoxLayout()
        self.new_charter = QLineEdit()
        self.new_charter.setPlaceholderText("Reserve #")
        self.new_charter.setMaximumWidth(90)
        charter_box.addWidget(self.new_charter)
        self.link_charter_btn = QPushButton("Link")
        self.link_charter_btn.setMaximumWidth(50)
        self.link_charter_btn.clicked.connect(self._link_charter_to_receipt_form)
        charter_box.addWidget(self.link_charter_btn)
        
        # Create a widget to hold the charter box layout
        charter_widget = QWidget()
        charter_widget.setLayout(charter_box)
        form_row3.addWidget(charter_widget)
        self._attach_charter_completer()
        
        form_row3.addWidget(QLabel("Vehicle:"))
        vehicle_box = QHBoxLayout()
        vehicle_box.setContentsMargins(0, 0, 0, 0)
        self.new_vehicle = QComboBox()
        self.new_vehicle.setEditable(True)
        self.new_vehicle.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.new_vehicle.addItem("", None)
        self.new_vehicle.setMinimumWidth(90)
        self.new_vehicle.setMaximumWidth(140)
        try:
            self.new_vehicle.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        except Exception:
            pass
        self._load_vehicles_into_combo()
        vehicle_box.addWidget(self.new_vehicle)
        vehicle_box.addWidget(QLabel("Type:"))
        self.new_vehicle_type_label = QLabel("")
        self.new_vehicle_type_label.setStyleSheet("color:#555; padding-left:4px;")
        vehicle_box.addWidget(self.new_vehicle_type_label)
        self.vehicle_from_charter_chk = QCheckBox("✓")
        self.vehicle_from_charter_chk.setMaximumWidth(30)
        self.vehicle_from_charter_chk.setToolTip("Auto-populate from charter")
        self.vehicle_from_charter_chk.stateChanged.connect(self._apply_vehicle_from_charter)
        vehicle_box.addWidget(self.vehicle_from_charter_chk)
        vehicle_widget = QWidget()
        vehicle_widget.setLayout(vehicle_box)
        form_row3.addWidget(vehicle_widget)
        
        form_row3.addWidget(QLabel("Driver:"))
        driver_box = QHBoxLayout()
        driver_box.setContentsMargins(0, 0, 0, 0)
        self.new_driver = QComboBox()
        self.new_driver.setEditable(True)
        self.new_driver.addItem("", None)
        self.new_driver.setMinimumWidth(130)
        self.new_driver.setMaximumWidth(150)
        self._load_drivers_into_combo()
        driver_box.addWidget(self.new_driver)
        self.driver_from_charter_chk = QCheckBox("✓")
        self.driver_from_charter_chk.setMaximumWidth(30)
        self.driver_from_charter_chk.setToolTip("Auto-populate from charter")
        self.driver_from_charter_chk.stateChanged.connect(self._apply_driver_from_charter)
        driver_box.addWidget(self.driver_from_charter_chk)
        driver_widget = QWidget()
        driver_widget.setLayout(driver_box)
        form_row3.addWidget(driver_widget)
        form_row3.addStretch()
        vbox_form.addLayout(form_row3)

        # Row 3b: Fuel (L) - hidden by default, shown only if GL contains "fuel" or "gas"
        form_row3b = QHBoxLayout()
        form_row3b.addWidget(QLabel("Fuel (L):"))
        self.fuel_liters = QDoubleSpinBox()
        self.fuel_liters.setRange(0, 5000)
        self.fuel_liters.setDecimals(3)
        self.fuel_liters.setSuffix(" L")
        self.fuel_liters.setMaximumWidth(100)
        form_row3b.addWidget(self.fuel_liters)
        form_row3b.addStretch()
        vbox_form.addLayout(form_row3b)
        # Hide by default, will show when GL is fuel/gas related
        self.fuel_liters.setVisible(False)
        # Connect GL change to toggle fuel visibility
        self.new_gl.currentTextChanged.connect(self._toggle_fuel_visibility)

        # Row 4: Payment Method + Personal + Dvr Personal
        form_row4 = QHBoxLayout()
        form_row4.addWidget(QLabel("Payment:"))
        self.payment_method = QComboBox()
        self.payment_method.addItems([
            "credit/debit_card",
            "cash",
            "check",
            "bank_transfer",
            "trade_of_services",
            "unknown",
        ])
        self.payment_method.setCurrentIndex(0)  # Default to credit/debit_card
        self.payment_method.setMaximumWidth(120)
        form_row4.addWidget(self.payment_method)
        
        self.personal_chk = QCheckBox("Personal")
        form_row4.addWidget(self.personal_chk)
        
        self.dvr_personal_chk = QCheckBox("Dvr Personal")
        form_row4.addWidget(self.dvr_personal_chk)
        form_row4.addStretch()
        vbox_form.addLayout(form_row4)

        # Row 5: Description + Reimbursement + Banking ID
        form_row5 = QHBoxLayout()
        form_row5.addWidget(QLabel("Description:"))
        self.new_desc = QLineEdit()
        self.new_desc.setMaximumWidth(250)
        form_row5.addWidget(self.new_desc)
        
        form_row5.addWidget(QLabel("Reimburse:"))
        self.new_reimburse = CurrencyInput()
        self.new_reimburse.setMaximumWidth(80)
        form_row5.addWidget(self.new_reimburse)
        
        self.new_banking_id = QLineEdit()
        self.new_banking_id.setPlaceholderText("Banking ID")
        self.new_banking_id.setMaximumWidth(80)
        form_row5.addWidget(self.new_banking_id)
        form_row5.addStretch()
        vbox_form.addLayout(form_row5)

        # Row 6: Buttons + "Apply to all split receipts" checkbox
        form_row6 = QHBoxLayout()
        
        self.add_btn = QPushButton("Add")
        self.add_btn.setMaximumWidth(60)
        self.add_btn.clicked.connect(self._add_receipt)
        if not self.write_enabled:
            self.add_btn.setEnabled(False)
            self.add_btn.setToolTip("Disabled (set RECEIPT_WIDGET_WRITE_ENABLED=1 to allow)")
        form_row6.addWidget(self.add_btn)
        
        self.update_btn = QPushButton("Update")
        self.update_btn.setMaximumWidth(80)
        self.update_btn.clicked.connect(self._update_receipt)
        if not self.write_enabled:
            self.update_btn.setEnabled(False)
            self.update_btn.setToolTip("Disabled (set RECEIPT_WIDGET_WRITE_ENABLED=1 to allow)")
        form_row6.addWidget(self.update_btn)
        
        self.clear_form_btn = QPushButton("Clear Form")
        self.clear_form_btn.setMaximumWidth(90)
        self.clear_form_btn.clicked.connect(self._clear_form)
        form_row6.addWidget(self.clear_form_btn)
        
        self.dup_check_btn = QPushButton("Check Duplicates")
        self.dup_check_btn.setMaximumWidth(130)
        form_row6.addWidget(self.dup_check_btn)
        
        self.split_mgr_btn = QPushButton("Manage Splits")
        self.split_mgr_btn.setMaximumWidth(110)
        self.split_mgr_btn.setEnabled(True)  # Always enabled for split management
        self.split_mgr_btn.clicked.connect(self._open_split_manager)
        self.split_mgr_btn.setToolTip("Split GL codes (e.g., Vehicle Maintenance, Driver Meal on Duty)")
        form_row6.addWidget(self.split_mgr_btn)
        
        form_row6.addWidget(QLabel("Apply to all splits:"))
        self.apply_to_splits_chk = QCheckBox("✓")
        self.apply_to_splits_chk.setMaximumWidth(40)
        self.apply_to_splits_chk.setToolTip("When updating, apply changes to all split receipts")
        form_row6.addWidget(self.apply_to_splits_chk)
        
        form_row6.addStretch()
        vbox_form.addLayout(form_row6)

        vbox.addWidget(add_box)
        return panel

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _find_receipt_by_id(self):
        receipt_id_text = (self.receipt_id_filter.text() or "").strip()
        if not receipt_id_text:
            QMessageBox.warning(self, "Input Required", "Enter a receipt ID to search")
            return
        try:
            receipt_id = int(receipt_id_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid ID", "Receipt ID must be a number")
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,
                COALESCE(r.gl_account_name, r.gl_account_code::text, '') AS gl_name,
                r.banking_transaction_id, COALESCE(r.reserve_number, '') AS reserve_num,
                COALESCE(r.description, '') AS description, COALESCE(r.payment_method, '') AS payment_method,
                COALESCE(r.created_from_banking, false) AS created_from_banking,
                CASE WHEN r.banking_transaction_id IS NOT NULL THEN 'Yes' ELSE 'No' END AS matched_status,
                COALESCE(e.first_name || ' ' || e.last_name, '') AS driver_name
                FROM receipts r
                LEFT JOIN employees e ON r.employee_id = e.employee_id
                WHERE r.receipt_id = %s
                """,
                (receipt_id,),
            )
            row = cur.fetchone()
            cur.close()

            if row:
                self._populate_table([row])
                self.results_label.setText(f"Found receipt #{receipt_id}")
            else:
                QMessageBox.information(self, "Not Found", f"Receipt #{receipt_id} not found")
                self.results_table.setRowCount(0)
                self.results_label.setText("(no results)")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Search Error", f"Failed to find receipt:\n\n{e}")

    def _clear_filters(self):
        self.date_from.setDate(None)
        self.date_to.setDate(None)
        self.vendor_filter.clear()
        self.include_desc_chk.setChecked(False)
        self.charter_filter.clear()
        self.receipt_id_filter.clear()
        self.amount_filter.clear()
        self.amount_range.setValue(0.0)
        self.results_label.clear()
        self.results_table.setRowCount(0)

    def _do_search(self):
        """Run receipt search using active filters."""
        try:
            sql = [
                "SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,",
                "       CASE WHEN r.gl_account_code IS NOT NULL THEN r.gl_account_code::text || ' — ' || COALESCE(r.gl_account_name, '') ELSE COALESCE(r.gl_account_name, '') END AS gl_name,",
                "       r.banking_transaction_id, COALESCE(r.reserve_number, '') AS reserve_num,",
                "       COALESCE(r.description, '') AS description, COALESCE(r.payment_method, '') AS payment_method,",
                "       COALESCE(r.created_from_banking, false) AS created_from_banking,",
                "       CASE WHEN r.banking_transaction_id IS NOT NULL THEN 'Yes' ELSE 'No' END AS matched_status,",
                "       COALESCE(e.first_name || ' ' || e.last_name, '') AS driver_name,",
            ]
            # Dynamically select tax columns to avoid failures if columns are missing
            gst_expr = "COALESCE(r.gst_amount, 0.00)" if self._receipts_has_column("gst_amount") else (
                "COALESCE(r.tax, 0.00)" if self._receipts_has_column("tax") else "0.00::numeric"
            )
            pst_expr = "COALESCE(r.sales_tax, 0.00)" if self._receipts_has_column("sales_tax") else "0.00::numeric"
            sql.append(f"       {gst_expr} AS gst_amt, {pst_expr} AS pst_amt,")
            sql += [
                "       COALESCE(r.gst_code, '') AS gst_code,",
                "       COALESCE(r.tax_category, '') AS tax_category,",
                "       COALESCE(r.is_split_receipt, false) AS is_split_receipt",
                "FROM receipts r",
                "LEFT JOIN employees e ON r.employee_id = e.employee_id",
                "WHERE 1=1",
            ]
            params: List = []

            # Date range (normalize QDate/QDateTime → Python date)
            df = self._normalize_date_param(self.date_from.getDate())
            dt = self._normalize_date_param(self.date_to.getDate())
            if df:
                sql.append("AND r.receipt_date >= %s")
                params.append(df)
            if dt:
                sql.append("AND r.receipt_date <= %s")
                params.append(dt)

            # Vendor filter
            vendor_text = (self.vendor_filter.text() or "").strip()
            if vendor_text:
                sql.append("AND LOWER(COALESCE(r.vendor_name, '')) LIKE LOWER(%s)")
                params.append(f"%{vendor_text}%")

            # Charter / reserve filter
            charter_text = (self.charter_filter.text() or "").strip()
            if charter_text:
                sql.append("AND (COALESCE(r.reserve_number, '') ILIKE %s OR CAST(r.reserve_number AS TEXT) ILIKE %s)")
                params.extend([f"%{charter_text}%", f"%{charter_text}%"])

            # Description filter (optional)
            if self.include_desc_chk.isChecked() and vendor_text:
                sql.append("AND LOWER(COALESCE(r.description, '')) LIKE LOWER(%s)")
                params.append(f"%{vendor_text}%")

            # Amount filter with tolerance or exact match
            amount_val = (self.amount_filter.text() or "").replace(",", "").strip()
            if amount_val:
                try:
                    amt = float(amount_val)
                except ValueError:
                    QMessageBox.warning(self, "Invalid Amount", "Amount must be numeric (use digits and decimals only).")
                    return
                
                # If "Match Total" checkbox is checked, search for exact amount
                if self.amount_check.isChecked():
                    # Search both gross_amount (for normal receipts) and split_group_total (for split receipts)
                    sql.append("AND (r.gross_amount = %s OR r.split_group_total = %s)")
                    params.append(amt)
                    params.append(amt)
                else:
                    # Otherwise use tolerance range
                    tol = float(self.amount_range.value())
                    sql.append("AND (r.gross_amount BETWEEN %s AND %s OR r.split_group_total BETWEEN %s AND %s)")
                    params.extend([amt - tol, amt + tol, amt - tol, amt + tol])

            # Receipt ID direct filter
            if self.receipt_id_filter.text().strip():
                try:
                    rid = int(self.receipt_id_filter.text())
                    sql.append("AND r.receipt_id = %s")
                    params.append(rid)
                except ValueError:
                    QMessageBox.warning(self, "Invalid ID", "Receipt ID must be a number.")
                    return

            sql.append("ORDER BY r.receipt_date DESC, r.receipt_id DESC LIMIT 200")

            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()

            self.last_results = rows
            self._populate_table(rows)
            self.results_label.setText(f"Found {len(rows)} rows")
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Search failed:\n\n{e}")

    def _check_duplicates(self):
        """Check for potential duplicate receipts based on current form values (±$1, ±7 days)."""
        rows: List[tuple] = []
        try:
            # Clean up any aborted transactions first
            try:
                self.conn.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            vendor = (self.new_vendor.text() or "").strip()
            amount_text = self.new_amount.text().strip()

            if not vendor or not amount_text:
                QMessageBox.information(self, "Missing Data", "Enter Vendor and Amount to check for duplicates.")
                return

            try:
                amount = float(amount_text)
            except ValueError:
                QMessageBox.information(self, "Invalid Amount", "Amount must be a valid number.")
                return

            if amount <= 0:
                QMessageBox.information(self, "Invalid Amount", "Amount must be greater than 0.")
                return

            if not self.new_date.getDate():
                QMessageBox.information(self, "Missing Date", "Select a receipt date to check duplicates.")
                return

            date = self._normalize_date_param(self.new_date.getDate())
            if date:
                try:
                    date = date.toPyDate()
                except AttributeError:
                    pass

            # Get current receipt_id to exclude from duplicate check
            current_receipt_id = None
            selected = self.results_table.selectedItems()
            if selected:
                row = selected[0].row()
                try:
                    current_receipt_id = int(self.results_table.item(row, 0).text())
                except (ValueError, AttributeError):
                    pass

            cur = self.conn.cursor()
            if current_receipt_id:
                cur.execute(
                    """SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
                              COALESCE(description, '') as description,
                              COALESCE(gl_account_name, '') as gl_account
                       FROM receipts
                       WHERE LOWER(COALESCE(vendor_name, '')) LIKE LOWER(%s)
                       AND receipt_date BETWEEN %s - INTERVAL '7 days' AND %s + INTERVAL '7 days'
                       AND gross_amount BETWEEN %s AND %s
                       AND receipt_id != %s
                       ORDER BY receipt_date DESC
                       LIMIT 10""",
                    [f"%{vendor}%", date, date, float(amount) - 1.0, float(amount) + 1.0, current_receipt_id]
                )
            else:
                cur.execute(
                    """SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
                              COALESCE(description, '') as description,
                              COALESCE(gl_account_name, '') as gl_account
                       FROM receipts
                       WHERE LOWER(COALESCE(vendor_name, '')) LIKE LOWER(%s)
                       AND receipt_date BETWEEN %s - INTERVAL '7 days' AND %s + INTERVAL '7 days'
                       AND gross_amount BETWEEN %s AND %s
                       ORDER BY receipt_date DESC
                       LIMIT 10""",
                    [f"%{vendor}%", date, date, float(amount) - 1.0, float(amount) + 1.0]
                )
            rows = cur.fetchall()
            cur.close()

            if not rows:
                QMessageBox.information(self, "No Duplicates", f"No potential duplicates found for {vendor} ~${amount:.2f} (±7 days, ±$1).")
                return  # Exit without clearing search results
            else:
                msg = f"Found {len(rows)} potential duplicate(s):\n\n"
                for rid, rdate, rvend, ramt, rdesc, rgl in rows:
                    msg += f"• Receipt #{rid}: {rdate} | {rvend} | ${ramt:.2f} | {rgl}\n  {rdesc[:50]}\n\n"
                QMessageBox.warning(self, "Potential Duplicates Found", msg)
                
                # Only update results if duplicates were found
                self.last_results = rows
                self._populate_table(rows)
                self.results_label.setText(f"Found {len(rows)} potential duplicate(s)")
        except Exception as e:
            try:
                self.conn.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Could not check duplicates:\n{e}")
            return

    def _open_split_manager(self):
        """Launch the split receipt manager dialog for the current receipt."""
        # Try to get receipt_id from currently selected row in table
        selected_rows = self.results_table.selectedIndexes()
        receipt_id = None
        
        if selected_rows:
            # Get receipt_id from first column (ID) of selected row
            row = selected_rows[0].row()
            id_item = self.results_table.item(row, 0)  # Receipt ID is in column 0
            if id_item:
                try:
                    receipt_id = int(id_item.text())
                except ValueError:
                    pass
        
        # Fallback: try receipt_id_filter if table selection didn't work
        if not receipt_id:
            receipt_id_text = (self.receipt_id_filter.text() or "").strip()
            if not receipt_id_text:
                QMessageBox.warning(self, "No Receipt Selected", "Click a receipt in the results table or enter a receipt ID to manage splits.")
                return
            
            try:
                receipt_id = int(receipt_id_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid ID", "Receipt ID must be a number.")
                return
        
        # Fetch receipt details to verify it exists and get amount
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT receipt_id, receipt_date, vendor_name, gross_amount, payment_method, split_status
                FROM receipts
                WHERE receipt_id = %s
            """, (receipt_id,))
            row = cur.fetchone()
            cur.close()
            
            if not row:
                QMessageBox.warning(self, "Not Found", f"Receipt #{receipt_id} not found.")
                return
            
            receipt_data = {
                "receipt_id": row[0],
                "date": row[1],  
                "vendor": row[2],  
                "amount": float(row[3]),  
                "payment_method": row[4],  
                "split_status": row[5] or "single",
            }
            
            # Launch split manager dialog
            try:
                dialog = SplitReceiptManagerDialog(self.conn, receipt_id, receipt_data, parent=self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    # Refresh current view after saving splits
                    QMessageBox.information(self, "Success", "Split receipt saved successfully!")
            except Exception as e:
                try:
                    self.db.rollback()
                except:
                    pass
                QMessageBox.critical(self, "Error", f"Could not open split manager: {e}")
                print(f"Split manager error: {e}")
                import traceback
                traceback.print_exc()
                # Optionally reload the receipt in form
                self._find_receipt_by_id()
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open split manager:\n{e}")
            return


    def _populate_table(self, rows: List[tuple]):
        self.results_table.setColumnCount(11)
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Date", "Vendor", "Amount", "GL/Category", "Charter", "Banking ID", "Matched", "Reserve #", "Driver", "Status"]
        )
        header: QHeaderView = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents)

        self.results_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            rid, rdate, vendor, amount, gl_name, banking_id, reserve_num = row[:7]
            desc = row[7] if len(row) > 7 else ""
            paym = row[8] if len(row) > 8 else ""
            created_from_banking = bool(row[9]) if len(row) > 9 else False
            matched_status = row[10] if len(row) > 10 else "No"
            driver_name = row[11] if len(row) > 11 else ""
            gst_amt = row[12] if len(row) > 12 else 0.00
            pst_amt = row[13] if len(row) > 13 else 0.00
            gst_code = row[14] if len(row) > 14 else ""
            tax_category = row[15] if len(row) > 15 else ""
            is_split_receipt = bool(row[16]) if len(row) > 16 else False

            self.results_table.setItem(r, 0, QTableWidgetItem(str(rid)))
            self.results_table.setItem(r, 1, QTableWidgetItem(str(rdate)))

            vendor_item = QTableWidgetItem(vendor or "")
            summary = {
                "date": str(rdate),
                "vendor": vendor or "",
                "amount": float(amount) if amount is not None else None,
                "gl": gl_name or "",
                "description": desc or "",
                "banking_id": banking_id,
                "charter": reserve_num or "",
                "payment_method": paym or "",
                "created_from_banking": created_from_banking,
                "matched_status": matched_status,
                "driver_name": driver_name or "",
                "gst_amount": float(gst_amt) if gst_amt is not None else 0.00,
                "pst_amount": float(pst_amt) if pst_amt is not None else 0.00,
                "gst_code": gst_code or "",
                "tax_category": tax_category or "",
                "is_split_receipt": is_split_receipt,
            }
            vendor_item.setData(Qt.ItemDataRole.UserRole, summary)
            self.results_table.setItem(r, 2, vendor_item)

            amt_item = QTableWidgetItem(f"${amount:,.2f}" if amount is not None else "")
            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.results_table.setItem(r, 3, amt_item)

            self.results_table.setItem(r, 4, QTableWidgetItem(gl_name or ""))
            self.results_table.setItem(r, 5, QTableWidgetItem(reserve_num or ""))
            self.results_table.setItem(r, 6, QTableWidgetItem(str(banking_id) if banking_id is not None else ""))
            self.results_table.setItem(r, 7, QTableWidgetItem(matched_status))
            self.results_table.setItem(r, 8, QTableWidgetItem(reserve_num or ""))
            self.results_table.setItem(r, 9, QTableWidgetItem(driver_name or ""))
            
            # Status column - show "split" for split receipts
            status_item = QTableWidgetItem("split" if is_split_receipt else "")
            if is_split_receipt:
                status_item.setForeground(QColor(255, 0, 0))  # Red text
                status_item.setFont(QFont())
                font = status_item.font()
                font.setBold(True)
                status_item.setFont(font)
            self.results_table.setItem(r, 10, status_item)
            
            # Color-code rows: split receipts in blue, matched in green, unmatched in light red
            if is_split_receipt:
                # Split receipt: light blue background
                bg_color = QColor(200, 220, 255)
            elif banking_id is not None:
                # Matched: light green
                bg_color = QColor(200, 255, 200)
            else:
                # Unmatched: light red
                bg_color = QColor(255, 220, 220)
            for col in range(11):
                item = self.results_table.item(r, col)
                if item:
                    item.setBackground(bg_color)
        
        # Auto-resize table height to fit all rows
        self._auto_resize_table_height()

    def _auto_resize_table_height(self):
        """Auto-expand table height to fit content (up to max 600px)."""
        self.results_table.resizeRowsToContents()
        total_height = self.results_table.horizontalHeader().height()
        for row in range(self.results_table.rowCount()):
            total_height += self.results_table.rowHeight(row)
        
        # Cap at 600px maximum
        target_height = min(total_height + 4, 600)  # +4 for scrollbar padding
        self.results_table.setMaximumHeight(target_height)

    def _on_receipt_double_clicked(self, model_index):
        """Double-click on receipt row - populate the form."""
        try:
            row = model_index.row()
            rid_item = self.results_table.item(row, 0)
            
            print(f"[DEBUG] Double-clicked row {row}")
            if rid_item:
                print(f"  Receipt ID: {rid_item.text()}")
            
            if not rid_item or not rid_item.text().isdigit():
                print(f"  [WARN] Invalid receipt ID, skipping")
                return
            
            # Select this row to trigger _populate_form_from_selection
            print(f"  Selecting row {row}...")
            self.results_table.selectRow(row)
            print(f"  Row selected")
            
        except Exception as e:
            print(f"[ERROR] Error in double-click handler: {e}")
            import traceback
            traceback.print_exc()

    def _delete_selected_receipts(self):
        """Delete selected receipt(s) from results table."""
        selected_rows = self.results_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please click a receipt row to select it, then click Delete")
            return
        
        # Get unique rows
        rows_to_delete = sorted(set(idx.row() for idx in selected_rows), reverse=True)
        receipt_ids = []
        
        for row in rows_to_delete:
            rid_item = self.results_table.item(row, 0)
            if rid_item and rid_item.text().isdigit():
                receipt_ids.append(int(rid_item.text()))
        
        if not receipt_ids:
            QMessageBox.warning(self, "No Receipts", "No valid receipts selected")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            "Confirm Delete",
            f"Delete {len(receipt_ids)} receipt(s)?\n\nReceipt IDs: {', '.join(map(str, receipt_ids))}\n\nThis will also remove any banking matches.\nThis cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Delete from database
        try:
            cur = self.conn.cursor()
            for receipt_id in receipt_ids:
                try:
                    # Step 1: Try to delete from banking_receipt_matching_ledger if it exists
                    try:
                        cur.execute("DELETE FROM banking_receipt_matching_ledger WHERE receipt_id = %s", (receipt_id,))
                        self.conn.commit()
                    except Exception as e1:
                        self.conn.rollback()
                        print(f"  Note: Could not delete from banking_receipt_matching_ledger: {e1}")
                    
                    # Step 2: Clear banking_transaction links
                    try:
                        cur.execute("UPDATE banking_transactions SET receipt_id = NULL WHERE receipt_id = %s", (receipt_id,))
                        self.conn.commit()
                    except Exception as e2:
                        self.conn.rollback()
                        print(f"  Note: Could not clear receipt_id in banking_transactions: {e2}")
                    
                    try:
                        cur.execute("UPDATE banking_transactions SET reconciled_receipt_id = NULL WHERE reconciled_receipt_id = %s", (receipt_id,))
                        self.conn.commit()
                    except Exception as e3:
                        self.conn.rollback()
                        print(f"  Note: Could not clear reconciled_receipt_id in banking_transactions: {e3}")
                    
                    # Step 3: Delete the receipt itself
                    cur.execute("DELETE FROM receipts WHERE receipt_id = %s", (receipt_id,))
                    self.conn.commit()
                    
                except Exception as e:
                    self.conn.rollback()
                    raise Exception(f"Error deleting receipt {receipt_id}: {e}")
            
            cur.close()
            
            QMessageBox.information(self, "Deleted", f"✅ Deleted {len(receipt_ids)} receipt(s)")
            
            # Refresh the results table
            self._do_search()
            
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Delete Failed", f"Could not delete receipts:\n{e}")
            print(f"Delete error: {e}")
            import traceback
            traceback.print_exc()

    def _populate_form_from_selection(self):
        """Populate form fields from selected table row."""
        selected = self.results_table.selectedItems()
        if not selected:
            self._clear_form()
            return
        row = selected[0].row()
        try:
            rid_item = self.results_table.item(row, 0)
            date_item = self.results_table.item(row, 1)
            vendor_item = self.results_table.item(row, 2)
            amt_item = self.results_table.item(row, 3)
            gl_item = self.results_table.item(row, 4)
            charter_item = self.results_table.item(row, 5)
            banking_item = self.results_table.item(row, 6)

            print(f"[DEBUG] Populating form from row {row}:")
            print(f"  Receipt ID: {rid_item.text() if rid_item else 'None'}")
            print(f"  Date: {date_item.text() if date_item else 'None'}")
            print(f"  Vendor: {vendor_item.text() if vendor_item else 'None'}")
            print(f"  Amount: {amt_item.text() if amt_item else 'None'}")

            if date_item and date_item.text():
                self.new_date.setDate(QDate.fromString(date_item.text(), "yyyy-MM-dd"))
            if vendor_item:
                self.new_vendor.setText(vendor_item.text())
            self.new_invoice.clear()
            if amt_item:
                self.new_amount.setText(amt_item.text().replace("$", "").replace(",", ""))
            self.new_desc.setText("")
            if gl_item:
                self.new_gl.setCurrentText(gl_item.text())
            if banking_item:
                self.new_banking_id.setText(banking_item.text())
            if hasattr(self, "new_charter") and charter_item:
                self.new_charter.setText(charter_item.text())
                # Also pre-fill Charter Lookup reserve filter for convenience
                if hasattr(self, "charter_reserve_number"):
                    self.charter_reserve_number.setText(charter_item.text())
            
            # Extract and populate GST/PST from vendor item's user data
            if vendor_item:
                summary = vendor_item.data(Qt.ItemDataRole.UserRole)
                if summary and isinstance(summary, dict):
                    gst_amt = summary.get('gst_amount', 0.00)
                    pst_amt = summary.get('pst_amount', 0.00)
                    # Note: gst_exempt column doesn't exist in receipts table; use gst_code to determine status
                    gst_code = summary.get('gst_code', '')
                    gst_exempt = 'EXEMPT' in gst_code.upper() if gst_code else False
                    
                    if gst_amt and gst_amt > 0:
                        self.new_gst.setText(f"{gst_amt:.2f}")
                    else:
                        self.new_gst.clear()
                    
                    if pst_amt and pst_amt > 0:
                        self.new_pst.setText(f"{pst_amt:.2f}")
                    else:
                        self.new_pst.clear()
                    
                    self.gst_exempt_chk.setChecked(gst_exempt)
                    print(f"  GST: ${gst_amt:.2f}, PST: ${pst_amt:.2f}, Exempt: {gst_exempt}, Code: {gst_code}")
                    
                    # Populate Tax Jurisdiction and Reason from tax_category
                    tax_category = summary.get('tax_category', '')
                    if tax_category:
                        # Parse tax_category to determine jurisdiction and reason
                        # Format might be like "AB" or "BC - PST" etc.
                        jurisdiction_map = {
                            "AB": "AB (GST 5%)",
                            "BC": "BC (GST 5% + PST 7%)",
                            "SK": "SK (GST 5%)",
                            "MB": "MB (GST 5%)",
                            "ON": "ON (HST 13%)",
                            "QC": "QC (GST 5% + PST 9.975%)",
                            "NB": "NB (HST 15%)",
                            "NS": "NS (HST 15%)",
                            "PE": "PE (HST 15%)",
                            "NL": "NL (HST 15%)",
                            "VT": "VT (GST 5%)",
                            "NT": "NT (GST 5%)",
                            "NU": "NU (GST 5%)",
                        }
                        # Try to match first 2 chars to jurisdiction
                        for abbrev, full_name in jurisdiction_map.items():
                            if tax_category.upper().startswith(abbrev):
                                self.tax_jurisdiction.setCurrentText(full_name)
                                break
                        else:
                            # Default to Alberta if not found
                            self.tax_jurisdiction.setCurrentText("AB (GST 5%)")
                        
                        # Detect reason from tax_category
                        if "manual" in tax_category.lower():
                            if "fee" in tax_category.lower():
                                self.tax_reason.setCurrentText("Manual - Government fee")
                            elif "adjust" in tax_category.lower():
                                self.tax_reason.setCurrentText("Manual - Adjustment")
                            elif "correct" in tax_category.lower():
                                self.tax_reason.setCurrentText("Manual - Correction")
                            elif "write" in tax_category.lower():
                                self.tax_reason.setCurrentText("Manual - Write-off")
                            else:
                                self.tax_reason.setCurrentIndex(0)
                        else:
                            self.tax_reason.setCurrentIndex(0)  # Standard purchase
            
            # Auto-populate banking search if this receipt has a banking link
            if banking_item and banking_item.text() and banking_item.text() != "":
                try:
                    banking_id = int(banking_item.text())
                    # Load this specific banking transaction
                    self._auto_load_banking_transaction(banking_id)
                except (ValueError, AttributeError):
                    pass
            
            if rid_item and rid_item.text().isdigit():
                self.loaded_receipt_id = int(rid_item.text())
                print(f"  Loading split details for receipt {self.loaded_receipt_id}")
                # Load split details if this receipt is part of a split
                self.split_details_widget.load_receipt(self.loaded_receipt_id)
            else:
                self.loaded_receipt_id = None
                
            # ENABLE UPDATE button when receipt is selected
            self.update_btn.setEnabled(self.write_enabled)
            print(f"[DEBUG] Form populated successfully. UPDATE button enabled: {self.write_enabled}")
            
        except Exception as e:
            print(f"[ERROR] Failed to populate form: {e}")
            import traceback
            traceback.print_exc()
            self._clear_form()

    def _clear_form(self):
        self.new_date.setDate(None)
        self.new_vendor.clear()
        self.new_invoice.clear()
        self.new_amount.clear()
        self.new_gst.clear()
        self.new_pst.clear()
        self.gst_exempt_chk.setChecked(False)
        # Tax Jurisdiction and Reason
        if hasattr(self, "tax_jurisdiction"):
            self.tax_jurisdiction.setCurrentIndex(0)  # Reset to AB
        if hasattr(self, "tax_reason"):
            self.tax_reason.setCurrentIndex(0)  # Reset to Standard purchase
        self.new_desc.clear()
        # GL is now a combo, clear by setting to first item
        if isinstance(self.new_gl, QComboBox):
            self.new_gl.setCurrentIndex(0)
        else:
            self.new_gl.clear()
        if hasattr(self, "new_charter"):
            self.new_charter.clear()
        # Vehicle is now a combo
        if hasattr(self, "new_vehicle") and isinstance(self.new_vehicle, QComboBox):
            self.new_vehicle.setCurrentIndex(0)
        elif hasattr(self, "new_vehicle"):
            self.new_vehicle.clear()
        # Driver is now a combo
        if hasattr(self, "new_driver") and isinstance(self.new_driver, QComboBox):
            self.new_driver.setCurrentIndex(0)
        elif hasattr(self, "new_driver"):
            self.new_driver.clear()
        # Fuel
        if hasattr(self, "fuel_liters"):
            self.fuel_liters.setValue(0.0)
        if hasattr(self, "new_reimburse"):
            self.new_reimburse.clear()
        if hasattr(self, "payment_method"):
            self.payment_method.setCurrentIndex(0)  # Reset to credit/debit_card
        if hasattr(self, "personal_chk"):
            self.personal_chk.setChecked(False)
        if hasattr(self, "dvr_personal_chk"):
            self.dvr_personal_chk.setChecked(False)
        self.new_banking_id.clear()
        self.loaded_receipt_id = None
        self.update_btn.setEnabled(self.write_enabled)
        self.add_btn.setEnabled(self.write_enabled)

    def _unlink_banking_match(self):
        """Unlink the current receipt from its banking transaction."""
        if not self.loaded_receipt_id:
            QMessageBox.warning(self, "No Receipt", "Please load a receipt first")
            return
        
        reply = QMessageBox.question(
            self,
            "Unlink Banking?",
            f"Unlink receipt #{self.loaded_receipt_id} from banking transaction?\n\nThis will remove the banking match.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            cur = self.conn.cursor()
            
            # Clear banking links
            cur.execute("UPDATE banking_transactions SET receipt_id = NULL WHERE receipt_id = %s", (self.loaded_receipt_id,))
            cur.execute("UPDATE banking_transactions SET reconciled_receipt_id = NULL WHERE reconciled_receipt_id = %s", (self.loaded_receipt_id,))
            cur.execute("DELETE FROM banking_receipt_matching_ledger WHERE receipt_id = %s", (self.loaded_receipt_id,))
            
            # Clear the receipt's banking_transaction_id
            cur.execute("UPDATE receipts SET banking_transaction_id = NULL WHERE receipt_id = %s", (self.loaded_receipt_id,))
            
            self.conn.commit()
            cur.close()
            
            QMessageBox.information(self, "Unlinked", f"✅ Unlinked receipt #{self.loaded_receipt_id} from banking")
            
            # Refresh the current results to show updated status
            self._do_search()
            
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Error", f"Could not unlink banking match:\n{e}")
            print(f"Unlink error: {e}")
            import traceback
            traceback.print_exc()

    def _add_receipt(self):
        if not self.write_enabled:
            QMessageBox.information(
                self,
                "Add disabled",
                "Set RECEIPT_WIDGET_WRITE_ENABLED=1 to allow add/update in this widget.",
            )
            return
        QMessageBox.information(
            self,
            "Add not implemented",
            "Write logic is not yet restored in this recovery build.",
        )

    def _update_receipt(self):
        if not self.write_enabled:
            QMessageBox.information(
                self,
                "Update disabled",
                "Set RECEIPT_WIDGET_WRITE_ENABLED=1 to allow add/update in this widget.",
            )
            return
        
        # Get currently selected receipt
        selected = self.results_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a receipt to update.")
            return
        
        row = selected[0].row()
        receipt_id = int(self.results_table.item(row, 0).text())
        
        try:
            # Get form values
            receipt_date = self.new_date.date().toPyDate()
            vendor = self.new_vendor.text().strip()
            amount = float(self.new_amount.text() or 0)
            description = self.new_desc.text().strip()
            invoice_num = self.new_invoice.text().strip()
            gl_code = self.new_gl.currentData()
            reserve_num = self.new_charter.text().strip() or None
            banking_id = self.new_banking_id.text().strip() or None
            
            # Get vehicle_id and employee_id from dropdowns
            vehicle_id = self.new_vehicle.currentData()
            employee_id = self.new_driver.currentData()
            
            if not vendor:
                QMessageBox.warning(self, "Validation", "Vendor name is required.")
                return
            
            # Update the receipt
            cur = self.conn.cursor()
            cur.execute("""
                UPDATE receipts 
                SET receipt_date = %s,
                    vendor_name = %s,
                    gross_amount = %s,
                    description = %s,
                    invoice_number = %s,
                    gl_account_code = %s,
                    reserve_number = %s,
                    banking_transaction_id = %s,
                    vehicle_id = %s,
                    employee_id = %s,
                    verified_by_edit = TRUE,
                    verified_at = NOW(),
                    verified_by_user = 'desktop_app'
                WHERE receipt_id = %s
            """, (receipt_date, vendor, amount, description, invoice_num, gl_code, 
                  reserve_num, banking_id, vehicle_id, employee_id, receipt_id))
            
            self.conn.commit()
            
            # If "Apply to all split receipts" is checked, apply to splits
            if self.apply_to_splits_chk.isChecked():
                cur = self.conn.cursor()
                # Get split_group_id for this receipt
                cur.execute("SELECT split_group_id FROM receipts WHERE receipt_id = %s", (receipt_id,))
                result = cur.fetchone()
                if result and result[0]:
                    split_group_id = result[0]
                    # Update all receipts in split group
                    cur.execute("""
                        UPDATE receipts
                        SET vehicle_id = %s,
                            employee_id = %s,
                            verified_by_edit = TRUE,
                            verified_at = NOW(),
                            verified_by_user = 'desktop_app'
                        WHERE split_group_id = %s AND receipt_id != %s
                    """, (vehicle_id, employee_id, split_group_id, receipt_id))
                    self.conn.commit()
                cur.close()
            
            cur.close()
            
            QMessageBox.information(self, "Success", f"Receipt #{receipt_id} updated and verified successfully!")
            
            # Refresh the table
            self._do_search()
            # Clear form and reset button state until next selection
            self._clear_form()
            self.update_btn.setEnabled(self.write_enabled)
            
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Update Error", f"Failed to update receipt:\n\n{e}")

    def _link_charter_to_receipt_form(self):
        """Link selected charter to receipt form (populate vehicle/driver from charter if checkboxes checked)."""
        if not self.new_charter.text().strip():
            QMessageBox.warning(self, "No Charter", "Enter a reserve number first.")
            return
        
        reserve_num = self.new_charter.text().strip()
        
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT vehicle, COALESCE(driver_name, driver) AS driver
                FROM charters
                WHERE reserve_number = %s
                LIMIT 1
            """, (reserve_num,))
            result = cur.fetchone()
            cur.close()
            
            if not result:
                QMessageBox.warning(self, "Not Found", f"Charter {reserve_num} not found.")
                return
            
            vehicle, driver = result
            
            # Auto-populate if checkboxes are checked
            if self.vehicle_from_charter_chk.isChecked() and vehicle:
                idx = self.new_vehicle.findText(vehicle)
                if idx >= 0:
                    self.new_vehicle.setCurrentIndex(idx)
                else:
                    self.new_vehicle.setEditText(vehicle)
            
            if self.driver_from_charter_chk.isChecked() and driver:
                idx = self.new_driver.findText(driver)
                if idx >= 0:
                    self.new_driver.setCurrentIndex(idx)
                else:
                    self.new_driver.setEditText(driver)
            
            QMessageBox.information(self, "Linked", f"Charter {reserve_num} linked to receipt.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to link charter:\n\n{e}")

    def _apply_vehicle_from_charter(self):
        """Auto-populate vehicle from charter when checkbox is checked."""
        if not self.vehicle_from_charter_chk.isChecked():
            return
        
        if not self.new_charter.text().strip():
            self.vehicle_from_charter_chk.setChecked(False)
            QMessageBox.warning(self, "No Charter", "Select a charter first.")
            return
        
        reserve_num = self.new_charter.text().strip()
        
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT vehicle FROM charters WHERE reserve_number = %s", (reserve_num,))
            result = cur.fetchone()
            cur.close()
            
            if result and result[0]:
                vehicle = result[0]
                idx = self.new_vehicle.findText(vehicle)
                if idx >= 0:
                    self.new_vehicle.setCurrentIndex(idx)
                else:
                    self.new_vehicle.setEditText(vehicle)
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            self.vehicle_from_charter_chk.setChecked(False)
            QMessageBox.warning(self, "Error", f"Could not populate vehicle:\n\n{e}")

    def _apply_driver_from_charter(self):
        """Auto-populate driver from charter when checkbox is checked."""
        if not self.driver_from_charter_chk.isChecked():
            return
        
        if not self.new_charter.text().strip():
            self.driver_from_charter_chk.setChecked(False)
            QMessageBox.warning(self, "No Charter", "Select a charter first.")
            return
        
        reserve_num = self.new_charter.text().strip()
        
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COALESCE(driver_name, driver) FROM charters WHERE reserve_number = %s", (reserve_num,))
            result = cur.fetchone()
            cur.close()
            
            if result and result[0]:
                driver = result[0]
                idx = self.new_driver.findText(driver)
                if idx >= 0:
                    self.new_driver.setCurrentIndex(idx)
                else:
                    self.new_driver.setEditText(driver)
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            self.driver_from_charter_chk.setChecked(False)
            QMessageBox.warning(self, "Error", f"Could not populate driver:\n\n{e}")

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------
    def _load_recent(self):
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                  SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,
                      COALESCE(r.gl_account_name, r.gl_account_code::text, '') AS gl_name,
                      r.banking_transaction_id, COALESCE(r.reserve_number, '') AS reserve_num,
                      COALESCE(r.description, '') AS description, COALESCE(r.payment_method, '') AS payment_method,
                      COALESCE(r.created_from_banking, false) AS created_from_banking,
                      CASE WHEN r.banking_transaction_id IS NOT NULL THEN 'Yes' ELSE 'No' END AS matched_status,
                      COALESCE(e.first_name || ' ' || e.last_name, '') AS driver_name
                  FROM receipts r
                  LEFT JOIN employees e ON r.employee_id = e.employee_id
                  ORDER BY r.receipt_date DESC, r.receipt_id DESC
                  LIMIT 50
                """
            )
            rows = cur.fetchall()
            cur.close()
            self.last_results = rows
            self._populate_table(rows)
            self.results_label.setText(f"Recent 50 receipts loaded ({len(rows)})")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Load Error", f"Could not load recent receipts:\n\n{e}")

    def _build_banking_match_panel(self) -> QWidget:
        """Tab for matching banking transactions to receipts."""
        panel = QWidget()
        vbox = QVBoxLayout(panel)

        info = QLabel(
            "🏦 <b>Banking Match</b><br>"
            "Search banking transactions by date range, amount, or status.<br>"
            "Double-click a banking txn to auto-link to selected receipt (if both selected)."
        )
        info.setWordWrap(True)
        vbox.addWidget(info)

        # Banking search filters
        search_group = QGroupBox("Banking Transaction Search")
        search_form = QFormLayout(search_group)

        self.bank_date_from = StandardDateEdit(allow_blank=True)
        self.bank_date_to = StandardDateEdit(allow_blank=True)
        bank_date_row = QHBoxLayout()
        bank_date_row.addWidget(self.bank_date_from)
        bank_date_row.addWidget(QLabel("to"))
        bank_date_row.addWidget(self.bank_date_to)
        bank_date_row.addStretch()
        search_form.addRow("Date Range", bank_date_row)

        self.bank_amount_filter = CurrencyInput()
        search_form.addRow("Amount (approx)", self.bank_amount_filter)

        # Show All checkbox - toggle between unmatched only vs all
        self.bank_show_all_chk = QCheckBox("Show All (including matched)")
        self.bank_show_all_chk.setChecked(False)
        search_form.addRow("Filter", self.bank_show_all_chk)

        bank_btn_row = QHBoxLayout()
        self.bank_search_btn = QPushButton("🔍 Search Banking")
        self.bank_search_btn.clicked.connect(self._search_banking_transactions)
        bank_btn_row.addWidget(self.bank_search_btn)
        bank_btn_row.addStretch()
        search_form.addRow("", bank_btn_row)

        vbox.addWidget(search_group)

        # Banking transactions table
        self.banking_table = QTableWidget(0, 6)
        self.banking_table.setHorizontalHeaderLabels(
            ["Transaction ID", "Date", "Description", "Amount", "Account", "Status"]
        )
        header = self.banking_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        vbox.addWidget(self.banking_table)

        # Hook up double-click to quick link if a receipt is selected
        self.banking_table.doubleClicked.connect(self._on_banking_double_clicked)

        info2 = QLabel(
            "ℹ️ Matched transactions will appear with green background.<br>"
            "Select a receipt from the 📋 Receipts tab and a banking txn here, then click 'Link Selected'."
        )
        info2.setWordWrap(True)
        vbox.addWidget(info2)

        link_btn_row = QHBoxLayout()
        self.link_selected_btn = QPushButton("🔗 Link Selected Receipt + Banking")
        self.link_selected_btn.clicked.connect(self._link_selected_to_banking)
        link_btn_row.addWidget(self.link_selected_btn)
        
        self.unlink_banking_btn = QPushButton("🔗 Unlink Banking")
        self.unlink_banking_btn.clicked.connect(self._unlink_banking_match)
        link_btn_row.addWidget(self.unlink_banking_btn)
        
        link_btn_row.addStretch()
        vbox.addLayout(link_btn_row)

        return panel

    def _build_charter_lookup_panel(self) -> QWidget:
        """Panel for searching and selecting charters."""
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(5, 5, 5, 5)
        vbox.setSpacing(5)

        info = QLabel(
            "Search for charters by reserve number, date, customer, or driver.<br>"
            "Select a charter to link to the current receipt."
        )
        info.setWordWrap(True)
        vbox.addWidget(info)

        # Charter search filters
        search_group = QGroupBox("Charter Search")
        search_form = QFormLayout(search_group)

        self.charter_reserve_number = QLineEdit()
        self.charter_reserve_number.setPlaceholderText("e.g., 019233")
        search_form.addRow("Reserve #", self.charter_reserve_number)

        self.charter_customer_name = QLineEdit()
        self.charter_customer_name.setPlaceholderText("Customer name or partial")
        search_form.addRow("Customer", self.charter_customer_name)

        self.charter_driver_name = QLineEdit()
        self.charter_driver_name.setPlaceholderText("Driver name or partial")
        search_form.addRow("Driver", self.charter_driver_name)

        # Center date ± days range for charter search
        charter_date_row = QHBoxLayout()
        self.charter_center_date = StandardDateEdit(allow_blank=True)
        charter_date_row.addWidget(self.charter_center_date)
        charter_date_row.addWidget(QLabel("±"))
        self.charter_days_range = QDoubleSpinBox()
        self.charter_days_range.setRange(0, 365)
        self.charter_days_range.setDecimals(0)
        self.charter_days_range.setValue(7)
        self.charter_days_range.setSuffix(" days")
        self.charter_days_range.setMaximumWidth(120)
        charter_date_row.addWidget(self.charter_days_range)
        # Copy selected receipt's date into charter search center
        self.copy_receipt_date_btn = QPushButton("📅 Copy Receipt Date")
        self.copy_receipt_date_btn.setMaximumWidth(160)
        self.copy_receipt_date_btn.clicked.connect(self._copy_receipt_date_to_charter)
        charter_date_row.addWidget(self.copy_receipt_date_btn)
        charter_date_row.addStretch()
        search_form.addRow("Date ± Days", charter_date_row)

        charter_btn_row = QHBoxLayout()
        self.charter_search_btn = QPushButton("🔍 Search Charters")
        self.charter_search_btn.clicked.connect(self._search_charters)
        charter_btn_row.addWidget(self.charter_search_btn)
        charter_btn_row.addStretch()
        search_form.addRow("", charter_btn_row)

        vbox.addWidget(search_group)

        # Charter results table
        self.charter_table = QTableWidget(0, 7)
        self.charter_table.setHorizontalHeaderLabels(
            ["Reserve #", "Date", "Customer", "Driver", "Vehicle", "Amount", "Status"]
        )
        self.charter_table.doubleClicked.connect(self._on_charter_double_clicked)
        header = self.charter_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        vbox.addWidget(self.charter_table)

        # Link selected charter to receipt button
        link_btn_row = QHBoxLayout()
        self.link_charter_to_receipt_btn = QPushButton("Link Selected Charter to Receipt")
        self.link_charter_to_receipt_btn.setMaximumWidth(250)
        self.link_charter_to_receipt_btn.clicked.connect(self._link_selected_charter_to_receipt)
        link_btn_row.addWidget(self.link_charter_to_receipt_btn)
        link_btn_row.addStretch()
        vbox.addLayout(link_btn_row)

        info2 = QLabel(
            "ℹ️ Select a receipt from the 📋 Receipt Details above and a charter here, "
            "then click 'Link Charter' to associate them."
        )
        info2.setWordWrap(True)
        vbox.addWidget(info2)

        link_charter_row = QHBoxLayout()
        self.link_charter_btn = QPushButton("🔗 Link Charter to Receipt")
        self.link_charter_btn.clicked.connect(self._link_charter_to_receipt)
        link_charter_row.addWidget(self.link_charter_btn)
        link_charter_row.addStretch()
        vbox.addLayout(link_charter_row)

        vbox.addStretch()

        return panel

    def _search_banking_transactions(self):
        """Search for banking transactions (matched or unmatched based on checkbox)."""
        sql = [
            "SELECT DISTINCT ON (bt.transaction_id) bt.transaction_id, bt.transaction_date, bt.description,",
            "CASE WHEN bt.debit_amount IS NOT NULL AND bt.debit_amount > 0 THEN bt.debit_amount",
            "     WHEN bt.credit_amount IS NOT NULL AND bt.credit_amount > 0 THEN bt.credit_amount",
            "     ELSE 0 END AS amount,",
            "COALESCE(bt.vendor_extracted, 'N/A') AS account_nickname,",
            "CASE WHEN EXISTS(SELECT 1 FROM receipts WHERE banking_transaction_id = bt.transaction_id) THEN 'Matched' ELSE 'UNMATCHED' END AS status",
            "FROM banking_transactions bt",
            "WHERE 1=1"
        ]
        params: List[object] = []

        # If "Show All" is unchecked, only show unmatched
        if not self.bank_show_all_chk.isChecked():
            sql.append("AND NOT EXISTS(SELECT 1 FROM receipts WHERE banking_transaction_id = bt.transaction_id)")

        # Amount filter
        amount_val = (self.bank_amount_filter.text() or "").replace(",", "").strip()
        if amount_val:
            try:
                amt = float(amount_val)
                sql.append("AND (bt.debit_amount = %s OR bt.credit_amount = %s)")
                params.extend([amt, amt])
            except ValueError:
                QMessageBox.warning(self, "Invalid Amount", "Amount must be numeric.")
                return

        start = self.bank_date_from.getDate()
        end = self.bank_date_to.getDate()
        # Normalize to Python date if QDate
        if start:
            try:
                start = start.toPyDate()
            except AttributeError:
                pass
        if end:
            try:
                end = end.toPyDate()
            except AttributeError:
                pass
        if start or end:
            if start and end:
                sql.append("AND bt.transaction_date BETWEEN %s AND %s")
                params.extend([start, end])
            elif start:
                sql.append("AND bt.transaction_date >= %s")
                params.append(start)
            elif end:
                sql.append("AND bt.transaction_date <= %s")
                params.append(end)

        sql.append("ORDER BY bt.transaction_id, bt.transaction_date DESC LIMIT 100")

        try:
            cur = self.conn.cursor()
            cur.execute("\n".join(sql), params)
            rows = cur.fetchall()
            cur.close()

            self.banking_table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                tid, tdate, desc, amount, account, status = row
                self.banking_table.setItem(r, 0, QTableWidgetItem(str(tid)))
                self.banking_table.setItem(r, 1, QTableWidgetItem(str(tdate)))
                self.banking_table.setItem(r, 2, QTableWidgetItem(desc or ""))
                
                amt_item = QTableWidgetItem(f"${amount:,.2f}" if amount else "")
                amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.banking_table.setItem(r, 3, amt_item)
                
                self.banking_table.setItem(r, 4, QTableWidgetItem(account or ""))
                self.banking_table.setItem(r, 5, QTableWidgetItem(status or ""))

                # Color code by status
                if status == "UNMATCHED":
                    bg_color = QColor(255, 255, 200)  # Light yellow for unmatched
                else:
                    bg_color = QColor(200, 255, 200)  # Light green for matched
                for col in range(6):
                    item = self.banking_table.item(r, col)
                    if item:
                        item.setBackground(bg_color)

            show_type = "All banking transactions" if self.bank_show_all_chk.isChecked() else "Unmatched banking transactions"
            self.results_label.setText(f"Found {len(rows)} {show_type}")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Search Error", f"Failed to search banking txns:\n\n{e}")

    def _get_selected_receipt_id(self) -> int | None:
        try:
            selected = self.results_table.selectedItems()
            if not selected:
                return None
            row = selected[0].row()
            rid_item = self.results_table.item(row, 0)
            if rid_item and rid_item.text().isdigit():
                return int(rid_item.text())
        except Exception:
            pass
        return None

    def _get_selected_banking_transaction_id(self) -> int | None:
        try:
            selected = self.banking_table.selectedItems()
            if not selected:
                return None
            row = selected[0].row()
            tid_item = self.banking_table.item(row, 0)
            if tid_item and tid_item.text().isdigit():
                return int(tid_item.text())
        except Exception:
            pass
        return None

    def _refresh_receipt_row(self, receipt_id: int, banking_id: int):
        """Update the receipts table UI to reflect new banking link."""
        try:
            for r in range(self.results_table.rowCount()):
                rid_item = self.results_table.item(r, 0)
                if rid_item and rid_item.text().isdigit() and int(rid_item.text()) == receipt_id:
                    # Update banking id and matched status
                    self.results_table.setItem(r, 6, QTableWidgetItem(str(banking_id)))
                    self.results_table.setItem(r, 7, QTableWidgetItem("Yes"))
                    # Green background
                    bg_color = QColor(200, 255, 200)
                    for col in range(10):
                        item = self.results_table.item(r, col)
                        if item:
                            item.setBackground(bg_color)
                    break
        except Exception:
            pass

    def _link_selected_to_banking(self):
        """Link currently selected receipt to currently selected banking transaction."""
        if not self.write_enabled:
            QMessageBox.information(
                self,
                "Link disabled",
                "Set RECEIPT_WIDGET_WRITE_ENABLED=1 to allow linking.",
            )
            return

        receipt_id = self._get_selected_receipt_id()
        if not receipt_id:
            QMessageBox.warning(self, "No Receipt Selected", "Select a receipt in the Receipts table first.")
            return

        transaction_id = self._get_selected_banking_transaction_id()
        if not transaction_id:
            QMessageBox.warning(self, "No Banking Transaction Selected", "Select a banking transaction to link.")
            return

        try:
            cur = self.conn.cursor()
            # Check if banking txn is already linked to a different receipt
            cur.execute(
                """
                SELECT receipt_id FROM receipts WHERE banking_transaction_id = %s AND receipt_id <> %s
                """,
                (transaction_id, receipt_id),
            )
            existing = cur.fetchone()
            if existing and existing[0]:
                # Ask for confirmation to reassign link
                resp = QMessageBox.question(
                    self,
                    "Reassign Link",
                    f"Banking txn #{transaction_id} is already linked to receipt #{existing[0]}.\n\n"
                    f"Do you want to reassign it to receipt #{receipt_id}?",
                )
                if resp != QMessageBox.StandardButton.Yes:
                    cur.close()
                    return

            # Perform link
            cur.execute(
                "UPDATE receipts SET banking_transaction_id = %s WHERE receipt_id = %s",
                (transaction_id, receipt_id),
            )
            self.conn.commit()
            cur.close()

            # Update form field and UI
            self.new_banking_id.setText(str(transaction_id))
            self._refresh_receipt_row(receipt_id, transaction_id)
            QMessageBox.information(self, "Linked", f"Linked receipt #{receipt_id} to banking txn #{transaction_id}.")
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Link Error", f"Failed to link: {e}")

    def _on_banking_double_clicked(self, _index):
        """Quick-link banking txn to the selected receipt on double-click."""
        # Attempt link using current selections
        self._link_selected_to_banking()
    
    def _auto_load_banking_transaction(self, transaction_id: int):
        """Auto-load a specific banking transaction in the banking table."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT bt.transaction_id, bt.transaction_date, bt.description,
                CASE WHEN bt.debit_amount IS NOT NULL AND bt.debit_amount > 0 THEN bt.debit_amount
                     WHEN bt.credit_amount IS NOT NULL AND bt.credit_amount > 0 THEN bt.credit_amount
                     ELSE 0 END AS amount,
                COALESCE(bt.vendor_extracted, 'N/A') AS account_nickname,
                'Matched' AS status
                FROM banking_transactions bt
                WHERE bt.transaction_id = %s
            """, (transaction_id,))
            row = cur.fetchone()
            cur.close()
            
            if row:
                # Populate the banking table with this one transaction
                self.banking_table.setRowCount(1)
                tid, tdate, desc, amount, account, status = row
                self.banking_table.setItem(0, 0, QTableWidgetItem(str(tid)))
                self.banking_table.setItem(0, 1, QTableWidgetItem(str(tdate)))
                self.banking_table.setItem(0, 2, QTableWidgetItem(desc or ""))
                
                amt_item = QTableWidgetItem(f"${amount:,.2f}" if amount else "")
                amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.banking_table.setItem(0, 3, amt_item)
                
                self.banking_table.setItem(0, 4, QTableWidgetItem(account or ""))
                self.banking_table.setItem(0, 5, QTableWidgetItem(status or ""))
                
                # Green background for matched
                bg_color = QColor(200, 255, 200)
                for col in range(6):
                    item = self.banking_table.item(0, col)
                    if item:
                        item.setBackground(bg_color)
                
                # Select this row
                self.banking_table.selectRow(0)
        except Exception as e:
            print(f"[DEBUG] Could not auto-load banking transaction: {e}")

    def _search_charters(self):
        """Search for charters based on filter criteria."""
        try:
            reserve_num = self.charter_reserve_number.text().strip()
            customer = self.charter_customer_name.text().strip()
            driver = self.charter_driver_name.text().strip()
            # Compute date range from center ± days
            center_qdate = self.charter_center_date.date()
            days = int(self.charter_days_range.value()) if hasattr(self, "charter_days_range") else 0
            date_from = None
            date_to = None
            if center_qdate and center_qdate.isValid():
                from PyQt6.QtCore import QDate
                date_from = center_qdate.addDays(-days).toPyDate()
                date_to = center_qdate.addDays(days).toPyDate()

            where_clauses = []
            params = []

            if reserve_num:
                where_clauses.append("CAST(c.reserve_number AS TEXT) ILIKE %s")
                params.append(f"%{reserve_num}%")

            if customer:
                where_clauses.append("COALESCE(c.client_display_name, '') ILIKE %s")
                params.append(f"%{customer}%")

            if driver:
                where_clauses.append("(COALESCE(c.driver_name, '') ILIKE %s OR COALESCE(c.driver, '') ILIKE %s)")
                params.append(f"%{driver}%")
                params.append(f"%{driver}%")

            if date_from:
                where_clauses.append("c.charter_date >= %s")
                params.append(date_from)

            if date_to:
                where_clauses.append("c.charter_date <= %s")
                params.append(date_to)

            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

            sql = f"""
                SELECT c.reserve_number, c.charter_date, c.client_display_name, 
                       COALESCE(c.driver_name, c.driver) AS driver,
                       c.vehicle,
                       COALESCE(c.total_amount_due, 0) AS total_amount_due,
                       CASE WHEN c.cancelled THEN 'CANCELLED' ELSE 'Active' END AS status
                FROM charters c
                WHERE {where_clause}
                ORDER BY c.charter_date DESC
                LIMIT 100
            """

            cur = self.conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.close()

            self.charter_table.setRowCount(0)
            for row in rows:
                self.charter_table.insertRow(self.charter_table.rowCount())
                for col, value in enumerate(row):
                    if col == 5:  # Amount
                        item = QTableWidgetItem(f"${value:.2f}" if value else "$0.00")
                    else:
                        item = QTableWidgetItem(str(value) if value is not None else "")

                    if col == 6 and "CANCELLED" in str(value):  # Status
                        item.setBackground(QColor(255, 200, 200))

                    self.charter_table.setItem(self.charter_table.rowCount() - 1, col, item)

        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Charter Search Error", f"Error searching charters: {e}")

    def _copy_receipt_date_to_charter(self):
        """Copy currently selected receipt date into charter center date and auto-fill reserve if present."""
        try:
            selected = self.results_table.selectedItems()
            if not selected:
                return
            row = selected[0].row()
            date_item = self.results_table.item(row, 1)
            charter_item = self.results_table.item(row, 5)
            if date_item and date_item.text():
                qd = QDate.fromString(date_item.text(), "yyyy-MM-dd")
                if qd and qd.isValid():
                    self.charter_center_date.setDate(qd)
            # If already linked, pre-fill reserve number for convenience
            if charter_item and charter_item.text():
                self.charter_reserve_number.setText(charter_item.text())
        except Exception:
            pass

    def _on_charter_double_clicked(self, index):
        """Show charter booking details in a popup when double-clicked."""
        try:
            row = index.row()
            reserve_number = self.charter_table.item(row, 0).text()
            
            # Fetch full charter details
            cur = self.conn.cursor()
            cur.execute("""
                SELECT 
                    c.reserve_number,
                    c.charter_date,
                    c.client_display_name,
                    COALESCE(c.driver_name, c.driver) AS driver,
                    c.vehicle,
                    c.pickup_time,
                    c.pickup_address,
                    c.dropoff_address,
                    c.passenger_count,
                    c.rate,
                    c.total_amount_due,
                    c.paid_amount,
                    c.balance,
                    c.notes,
                    c.booking_notes,
                    c.special_requirements,
                    c.beverage_service_required,
                    CASE WHEN c.cancelled THEN 'CANCELLED' 
                         WHEN c.closed THEN 'CLOSED'
                         ELSE 'Active' END as status,
                    c.created_at,
                    c.updated_at
                FROM charters c
                WHERE c.reserve_number = %s
            """, (reserve_number,))
            
            charter_data = cur.fetchone()
            cur.close()
            
            if not charter_data:
                QMessageBox.warning(self, "Not Found", f"Charter {reserve_number} not found.")
                return
            
            # Show details dialog
            dlg = CharterDetailsDialog(charter_data, self)
            dlg.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading charter details: {e}")

    def _link_selected_charter_to_receipt(self):
        """Link the selected charter from the table to the receipt form."""
        selected = self.charter_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a charter from the table.")
            return
        
        row = selected[0].row()
        reserve_number = self.charter_table.item(row, 0).text()
        
        # Fill in the charter reserve field
        self.new_charter.setText(reserve_number)
        
        # Populate vehicle and driver if their checkboxes are checked
        vehicle = self.charter_table.item(row, 4).text()
        driver = self.charter_table.item(row, 3).text()
        
        if self.vehicle_from_charter_chk.isChecked() and vehicle:
            idx = self.new_vehicle.findText(vehicle)
            if idx >= 0:
                self.new_vehicle.setCurrentIndex(idx)
            else:
                self.new_vehicle.setEditText(vehicle)
        
        if self.driver_from_charter_chk.isChecked() and driver:
            idx = self.new_driver.findText(driver)
            if idx >= 0:
                self.new_driver.setCurrentIndex(idx)
            else:
                self.new_driver.setEditText(driver)
        
        QMessageBox.information(self, "Linked", f"Charter {reserve_number} linked to receipt!")

    def _link_charter_to_receipt(self):
        """Link selected charter to currently selected receipt."""
        QMessageBox.information(
            self,
            "Link Charter (Coming Soon)",
            "Linking charters to receipts is coming in a future build."
        )

    def _load_gl_accounts(self):
        """Load GL accounts from chart_of_accounts into dropdown with autocomplete."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT account_code, account_name FROM chart_of_accounts ORDER BY account_code")
            gl_items = []
            for code, name in cur.fetchall():
                if code:
                    label = f"{code} — {name}"
                    self.new_gl.addItem(label, code)
                    gl_items.append(label)
            # Add autocomplete with case-insensitive, contains-matching
            completer = QCompleter(gl_items)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.new_gl.setCompleter(completer)
            cur.close()
        except Exception:
            pass

    def _load_vehicles_into_combo(self):
        """Load vehicles into dropdown with active first, numeric L-series ordering, and store vehicle_type."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT vehicle_id, vehicle_number, status, vehicle_type
                FROM vehicles
                ORDER BY
                    CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                    CASE
                        WHEN vehicle_number ~ '^[Ll]-?\d+$' THEN CAST(regexp_replace(vehicle_number, '[^0-9]', '', 'g') AS INT)
                        ELSE 9999
                    END,
                    vehicle_number
            """)
            rows = cur.fetchall()
            cur.close()
            
            labels = []
            self._vehicle_types = {}
            for vid, vehicle_number, status, vehicle_type in rows:
                label = str(vehicle_number or f"Vehicle {vid}")
                self.new_vehicle.addItem(label, vid)
                labels.append(label)
                self._vehicle_types[vid] = vehicle_type or ""
            
            # Add fuzzy/contains autocomplete
            if labels:
                completer = QCompleter(labels)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                self.new_vehicle.setCompleter(completer)
            try:
                self.new_vehicle.currentIndexChanged.connect(self._update_new_vehicle_type_display)
            except Exception:
                pass
            self._update_new_vehicle_type_display()
            
            if not labels:
                QMessageBox.information(self, "Vehicles", "No vehicles found in database.")
        except Exception as e:
            QMessageBox.warning(self, "Vehicles", f"Could not load vehicles: {e}")

    def _update_new_vehicle_type_display(self):
        try:
            vid = self.new_vehicle.currentData()
            vtype = ""
            if hasattr(self, "_vehicle_types") and vid in self._vehicle_types:
                vtype = self._vehicle_types.get(vid) or ""
            self.new_vehicle_type_label.setText(str(vtype))
        except Exception:
            try:
                self.new_vehicle_type_label.setText("")
            except Exception:
                pass


    def _load_drivers_into_combo(self):
        """Load drivers into dropdown with autocomplete."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT employee_id, first_name || ' ' || last_name FROM employees ORDER BY first_name, last_name")
            driver_names = []
            for emp_id, name in cur.fetchall():
                self.new_driver.addItem(name, emp_id)
                driver_names.append(name)
            # Add autocomplete
            if driver_names:
                completer = QCompleter(driver_names)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                self.new_driver.setCompleter(completer)
            cur.close()
            if not driver_names:
                QMessageBox.information(self, "Drivers", "No drivers found in database.")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Drivers", f"Could not load drivers: {e}")

    def _attach_charter_completer(self):
        """Add fuzzy/contains charter number lookup completer."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT CAST(reserve_number AS TEXT) FROM charters WHERE reserve_number IS NOT NULL ORDER BY reserve_number LIMIT 5000")
            charters = [row[0] for row in cur.fetchall()]
            cur.close()
            completer = QCompleter(charters)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.new_charter.setCompleter(completer)
        except Exception:
            pass

    def _toggle_fuel_visibility(self):
        """Show fuel field only if GL contains 'fuel' or 'gas'."""
        try:
            gl_text = (self.new_gl.currentText() or "").lower()
            is_fuel = "fuel" in gl_text or "gas" in gl_text
            self.fuel_liters.setVisible(is_fuel)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Calculator dialog (simple keypad-style)
    # ------------------------------------------------------------------
    def _auto_calculate_gst(self):
        """Auto-calculate GST/PST based on jurisdiction and gross amount."""
        amount_text = (self.new_amount.text() or "").strip()
        if not amount_text:
            return
        
        try:
            gross_amount = float(amount_text)
            if gross_amount <= 0:
                self.new_gst.clear()
                self.new_pst.clear()
                return
            
            # Get selected jurisdiction
            jurisdiction = self.tax_jurisdiction.currentText()
            
            # Tax rates by jurisdiction (% rates, tax-included formula)
            tax_configs = {
                "AB (GST 5%)": {"gst": 0.05, "pst": 0.00},
                "BC (GST 5% + PST 7%)": {"gst": 0.05, "pst": 0.07},
                "SK (GST 5%)": {"gst": 0.05, "pst": 0.00},
                "MB (GST 5%)": {"gst": 0.05, "pst": 0.00},
                "ON (HST 13%)": {"gst": 0.13, "pst": 0.00},  # HST combined
                "QC (GST 5% + PST 9.975%)": {"gst": 0.05, "pst": 0.09975},
                "NB (HST 15%)": {"gst": 0.15, "pst": 0.00},  # HST combined
                "NS (HST 15%)": {"gst": 0.15, "pst": 0.00},  # HST combined
                "PE (HST 15%)": {"gst": 0.15, "pst": 0.00},  # HST combined
                "NL (HST 15%)": {"gst": 0.15, "pst": 0.00},  # HST combined
                "VT (GST 5%)": {"gst": 0.05, "pst": 0.00},
                "NT (GST 5%)": {"gst": 0.05, "pst": 0.00},
                "NU (GST 5%)": {"gst": 0.05, "pst": 0.00},
            }
            
            config = tax_configs.get(jurisdiction, {"gst": 0.05, "pst": 0.00})
            gst_rate = config["gst"]
            pst_rate = config["pst"]
            
            # Calculate taxes using tax-included formula
            # For multiple taxes: split the amount proportionally
            total_tax_rate = gst_rate + pst_rate
            
            if total_tax_rate > 0:
                gst_amount = gross_amount * gst_rate / (1 + total_tax_rate)
                pst_amount = gross_amount * pst_rate / (1 + total_tax_rate)
            else:
                gst_amount = 0.00
                pst_amount = 0.00
            
            self.new_gst.setText(f"{gst_amount:.2f}")
            if pst_rate > 0:
                self.new_pst.setText(f"{pst_amount:.2f}")
            else:
                self.new_pst.clear()
            
            print(f"[AUTO-CALC] {jurisdiction} | Amount: ${gross_amount:.2f}, GST: ${gst_amount:.2f}, PST: ${pst_amount:.2f}")
        except (ValueError, AttributeError):
            # If amount is invalid, clear taxes
            self.new_gst.clear()
            self.new_pst.clear()

    # ------------------------------------------------------------------
    def _open_calculator(self):
        dlg = _CalculatorDialog(self)
        dlg.set_expression(self.new_amount.text())
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result is not None:
            self.new_amount.setText(f"{dlg.result:.2f}")


class _CalculatorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        self.setModal(True)
        self.result = None

        vbox = QVBoxLayout(self)
        self.display = QLineEdit()
        self.display.setReadOnly(True)
        vbox.addWidget(self.display)

        # Simple keypad layout
        rows = [
            ["7", "8", "9", "/"],
            ["4", "5", "6", "*"],
            ["1", "2", "3", "-"],
            ["0", ".", "=", "+"],
        ]

        for row in rows:
            h = QHBoxLayout()
            for label in row:
                btn = QPushButton(label)
                btn.setFixedWidth(40)
                btn.clicked.connect(lambda _, text=label: self._on_button(text))
                h.addWidget(btn)
            vbox.addLayout(h)

        action_row = QHBoxLayout()
        clear_btn = QPushButton("C")
        clear_btn.clicked.connect(self._on_clear)
        action_row.addWidget(clear_btn)
        back_btn = QPushButton("←")
        back_btn.clicked.connect(self._on_backspace)
        action_row.addWidget(back_btn)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_apply)
        action_row.addWidget(apply_btn)
        cancel_btn = QPushButton("Close")
        cancel_btn.clicked.connect(self.reject)
        action_row.addWidget(cancel_btn)
        vbox.addLayout(action_row)

    def set_expression(self, expr: str):
        self.display.setText(expr or "")

    def _on_button(self, text: str):
        if text == "=":
            self._evaluate()
        else:
            self.display.setText(self.display.text() + text)

    def _on_clear(self):
        self.display.clear()

    def _on_backspace(self):
        self.display.setText(self.display.text()[:-1])

    def _on_apply(self):
        if self._evaluate():
            self.accept()

    def _evaluate(self) -> bool:
        expr = self.display.text().strip()
        if not expr:
            return False
        # Safe eval: allow digits, parentheses, + - * / and dot
        for ch in expr:
            if ch not in "0123456789.+-*/() ":
                QMessageBox.warning(self, "Invalid", "Only digits and + - * / ( ) are allowed.")
                return False
        try:
            value = eval(expr, {"__builtins__": {}}, {})
            self.result = float(value)
            self.display.setText(str(self.result))
            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not evaluate: {e}")
            return False
        except Exception:
            pass


class CharterDetailsDialog(QDialog):
    """Popup dialog showing full charter booking details."""
    
    def __init__(self, charter_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Charter Booking Details - Reserve #{charter_data[0]}")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        layout = QVBoxLayout(self)
        
        # Create scroll area for details
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        form = QFormLayout(scroll_widget)
        
        # Unpack charter data
        (reserve_num, charter_date, client, driver, vehicle, pickup_time,
         pickup_addr, dropoff_addr, pax_count, rate, total_due, paid_amt,
         balance, notes, booking_notes, special_req, beverage_service, status, created_at, 
         updated_at) = charter_data
        
        # Add fields
        form.addRow("Reserve Number:", QLabel(f"<b>{reserve_num}</b>"))
        form.addRow("Status:", QLabel(f"<b>{status}</b>"))
        form.addRow("Charter Date:", QLabel(str(charter_date) if charter_date else ""))
        form.addRow("Pickup Time:", QLabel(str(pickup_time) if pickup_time else ""))
        
        # Beverage Service
        if beverage_service:
            beverage_label = QLabel("✓ YES")
            beverage_label.setStyleSheet("color: green; font-weight: bold;")
            form.addRow("Beverage Service:", beverage_label)
        
        # Client & Driver
        form.addRow("", QLabel(""))  # Spacer
        form.addRow("Client:", QLabel(f"<b>{client}</b>" if client else ""))
        form.addRow("Driver:", QLabel(f"<b>{driver}</b>" if driver else ""))
        form.addRow("Vehicle:", QLabel(f"<b>{vehicle}</b>" if vehicle else ""))
        
        # Locations
        form.addRow("", QLabel(""))  # Spacer
        pickup_label = QLabel(pickup_addr or "")
        pickup_label.setWordWrap(True)
        form.addRow("Pickup Address:", pickup_label)
        
        dropoff_label = QLabel(dropoff_addr or "")
        dropoff_label.setWordWrap(True)
        form.addRow("Dropoff Address:", dropoff_label)
        
        form.addRow("Passenger Count:", QLabel(str(pax_count) if pax_count else ""))
        
        # Financial
        form.addRow("", QLabel(""))  # Spacer
        form.addRow("Rate:", QLabel(f"${rate:.2f}" if rate else "$0.00"))
        form.addRow("Total Amount Due:", QLabel(f"<b>${total_due:.2f}</b>" if total_due else "<b>$0.00</b>"))
        form.addRow("Paid Amount:", QLabel(f"${paid_amt:.2f}" if paid_amt else "$0.00"))
        form.addRow("Balance:", QLabel(f"<b>${balance:.2f}</b>" if balance else "<b>$0.00</b>"))
        
        # Notes
        if notes:
            form.addRow("", QLabel(""))  # Spacer
            notes_label = QLabel(notes)
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet("background-color: #ffffcc; padding: 5px;")
            form.addRow("Notes:", notes_label)
        
        if booking_notes:
            booking_label = QLabel(booking_notes)
            booking_label.setWordWrap(True)
            booking_label.setStyleSheet("background-color: #e6f3ff; padding: 5px;")
            form.addRow("Booking Notes:", booking_label)
        
        if special_req:
            special_label = QLabel(special_req)
            special_label.setWordWrap(True)
            special_label.setStyleSheet("background-color: #ffe6e6; padding: 5px;")
            form.addRow("Special Requirements:", special_label)
        
        # Timestamps
        form.addRow("", QLabel(""))  # Spacer
        form.addRow("Created:", QLabel(str(created_at) if created_at else ""))
        form.addRow("Updated:", QLabel(str(updated_at) if updated_at else ""))
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Close button
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)


__all__ = ["ReceiptSearchMatchWidget"]