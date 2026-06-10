"""
Vehicle Management Widget
Comprehensive vehicle CRUD with maintenance tracking, insurance,
and documentation
Ported from frontend/src/components/VehicleForm.vue
"""

import csv
import logging
import os
import re
import shutil
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QDate, Qt

_APP_ROOT = (
    Path(sys.executable).parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent.parent
)

from common_widgets import StandardDateEdit
from db_error_handling import DatabaseContext
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class VehicleManagementWidget(QWidget):
    def __init__(self, db) -> None:
        super().__init__()
        self.db = db
        self.current_vehicle_id = None
        self.lease_docs_root = _APP_ROOT / "data" / "vehicle_lease_docs"
        # Detect optional schema features once so the widget can adapt safely
        self.has_vehicle_code = self._column_exists("vehicles", "vehicle_code")
        self._ensure_lease_schema()
        self.init_ui()
        self.load_vehicles()

    def _ensure_lease_schema(self) -> None:
        """Create lease profile/document tables if they do not exist."""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vehicle_lease_profiles (
                        lease_id SERIAL PRIMARY KEY,
                        vehicle_id INTEGER NOT NULL UNIQUE REFERENCES
                        vehicles(vehicle_id) ON DELETE CASCADE,
                        lease_status TEXT NOT NULL DEFAULT 'active',
                        lease_type TEXT,
                        lessor_name TEXT,
                        contract_number TEXT,
                        lease_start_date DATE,
                        lease_end_date DATE,
                        payment_day SMALLINT,
                        down_payment NUMERIC(12,2),
                        monthly_payment NUMERIC(12,2),
                        buyout_amount NUMERIC(12,2),
                        contract_total NUMERIC(12,2),
                        security_deposit NUMERIC(12,2),
                        expected_total_cost NUMERIC(12,2),
                        missed_payments_count INTEGER NOT NULL DEFAULT 0,
                        nsf_payment_count INTEGER NOT NULL DEFAULT 0,
                        nsf_fee_total NUMERIC(12,2) NOT NULL DEFAULT 0,
                        late_fee_total NUMERIC(12,2) NOT NULL DEFAULT 0,
                        business_use_percent NUMERIC(5,2),
                        vehicle_type TEXT DEFAULT 'Livery Motor Vehicle',
                        gst_per_payment_amount NUMERIC(10,2),
                        total_gst_charged NUMERIC(12,2),
                        itc_amount NUMERIC(12,2),
                        itc_verified BOOLEAN NOT NULL DEFAULT FALSE,
                        itc_verified_date TIMESTAMP,
                        has_signed_lease BOOLEAN NOT NULL DEFAULT FALSE,
                        has_payment_schedule BOOLEAN NOT NULL DEFAULT FALSE,
                        has_insurance_proof BOOLEAN NOT NULL DEFAULT FALSE,
                        has_buyout_terms BOOLEAN NOT NULL DEFAULT FALSE,
                        has_vendor_statement BOOLEAN NOT NULL DEFAULT FALSE,
                        lessor_gst_number TEXT,
                        notes TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vehicle_lease_documents (
                        lease_doc_id SERIAL PRIMARY KEY,
                        vehicle_id INTEGER NOT NULL REFERENCES
                        vehicles(vehicle_id) ON DELETE CASCADE,
                        lease_id INTEGER REFERENCES
                        vehicle_lease_profiles(lease_id) ON DELETE SET NULL,
                        doc_type TEXT,
                        original_file_name TEXT,
                        file_path TEXT NOT NULL,
                        is_required BOOLEAN NOT NULL DEFAULT FALSE,
                        is_verified BOOLEAN NOT NULL DEFAULT FALSE,
                        verified_at TIMESTAMP,
                        notes TEXT,
                        uploaded_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """)
                # Add lessor_gst_number if upgrading an existing table
                cur.execute("""
                    ALTER TABLE vehicle_lease_profiles
                    ADD COLUMN IF NOT EXISTS lessor_gst_number TEXT
                    """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_vehicle_lease_documents_vehicle_id
                    ON vehicle_lease_documents(vehicle_id)
                    """)
        except Exception as e:
            logger.error(f"Failed to ensure lease schema: {e}")

    def _column_exists(
        self, table_name: str, column_name: str, schema: str = "public"
    ) -> bool:
        """Return True if the column exists; fallback False on any error."""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s AND
                    column_name = %s
                    LIMIT 1
                    """,
                    (schema, table_name, column_name),
                )
                return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check column existence: {e}")
            return False

    @staticmethod
    def _natural_sort_key(vehicle_number: str) -> object:
        """Convert 'L-3', 'L-10', 'L-20' to sortable key: ('L', 3), ('L',"
        "10), ('L', 20)."""

        match = re.match(r"([A-Z]+)[-]?(\d+)", str(vehicle_number).strip())
        if match:
            prefix, num = match.groups()
            return (prefix, int(num))
        return (str(vehicle_number), 0)

    def init_ui(self) -> None:
        """Initialize the UI with search and vehicle list (no stats cards)"""
        layout = QVBoxLayout()

        # Search and filter (simplified)
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Vehicle #, make, model, VIN, license plate..."
        )
        self.search_input.textChanged.connect(self.load_vehicles)
        search_layout.addWidget(self.search_input)

        # Status filter: default to "Active"
        search_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(
            ["Active", "Inactive", "Decommissioned", "All Status"]
        )
        self.status_filter.setCurrentText("Active")
        self.status_filter.currentTextChanged.connect(self.load_vehicles)
        search_layout.addWidget(self.status_filter)

        self.add_btn = QPushButton("➕ New Vehicle")
        self.add_btn.clicked.connect(self.new_vehicle)
        search_layout.addWidget(self.add_btn)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # Main content: Split between vehicle list and form
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Vehicle list with maintenance flags
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        self.vehicle_table = QTableWidget()
        self.vehicle_table.setColumnCount(10)
        self.vehicle_table.setHorizontalHeaderLabels(
            [
                "Vehicle #",
                "Make",
                "Model",
                "Year",
                "License",
                "Status",
                "Odometer",
                "CVIP Due",
                "Repairs",
                "Last Service",
            ]
        )
        self.vehicle_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.vehicle_table.itemSelectionChanged.connect(
            self.load_selected_vehicle
        )
        left_layout.addWidget(self.vehicle_table)
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # Right: Vehicle form with tabs
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        # Form tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(
            self._wrap_in_scroll_area(self._create_identification_tab()),
            "🆔 Identification",
        )
        self.tabs.addTab(
            self._wrap_in_scroll_area(self._create_status_tab()),
            "📊 Status & Specs",
        )
        self.tabs.addTab(
            self._wrap_in_scroll_area(self._create_maintenance_tab()),
            "🔧 Maintenance",
        )
        self.tabs.addTab(
            self._wrap_in_scroll_area(self._create_insurance_tab()),
            "🛡️ Insurance & Registration",
        )
        self.tabs.addTab(
            self._wrap_in_scroll_area(self._create_lease_tab()),
            "📑 Lease Compliance",
        )
        self.tabs.addTab(
            self._wrap_in_scroll_area(self._create_documents_tab()),
            "📄 Documents",
        )
        right_layout.addWidget(self.tabs)

        # Sync odometer fields between Status and Maintenance tabs
        self.odometer_input.valueChanged.connect(
            lambda value: self.service_odometer_input.setValue(value)
        )

        # Action buttons
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save Vehicle")
        self.save_btn.clicked.connect(self.save_vehicle)
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_vehicle)
        self.clear_btn = QPushButton("Clear Form")
        self.clear_btn.clicked.connect(self.new_vehicle)
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()
        right_layout.addLayout(button_layout)

        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        splitter.setSizes([400, 600])
        layout.addWidget(splitter)

        self.setLayout(layout)
        self.new_vehicle()

    def _wrap_in_scroll_area(self, content_widget: QWidget) -> QScrollArea:
        """Wrap tab content with a vertically scrollable container."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content_widget)
        return scroll

    def _create_stat_card(self, label, value, color) -> object:
        """Create a statistics card widget"""
        group = QGroupBox()
        group.setStyleSheet("""
            QGroupBox {{
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background-color: #f5f8ff;}}
        """)
        layout = QVBoxLayout()
        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {color};"
        )
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        layout.addWidget(text_label)
        group.setLayout(layout)
        return group

    def _create_identification_tab(self) -> object:
        """Create the Identification tab"""
        widget = QWidget()
        layout = QFormLayout()

        self.vehicle_number_input = QLineEdit()
        self.vin_input = QLineEdit()
        self.vehicle_code_input = QLineEdit()
        if not self.has_vehicle_code:
            self.vehicle_code_input.setDisabled(True)
            self.vehicle_code_input.setPlaceholderText(
                "vehicle_code column not present in DB"
            )
        self.fleet_number_input = QLineEdit()
        self.fleet_position_input = QSpinBox()
        self.fleet_position_input.setMaximum(999)
        self.license_plate_input = QLineEdit()
        self.make_input = QLineEdit()
        self.model_input = QLineEdit()
        self.year_input = QSpinBox()
        self.year_input.setRange(1900, 2100)
        self.year_input.setValue(datetime.now().year)
        self.type_input = QComboBox()
        self.type_input.addItems(
            [
                "Sedan",
                "SUV",
                "Shuttle Bus",
                "Party Bus",
                "Limo",
                "Bus",
                "small_suv",
                "large_suv",
                "small_bus",
                "large_bus",
                "unknown",
            ]
        )
        self.vehicle_category_input = QLineEdit()
        self.vehicle_class_input = QLineEdit()
        self.passenger_capacity_input = QSpinBox()
        self.passenger_capacity_input.setMaximum(99)
        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(60)

        layout.addRow("Vehicle Number*", self.vehicle_number_input)
        layout.addRow("VIN Number", self.vin_input)
        layout.addRow("Vehicle Code", self.vehicle_code_input)
        layout.addRow("Fleet Number", self.fleet_number_input)
        layout.addRow("Fleet Position", self.fleet_position_input)
        layout.addRow("License Plate*", self.license_plate_input)
        layout.addRow("Make*", self.make_input)
        layout.addRow("Model*", self.model_input)
        layout.addRow("Year*", self.year_input)
        layout.addRow("Type", self.type_input)
        layout.addRow("Category", self.vehicle_category_input)
        layout.addRow("Class", self.vehicle_class_input)
        layout.addRow("Passenger Capacity", self.passenger_capacity_input)
        layout.addRow("Description", self.description_input)

        widget.setLayout(layout)
        return widget

    def _create_status_tab(self) -> object:
        """Create the Status & Specs tab"""
        widget = QWidget()
        layout = QFormLayout()

        # Operational Status
        self.operational_status_input = QComboBox()
        self.operational_status_input.addItems(
            [
                "Active",
                "Inactive",
                "Maintenance",
                # Additional statuses present in data imports
                "active",
                "retired",
                "decommissioned",
                "total loss",
                "historical",
            ]
        )
        self.is_active_input = QCheckBox("Active")
        self.commission_date_input = StandardDateEdit(prefer_month_text=True)
        self.commission_date_input.setCalendarPopup(True)
        self.commission_date_input.setDate(QDate.currentDate())
        self.decommission_date_input = StandardDateEdit(prefer_month_text=True)
        self.decommission_date_input.setCalendarPopup(True)
        self.decommission_date_input.setSpecialValueText("N/A")

        # Physical Specs
        self.ext_color_input = QLineEdit()
        self.int_color_input = QLineEdit()
        self.length_input = QDoubleSpinBox()
        self.length_input.setSuffix(" m")
        self.length_input.setMaximum(50.0)
        self.width_input = QDoubleSpinBox()
        self.width_input.setSuffix(" m")
        self.width_input.setMaximum(10.0)
        self.height_input = QDoubleSpinBox()
        self.height_input.setSuffix(" m")
        self.height_input.setMaximum(10.0)
        self.odometer_input = QSpinBox()
        self.odometer_input.setMaximum(9999999)
        self.odometer_input.setSuffix(" km")

        layout.addRow("Operational Status", self.operational_status_input)
        layout.addRow("Is Active", self.is_active_input)
        layout.addRow("Commission Date", self.commission_date_input)
        layout.addRow("Decommission Date", self.decommission_date_input)
        layout.addRow("Exterior Color", self.ext_color_input)
        layout.addRow("Interior Color", self.int_color_input)
        layout.addRow("Length", self.length_input)
        layout.addRow("Width", self.width_input)
        layout.addRow("Height", self.height_input)
        layout.addRow("Odometer", self.odometer_input)

        widget.setLayout(layout)
        return widget

    def _create_maintenance_tab(self) -> object:
        """Create the Maintenance tab"""
        widget = QWidget()
        layout = QFormLayout()

        self.next_service_due_input = StandardDateEdit(prefer_month_text=True)
        self.next_service_due_input.setCalendarPopup(True)
        self.next_service_due_input.setSpecialValueText("N/A")
        self.last_service_date_input = StandardDateEdit(prefer_month_text=True)
        self.last_service_date_input.setCalendarPopup(True)
        self.last_service_date_input.setSpecialValueText("N/A")
        self.service_type_input = QLineEdit()
        self.service_cost_input = QDoubleSpinBox()
        self.service_cost_input.setPrefix("$")
        self.service_cost_input.setMaximum(999999.99)
        self.service_odometer_input = QSpinBox()
        self.service_odometer_input.setMaximum(9999999)
        self.service_odometer_input.setSuffix(" km")
        self.service_odometer_input.setToolTip(
            "Odometer reading at last service"
        )
        self.maintenance_notes_input = QTextEdit()
        self.maintenance_notes_input.setFixedHeight(100)

        layout.addRow("Next Service Due", self.next_service_due_input)
        layout.addRow("Last Service Date", self.last_service_date_input)
        layout.addRow("Service Type", self.service_type_input)
        layout.addRow("Service Cost", self.service_cost_input)
        layout.addRow("Odometer", self.service_odometer_input)
        layout.addRow("Maintenance Notes", self.maintenance_notes_input)

        widget.setLayout(layout)
        return widget

    def _create_insurance_tab(self) -> object:
        """Create the Insurance & Registration tab"""
        widget = QWidget()
        layout = QFormLayout()

        self.insurance_policy_input = QLineEdit()
        self.policy_end_date_input = StandardDateEdit(prefer_month_text=True)
        self.policy_end_date_input.setCalendarPopup(True)
        self.policy_end_date_input.setSpecialValueText("N/A")
        self.registration_expiry_input = StandardDateEdit(
            prefer_month_text=True
        )
        self.registration_expiry_input.setCalendarPopup(True)
        self.registration_expiry_input.setSpecialValueText("N/A")
        self.financing_status_input = QComboBox()
        self.financing_status_input.addItems(["Owned", "Financed", "Leased"])
        self.financing_notes_input = QTextEdit()
        self.financing_notes_input.setFixedHeight(80)

        layout.addRow("Insurance Policy Number", self.insurance_policy_input)
        layout.addRow("Policy End Date", self.policy_end_date_input)
        layout.addRow("Registration Expiry", self.registration_expiry_input)
        layout.addRow("Financing Status", self.financing_status_input)
        layout.addRow("Financing Notes", self.financing_notes_input)

        widget.setLayout(layout)
        return widget

    def _create_documents_tab(self) -> object:
        """Create the Documents tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(
            QLabel("Vehicle Documents (photos, insurance, registration, etc.)")
        )

        self.documents_list = QListWidget()
        layout.addWidget(self.documents_list)

        button_layout = QHBoxLayout()
        upload_btn = QPushButton("📤 Upload Documents")
        upload_btn.clicked.connect(self.upload_documents)
        view_btn = QPushButton("👁️ View Selected")
        view_btn.clicked.connect(self.view_document)
        delete_doc_btn = QPushButton("🗑️ Remove Selected")
        delete_doc_btn.clicked.connect(self.delete_document)
        button_layout.addWidget(upload_btn)
        button_layout.addWidget(view_btn)
        button_layout.addWidget(delete_doc_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        widget.setLayout(layout)
        return widget

    def _create_lease_tab(self) -> object:
        """Create CRA-focused lease profile and document tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        profile_group = QGroupBox("Lease Profile")
        profile_layout = QGridLayout()

        self.lease_status_input = QComboBox()
        self.lease_status_input.addItems(
            ["active", "closed", "defaulted", "returned"]
        )
        self.lease_type_input = QComboBox()
        self.lease_type_input.addItems(
            ["operating", "finance", "loan", "other"]
        )
        self.lessor_name_input = QLineEdit()
        self.lessor_gst_number_input = QLineEdit()
        self.lessor_gst_number_input.setPlaceholderText(
            "e.g. 123456789 RT0001"
        )
        self.lessor_gst_number_input.setToolTip(
            "CRA requires the lessor's GST/HST registration number on"
            "invoices to claim ITC"

        )
        self.contract_number_input = QLineEdit()
        self.lease_start_date_input = StandardDateEdit(prefer_month_text=True)
        self.lease_start_date_input.setCalendarPopup(True)
        self.lease_end_date_input = StandardDateEdit(prefer_month_text=True)
        self.lease_end_date_input.setCalendarPopup(True)
        self.payment_day_input = QSpinBox()
        self.payment_day_input.setRange(0, 31)
        self.payment_day_input.setSpecialValueText("N/A")

        self.down_payment_input = QDoubleSpinBox()
        self.down_payment_input.setPrefix("$")
        self.down_payment_input.setMaximum(9999999.99)
        self.monthly_payment_input = QDoubleSpinBox()
        self.monthly_payment_input.setPrefix("$")
        self.monthly_payment_input.setMaximum(9999999.99)
        self.buyout_amount_input = QDoubleSpinBox()
        self.buyout_amount_input.setPrefix("$")
        self.buyout_amount_input.setMaximum(9999999.99)
        self.contract_total_input = QDoubleSpinBox()
        self.contract_total_input.setPrefix("$")
        self.contract_total_input.setMaximum(99999999.99)
        self.security_deposit_input = QDoubleSpinBox()
        self.security_deposit_input.setPrefix("$")
        self.security_deposit_input.setMaximum(9999999.99)
        self.expected_total_input = QDoubleSpinBox()
        self.expected_total_input.setPrefix("$")
        self.expected_total_input.setMaximum(99999999.99)

        self.missed_payments_input = QSpinBox()
        self.missed_payments_input.setMaximum(999)
        self.nsf_count_input = QSpinBox()
        self.nsf_count_input.setMaximum(999)
        self.nsf_fee_total_input = QDoubleSpinBox()
        self.nsf_fee_total_input.setPrefix("$")
        self.nsf_fee_total_input.setMaximum(9999999.99)
        self.late_fee_total_input = QDoubleSpinBox()
        self.late_fee_total_input.setPrefix("$")
        self.late_fee_total_input.setMaximum(9999999.99)
        self.business_use_percent_input = QDoubleSpinBox()
        self.business_use_percent_input.setSuffix("%")
        self.business_use_percent_input.setRange(0.0, 100.0)
        self.business_use_percent_input.setDecimals(2)

        # GST/ITC tracking fields
        self.vehicle_type_input = QComboBox()
        self.vehicle_type_input.addItems(
            ["Livery Motor Vehicle", "Passenger Vehicle", "Other"]
        )
        self.gst_per_payment_input = QDoubleSpinBox()
        self.gst_per_payment_input.setPrefix("$")
        self.gst_per_payment_input.setMaximum(99999.99)
        self.total_gst_input = QDoubleSpinBox()
        self.total_gst_input.setPrefix("$")
        self.total_gst_input.setMaximum(999999.99)
        self.itc_amount_display = QLineEdit()
        self.itc_amount_display.setReadOnly(True)
        self.itc_amount_display.setText("$0.00")
        self.itc_verified_input = QCheckBox("ITC Verified")
        self.itc_verified_input.setToolTip(
            "Auto-checked when GST is documented and QA requirements met"
        )
        self.auto_verify_itc_btn = QPushButton(
            "🔍 Auto-Verify ITC from Receipts"
        )
        self.auto_verify_itc_btn.clicked.connect(
            self._auto_verify_itc_from_receipts
        )

        self.has_signed_lease_input = QCheckBox(
            "Signed lease agreement on file"
        )
        self.has_payment_schedule_input = QCheckBox("Payment schedule on file")
        self.has_insurance_proof_input = QCheckBox("Insurance proof on file")
        self.has_buyout_terms_input = QCheckBox("Buyout terms on file")
        self.has_vendor_statement_input = QCheckBox(
            "Annual lessor statement on file"
        )

        self.lease_notes_input = QTextEdit()
        self.lease_notes_input.setFixedHeight(80)

        left_form = QFormLayout()
        right_form = QFormLayout()

        left_form.addRow("Lease Status", self.lease_status_input)
        left_form.addRow("Lease Type", self.lease_type_input)
        left_form.addRow("Lessor Name", self.lessor_name_input)
        left_form.addRow("Lessor GST/HST #", self.lessor_gst_number_input)
        left_form.addRow("Contract Number", self.contract_number_input)
        left_form.addRow("Lease Start", self.lease_start_date_input)
        left_form.addRow("Lease End", self.lease_end_date_input)
        left_form.addRow("Payment Day", self.payment_day_input)
        left_form.addRow("Monthly Payment", self.monthly_payment_input)
        left_form.addRow("Down Payment", self.down_payment_input)
        left_form.addRow("Buyout Amount", self.buyout_amount_input)
        left_form.addRow("Contract Total", self.contract_total_input)
        left_form.addRow("Expected Total Cost", self.expected_total_input)

        right_form.addRow("Security Deposit", self.security_deposit_input)
        right_form.addRow("Missed Payments", self.missed_payments_input)
        right_form.addRow("NSF Payments", self.nsf_count_input)
        right_form.addRow("NSF Fees", self.nsf_fee_total_input)
        right_form.addRow("Late Fees", self.late_fee_total_input)
        right_form.addRow("Business Use", self.business_use_percent_input)
        right_form.addRow("Vehicle Type (GST/ITC)", self.vehicle_type_input)
        right_form.addRow("GST Per Payment", self.gst_per_payment_input)
        right_form.addRow("Total GST Charged", self.total_gst_input)
        right_form.addRow("ITC Amount (Recoverable)", self.itc_amount_display)

        gst_button_layout = QHBoxLayout()
        gst_button_layout.addWidget(self.itc_verified_input)
        gst_button_layout.addWidget(self.auto_verify_itc_btn)
        gst_button_layout.addStretch()
        right_form.addRow("ITC Status", gst_button_layout)

        left_form_widget = QWidget()
        left_form_widget.setLayout(left_form)
        right_form_widget = QWidget()
        right_form_widget.setLayout(right_form)

        profile_layout.addWidget(left_form_widget, 0, 0)
        profile_layout.addWidget(right_form_widget, 0, 1)
        profile_layout.setColumnStretch(0, 1)
        profile_layout.setColumnStretch(1, 1)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        compliance_group = QGroupBox("Compliance Evidence")
        compliance_layout = QVBoxLayout()
        compliance_layout.addWidget(self.has_signed_lease_input)
        compliance_layout.addWidget(self.has_payment_schedule_input)
        compliance_layout.addWidget(self.has_insurance_proof_input)
        compliance_layout.addWidget(self.has_buyout_terms_input)
        compliance_layout.addWidget(self.has_vendor_statement_input)
        compliance_group.setLayout(compliance_layout)
        layout.addWidget(compliance_group)

        notes_group = QGroupBox("Compliance Notes")
        notes_layout = QVBoxLayout()
        notes_layout.addWidget(self.lease_notes_input)
        notes_group.setLayout(notes_layout)
        layout.addWidget(notes_group)

        docs_group = QGroupBox("Lease Documents")
        docs_layout = QVBoxLayout()
        self.lease_docs_list = QListWidget()
        docs_layout.addWidget(self.lease_docs_list)

        docs_btn_layout = QHBoxLayout()
        add_doc_btn = QPushButton("📤 Upload Lease Document")
        add_doc_btn.clicked.connect(self.upload_lease_document)
        open_doc_btn = QPushButton("👁️ Open Selected")
        open_doc_btn.clicked.connect(self.open_lease_document)
        remove_doc_btn = QPushButton("🗑️ Remove Selected")
        remove_doc_btn.clicked.connect(self.delete_lease_document)
        docs_btn_layout.addWidget(add_doc_btn)
        docs_btn_layout.addWidget(open_doc_btn)
        docs_btn_layout.addWidget(remove_doc_btn)
        docs_btn_layout.addStretch()
        docs_layout.addLayout(docs_btn_layout)
        docs_group.setLayout(docs_layout)
        layout.addWidget(docs_group)

        report_btn_layout = QHBoxLayout()
        cra_report_btn = QPushButton("📋 Generate CRA Lease Compliance Report")
        cra_report_btn.clicked.connect(self._generate_cra_lease_report)
        cra_report_btn.setToolTip(
            "Generate a CRA-ready audit report for all vehicles with lease"
            "profiles"

        )
        report_btn_layout.addWidget(cra_report_btn)
        report_btn_layout.addStretch()
        layout.addLayout(report_btn_layout)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def new_vehicle(self) -> None:
        """Clear form for new vehicle entry"""
        self.current_vehicle_id = None

        # Identification
        self.vehicle_number_input.clear()
        self.vin_input.clear()
        self.vehicle_code_input.clear()
        self.fleet_number_input.clear()
        self.fleet_position_input.setValue(0)
        self.license_plate_input.clear()
        self.make_input.clear()
        self.model_input.clear()
        self.year_input.setValue(datetime.now().year)
        self.type_input.setCurrentIndex(0)
        self.vehicle_category_input.clear()
        self.vehicle_class_input.clear()
        self.passenger_capacity_input.setValue(0)
        self.description_input.clear()

        # Status & Specs
        self.operational_status_input.setCurrentText("Active")
        self.is_active_input.setChecked(True)
        self.commission_date_input.setDate(QDate.currentDate())
        self.decommission_date_input.setDate(QDate.currentDate())
        self.ext_color_input.clear()
        self.int_color_input.clear()
        self.length_input.setValue(0.0)
        self.width_input.setValue(0.0)
        self.height_input.setValue(0.0)
        self.odometer_input.setValue(0)

        # Maintenance
        self.next_service_due_input.setDate(QDate.currentDate())
        self.last_service_date_input.setDate(QDate.currentDate())
        self.service_type_input.clear()
        self.service_cost_input.setValue(0.0)
        self.service_odometer_input.setValue(0)
        self.maintenance_notes_input.clear()

        # Insurance
        self.insurance_policy_input.clear()
        self.policy_end_date_input.setDate(QDate.currentDate())
        self.registration_expiry_input.setDate(QDate.currentDate())
        self.financing_status_input.setCurrentText("Owned")
        self.financing_notes_input.clear()

        # Documents
        self.documents_list.clear()
        self._clear_lease_fields()

        self.delete_btn.setEnabled(False)
        self.vehicle_number_input.setFocus()

    def load_selected_vehicle(self) -> None:
        """Load selected vehicle from table into form"""
        selected = self.vehicle_table.selectedItems()
        if not selected:
            return

        row = self.vehicle_table.row(selected[0])
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Get actual columns in vehicles table
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'vehicles'
                    ORDER BY ordinal_position
                    """)
                actual_cols = {r[0] for r in cur.fetchall()}

                vehicle_number = self.vehicle_table.item(row, 0).text()
                # Desired columns in priority order
                desired = [
                    "vehicle_id",
                    "vehicle_number",
                    "vin_number",
                    "vehicle_code",
                    "fleet_number",
                    "fleet_position",
                    "license_plate",
                    "make",
                    "model",
                    "year",
                    "type",
                    "vehicle_category",
                    "vehicle_class",
                    "passenger_capacity",
                    "description",
                    "operational_status",
                    "is_active",
                    "commission_date",
                    "decommission_date",
                    "ext_color",
                    "int_color",
                    "length",
                    "width",
                    "height",
                    "odometer",
                    "next_service_due",
                    "last_service_date",
                    "service_type",
                    "service_cost",
                    "maintenance_notes",
                    "insurance_policy_number",
                    "policy_end_date",
                    "registration_expiry",
                    "financing_status",
                    "financing_notes",
                ]
                # Only include columns that actually exist
                columns = [c for c in desired if c in actual_cols]

                select_clause = ", ".join(columns)
                cur.execute(
                    f"""
                    SELECT {select_clause}
                    FROM vehicles
                    WHERE vehicle_number = %s
                    LIMIT 1
                    """,
                    (vehicle_number,),
                )
                result = cur.fetchone()

            if result:
                row_data = dict(zip(columns, result))
                self.current_vehicle_id = row_data.get("vehicle_id")

                # Identification
                self.vehicle_number_input.setText(
                    row_data.get("vehicle_number") or ""
                )
                self.vin_input.setText(row_data.get("vin_number") or "")
                if self.has_vehicle_code:
                    self.vehicle_code_input.setText(
                        row_data.get("vehicle_code") or ""
                    )
                else:
                    self.vehicle_code_input.clear()
                self.fleet_number_input.setText(
                    row_data.get("fleet_number") or ""
                )
                self.fleet_position_input.setValue(
                    row_data.get("fleet_position") or 0
                )
                self.license_plate_input.setText(
                    row_data.get("license_plate") or ""
                )
                self.make_input.setText(row_data.get("make") or "")
                self.model_input.setText(row_data.get("model") or "")
                self.year_input.setValue(
                    row_data.get("year") or datetime.now().year
                )

                # Ensure type value is selectable; add on the fly if new
                vehicle_type_val = row_data.get("type") or "Sedan"
                if (
                    vehicle_type_val
                    and self.type_input.findText(vehicle_type_val) == -1
                ):
                    self.type_input.addItem(vehicle_type_val)
                self.type_input.setCurrentText(vehicle_type_val)
                self.vehicle_category_input.setText(
                    row_data.get("vehicle_category") or ""
                )
                self.vehicle_class_input.setText(
                    row_data.get("vehicle_class") or ""
                )
                self.passenger_capacity_input.setValue(
                    row_data.get("passenger_capacity") or 0
                )
                self.description_input.setText(
                    row_data.get("description") or ""
                )

                # Status & Specs
                operational_status_val = (
                    row_data.get("operational_status") or "Active"
                )
                if (
                    self.operational_status_input.findText(
                        operational_status_val
                    )
                    == -1
                ):
                    self.operational_status_input.addItem(
                        operational_status_val
                    )
                self.operational_status_input.setCurrentText(
                    operational_status_val
                )
                is_active_val = row_data.get("is_active")
                self.is_active_input.setChecked(
                    is_active_val if is_active_val is not None else True
                )
                if row_data.get("commission_date"):
                    self.commission_date_input.setDate(
                        QDate.fromString(
                            str(row_data.get("commission_date")), "yyyy-MM-dd"
                        )
                    )
                if row_data.get("decommission_date"):
                    self.decommission_date_input.setDate(
                        QDate.fromString(
                            str(row_data.get("decommission_date")),
                            "yyyy-MM-dd",
                        )
                    )
                self.ext_color_input.setText(row_data.get("ext_color") or "")
                self.int_color_input.setText(row_data.get("int_color") or "")
                self.length_input.setValue(
                    float(row_data.get("length"))
                    if row_data.get("length")
                    else 0.0
                )
                self.width_input.setValue(
                    float(row_data.get("width"))
                    if row_data.get("width")
                    else 0.0
                )
                self.height_input.setValue(
                    float(row_data.get("height"))
                    if row_data.get("height")
                    else 0.0
                )
                self.odometer_input.setValue(row_data.get("odometer") or 0)

                # Maintenance (only set if columns exist)
                if "next_service_due" in columns and row_data.get(
                    "next_service_due"
                ):
                    self.next_service_due_input.setDate(
                        QDate.fromString(
                            str(row_data.get("next_service_due")), "yyyy-MM-dd"
                        )
                    )
                if "last_service_date" in columns and row_data.get(
                    "last_service_date"
                ):
                    self.last_service_date_input.setDate(
                        QDate.fromString(
                            str(row_data.get("last_service_date")),
                            "yyyy-MM-dd",
                        )
                    )
                if "service_type" in columns:
                    self.service_type_input.setText(
                        row_data.get("service_type") or ""
                    )
                if "service_cost" in columns:
                    self.service_cost_input.setValue(
                        float(row_data.get("service_cost"))
                        if row_data.get("service_cost")
                        else 0.0
                    )
                # Sync odometer to maintenance tab
                if "odometer" in columns:
                    self.service_odometer_input.setValue(
                        row_data.get("odometer") or 0
                    )
                if "maintenance_notes" in columns:
                    self.maintenance_notes_input.setText(
                        row_data.get("maintenance_notes") or ""
                    )

                # Insurance (only set if columns exist)
                if "insurance_policy_number" in columns:
                    self.insurance_policy_input.setText(
                        row_data.get("insurance_policy_number") or ""
                    )
                if "policy_end_date" in columns and row_data.get(
                    "policy_end_date"
                ):
                    self.policy_end_date_input.setDate(
                        QDate.fromString(
                            str(row_data.get("policy_end_date")), "yyyy-MM-dd"
                        )
                    )
                if "registration_expiry" in columns and row_data.get(
                    "registration_expiry"
                ):
                    self.registration_expiry_input.setDate(
                        QDate.fromString(
                            str(row_data.get("registration_expiry")),
                            "yyyy-MM-dd",
                        )
                    )
                if "financing_status" in columns:
                    self.financing_status_input.setCurrentText(
                        row_data.get("financing_status") or "Owned"
                    )
                if "financing_notes" in columns:
                    self.financing_notes_input.setText(
                        row_data.get("financing_notes") or ""
                    )

                self._load_lease_profile()

                self.delete_btn.setEnabled(True)
                self.load_vehicle_documents()

        except Exception as e:
            logger.error(f"Failed to load selected vehicle: {e}")
            QMessageBox.warning(
                self, "Load Error", f"Failed to load vehicle: {e}"
            )

    def load_vehicles(self) -> None:
        """Load vehicles matching search/filter criteria, with natural"
        "sorting"""

        search_text = self.search_input.text().strip()
        status_filter = self.status_filter.currentText()

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Build query with filters
                query = """
                    SELECT
                        vehicle_id, vehicle_number, make, model, year,
                        license_plate,
                        operational_status, odometer, odometer_type,
                        next_cvip_due, last_service_date
                    FROM vehicles
                    WHERE 1=1
                """
                params = []

                if search_text:
                    query += """ AND (
                        vehicle_number ILIKE %s OR
                        make ILIKE %s OR
                        model ILIKE %s OR
                        vin_number ILIKE %s OR
                        license_plate ILIKE %s)"""
                    search_pattern = f"%{search_text}%"
                    params.extend([search_pattern] * 5)

                if status_filter != "All Status":
                    if status_filter == "Active":
                        query += (
                            " AND operational_status IN ('active', 'Active')"
                        )
                    elif status_filter == "Inactive":
                        query += (
                            " AND operational_status IN ('inactive', "
                            "'Inactive')"
                        )
                    elif status_filter == "Decommissioned":
                        query += (
                            " AND operational_status IN ('decommissioned', "
                            "'retired', 'total loss')"
                        )

                query += " ORDER BY vehicle_number"

                cur.execute(query, params)
                vehicles = cur.fetchall()

                # Sort naturally: L-1, L-2, L-3... L-10, L-11, etc.
                vehicles_sorted = sorted(
                    vehicles, key=lambda v: self._natural_sort_key(v[1])
                )

                self.vehicle_table.setRowCount(len(vehicles_sorted))
                for row_idx, vehicle in enumerate(vehicles_sorted):
                    (
                        vehicle_id,
                        vehicle_num,
                        make,
                        model,
                        year,
                        license,
                        status,
                        odometer,
                        odometer_type,
                        next_cvip,
                        last_service,
                    ) = vehicle

                    items = [
                        QTableWidgetItem(
                            str(vehicle_num) if vehicle_num else ""
                        ),
                        QTableWidgetItem(str(make) if make else ""),
                        QTableWidgetItem(str(model) if model else ""),
                        QTableWidgetItem(str(year) if year else ""),
                        QTableWidgetItem(str(license) if license else ""),
                        QTableWidgetItem(str(status) if status else ""),
                        QTableWidgetItem(
                            f"{odometer} {odometer_type}" if odometer else ""
                        ),
                        QTableWidgetItem(
                            str(next_cvip)[:10] if next_cvip else "N/A"
                        ),
                        QTableWidgetItem(
                            "🔴" if self._needs_repairs(vehicle_id) else "✓"
                        ),
                        QTableWidgetItem(
                            str(last_service)[:10] if last_service else "N/A"
                        ),
                    ]
                    for col_idx, item in enumerate(items):
                        self.vehicle_table.setItem(row_idx, col_idx, item)

        except Exception as e:
            logger.error(f"Failed to load vehicles: {e}")
            QMessageBox.warning(
                self, "Load Error", f"Failed to load vehicles: {e}"
            )

    def _needs_repairs(self, vehicle_id: int) -> bool:
        """Check if vehicle has pending repairs or maintenance due"
        "(placeholder)"""

        # TODO: Query maintenance table or service history
        return False

    def save_vehicle(self) -> None:
        """Save vehicle to database"""
        # Validate required fields
        if not self.vehicle_number_input.text().strip():
            QMessageBox.warning(
                self, "Validation Error", "Vehicle Number is required"
            )
            return
        if not self.make_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Make is required")
            return
        if not self.model_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Model is required")
            return
        if not self.license_plate_input.text().strip():
            QMessageBox.warning(
                self, "Validation Error", "License Plate is required"
            )
            return

        try:
            # Prepare data
            data = {
                "vehicle_number": self.vehicle_number_input.text().strip(),
                "vin_number": self.vin_input.text().strip() or None,
                "fleet_number": self.fleet_number_input.text().strip() or None,
                "fleet_position": (
                    self.fleet_position_input.value()
                    if self.fleet_position_input.value() > 0
                    else None
                ),
                "license_plate": self.license_plate_input.text().strip(),
                "make": self.make_input.text().strip(),
                "model": self.model_input.text().strip(),
                "year": self.year_input.value(),
                "type": self.type_input.currentText(),
                "vehicle_category": self.vehicle_category_input.text().strip()
                or None,
                "vehicle_class": self.vehicle_class_input.text().strip()
                or None,
                "passenger_capacity": (
                    self.passenger_capacity_input.value()
                    if self.passenger_capacity_input.value() > 0
                    else None
                ),
                "description": self.description_input.toPlainText().strip()
                or None,
                "operational_status": (
                    self.operational_status_input.currentText()
                ),
                "is_active": self.is_active_input.isChecked(),
                "commission_date": (
                    self.commission_date_input.date().toString("yyyy-MM-dd")
                    if self.commission_date_input.date().isValid()
                    else None
                ),
                "decommission_date": (
                    self.decommission_date_input.date().toString("yyyy-MM-dd")
                    if self.decommission_date_input.date().isValid()
                    and self.decommission_date_input.specialValueText()
                    != self.decommission_date_input.text()
                    else None
                ),
                "ext_color": self.ext_color_input.text().strip() or None,
                "int_color": self.int_color_input.text().strip() or None,
                "length": (
                    self.length_input.value()
                    if self.length_input.value() > 0
                    else None
                ),
                "width": (
                    self.width_input.value()
                    if self.width_input.value() > 0
                    else None
                ),
                "height": (
                    self.height_input.value()
                    if self.height_input.value() > 0
                    else None
                ),
                "odometer": (
                    self.odometer_input.value()
                    if self.odometer_input.value() > 0
                    else None
                ),
                "next_service_due": (
                    self.next_service_due_input.date().toString("yyyy-MM-dd")
                    if self.next_service_due_input.date().isValid()
                    and self.next_service_due_input.specialValueText()
                    != self.next_service_due_input.text()
                    else None
                ),
                "last_service_date": (
                    self.last_service_date_input.date().toString("yyyy-MM-dd")
                    if self.last_service_date_input.date().isValid()
                    and self.last_service_date_input.specialValueText()
                    != self.last_service_date_input.text()
                    else None
                ),
                "service_type": self.service_type_input.text().strip() or None,
                "service_cost": (
                    self.service_cost_input.value()
                    if self.service_cost_input.value() > 0
                    else None
                ),
                "maintenance_notes": (
                    self.maintenance_notes_input.toPlainText().strip()
                    or None
                ),
                "insurance_policy_number": (
                    self.insurance_policy_input.text().strip() or None
                ),
                "policy_end_date": (
                    self.policy_end_date_input.date().toString("yyyy-MM-dd")
                    if self.policy_end_date_input.date().isValid()
                    and self.policy_end_date_input.specialValueText()
                    != self.policy_end_date_input.text()
                    else None
                ),
                "registration_expiry": (
                    self.registration_expiry_input.date().toString(
                        "yyyy-MM-dd"
                    )
                    if self.registration_expiry_input.date().isValid()
                    and self.registration_expiry_input.specialValueText()
                    != self.registration_expiry_input.text()
                    else None
                ),
                "financing_status": self.financing_status_input.currentText(),
                "financing_notes": (
                    self.financing_notes_input.toPlainText().strip() or None
                ),
            }

            if self.has_vehicle_code:
                data["vehicle_code"] = (
                    self.vehicle_code_input.text().strip() or None
                )

            if self.current_vehicle_id:
                # Update existing vehicle
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    update_fields = ", ".join(
                        [f"{key} = %s" for key in data]
                    )
                    cur.execute(
                        f"UPDATE vehicles SET {update_fields} "
                        f"WHERE vehicle_id = %s",

                        list(data.values()) + [self.current_vehicle_id],
                    )
                QMessageBox.information(
                    self, "Success", "Vehicle updated successfully!"
                )
            else:
                # Insert new vehicle
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    columns = ", ".join(data.keys())
                    placeholders = ", ".join(["%s"] * len(data))
                    cur.execute(
                        f"INSERT INTO vehicles ({columns}) VALUES"
                        f"({placeholders}) RETURNING vehicle_id",

                        list(data.values()),
                    )
                    self.current_vehicle_id = cur.fetchone()[0]
                QMessageBox.information(
                    self, "Success", "Vehicle added successfully!"
                )

            self._save_lease_profile()

            self.load_vehicles()
            self.delete_btn.setEnabled(True)

        except Exception as e:
            logger.error(f"Failed to save vehicle: {e}")
            QMessageBox.critical(
                self, "Save Error", f"Failed to save vehicle: {e}"
            )

    def delete_vehicle(self) -> None:
        """Delete current vehicle"""
        if not self.current_vehicle_id:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete vehicle"
            f"{self.vehicle_number_input.text()}?",

            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        "DELETE FROM vehicles WHERE vehicle_id = %s",
                        (self.current_vehicle_id,),
                    )
                QMessageBox.information(
                    self, "Success", "Vehicle deleted successfully!"
                )
                self.new_vehicle()
                self.load_vehicles()
            except Exception as e:
                logger.error(f"Failed to delete vehicle: {e}")
                QMessageBox.critical(
                    self, "Delete Error", f"Failed to delete vehicle: {e}"
                )

    def load_vehicle_documents(self) -> None:
        """Load documents for current vehicle (placeholder for future"
        "implementation)"""

        self.documents_list.clear()
        if self.current_vehicle_id:
            # TODO: Implement document storage/retrieval
            # For now, show placeholder
            item = QListWidgetItem("📄 Document management coming soon...")
            item.setForeground(QColor("#999"))
            self.documents_list.addItem(item)

    def upload_documents(self) -> None:
        """Upload documents for vehicle (placeholder)"""
        if not self.current_vehicle_id:
            QMessageBox.warning(
                self,
                "No Vehicle",
                "Please save the vehicle first before uploading documents.",
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Vehicle Documents",
            "",
            "All Files (*);;PDF Files (*.pdf);;Images (*.jpg *.jpeg *.png)",
        )

        if files:
            QMessageBox.information(
                self,
                "Upload",
                f"Selected {len(files)} file(s). Document storage will be"
                f"implemented in future update.",

            )
            # TODO: Implement document storage

    def view_document(self) -> None:
        """View selected document (placeholder)"""
        QMessageBox.information(
            self,
            "View Document",
            "Document viewing will be implemented in future update.",
        )

    def delete_document(self) -> None:
        """Delete selected document (placeholder)"""
        QMessageBox.information(
            self,
            "Delete Document",
            "Document deletion will be implemented in future update.",
        )

    def _clear_lease_fields(self) -> None:
        self.lease_status_input.setCurrentText("active")
        self.lease_type_input.setCurrentText("operating")
        self.lessor_name_input.clear()
        self.contract_number_input.clear()
        self.lease_start_date_input.setDate(QDate.currentDate())
        self.lease_end_date_input.setDate(QDate.currentDate())
        self.payment_day_input.setValue(0)
        self.down_payment_input.setValue(0.0)
        self.monthly_payment_input.setValue(0.0)
        self.buyout_amount_input.setValue(0.0)
        self.contract_total_input.setValue(0.0)
        self.security_deposit_input.setValue(0.0)
        self.expected_total_input.setValue(0.0)
        self.missed_payments_input.setValue(0)
        self.nsf_count_input.setValue(0)
        self.nsf_fee_total_input.setValue(0.0)
        self.late_fee_total_input.setValue(0.0)
        self.business_use_percent_input.setValue(100.0)
        self.has_signed_lease_input.setChecked(False)
        self.has_payment_schedule_input.setChecked(False)
        self.has_insurance_proof_input.setChecked(False)
        self.has_buyout_terms_input.setChecked(False)
        self.has_vendor_statement_input.setChecked(False)
        self.lease_notes_input.clear()
        self.lease_docs_list.clear()

    def _load_lease_profile(self) -> None:
        """Load lease profile and documents for selected vehicle."""
        if not self.current_vehicle_id:
            self._clear_lease_fields()
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT
                        lease_status, lease_type, lessor_name, contract_number,
                        lease_start_date, lease_end_date, payment_day,
                        down_payment, monthly_payment, buyout_amount,
                        contract_total,
                        security_deposit, expected_total_cost,
                        missed_payments_count, nsf_payment_count,
                        nsf_fee_total, late_fee_total,
                        business_use_percent,
                        has_signed_lease, has_payment_schedule,
                        has_insurance_proof,
                        has_buyout_terms, has_vendor_statement, notes
                    FROM vehicle_lease_profiles
                    WHERE vehicle_id = %s
                    """,
                    (self.current_vehicle_id,),
                )
                row = cur.fetchone()

                if not row:
                    self._clear_lease_fields()
                    self._load_lease_documents()
                    return

                (
                    lease_status,
                    lease_type,
                    lessor_name,
                    lessor_gst_number,
                    contract_number,
                    lease_start_date,
                    lease_end_date,
                    payment_day,
                    down_payment,
                    monthly_payment,
                    buyout_amount,
                    contract_total,
                    security_deposit,
                    expected_total_cost,
                    missed_count,
                    nsf_count,
                    nsf_fee_total,
                    late_fee_total,
                    business_use_percent,
                    vehicle_type,
                    gst_per_payment_amount,
                    total_gst_charged,
                    itc_amount,
                    itc_verified,
                    has_signed,
                    has_schedule,
                    has_insurance,
                    has_buyout,
                    has_statement,
                    notes,
                ) = row

            self.lease_status_input.setCurrentText(lease_status or "active")
            self.lease_type_input.setCurrentText(lease_type or "operating")
            self.lessor_name_input.setText(lessor_name or "")
            self.lessor_gst_number_input.setText(lessor_gst_number or "")
            self.contract_number_input.setText(contract_number or "")
            if lease_start_date:
                self.lease_start_date_input.setDate(
                    QDate.fromString(str(lease_start_date), "yyyy-MM-dd")
                )
            if lease_end_date:
                self.lease_end_date_input.setDate(
                    QDate.fromString(str(lease_end_date), "yyyy-MM-dd")
                )
            self.payment_day_input.setValue(payment_day or 0)
            self.down_payment_input.setValue(float(down_payment or 0.0))
            self.monthly_payment_input.setValue(float(monthly_payment or 0.0))
            self.buyout_amount_input.setValue(float(buyout_amount or 0.0))
            self.contract_total_input.setValue(float(contract_total or 0.0))
            self.security_deposit_input.setValue(
                float(security_deposit or 0.0)
            )
            self.expected_total_input.setValue(
                float(expected_total_cost or 0.0)
            )
            self.missed_payments_input.setValue(missed_count or 0)
            self.nsf_count_input.setValue(nsf_count or 0)
            self.nsf_fee_total_input.setValue(float(nsf_fee_total or 0.0))
            self.late_fee_total_input.setValue(float(late_fee_total or 0.0))
            self.business_use_percent_input.setValue(
                float(business_use_percent or 0.0)
            )
            self.vehicle_type_input.setCurrentText(
                vehicle_type or "Livery Motor Vehicle"
            )
            self.gst_per_payment_input.setValue(
                float(gst_per_payment_amount or 0.0)
            )
            self.total_gst_input.setValue(float(total_gst_charged or 0.0))
            self.itc_amount_display.setText(f"${float(itc_amount or 0.0):.2f}")
            self.itc_verified_input.setChecked(bool(itc_verified))
            self.has_signed_lease_input.setChecked(bool(has_signed))
            self.has_payment_schedule_input.setChecked(bool(has_schedule))
            self.has_insurance_proof_input.setChecked(bool(has_insurance))
            self.has_buyout_terms_input.setChecked(bool(has_buyout))
            self.has_vendor_statement_input.setChecked(bool(has_statement))
            self.lease_notes_input.setText(notes or "")
            self._load_lease_documents()
        except Exception as e:
            logger.error(f"Failed to load lease profile: {e}")
            QMessageBox.warning(
                self, "Lease Load Error", f"Failed to load lease profile: {e}"
            )

    def _save_lease_profile(self) -> None:
        """Insert/update lease profile for the current vehicle."""
        if not self.current_vehicle_id:
            return

        data = {
            "lease_status": self.lease_status_input.currentText(),
            "lease_type": self.lease_type_input.currentText(),
            "lessor_name": self.lessor_name_input.text().strip() or None,
            "lessor_gst_number": self.lessor_gst_number_input.text().strip()
            or None,
            "contract_number": self.contract_number_input.text().strip()
            or None,
            "lease_start_date": (
                self.lease_start_date_input.date().toString("yyyy-MM-dd")
                if self.lease_start_date_input.date().isValid()
                else None
            ),
            "lease_end_date": (
                self.lease_end_date_input.date().toString("yyyy-MM-dd")
                if self.lease_end_date_input.date().isValid()
                else None
            ),
            "payment_day": (
                self.payment_day_input.value()
                if self.payment_day_input.value() > 0
                else None
            ),
            "down_payment": self.down_payment_input.value(),
            "monthly_payment": self.monthly_payment_input.value(),
            "buyout_amount": self.buyout_amount_input.value(),
            "contract_total": self.contract_total_input.value(),
            "security_deposit": self.security_deposit_input.value(),
            "expected_total_cost": self.expected_total_input.value(),
            "missed_payments_count": self.missed_payments_input.value(),
            "nsf_payment_count": self.nsf_count_input.value(),
            "nsf_fee_total": self.nsf_fee_total_input.value(),
            "late_fee_total": self.late_fee_total_input.value(),
            "business_use_percent": self.business_use_percent_input.value(),
            "vehicle_type": self.vehicle_type_input.currentText(),
            "gst_per_payment_amount": self.gst_per_payment_input.value(),
            "total_gst_charged": self.total_gst_input.value(),
            "itc_amount": float(
                self.itc_amount_display.text().replace("$", "")
            )
            or None,
            "itc_verified": self.itc_verified_input.isChecked(),
            "has_signed_lease": self.has_signed_lease_input.isChecked(),
            "has_payment_schedule": (
                self.has_payment_schedule_input.isChecked()
            ),
            "has_insurance_proof": self.has_insurance_proof_input.isChecked(),
            "has_buyout_terms": self.has_buyout_terms_input.isChecked(),
            "has_vendor_statement": (
                self.has_vendor_statement_input.isChecked()
            ),
            "notes": self.lease_notes_input.toPlainText().strip() or None,
        }

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    """
                    INSERT INTO vehicle_lease_profiles (
                        vehicle_id,
                        lease_status, lease_type, lessor_name,
                        lessor_gst_number, contract_number,
                        lease_start_date, lease_end_date, payment_day,
                        down_payment, monthly_payment, buyout_amount,
                        contract_total,
                        security_deposit, expected_total_cost,
                        missed_payments_count, nsf_payment_count,
                        nsf_fee_total, late_fee_total,
                        business_use_percent,
                        vehicle_type, gst_per_payment_amount,
                        total_gst_charged, itc_amount, itc_verified,
                        has_signed_lease, has_payment_schedule,
                        has_insurance_proof,
                        has_buyout_terms, has_vendor_statement,
                        notes
                    ) VALUES (
                        %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s, %s,
                        %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s
                    )
                    ON CONFLICT (vehicle_id)
                    DO UPDATE SET
                        lease_status = EXCLUDED.lease_status,
                        lease_type = EXCLUDED.lease_type,
                        lessor_name = EXCLUDED.lessor_name,
                        lessor_gst_number = EXCLUDED.lessor_gst_number,
                        contract_number = EXCLUDED.contract_number,
                        lease_start_date = EXCLUDED.lease_start_date,
                        lease_end_date = EXCLUDED.lease_end_date,
                        payment_day = EXCLUDED.payment_day,
                        down_payment = EXCLUDED.down_payment,
                        monthly_payment = EXCLUDED.monthly_payment,
                        buyout_amount = EXCLUDED.buyout_amount,
                        contract_total = EXCLUDED.contract_total,
                        security_deposit = EXCLUDED.security_deposit,
                        expected_total_cost = EXCLUDED.expected_total_cost,
                        missed_payments_count = EXCLUDED.missed_payments_count,
                        nsf_payment_count = EXCLUDED.nsf_payment_count,
                        nsf_fee_total = EXCLUDED.nsf_fee_total,
                        late_fee_total = EXCLUDED.late_fee_total,
                        business_use_percent = EXCLUDED.business_use_percent,
                        vehicle_type = EXCLUDED.vehicle_type,
                        gst_per_payment_amount =
                        EXCLUDED.gst_per_payment_amount,
                        total_gst_charged = EXCLUDED.total_gst_charged,
                        itc_amount = EXCLUDED.itc_amount,
                        itc_verified = EXCLUDED.itc_verified,
                        has_signed_lease = EXCLUDED.has_signed_lease,
                        has_payment_schedule = EXCLUDED.has_payment_schedule,
                        has_insurance_proof = EXCLUDED.has_insurance_proof,
                        has_buyout_terms = EXCLUDED.has_buyout_terms,
                        has_vendor_statement = EXCLUDED.has_vendor_statement,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                    """,
                    (
                        self.current_vehicle_id,
                        data["lease_status"],
                        data["lease_type"],
                        data["lessor_name"],
                        data["lessor_gst_number"],
                        data["contract_number"],
                        data["lease_start_date"],
                        data["lease_end_date"],
                        data["payment_day"],
                        data["down_payment"],
                        data["monthly_payment"],
                        data["buyout_amount"],
                        data["contract_total"],
                        data["security_deposit"],
                        data["expected_total_cost"],
                        data["missed_payments_count"],
                        data["nsf_payment_count"],
                        data["nsf_fee_total"],
                        data["late_fee_total"],
                        data["business_use_percent"],
                        data["vehicle_type"],
                        data["gst_per_payment_amount"],
                        data["total_gst_charged"],
                        data["itc_amount"],
                        data["itc_verified"],
                        data["has_signed_lease"],
                        data["has_payment_schedule"],
                        data["has_insurance_proof"],
                        data["has_buyout_terms"],
                        data["has_vendor_statement"],
                        data["notes"],
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to save lease profile: {e}")
            QMessageBox.warning(
                self, "Lease Save Error", f"Failed to save lease profile: {e}"
            )

    def _load_lease_documents(self) -> None:
        self.lease_docs_list.clear()
        if not self.current_vehicle_id:
            return

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT lease_doc_id, doc_type, original_file_name,
                    file_path, is_verified
                    FROM vehicle_lease_documents
                    WHERE vehicle_id = %s
                    ORDER BY uploaded_at DESC
                    """,
                    (self.current_vehicle_id,),
                )
                rows = cur.fetchall()

            for (
                doc_id,
                doc_type,
                original_name,
                file_path,
                is_verified,
            ) in rows:
                label = (
                    f"[{doc_type or 'doc'}] "
                    f"{original_name or os.path.basename(file_path)}"
                )
                if is_verified:
                    label = f"✅ {label}"
                item = QListWidgetItem(label)
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    {"lease_doc_id": doc_id, "file_path": file_path},
                )
                self.lease_docs_list.addItem(item)
        except Exception as e:
            logger.error(f"Failed loading lease docs: {e}")

    def upload_lease_document(self) -> None:
        if not self.current_vehicle_id:
            QMessageBox.warning(
                self,
                "No Vehicle",
                "Save the vehicle first before adding lease documents.",
            )
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Lease Documents",
            "",
            "All Files (*);;PDF Files (*.pdf);;Images (*.jpg *.jpeg *.png)",
        )
        if not files:
            return

        vehicle_folder = self.lease_docs_root / str(
            self.vehicle_number_input.text().strip() or self.current_vehicle_id
        )
        vehicle_folder.mkdir(parents=True, exist_ok=True)

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                for src in files:
                    src_path = Path(src)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dst_name = f"{timestamp}_{src_path.name}"
                    dst_path = vehicle_folder / dst_name
                    shutil.copy2(src_path, dst_path)

                    doc_type = "lease_agreement"
                    lower_name = src_path.name.lower()
                    if "insurance" in lower_name:
                        doc_type = "insurance_proof"
                    elif "statement" in lower_name:
                        doc_type = "vendor_statement"
                    elif "buyout" in lower_name:
                        doc_type = "buyout_terms"
                    elif "schedule" in lower_name:
                        doc_type = "payment_schedule"

                    cur.execute(
                        """
                        INSERT INTO vehicle_lease_documents (
                            vehicle_id,
                            lease_id,
                            doc_type,
                            original_file_name,
                            file_path,
                            is_required,
                            is_verified
                        )
                        VALUES (
                            %s,
                            (SELECT lease_id FROM vehicle_lease_profiles WHERE
                            vehicle_id = %s),
                            %s,
                            %s,
                            %s,
                            %s,
                            %s
                        )
                        """,
                        (
                            self.current_vehicle_id,
                            self.current_vehicle_id,
                            doc_type,
                            src_path.name,
                            str(dst_path),
                            True,
                            False,
                        ),
                    )
            self._load_lease_documents()
        except Exception as e:
            logger.error(f"Failed uploading lease docs: {e}")
            QMessageBox.critical(
                self,
                "Lease Doc Upload Error",
                f"Failed to upload lease document(s): {e}",
            )

    def open_lease_document(self) -> None:
        item = self.lease_docs_list.currentItem()
        if not item:
            QMessageBox.warning(
                self, "No Selection", "Select a lease document to open."
            )
            return

        data = item.data(Qt.ItemDataRole.UserRole) or {}
        file_path = data.get("file_path")
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(
                self, "Missing File", f"File not found:\n{file_path}"
            )
            return

        try:
            os.startfile(file_path)
        except Exception as e:
            QMessageBox.critical(
                self, "Open Error", f"Could not open file:\n{e}"
            )

    def delete_lease_document(self) -> None:
        item = self.lease_docs_list.currentItem()
        if not item:
            QMessageBox.warning(
                self, "No Selection", "Select a lease document to remove."
            )
            return

        data = item.data(Qt.ItemDataRole.UserRole) or {}
        lease_doc_id = data.get("lease_doc_id")
        file_path = data.get("file_path")
        if not lease_doc_id:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete selected lease document record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM vehicle_lease_documents WHERE lease_doc_id ="
                    "%s",

                    (lease_doc_id,),
                )

            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as _e:
                    logger.debug('Suppressed: %s', _e)
            self._load_lease_documents()
        except Exception as e:
            logger.error(f"Failed deleting lease doc: {e}")
            QMessageBox.critical(
                self, "Delete Error", f"Failed to remove lease document: {e}"
            )

    def _generate_cra_lease_report(self) -> object:
        """Generate a CRA-ready HTML lease compliance report for all vehicles"
        "with lease profiles."""

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT
                        v.vehicle_number, v.make, v.model, v.year, v.vin_number,
                        lp.lease_status, lp.lease_type, lp.lessor_name,
                        lp.lessor_gst_number, lp.contract_number,
                        lp.lease_start_date, lp.lease_end_date, lp.payment_day,
                        lp.monthly_payment, lp.down_payment, lp.buyout_amount,
                        lp.missed_payments_count, lp.nsf_payment_count,
                        lp.nsf_fee_total, lp.late_fee_total,
                        lp.business_use_percent,
                        lp.vehicle_type, lp.gst_per_payment_amount,
                        lp.total_gst_charged,
                        lp.itc_amount, lp.itc_verified,
                        lp.has_signed_lease, lp.has_payment_schedule,
                        lp.has_insurance_proof,
                        lp.has_buyout_terms, lp.has_vendor_statement,
                        lp.notes, lp.updated_at
                    FROM vehicle_lease_profiles lp
                    JOIN vehicles v ON v.vehicle_id = lp.vehicle_id
                    ORDER BY v.vehicle_number
                    """)
                profiles = cur.fetchall()

                # Receipt summary per vehicle
                cur.execute("""
                    SELECT
                        v.vehicle_number,
                        COUNT(r.receipt_id) as receipt_count,
                        SUM(r.gross_amount) as total_paid,
                        COUNT(r.receipt_id) FILTER (WHERE
                        r.banking_transaction_id IS NOT NULL) as bank_linked,
                        COUNT(r.receipt_id) FILTER (WHERE r.is_paper_verified
                        = TRUE) as paper_verified,
                        MIN(r.receipt_date) as first_payment,
                        MAX(r.receipt_date) as last_payment
                    FROM vehicle_lease_profiles lp
                    JOIN vehicles v ON v.vehicle_id = lp.vehicle_id
                    LEFT JOIN receipts r ON r.vendor_account_id IN (
                        SELECT account_id FROM vendor_accounts
                        WHERE canonical_vendor ILIKE '%lease%'
                           OR canonical_vendor ILIKE '%rent%'
                    )
                    AND r.receipt_date
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                   
                    BETWEEN COALESCE(lp.lease_start_date, '2010-01-01')
                        AND COALESCE(lp.lease_end_date, NOW())
                    GROUP BY v.vehicle_number
                    ORDER BY v.vehicle_number
                    """)
                receipt_rows = cur.fetchall()

            receipt_map = {r[0]: r for r in receipt_rows}

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = _APP_ROOT / "data" / "cra_lease_reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            html_path = report_dir / f"CRA_Lease_Compliance_{ts}.html"
            csv_path = report_dir / f"CRA_Lease_Compliance_{ts}.csv"

            # --- CSV export ---
            csv_headers = [
                "Vehicle#",
                "Make",
                "Model",
                "Year",
                "VIN",
                "Status",
                "Type",
                "Lessor",
                "Contract#",
                "Start",
                "End",
                "Payment Day",
                "Monthly ($)",
                "Down ($)",
                "Buyout ($)",
                "Missed Payments",
                "NSF Count",
                "NSF Fees ($)",
                "Late Fees ($)",
                "Business Use %",
                "Vehicle Type",
                "GST/Payment ($)",
                "Total GST ($)",
                "ITC Amount ($)",
                "ITC Verified",
                "Signed Lease",
                "Payment Schedule",
                "Insurance",
                "Buyout Terms",
                "Vendor Statement",
                "Receipt Count",
                "Total Paid ($)",
                "Bank-Linked",
                "Paper Verified",
                "First Payment",
                "Last Payment",
                "Notes",
            ]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(csv_headers)
                for row in profiles:
                    vn = row[0]
                    rw = receipt_map.get(vn, (None,) * 7)
                    writer.writerow(
                        [
                            row[0],
                            row[1],
                            row[2],
                            row[3],
                            row[4],
                            row[5],
                            row[6],
                            row[7],
                            row[8],
                            row[9],
                            row[10],
                            row[11],
                            f"{float(row[12] or 0):.2f}",
                            f"{float(row[13] or 0):.2f}",
                            f"{float(row[14] or 0):.2f}",
                            row[15],
                            row[16],
                            f"{float(row[17] or 0):.2f}",
                            f"{float(row[18] or 0):.2f}",
                            f"{float(row[19] or 0):.2f}",
                            row[20],
                            f"{float(row[21] or 0):.2f}",
                            f"{float(row[22] or 0):.2f}",
                            f"{float(row[23] or 0):.2f}",
                            "YES" if row[24] else "NO",
                            "YES" if row[25] else "NO",
                            "YES" if row[26] else "NO",
                            "YES" if row[27] else "NO",
                            "YES" if row[28] else "NO",
                            "YES" if row[29] else "NO",
                            rw[1] or 0,
                            f"{float(rw[2] or 0):.2f}",
                            rw[3] or 0,
                            rw[4] or 0,
                            rw[5],
                            rw[6],
                            row[30],
                        ]
                    )

            # --- HTML report ---
            def ck(val) -> object:
                return (
                    '<span style="color:#27ae60;font-weight:bold">✅</span>'
                    if val
                    else (
                        '<span style="color:#e74c3c;font-weight:bold">'
                        '❌</span>'
                    )
                )

            def money(val) -> object:
                return f"${float(val or 0):,.2f}"

            now_str = datetime.now().strftime("%B %d, %Y %H:%M")
            rows_html = ""
            total_itc = 0.0
            total_gst = 0.0
            missing_gst_count = 0
            for row in profiles:
                (
                    vn,
                    make,
                    model,
                    year,
                    vin,
                    status,
                    ltype,
                    lessor,
                    lessor_gst,
                    contract,
                    start,
                    end,
                    pday,
                    monthly,
                    down,
                    buyout,
                    missed,
                    nsf_cnt,
                    nsf_fees,
                    late_fees,
                    biz_use,
                    veh_type,
                    gst_per,
                    total_gst_row,
                    itc_amt,
                    itc_ver,
                    s_lease,
                    s_sched,
                    s_ins,
                    s_buyout,
                    s_stmt,
                    notes,
                    updated,
                ) = row

                rw = receipt_map.get(vn, (None,) * 7)
                r_count = rw[1] or 0
                r_total = float(rw[2] or 0)
                r_bank = rw[3] or 0
                r_paper = rw[4] or 0

                # Compliance score (now 7 checks — GST# is the critical one)
                checks = [
                    bool(s_lease),
                    bool(s_sched),
                    bool(s_ins),
                    bool(s_buyout),
                    bool(s_stmt),
                    bool(itc_ver),
                    bool(lessor_gst),
                ]
                score = sum(checks)
                color = (
                    "#27ae60"
                    if score == 7
                    else ("#f39c12" if score >= 4 else "#e74c3c")
                )
                grade = (
                    "COMPLIANT"
                    if score == 7
                    else ("PARTIAL" if score >= 4 else "AT RISK")
                )

                itc_val = float(itc_amt or 0)
                gst_val = float(total_gst_row or 0)
                total_itc += itc_val
                total_gst += gst_val
                if not lessor_gst:
                    missing_gst_count += 1

                rows_html += f"""
                <tr>
                    <td>
                        <strong>{vn or '—'}</strong><br>
                        <small>
                            {year or ''} {make or ''} {model or ''}
                        </small><br>
                        <small style="color:#888">VIN: {vin or '—'}</small>
                    </td>
                    <td>
                        <code>{status or '—'}</code><br>
                        <small>{ltype or ''}</small>
                    </td>
                    <td>
                        {lessor or '—'}<br>
                        <small>GST/HST #:
                            {
                                '<span style="color:#e74c3c;font-weight:bold">'
                                'MISSING ⚠️</span>'
                                if not lessor_gst
                                else lessor_gst
                            }
                        </small><br>
                        <small>Contract: {contract or '—'}</small>
                    </td>
                    <td>{start or '—'}<br>to<br>{end or '—'}</td>
                    <td style="text-align:right">
                        {money(monthly)}/mo<br>
                        <small>Down: {money(down)}</small><br>
                        <small>Buyout: {money(buyout)}</small>
                    </td>
                    <td style="text-align:right">
                        {money(gst_val)}<br>
                        <small>ITC: {money(itc_val)}</small><br>
                        {ck(itc_ver)} ITC Verified
                    </td>
                    <td>
                        {ck(s_lease)} Signed Lease<br>
                        {ck(s_sched)} Payment Schedule<br>
                        {ck(s_ins)} Insurance<br>
                        {ck(s_buyout)} Buyout Terms<br>
                        {ck(s_stmt)} Vendor Statement
                    </td>
                    <td style="text-align:center">
                        {r_count} receipts<br>
                        <small>{money(r_total)} paid</small><br>
                        <small>
                            🏦 {r_bank} bank-linked<br>
                            📄 {r_paper} paper-verified
                        </small>
                    </td>
                    <td style="text-align:center">
                        <span
                            style="background:{color};color:white;"
                            "padding:3px 8px;border-radius:4px;"
                            "font-size:11px"
                        >{grade}</span><br>
                        <small>{score}/7 checks</small>
                        {
                            '<br><small style="color:#e74c3c">'
                            '⚠️ GST # missing</small>'
                            if not lessor_gst
                            else ''
                        }
                    </td>
                </tr>"""

            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CRA Vehicle Lease Compliance Report</title>
<style>
    body {{
        font-family: Arial, sans-serif;
        font-size: 13px;
        margin: 24px;
        color: #222;
    }}
    h1 {{
        color: #2c3e50;
        border-bottom: 2px solid #2980b9;
        padding-bottom: 8px;
    }}
  .meta {{ color: #666; margin-bottom: 20px; }}
    .summary-box {{
        display: inline-block;
        background: #f4f6f8;
        border: 1px solid #ddd;
        border-radius: 6px;
        padding: 12px 20px;
        margin: 8px;
        vertical-align: top;
    }}
  .summary-box h3 {{ margin:0 0 6px 0; color:#2980b9; font-size:14px; }}
  .summary-box .big {{ font-size:22px; font-weight:bold; color:#2c3e50; }}
  table {{ border-collapse: collapse; width:100%; margin-top:20px; }}
    th {{
        background:#2980b9;
        color:white;
        padding:8px 10px;
        text-align:left;
        font-size:12px;
    }}
    td {{
        padding:8px 10px;
        border-bottom:1px solid #eee;
        vertical-align:top;
        font-size:12px;
    }}
  tr:hover {{ background:#f9f9f9; }}
  code {{ background:#eee; padding:1px 4px; border-radius:3px; }}
    .disclaimer {{
        margin-top:30px;
        padding:12px;
        background:#fffde7;
        border-left:4px solid #f9a825;
        font-size:11px;
        color:#666;
    }}
  .footer {{ margin-top:20px; color:#aaa; font-size:10px; }}
</style>
</head>
<body>
<h1>🚌 CRA Vehicle Lease Compliance Report</h1>
<div class="meta">Generated: {now_str} &nbsp;|&nbsp; Arrow Limo
&nbsp;|&nbsp; All Livery Motor Vehicles</div>

<div class="summary-box"><h3>Total Lease Profiles</h3>
<div class="big">{len(profiles)}</div></div>
<div class="summary-box"><h3>Total GST Charged</h3>
<div class="big">${total_gst:,.2f}</div></div>
<div class="summary-box"><h3>Total ITC Recoverable</h3>
<div class="big" style="color:#27ae60">${total_itc:,.2f}</div></div>
<div class="summary-box"><h3>ITC Verified Profiles</h3>
<div class="big">{sum(1 for r in profiles if r[24])}</div></div>
<div class="summary-box"
style="border-color:{'#e74c3c' if missing_gst_count else '#27ae60'}">
<h3>Missing Lessor GST #</h3>
<div class="big"
style="color:{'#e74c3c' if missing_gst_count else '#27ae60'}">
{missing_gst_count}</div></div>

<table>
<thead>
<tr>
  <th>Vehicle</th><th>Status / Type</th><th>Lessor</th><th>Lease Period</th>
  <th>Payments</th><th>GST / ITC</th><th>CRA Compliance Docs</th>
  <th>Receipts</th><th>Audit Grade</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>

<div class="disclaimer">
    <strong>CRA ITC Notice:</strong> Vehicle lease ITC claims are based on
    business-use percentage.
  Arrow Limo operates exclusively as a livery carrier (100% commercial use). 
  GST estimates are calculated at 5% (Canadian standard rate). 
  Verify actual GST on each lessor invoice before filing. 
    Retain all supporting documents for a minimum of 6 years per CRA
    requirements.
</div>
<p class="footer">Report saved: {html_path}<br>CSV saved: {csv_path}</p>
</body></html>"""

            html_path.write_text(html_content, encoding="utf-8")

            webbrowser.open(html_path.as_uri())
            QMessageBox.information(
                self,
                "CRA Report Generated",
                f"CRA Lease Compliance Report opened in browser.\n\n"
                f"HTML: {html_path}\n"
                f"CSV:  {csv_path}",
            )

        except Exception as e:
            logger.error(f"Failed to generate CRA lease report: {e}")
            QMessageBox.critical(
                self, "Report Error", f"Failed to generate CRA report:\n{e}"
            )

    def _auto_verify_itc_from_receipts(self) -> None:
        """Auto-verify ITC by scanning lease payment receipts and
        extracting GST amounts."""
        if not self.current_vehicle_id:
            QMessageBox.warning(self, "No Vehicle", "Save the vehicle first.")
            return

        try:
            vehicle_type = self.vehicle_type_input.currentText()
            if vehicle_type not in [
                "Livery Motor Vehicle",
                "Passenger Vehicle",
            ]:
                QMessageBox.warning(
                    self,
                    "Unknown Vehicle Type",
                    f"Cannot verify ITC for vehicle type: {vehicle_type}",
                )
                return

            lessor_gst = self.lessor_gst_number_input.text().strip()
            if not lessor_gst:
                QMessageBox.critical(
                    self,
                    "Lessor GST Number Required",
                    "Cannot verify ITC — the Lessor's GST/HST registration "
                    "number is missing.\n\n"
                    "CRA requires this number on every lease invoice to "
                    "support an ITC claim.\n"
                    "Check the lease agreement or monthly invoices for "
                    "the lessor's GST/HST #.",
                )
                return

            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Query receipts linked to this vehicle's lease payments
                # Join on GL codes 2807/2808 (lease liabilities)
                # or category containing 'lease'
                cur.execute(
                    """
                    SELECT 
                        COALESCE(SUM(r.gross_amount), 0)
                            AS total_receipt_amount,
                        COUNT(DISTINCT DATE(r.receipt_date))
                            AS distinct_payment_dates,
                        COUNT(*) as receipt_count,
                        ARRAY_AGG(DISTINCT r.description) as descriptions
                    FROM receipts r
                    WHERE r.vendor_account_id IN (
                        SELECT account_id FROM vendor_accounts 
                        WHERE canonical_vendor ILIKE '%lease%'
                           OR canonical_vendor ILIKE '%rent%'
                    )
                    AND r.receipt_date >= COALESCE(%s, '2010-01-01')
                    AND r.receipt_date <= COALESCE(%s, NOW())
                    AND (
                        r.banking_transaction_id IS NOT NULL
                        OR r.is_paper_verified = TRUE
                    )
                    """,
                    (
                        (
                            self.lease_start_date_input.date().toPython()
                            if self.lease_start_date_input.date().isValid()
                            else None
                        ),
                        (
                            self.lease_end_date_input.date().toPython()
                            if self.lease_end_date_input.date().isValid()
                            else None
                        ),
                    ),
                )
                receipt_row = cur.fetchone()

            if not receipt_row or receipt_row[0] == 0:
                QMessageBox.information(
                    self,
                    "No Receipts Found",
                    "Could not find verified lease payment receipts "
                    "for this period.\n"
                    "Ensure receipts are marked as paper-verified or "
                    "linked to banking transactions.",
                )
                return

            total_receipt = float(receipt_row[0])
            distinct_dates = receipt_row[1]
            receipt_count = receipt_row[2]

            # For livery vehicles, estimate GST as 5% of lease payments
            # (5/105 of total if GST-inclusive)
            # This assumes standard 5% GST rate; adjust if HST applies
            gst_rate = 0.05 if vehicle_type == "Livery Motor Vehicle" else 0.05

            # If receipts are GST-inclusive, back out:
            # GST = Amount * (GST_Rate / (1 + GST_Rate))
            # Standard calculation: GST = Total / 1.05 * 0.05
            # = Total * (5/105) ~= Total * 0.0476
            estimated_gst = total_receipt * (gst_rate / (1.0 + gst_rate))

            # ITC recovery depends on vehicle type and business use %
            business_use = self.business_use_percent_input.value() / 100.0
            itc_recoverable = estimated_gst * business_use

            # Verification conditions
            has_signed = self.has_signed_lease_input.isChecked()
            has_schedule = self.has_payment_schedule_input.isChecked()

            # Mark ITC verified if:
            # - Receipt count >= 1 and at least paper-verified
            #   or banking-linked
            # - Vehicle type is "Livery Motor Vehicle"
            #   (100% business use eligible)
            # - Signed lease + payment schedule on file
            can_verify = (
                receipt_count > 0
                and vehicle_type == "Livery Motor Vehicle"
                and has_signed
                and has_schedule
                and bool(lessor_gst)
            )

            # Update display fields
            self.gst_per_payment_input.setValue(
                estimated_gst / max(distinct_dates, 1)
            )
            # Average per payment
            self.total_gst_input.setValue(estimated_gst)
            self.itc_amount_display.setText(f"${itc_recoverable:.2f}")

            if can_verify:
                self.itc_verified_input.setChecked(True)
                QMessageBox.information(
                    self,
                    "ITC Auto-Verified",
                    f"ITC has been auto-verified based on:\n"
                    f"• {receipt_count} verified lease payment receipt(s)\n"
                    f"• Lessor GST/HST #: {lessor_gst}\n"
                    f"• Estimated GST: ${estimated_gst:.2f}\n"
                    f"• ITC Recoverable "
                    f"({100*business_use:.0f}% business use): "
                    f"${itc_recoverable:.2f}\n"
                    f"• Vehicle Type: {vehicle_type}\n\n"
                    f"Confirm the estimated GST amount if actual GST "
                    f"is known.",
                )
            else:
                self.itc_verified_input.setChecked(False)
                missing_docs = []
                if not has_signed:
                    missing_docs.append("Signed lease agreement")
                if not has_schedule:
                    missing_docs.append("Payment schedule")

                missing_doc_text = (
                    ", ".join(missing_docs)
                    if missing_docs
                    else "No missing documents"
                )

                QMessageBox.warning(
                    self,
                    "ITC Verification Incomplete",
                    f"ITC cannot be verified until required documents are "
                    f"on file:\n"
                    f"• {missing_doc_text}"
                    f"\n\n"
                    f"Estimated GST: ${estimated_gst:.2f}\n"
                    f"ITC Recoverable (if eligible): "
                    f"${itc_recoverable:.2f}",
                )
        except Exception as e:
            logger.error(f"Failed to auto-verify ITC: {e}")
            QMessageBox.critical(
                self,
                "ITC Verification Error",
                f"Failed to verify ITC:\n{e}",
            )
