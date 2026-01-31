"""
Vehicle Management Widget
Comprehensive vehicle CRUD with maintenance tracking, insurance, and documentation
Ported from frontend/src/components/VehicleForm.vue
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QComboBox, QTextEdit, QCheckBox,
    QSpinBox, QDoubleSpinBox, QTabWidget, QFileDialog,
    QListWidget, QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor
import psycopg2
from datetime import datetime, timedelta
import os
import re

from desktop_app.common_widgets import StandardDateEdit


class VehicleManagementWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_vehicle_id = None
        # Detect optional schema features once so the widget can adapt safely
        self.has_vehicle_code = self._column_exists("vehicles", "vehicle_code")
        self.init_ui()
        self.load_vehicles()

    def _column_exists(self, table_name: str, column_name: str, schema: str = "public") -> bool:
        """Return True if the column exists; fallback False on any error."""
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = %s
                LIMIT 1
                """,
                (schema, table_name, column_name),
            )
            return cur.fetchone() is not None
        except Exception:
            return False

    @staticmethod
    def _natural_sort_key(vehicle_number: str):
        """Convert 'L-3', 'L-10', 'L-20' to sortable key: ('L', 3), ('L', 10), ('L', 20)."""
        match = re.match(r'([A-Z]+)[-]?(\d+)', str(vehicle_number).strip())
        if match:
            prefix, num = match.groups()
            return (prefix, int(num))
        return (str(vehicle_number), 0)

    def init_ui(self):
        """Initialize the UI with search and vehicle list (no stats cards)"""
        layout = QVBoxLayout()

        # Search and filter (simplified)
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Vehicle #, make, model, VIN, license plate...")
        self.search_input.textChanged.connect(self.load_vehicles)
        search_layout.addWidget(self.search_input)

        # Status filter: default to "Active"
        search_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Active", "Inactive", "Decommissioned", "All Status"])
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
        self.vehicle_table.setHorizontalHeaderLabels([
            "Vehicle #", "Make", "Model", "Year", "License", "Status",
            "Odometer", "CVIP Due", "Repairs", "Last Service"
        ])
        self.vehicle_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.vehicle_table.itemSelectionChanged.connect(self.load_selected_vehicle)
        left_layout.addWidget(self.vehicle_table)
        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # Right: Vehicle form with tabs
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        # Form tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_identification_tab(), "🆔 Identification")
        self.tabs.addTab(self._create_status_tab(), "📊 Status & Specs")
        self.tabs.addTab(self._create_maintenance_tab(), "🔧 Maintenance")
        self.tabs.addTab(self._create_insurance_tab(), "🛡️ Insurance & Registration")
        self.tabs.addTab(self._create_documents_tab(), "📄 Documents")
        right_layout.addWidget(self.tabs)

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

    def _create_stat_card(self, label, value, color):
        """Create a statistics card widget"""
        group = QGroupBox()
        group.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background-color: #f5f8ff;
            }}
        """)
        layout = QVBoxLayout()
        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        layout.addWidget(text_label)
        group.setLayout(layout)
        return group

    def load_vehicles(self):
        """Load vehicles matching search/filter criteria, with natural sorting"""
        search_text = self.search_input.text().strip()
        status_filter = self.status_filter.currentText()

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()

            # Build query with filters
            query = """
                SELECT 
                    vehicle_id, vehicle_number, make, model, year, license_plate, 
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
                    license_plate ILIKE %s
                )"""
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern] * 5)

            if status_filter != "All Status":
                if status_filter == "Active":
                    query += " AND operational_status IN ('active', 'Active')"
                elif status_filter == "Inactive":
                    query += " AND operational_status IN ('inactive', 'Inactive')"
                elif status_filter == "Decommissioned":
                    query += " AND operational_status IN ('decommissioned', 'retired', 'total loss')"

            query += " ORDER BY vehicle_number"

            cur.execute(query, params)
            vehicles = cur.fetchall()

            # Sort naturally: L-1, L-2, L-3... L-10, L-11, etc.
            vehicles_sorted = sorted(vehicles, key=lambda v: self._natural_sort_key(v[1]))

            self.vehicle_table.setRowCount(len(vehicles_sorted))
            for row_idx, vehicle in enumerate(vehicles_sorted):
                vehicle_id, vehicle_num, make, model, year, license, status, odometer, odometer_type, next_cvip, last_service = vehicle

                items = [
                    QTableWidgetItem(str(vehicle_num) if vehicle_num else ""),
                    QTableWidgetItem(str(make) if make else ""),
                    QTableWidgetItem(str(model) if model else ""),
                    QTableWidgetItem(str(year) if year else ""),
                    QTableWidgetItem(str(license) if license else ""),
                    QTableWidgetItem(str(status) if status else ""),
                    QTableWidgetItem(f"{odometer} {odometer_type}" if odometer else ""),
                    QTableWidgetItem(str(next_cvip)[:10] if next_cvip else "N/A"),
                    QTableWidgetItem("🔴" if self._needs_repairs(vehicle_id) else "✓"),
                    QTableWidgetItem(str(last_service)[:10] if last_service else "N/A"),
                ]
                for col_idx, item in enumerate(items):
                    self.vehicle_table.setItem(row_idx, col_idx, item)

        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Load Error", f"Failed to load vehicles: {e}")

    def _needs_repairs(self, vehicle_id: int) -> bool:
        """Check if vehicle has pending repairs or maintenance due (placeholder)"""
        # TODO: Query maintenance table or service history
        return False

    def _create_identification_tab(self):
        """Create the Identification tab"""
        widget = QWidget()
        layout = QFormLayout()

        self.vehicle_number_input = QLineEdit()
        self.vin_input = QLineEdit()
        self.vehicle_code_input = QLineEdit()
        if not self.has_vehicle_code:
            self.vehicle_code_input.setDisabled(True)
            self.vehicle_code_input.setPlaceholderText("vehicle_code column not present in DB")
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
        self.type_input.addItems([
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
        ])
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

    def _create_status_tab(self):
        """Create the Status & Specs tab"""
        widget = QWidget()
        layout = QFormLayout()

        # Operational Status
        self.operational_status_input = QComboBox()
        self.operational_status_input.addItems([
            "Active",
            "Inactive",
            "Maintenance",
            # Additional statuses present in data imports
            "active",
            "retired",
            "decommissioned",
            "total loss",
            "historical",
        ])
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

    def _create_maintenance_tab(self):
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
        self.maintenance_notes_input = QTextEdit()
        self.maintenance_notes_input.setFixedHeight(100)

        layout.addRow("Next Service Due", self.next_service_due_input)
        layout.addRow("Last Service Date", self.last_service_date_input)
        layout.addRow("Service Type", self.service_type_input)
        layout.addRow("Service Cost", self.service_cost_input)
        layout.addRow("Maintenance Notes", self.maintenance_notes_input)

        widget.setLayout(layout)
        return widget

    def _create_insurance_tab(self):
        """Create the Insurance & Registration tab"""
        widget = QWidget()
        layout = QFormLayout()

        self.insurance_policy_input = QLineEdit()
        self.policy_end_date_input = StandardDateEdit(prefer_month_text=True)
        self.policy_end_date_input.setCalendarPopup(True)
        self.policy_end_date_input.setSpecialValueText("N/A")
        self.registration_expiry_input = StandardDateEdit(prefer_month_text=True)
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

    def _create_documents_tab(self):
        """Create the Documents tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Vehicle Documents (photos, insurance, registration, etc.)"))

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

    def new_vehicle(self):
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
        self.maintenance_notes_input.clear()

        # Insurance
        self.insurance_policy_input.clear()
        self.policy_end_date_input.setDate(QDate.currentDate())
        self.registration_expiry_input.setDate(QDate.currentDate())
        self.financing_status_input.setCurrentText("Owned")
        self.financing_notes_input.clear()

        # Documents
        self.documents_list.clear()

        self.delete_btn.setEnabled(False)
        self.vehicle_number_input.setFocus()

    def load_selected_vehicle(self):
        """Load selected vehicle from table into form"""
        selected = self.vehicle_table.selectedItems()
        if not selected:
            return

        row = self.vehicle_table.row(selected[0])
        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()
            # Get actual columns in vehicles table
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'vehicles'
                ORDER BY ordinal_position
                """
            )
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
                self.vehicle_number_input.setText(row_data.get("vehicle_number") or "")
                self.vin_input.setText(row_data.get("vin_number") or "")
                if self.has_vehicle_code:
                    self.vehicle_code_input.setText(row_data.get("vehicle_code") or "")
                else:
                    self.vehicle_code_input.clear()
                self.fleet_number_input.setText(row_data.get("fleet_number") or "")
                self.fleet_position_input.setValue(row_data.get("fleet_position") or 0)
                self.license_plate_input.setText(row_data.get("license_plate") or "")
                self.make_input.setText(row_data.get("make") or "")
                self.model_input.setText(row_data.get("model") or "")
                self.year_input.setValue(row_data.get("year") or datetime.now().year)

                # Ensure type value is selectable; add on the fly if new
                vehicle_type_val = row_data.get("type") or "Sedan"
                if vehicle_type_val and self.type_input.findText(vehicle_type_val) == -1:
                    self.type_input.addItem(vehicle_type_val)
                self.type_input.setCurrentText(vehicle_type_val)
                self.vehicle_category_input.setText(row_data.get("vehicle_category") or "")
                self.vehicle_class_input.setText(row_data.get("vehicle_class") or "")
                self.passenger_capacity_input.setValue(row_data.get("passenger_capacity") or 0)
                self.description_input.setText(row_data.get("description") or "")

                # Status & Specs
                operational_status_val = row_data.get("operational_status") or "Active"
                if self.operational_status_input.findText(operational_status_val) == -1:
                    self.operational_status_input.addItem(operational_status_val)
                self.operational_status_input.setCurrentText(operational_status_val)
                is_active_val = row_data.get("is_active")
                self.is_active_input.setChecked(is_active_val if is_active_val is not None else True)
                if row_data.get("commission_date"):
                    self.commission_date_input.setDate(QDate.fromString(str(row_data.get("commission_date")), "yyyy-MM-dd"))
                if row_data.get("decommission_date"):
                    self.decommission_date_input.setDate(QDate.fromString(str(row_data.get("decommission_date")), "yyyy-MM-dd"))
                self.ext_color_input.setText(row_data.get("ext_color") or "")
                self.int_color_input.setText(row_data.get("int_color") or "")
                self.length_input.setValue(float(row_data.get("length")) if row_data.get("length") else 0.0)
                self.width_input.setValue(float(row_data.get("width")) if row_data.get("width") else 0.0)
                self.height_input.setValue(float(row_data.get("height")) if row_data.get("height") else 0.0)
                self.odometer_input.setValue(row_data.get("odometer") or 0)

                # Maintenance (only set if columns exist)
                if "next_service_due" in columns and row_data.get("next_service_due"):
                    self.next_service_due_input.setDate(QDate.fromString(str(row_data.get("next_service_due")), "yyyy-MM-dd"))
                if "last_service_date" in columns and row_data.get("last_service_date"):
                    self.last_service_date_input.setDate(QDate.fromString(str(row_data.get("last_service_date")), "yyyy-MM-dd"))
                if "service_type" in columns:
                    self.service_type_input.setText(row_data.get("service_type") or "")
                if "service_cost" in columns:
                    self.service_cost_input.setValue(float(row_data.get("service_cost")) if row_data.get("service_cost") else 0.0)
                if "maintenance_notes" in columns:
                    self.maintenance_notes_input.setText(row_data.get("maintenance_notes") or "")

                # Insurance (only set if columns exist)
                if "insurance_policy_number" in columns:
                    self.insurance_policy_input.setText(row_data.get("insurance_policy_number") or "")
                if "policy_end_date" in columns and row_data.get("policy_end_date"):
                    self.policy_end_date_input.setDate(QDate.fromString(str(row_data.get("policy_end_date")), "yyyy-MM-dd"))
                if "registration_expiry" in columns and row_data.get("registration_expiry"):
                    self.registration_expiry_input.setDate(QDate.fromString(str(row_data.get("registration_expiry")), "yyyy-MM-dd"))
                if "financing_status" in columns:
                    self.financing_status_input.setCurrentText(row_data.get("financing_status") or "Owned")
                if "financing_notes" in columns:
                    self.financing_notes_input.setText(row_data.get("financing_notes") or "")

                self.delete_btn.setEnabled(True)
                self.load_vehicle_documents()

        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load vehicle: {e}")

    def load_vehicles(self):
        """Load vehicles matching search/filter criteria, with natural sorting"""
        search_text = self.search_input.text().strip()
        status_filter = self.status_filter.currentText()

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()

            # Build query with filters
            query = """
                SELECT 
                    vehicle_id, vehicle_number, make, model, year, license_plate, 
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
                    license_plate ILIKE %s
                )"""
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern] * 5)

            if status_filter != "All Status":
                if status_filter == "Active":
                    query += " AND operational_status IN ('active', 'Active')"
                elif status_filter == "Inactive":
                    query += " AND operational_status IN ('inactive', 'Inactive')"
                elif status_filter == "Decommissioned":
                    query += " AND operational_status IN ('decommissioned', 'retired', 'total loss')"

            query += " ORDER BY vehicle_number"

            cur.execute(query, params)
            vehicles = cur.fetchall()

            # Sort naturally: L-1, L-2, L-3... L-10, L-11, etc.
            vehicles_sorted = sorted(vehicles, key=lambda v: self._natural_sort_key(v[1]))

            self.vehicle_table.setRowCount(len(vehicles_sorted))
            for row_idx, vehicle in enumerate(vehicles_sorted):
                vehicle_id, vehicle_num, make, model, year, license, status, odometer, odometer_type, next_cvip, last_service = vehicle

                items = [
                    QTableWidgetItem(str(vehicle_num) if vehicle_num else ""),
                    QTableWidgetItem(str(make) if make else ""),
                    QTableWidgetItem(str(model) if model else ""),
                    QTableWidgetItem(str(year) if year else ""),
                    QTableWidgetItem(str(license) if license else ""),
                    QTableWidgetItem(str(status) if status else ""),
                    QTableWidgetItem(f"{odometer} {odometer_type}" if odometer else ""),
                    QTableWidgetItem(str(next_cvip)[:10] if next_cvip else "N/A"),
                    QTableWidgetItem("🔴" if self._needs_repairs(vehicle_id) else "✓"),
                    QTableWidgetItem(str(last_service)[:10] if last_service else "N/A"),
                ]
                for col_idx, item in enumerate(items):
                    self.vehicle_table.setItem(row_idx, col_idx, item)

        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Load Error", f"Failed to load vehicles: {e}")

    def _needs_repairs(self, vehicle_id: int) -> bool:
        """Check if vehicle has pending repairs or maintenance due (placeholder)"""
        # TODO: Query maintenance table or service history
        return False

    def save_vehicle(self):
        """Save vehicle to database"""
        # Validate required fields
        if not self.vehicle_number_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Vehicle Number is required")
            return
        if not self.make_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Make is required")
            return
        if not self.model_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "Model is required")
            return
        if not self.license_plate_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "License Plate is required")
            return

        try:
            # Rollback any failed transactions first
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            
            cur = self.db.get_cursor()

            # Prepare data
            data = {
                'vehicle_number': self.vehicle_number_input.text().strip(),
                'vin_number': self.vin_input.text().strip() or None,
                'fleet_number': self.fleet_number_input.text().strip() or None,
                'fleet_position': self.fleet_position_input.value() if self.fleet_position_input.value() > 0 else None,
                'license_plate': self.license_plate_input.text().strip(),
                'make': self.make_input.text().strip(),
                'model': self.model_input.text().strip(),
                'year': self.year_input.value(),
                'type': self.type_input.currentText(),
                'vehicle_category': self.vehicle_category_input.text().strip() or None,
                'vehicle_class': self.vehicle_class_input.text().strip() or None,
                'passenger_capacity': self.passenger_capacity_input.value() if self.passenger_capacity_input.value() > 0 else None,
                'description': self.description_input.toPlainText().strip() or None,
                'operational_status': self.operational_status_input.currentText(),
                'is_active': self.is_active_input.isChecked(),
                'commission_date': self.commission_date_input.date().toString("yyyy-MM-dd") if self.commission_date_input.date().isValid() else None,
                'decommission_date': self.decommission_date_input.date().toString("yyyy-MM-dd") if self.decommission_date_input.date().isValid() and self.decommission_date_input.specialValueText() != self.decommission_date_input.text() else None,
                'ext_color': self.ext_color_input.text().strip() or None,
                'int_color': self.int_color_input.text().strip() or None,
                'length': self.length_input.value() if self.length_input.value() > 0 else None,
                'width': self.width_input.value() if self.width_input.value() > 0 else None,
                'height': self.height_input.value() if self.height_input.value() > 0 else None,
                'odometer': self.odometer_input.value() if self.odometer_input.value() > 0 else None,
                'next_service_due': self.next_service_due_input.date().toString("yyyy-MM-dd") if self.next_service_due_input.date().isValid() and self.next_service_due_input.specialValueText() != self.next_service_due_input.text() else None,
                'last_service_date': self.last_service_date_input.date().toString("yyyy-MM-dd") if self.last_service_date_input.date().isValid() and self.last_service_date_input.specialValueText() != self.last_service_date_input.text() else None,
                'service_type': self.service_type_input.text().strip() or None,
                'service_cost': self.service_cost_input.value() if self.service_cost_input.value() > 0 else None,
                'maintenance_notes': self.maintenance_notes_input.toPlainText().strip() or None,
                'insurance_policy_number': self.insurance_policy_input.text().strip() or None,
                'policy_end_date': self.policy_end_date_input.date().toString("yyyy-MM-dd") if self.policy_end_date_input.date().isValid() and self.policy_end_date_input.specialValueText() != self.policy_end_date_input.text() else None,
                'registration_expiry': self.registration_expiry_input.date().toString("yyyy-MM-dd") if self.registration_expiry_input.date().isValid() and self.registration_expiry_input.specialValueText() != self.registration_expiry_input.text() else None,
                'financing_status': self.financing_status_input.currentText(),
                'financing_notes': self.financing_notes_input.toPlainText().strip() or None,
            }

            if self.has_vehicle_code:
                data['vehicle_code'] = self.vehicle_code_input.text().strip() or None

            if self.current_vehicle_id:
                # Update existing vehicle
                update_fields = ', '.join([f"{key} = %s" for key in data.keys()])
                cur.execute(
                    f"UPDATE vehicles SET {update_fields} WHERE vehicle_id = %s",
                    list(data.values()) + [self.current_vehicle_id]
                )
                self.db.commit()
                QMessageBox.information(self, "Success", "Vehicle updated successfully!")
            else:
                # Insert new vehicle
                columns = ', '.join(data.keys())
                placeholders = ', '.join(['%s'] * len(data))
                cur.execute(
                    f"INSERT INTO vehicles ({columns}) VALUES ({placeholders}) RETURNING vehicle_id",
                    list(data.values())
                )
                self.current_vehicle_id = cur.fetchone()[0]
                self.db.commit()
                QMessageBox.information(self, "Success", "Vehicle added successfully!")

            self.load_vehicles()
            self.delete_btn.setEnabled(True)

        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Save Error", f"Failed to save vehicle: {e}")

    def delete_vehicle(self):
        """Delete current vehicle"""
        if not self.current_vehicle_id:
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete vehicle {self.vehicle_number_input.text()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Rollback any failed transactions first
                try:
                    self.db.rollback()
                except:
                    try:
                        self.db.rollback()
                    except:
                        pass
                    pass
                
                cur = self.db.get_cursor()
                cur.execute("DELETE FROM vehicles WHERE vehicle_id = %s", (self.current_vehicle_id,))
                self.db.commit()
                QMessageBox.information(self, "Success", "Vehicle deleted successfully!")
                self.new_vehicle()
                self.load_vehicles()
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Delete Error", f"Failed to delete vehicle: {e}")

    def load_vehicle_documents(self):
        """Load documents for current vehicle (placeholder for future implementation)"""
        self.documents_list.clear()
        if self.current_vehicle_id:
            # TODO: Implement document storage/retrieval
            # For now, show placeholder
            item = QListWidgetItem("📄 Document management coming soon...")
            item.setForeground(QColor("#999"))
            self.documents_list.addItem(item)

    def upload_documents(self):
        """Upload documents for vehicle (placeholder)"""
        if not self.current_vehicle_id:
            QMessageBox.warning(self, "No Vehicle", "Please save the vehicle first before uploading documents.")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Vehicle Documents",
            "",
            "All Files (*);;PDF Files (*.pdf);;Images (*.jpg *.jpeg *.png)"
        )

        if files:
            QMessageBox.information(
                self,
                "Upload",
                f"Selected {len(files)} file(s). Document storage will be implemented in future update."
            )
            # TODO: Implement document storage

    def view_document(self):
        """View selected document (placeholder)"""
        QMessageBox.information(self, "View Document", "Document viewing will be implemented in future update.")

    def delete_document(self):
        """Delete selected document (placeholder)"""
        QMessageBox.information(self, "Delete Document", "Document deletion will be implemented in future update.")
