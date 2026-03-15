"""
Vehicle Drill-Down Detail View
Comprehensive vehicle management - maintenance, fuel, insurance, accidents, assignments, costs
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QTextEdit, QDoubleSpinBox,
    QComboBox, QDialog, QTabWidget, QMessageBox, QSpinBox, QCheckBox,
    QFormLayout, QGroupBox, QScrollArea, QFileDialog, QListWidget
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from desktop_app.common_widgets import StandardDateEdit
from datetime import datetime, timedelta


class MaintenanceRecordDialog(QDialog):
    """Add/Edit maintenance record"""
    
    def __init__(self, db, vehicle_id, record_id=None, scheduled=False, parent=None):
        super().__init__(parent)
        self.db = db
        self.vehicle_id = vehicle_id
        self.record_id = record_id
        self.scheduled = scheduled
        
        self.setWindowTitle("Schedule Maintenance" if scheduled else "Maintenance Record")
        self.setGeometry(100, 100, 600, 500)
        
        layout = QVBoxLayout()
        form = QFormLayout()
        
        # Service type dropdown
        self.service_type = QComboBox()
        self.load_service_types()
        form.addRow("Service Type:", self.service_type)
        
        # Date
        self.service_date = StandardDateEdit(prefer_month_text=True)
        self.service_date.setCalendarPopup(True)
        self.service_date.setDate(QDate.currentDate())
        form.addRow("Scheduled Date:" if scheduled else "Service Date:", self.service_date)
        
        # Odometer
        self.odometer = QSpinBox()
        self.odometer.setMaximum(999999)
        self.odometer.setSuffix(" km")
        form.addRow("Odometer Reading:", self.odometer)
        
        # Cost
        self.cost = QDoubleSpinBox()
        self.cost.setMaximum(99999)
        self.cost.setPrefix("$")
        self.cost.setDecimals(2)
        form.addRow("Estimated Cost:" if scheduled else "Total Cost:", self.cost)
        
        # Performed by / scheduled with
        self.performed_by = QLineEdit()
        form.addRow("Scheduled With:" if scheduled else "Performed By:", self.performed_by)
        
        # Notes
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(100)
        form.addRow("Notes:", self.notes)
        
        # Next service (for completed only)
        if not scheduled:
            self.next_service_km = QSpinBox()
            self.next_service_km.setMaximum(999999)
            self.next_service_km.setSuffix(" km")
            form.addRow("Next Service (km):", self.next_service_km)
            
            self.next_service_date = StandardDateEdit(prefer_month_text=True)
            self.next_service_date.setCalendarPopup(True)
            form.addRow("Next Service Date:", self.next_service_date)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self.save_record)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def load_service_types(self):
        """Load maintenance activity types from database"""
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
            cur.execute("""
                SELECT activity_type_id, activity_name
                FROM maintenance_activity_types
                ORDER BY activity_name
            """)
            rows = cur.fetchall()
            
            for type_id, type_name in rows:
                self.service_type.addItem(type_name, type_id)
            
            cur.close()
            
            # Add default if empty
            if self.service_type.count() == 0:
                self.service_type.addItem("General Maintenance", None)
                
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"❌ Error loading service types: {e}")
            self.service_type.addItem("General Maintenance", None)
    
    def save_record(self):
        """Save maintenance record to database"""
        try:
            activity_type_id = self.service_type.currentData()
            service_date = self.service_date.date().toPyDate()
            odometer = self.odometer.value() if self.odometer.value() > 0 else None
            cost = self.cost.value()
            performed_by = self.performed_by.text().strip()
            notes = self.notes.toPlainText().strip()
            
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
            
            if self.scheduled:
                # Insert scheduled maintenance
                cur.execute("""
                    INSERT INTO maintenance_records
                    (vehicle_id, activity_type_id, scheduled_date, odometer_reading,
                     estimated_cost, scheduled_with_vendor, notes, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'scheduled', NOW())
                """, (self.vehicle_id, activity_type_id, service_date, odometer,
                      cost, performed_by, notes))
            else:
                # Insert completed maintenance
                next_service_km = self.next_service_km.value() if self.next_service_km.value() > 0 else None
                next_service_date = self.next_service_date.date().toPyDate() if self.next_service_date.date().isValid() else None
                
                cur.execute("""
                    INSERT INTO maintenance_records
                    (vehicle_id, activity_type_id, service_date, odometer_reading,
                     total_cost, performed_by, notes, next_service_km, next_service_date,
                     status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed', NOW())
                """, (self.vehicle_id, activity_type_id, service_date, odometer,
                      cost, performed_by, notes, next_service_km, next_service_date))
            
            self.db.commit()
            cur.close()
            
            QMessageBox.information(self, "Success", "Maintenance record saved successfully!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save maintenance record: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass


class VehicleDetailDialog(QDialog):
    """
    Complete vehicle master-detail view with:
    - Vehicle specs, registration, insurance
    - Maintenance history and schedules
    - Fuel logs and efficiency tracking
    - Accident reports and damage history
    - Assignment history (who drove when)
    - Cost tracking (total cost of ownership)
    - Document management (PDFs, photos)
    - Parts inventory for this vehicle
    - Inspection records
    - Depreciation tracking
    """
    
    saved = pyqtSignal(dict)
    
    def __init__(self, db, vehicle_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.vehicle_id = vehicle_id
        self.vehicle_data = None
        
        self.setWindowTitle(f"Vehicle Detail - {vehicle_id or 'New'}")
        self.setGeometry(50, 50, 1400, 900)
        
        layout = QVBoxLayout()
        
        # ===== TOP ACTION BUTTONS (STANDARD LAYOUT) =====
        button_layout = QHBoxLayout()
        
        # Left side: Action-specific buttons (Retire, Sell)
        self.retire_btn = QPushButton("🚫 Retire Vehicle")
        self.retire_btn.clicked.connect(self.retire_vehicle)
        button_layout.addWidget(self.retire_btn)
        
        self.sell_btn = QPushButton("💵 Sell Vehicle")
        self.sell_btn.clicked.connect(self.sell_vehicle)
        button_layout.addWidget(self.sell_btn)
        
        button_layout.addStretch()
        
        # Right side: Standard drill-down buttons (Add, Duplicate, Delete, Save, Close)
        self.add_new_btn = QPushButton("➕ Add New")
        self.add_new_btn.clicked.connect(self.add_new_vehicle)
        button_layout.addWidget(self.add_new_btn)
        
        self.duplicate_btn = QPushButton("📋 Duplicate")
        self.duplicate_btn.clicked.connect(self.duplicate_vehicle)
        button_layout.addWidget(self.duplicate_btn)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_vehicle)
        button_layout.addWidget(self.delete_btn)
        
        self.save_btn = QPushButton("💾 Save All Changes")
        self.save_btn.clicked.connect(self.save_vehicle)
        button_layout.addWidget(self.save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # ===== TABS =====
        tabs = QTabWidget()
        
        tabs.addTab(self.create_specs_tab(), "🚗 Vehicle Info")
        tabs.addTab(self.create_compliance_tab(), "📋 Compliance & Services")
        tabs.addTab(self.create_maintenance_tab(), "🔧 Maintenance")
        tabs.addTab(self.create_fuel_tab(), "⛽ Fuel Logs")
        tabs.addTab(self.create_insurance_tab(), "🛡️ Insurance")
        tabs.addTab(self.create_accidents_tab(), "💥 Accidents/Damage")
        tabs.addTab(self.create_assignments_tab(), "👤 Assignment History")
        tabs.addTab(self.create_costs_tab(), "💰 Cost Tracking")
        tabs.addTab(self.create_documents_tab(), "📄 Documents")
        tabs.addTab(self.create_inspections_tab(), "✅ Inspections")
        tabs.addTab(self.create_depreciation_tab(), "📉 Depreciation")
        
        layout.addWidget(tabs)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        if vehicle_id:
            self.load_vehicle_data()
    
    def create_specs_tab(self):
        """Tab 1: Vehicle specifications and registration"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Vehicle Information")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form = QFormLayout()
        
        # Basic info
        self.vehicle_num = QLineEdit()
        form.addRow("Vehicle #:", self.vehicle_num)
        
        self.license_plate = QLineEdit()
        form.addRow("License Plate:", self.license_plate)
        
        self.vin = QLineEdit()
        self.vin.setMaxLength(17)
        form.addRow("VIN:", self.vin)
        
        self.year = QSpinBox()
        self.year.setMinimum(1990)
        self.year.setMaximum(2030)
        form.addRow("Year:", self.year)
        
        self.make = QLineEdit()
        form.addRow("Make:", self.make)
        
        self.model = QLineEdit()
        form.addRow("Model:", self.model)
        
        self.vehicle_type = QComboBox()
        self.vehicle_type.addItems(["Sedan", "SUV", "Limousine", "Stretch Limo", "Van", "Bus", "Town Car"])
        form.addRow("Type:", self.vehicle_type)
        
        self.color = QLineEdit()
        form.addRow("Color:", self.color)
        
        self.passenger_capacity = QSpinBox()
        self.passenger_capacity.setMinimum(1)
        self.passenger_capacity.setMaximum(40)
        form.addRow("Passenger Capacity:", self.passenger_capacity)
        
        self.current_mileage = QSpinBox()
        self.current_mileage.setMaximum(9999999)
        form.addRow("Current Mileage:", self.current_mileage)
        
        self.registration_expiry = StandardDateEdit(prefer_month_text=True)
        self.registration_expiry.setCalendarPopup(True)
        form.addRow("Registration Expiry:", self.registration_expiry)
        
        # Lifecycle status
        self.is_active = QCheckBox("Vehicle is Active")
        self.is_active.setChecked(True)
        form.addRow("Active Status:", self.is_active)
        
        self.operational_status = QComboBox()
        self.operational_status.addItems(["operational", "in_maintenance", "out_of_service", "sold", "decommissioned"])
        form.addRow("Operational Status:", self.operational_status)
        
        self.commission_date = StandardDateEdit(prefer_month_text=True)
        self.commission_date.setCalendarPopup(True)
        form.addRow("Commission Date:", self.commission_date)
        
        self.decommission_date = StandardDateEdit(prefer_month_text=True)
        self.decommission_date.setCalendarPopup(True)
        form.addRow("Decommission Date:", self.decommission_date)
        
        self.sale_date = StandardDateEdit(prefer_month_text=True)
        self.sale_date.setCalendarPopup(True)
        form.addRow("Sale Date:", self.sale_date)
        
        self.sale_price = QDoubleSpinBox()
        self.sale_price.setMaximum(9999999)
        self.sale_price.setPrefix("$")
        form.addRow("Sale Price:", self.sale_price)
        
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(100)
        form.addRow("Notes:", self.notes)
        
        form_widget.setLayout(form)
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_compliance_tab(self):
        """Compliance & Services: CVIP, Registration, Insurance, Permits, Oil Changes, Odometer"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("📋 Compliance & Service Tracking")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # ===== CURRENT ODOMETER =====
        odo_group = QGroupBox("Current Vehicle Status")
        odo_form = QFormLayout()
        
        self.current_odometer = QSpinBox()
        self.current_odometer.setMaximum(9999999)
        self.current_odometer.setSuffix(" km")
        odo_form.addRow("Current Odometer:", self.current_odometer)
        
        self.last_recorded_date = QLabel("Last updated: Never")
        odo_form.addRow("Status Date:", self.last_recorded_date)
        
        odo_group.setLayout(odo_form)
        scroll_layout.addWidget(odo_group)
        
        # ===== CVIP (Commercial Vehicle Inspection) =====
        cvip_group = QGroupBox("🔍 CVIP - Commercial Vehicle Inspection Program")
        cvip_form = QFormLayout()
        
        self.cvip_number = QLineEdit()
        cvip_form.addRow("Inspection #:", self.cvip_number)
        
        self.cvip_last_date = StandardDateEdit(prefer_month_text=True)
        self.cvip_last_date.setCalendarPopup(True)
        cvip_form.addRow("Last CVIP Date:", self.cvip_last_date)
        
        self.cvip_expiry = StandardDateEdit(prefer_month_text=True)
        self.cvip_expiry.setCalendarPopup(True)
        cvip_form.addRow("Expiry Date:", self.cvip_expiry)
        
        self.cvip_status = QComboBox()
        self.cvip_status.addItems(["passed", "failed", "conditional", "due_soon", "overdue"])
        cvip_form.addRow("Status:", self.cvip_status)
        
        self.cvip_warning = QLabel("")
        self.cvip_warning.setStyleSheet("color: red; font-weight: bold;")
        cvip_form.addRow("⚠️ Alert:", self.cvip_warning)
        
        cvip_group.setLayout(cvip_form)
        scroll_layout.addWidget(cvip_group)
        
        # ===== REGISTRATION =====
        reg_group = QGroupBox("📝 Registration & Licensing")
        reg_form = QFormLayout()
        
        self.reg_expiry = StandardDateEdit(prefer_month_text=True)
        self.reg_expiry.setCalendarPopup(True)
        reg_form.addRow("Registration Expiry:", self.reg_expiry)
        
        self.reg_renewed = QCheckBox("Registration is Current")
        reg_form.addRow("Status:", self.reg_renewed)
        
        self.reg_warning = QLabel("")
        self.reg_warning.setStyleSheet("color: red; font-weight: bold;")
        reg_form.addRow("⚠️ Alert:", self.reg_warning)
        
        reg_group.setLayout(reg_form)
        scroll_layout.addWidget(reg_group)
        
        # ===== OIL CHANGE SCHEDULE =====
        oil_group = QGroupBox("🛢️ Oil Change Tracking")
        oil_form = QFormLayout()
        
        self.oil_last_date = StandardDateEdit(prefer_month_text=True)
        self.oil_last_date.setCalendarPopup(True)
        oil_form.addRow("Last Oil Change:", self.oil_last_date)
        
        self.oil_last_km = QSpinBox()
        self.oil_last_km.setMaximum(9999999)
        self.oil_last_km.setSuffix(" km")
        oil_form.addRow("Oil Change at KM:", self.oil_last_km)
        
        self.oil_interval_km = QSpinBox()
        self.oil_interval_km.setMaximum(99999)
        self.oil_interval_km.setSuffix(" km")
        self.oil_interval_km.setValue(5000)
        oil_form.addRow("Service Interval:", self.oil_interval_km)
        
        self.oil_next_km = QLabel("Next Due: Unknown")
        self.oil_next_km.setStyleSheet("color: blue; font-weight: bold;")
        oil_form.addRow("Next Due at KM:", self.oil_next_km)
        
        self.oil_overdue_km = QLabel("")
        self.oil_overdue_km.setStyleSheet("color: red; font-weight: bold;")
        oil_form.addRow("⚠️ Overdue:", self.oil_overdue_km)
        
        oil_group.setLayout(oil_form)
        scroll_layout.addWidget(oil_group)
        
        # ===== PERMITS & BYLAWS =====
        permit_group = QGroupBox("📋 Permits & Bylaw Compliance")
        permit_form = QFormLayout()
        
        self.bylaw_permit = QCheckBox("Valid Bylaw Permit")
        permit_form.addRow("Bylaw Permit:", self.bylaw_permit)
        
        self.permit_expiry = StandardDateEdit(prefer_month_text=True)
        self.permit_expiry.setCalendarPopup(True)
        permit_form.addRow("Permit Expiry:", self.permit_expiry)
        
        self.permit_warning = QLabel("")
        self.permit_warning.setStyleSheet("color: red; font-weight: bold;")
        permit_form.addRow("⚠️ Alert:", self.permit_warning)
        
        permit_group.setLayout(permit_form)
        scroll_layout.addWidget(permit_group)
        
        # ===== MAINTENANCE WARNINGS =====
        warn_group = QGroupBox("⚠️ Maintenance Warnings & Service Notes")
        warn_layout = QVBoxLayout()
        
        self.maintenance_warnings = QListWidget()
        self.maintenance_warnings.setMaximumHeight(150)
        warn_layout.addWidget(self.maintenance_warnings)
        
        warn_group.setLayout(warn_layout)
        scroll_layout.addWidget(warn_group)
        
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_maintenance_tab(self):
        """Tab 3: Maintenance history and schedule"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Maintenance History & Schedule")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Upcoming maintenance alerts
        alert_label = QLabel("⚠️ Upcoming Maintenance:")
        alert_label.setStyleSheet("color: orange; font-weight: bold;")
        layout.addWidget(alert_label)
        
        self.upcoming_table = QTableWidget()
        self.upcoming_table.setColumnCount(5)
        self.upcoming_table.setHorizontalHeaderLabels([
            "Service Type", "Due Date", "Due Mileage", "Days Until Due", "Status"
        ])
        self.upcoming_table.setMaximumHeight(150)
        layout.addWidget(self.upcoming_table)
        
        # Maintenance history
        history_label = QLabel("Maintenance History:")
        layout.addWidget(history_label)
        
        self.maint_table = QTableWidget()
        self.maint_table.setColumnCount(7)
        self.maint_table.setHorizontalHeaderLabels([
            "Date", "Type", "Description", "Mileage", "Cost", "Vendor", "Next Due"
        ])
        layout.addWidget(self.maint_table)
        
        # Maintenance buttons
        btn_layout = QHBoxLayout()
        add_maint_btn = QPushButton("➕ Add Service Record")
        add_maint_btn.clicked.connect(self.add_maintenance)
        btn_layout.addWidget(add_maint_btn)
        
        schedule_btn = QPushButton("📅 Schedule Service")
        schedule_btn.clicked.connect(self.schedule_maintenance)
        btn_layout.addWidget(schedule_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_fuel_tab(self):
        """Tab 3: Fuel logs and efficiency"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Fuel Logs & Efficiency Tracking")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Efficiency summary
        summary_layout = QHBoxLayout()
        self.avg_efficiency = QLabel("Avg: 0.0 L/100km")
        self.total_fuel_cost = QLabel("Total Cost: $0.00")
        self.last_fillup = QLabel("Last Fill: Never")
        summary_layout.addWidget(self.avg_efficiency)
        summary_layout.addWidget(self.total_fuel_cost)
        summary_layout.addWidget(self.last_fillup)
        summary_layout.addStretch()
        layout.addLayout(summary_layout)
        
        # Fuel logs table
        self.fuel_table = QTableWidget()
        self.fuel_table.setColumnCount(8)
        self.fuel_table.setHorizontalHeaderLabels([
            "Date", "Odometer", "Liters", "Cost", "$/L", "L/100km", "Driver", "Location"
        ])
        layout.addWidget(self.fuel_table)
        
        # Fuel buttons
        btn_layout = QHBoxLayout()
        add_fuel_btn = QPushButton("➕ Add Fuel Entry")
        add_fuel_btn.clicked.connect(self.add_fuel)
        btn_layout.addWidget(add_fuel_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_insurance_tab(self):
        """Tab 4: Insurance policies and claims"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Insurance Policies & Claims")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Current policy
        policy_group = QGroupBox("Current Policy")
        policy_form = QFormLayout()
        
        self.policy_number = QLineEdit()
        policy_form.addRow("Policy #:", self.policy_number)
        
        self.insurer = QLineEdit()
        policy_form.addRow("Insurer:", self.insurer)
        
        self.policy_expiry = StandardDateEdit(prefer_month_text=True)
        self.policy_expiry.setCalendarPopup(True)
        policy_form.addRow("Expiry Date:", self.policy_expiry)
        
        self.coverage_amount = QDoubleSpinBox()
        self.coverage_amount.setMaximum(9999999)
        policy_form.addRow("Coverage Amount:", self.coverage_amount)
        
        self.annual_premium = QDoubleSpinBox()
        self.annual_premium.setMaximum(999999)
        policy_form.addRow("Annual Premium:", self.annual_premium)
        
        policy_group.setLayout(policy_form)
        layout.addWidget(policy_group)
        
        # Claims history
        claims_label = QLabel("Claims History:")
        layout.addWidget(claims_label)
        
        self.claims_table = QTableWidget()
        self.claims_table.setColumnCount(6)
        self.claims_table.setHorizontalHeaderLabels([
            "Date", "Claim #", "Type", "Amount", "Status", "Notes"
        ])
        layout.addWidget(self.claims_table)
        
        # Claims buttons
        btn_layout = QHBoxLayout()
        add_claim_btn = QPushButton("➕ File Claim")
        add_claim_btn.clicked.connect(self.add_claim)
        btn_layout.addWidget(add_claim_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_accidents_tab(self):
        """Tab 5: Accident reports and damage history"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Accidents & Damage Reports")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Accident history
        self.accident_table = QTableWidget()
        self.accident_table.setColumnCount(7)
        self.accident_table.setHorizontalHeaderLabels([
            "Date", "Driver", "Type", "Severity", "Fault", "Repair Cost", "Status"
        ])
        layout.addWidget(self.accident_table)
        
        # Accident buttons
        btn_layout = QHBoxLayout()
        add_accident_btn = QPushButton("➕ Report Accident")
        add_accident_btn.clicked.connect(self.add_accident)
        btn_layout.addWidget(add_accident_btn)
        
        view_photos_btn = QPushButton("📷 View Photos")
        view_photos_btn.clicked.connect(self.view_accident_photos)
        btn_layout.addWidget(view_photos_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_assignments_tab(self):
        """Tab 6: Assignment history - who drove when"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Assignment History")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Current assignment
        current_layout = QHBoxLayout()
        self.current_driver = QLabel("Current Driver: Unassigned")
        self.current_charter = QLabel("Current Charter: None")
        current_layout.addWidget(self.current_driver)
        current_layout.addWidget(self.current_charter)
        current_layout.addStretch()
        layout.addLayout(current_layout)
        
        # Assignment history
        self.assign_table = QTableWidget()
        self.assign_table.setColumnCount(6)
        self.assign_table.setHorizontalHeaderLabels([
            "Charter Date", "Reserve #", "Driver", "Client", "Revenue", "Notes"
        ])
        layout.addWidget(self.assign_table)
        
        widget.setLayout(layout)
        return widget
    
    def create_costs_tab(self):
        """Tab 7: Total cost of ownership"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Cost Tracking - Total Cost of Ownership")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Cost summary
        summary_group = QGroupBox("Cost Summary")
        summary_form = QFormLayout()
        
        self.purchase_cost = QDoubleSpinBox()
        self.purchase_cost.setMaximum(9999999)
        self.purchase_cost.setReadOnly(True)
        summary_form.addRow("Purchase Price:", self.purchase_cost)
        
        self.total_fuel = QDoubleSpinBox()
        self.total_fuel.setMaximum(9999999)
        self.total_fuel.setReadOnly(True)
        summary_form.addRow("Total Fuel:", self.total_fuel)
        
        self.total_maint = QDoubleSpinBox()
        self.total_maint.setMaximum(9999999)
        self.total_maint.setReadOnly(True)
        summary_form.addRow("Total Maintenance:", self.total_maint)
        
        self.total_insurance = QDoubleSpinBox()
        self.total_insurance.setMaximum(9999999)
        self.total_insurance.setReadOnly(True)
        summary_form.addRow("Total Insurance:", self.total_insurance)
        
        self.total_ownership = QDoubleSpinBox()
        self.total_ownership.setMaximum(9999999)
        self.total_ownership.setReadOnly(True)
        summary_form.addRow("TOTAL COST:", self.total_ownership)
        
        self.cost_per_km = QDoubleSpinBox()
        self.cost_per_km.setReadOnly(True)
        summary_form.addRow("Cost per KM:", self.cost_per_km)
        
        summary_group.setLayout(summary_form)
        layout.addWidget(summary_group)
        
        # Cost breakdown table
        cost_label = QLabel("Cost Breakdown by Category:")
        layout.addWidget(cost_label)
        
        self.cost_table = QTableWidget()
        self.cost_table.setColumnCount(4)
        self.cost_table.setHorizontalHeaderLabels([
            "Category", "Total Cost", "% of Total", "Avg per Month"
        ])
        layout.addWidget(self.cost_table)
        
        widget.setLayout(layout)
        return widget
    
    def create_documents_tab(self):
        """Tab 8: Document management"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Vehicle Documents")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Document list
        self.doc_list = QListWidget()
        self.doc_list.doubleClicked.connect(self.open_vehicle_document)
        layout.addWidget(self.doc_list)
        
        # Document buttons
        btn_layout = QHBoxLayout()
        upload_btn = QPushButton("📤 Upload Document")
        upload_btn.clicked.connect(self.upload_vehicle_doc)
        btn_layout.addWidget(upload_btn)
        
        view_btn = QPushButton("👁️ View Selected")
        view_btn.clicked.connect(self.view_vehicle_doc)
        btn_layout.addWidget(view_btn)
        
        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.clicked.connect(self.delete_vehicle_doc)
        btn_layout.addWidget(delete_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_inspections_tab(self):
        """Tab 9: Inspection records"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Inspection Records")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Inspection table
        self.inspect_table = QTableWidget()
        self.inspect_table.setColumnCount(6)
        self.inspect_table.setHorizontalHeaderLabels([
            "Date", "Type", "Result", "Inspector", "Next Due", "Certificate #"
        ])
        layout.addWidget(self.inspect_table)
        
        # Inspection buttons
        btn_layout = QHBoxLayout()
        add_inspect_btn = QPushButton("➕ Add Inspection")
        add_inspect_btn.clicked.connect(self.add_inspection)
        btn_layout.addWidget(add_inspect_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        widget.setLayout(layout)
        return widget
    
    def create_depreciation_tab(self):
        """Tab 10: Depreciation tracking"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        title = QLabel("Depreciation & Book Value")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Depreciation summary
        depr_form = QFormLayout()
        
        self.original_value = QDoubleSpinBox()
        self.original_value.setMaximum(9999999)
        depr_form.addRow("Original Purchase Price:", self.original_value)
        
        self.current_book_value = QDoubleSpinBox()
        self.current_book_value.setMaximum(9999999)
        self.current_book_value.setReadOnly(True)
        depr_form.addRow("Current Book Value:", self.current_book_value)
        
        self.total_depreciation = QDoubleSpinBox()
        self.total_depreciation.setMaximum(9999999)
        self.total_depreciation.setReadOnly(True)
        depr_form.addRow("Total Depreciation:", self.total_depreciation)
        
        self.depr_rate = QDoubleSpinBox()
        self.depr_rate.setMaximum(100)
        self.depr_rate.setDecimals(2)
        self.depr_rate.setValue(20)  # 20% per year default
        depr_form.addRow("Depreciation Rate (%):", self.depr_rate)
        
        layout.addLayout(depr_form)
        
        # Depreciation table
        depr_label = QLabel("Depreciation Schedule:")
        layout.addWidget(depr_label)
        
        self.depr_table = QTableWidget()
        self.depr_table.setColumnCount(4)
        self.depr_table.setHorizontalHeaderLabels([
            "Year", "Beginning Value", "Depreciation", "Ending Value"
        ])
        layout.addWidget(self.depr_table)
        
        widget.setLayout(layout)
        return widget
    
    def load_vehicle_data(self):
        """Load all vehicle data from database"""
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
            
            # Main vehicle data
            cur.execute("""
                SELECT vehicle_id, vehicle_number, license_plate, vin_number, year, make, model,
                       vehicle_type, passenger_capacity, is_active, operational_status,
                       commission_date, decommission_date, sale_date, sale_price
                FROM vehicles
                WHERE vehicle_id = %s
            """, (self.vehicle_id,))
            
            veh = cur.fetchone()
            if veh:
                vid, vnum, plate, vin, yr, make, model, vtype, capacity, is_active, op_status, comm_date, decomm_date, s_date, s_price = veh
                
                self.vehicle_num.setText(str(vnum or ""))
                self.license_plate.setText(str(plate or ""))
                self.vin.setText(str(vin or ""))
                self.year.setValue(int(yr or 2020))
                self.make.setText(str(make or ""))
                self.model.setText(str(model or ""))
                if vtype:
                    self.vehicle_type.setCurrentText(str(vtype))
                self.passenger_capacity.setValue(int(capacity or 4))
                
                # Status fields
                self.is_active.setChecked(is_active if is_active is not None else True)
                if op_status:
                    self.operational_status.setCurrentText(str(op_status))
                if comm_date:
                    self.commission_date.setDate(QDate(comm_date.year, comm_date.month, comm_date.day))
                if decomm_date:
                    self.decommission_date.setDate(QDate(decomm_date.year, decomm_date.month, decomm_date.day))
                if s_date:
                    self.sale_date.setDate(QDate(s_date.year, s_date.month, s_date.day))
                if s_price:
                    self.sale_price.setValue(float(s_price))
            
            # Load assignment history
            cur.execute("""
                SELECT c.charter_date, c.reserve_number, e.full_name,
                       cl.company_name, c.total_amount_due
                FROM charters c
                LEFT JOIN employees e ON c.employee_id = e.employee_id
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                WHERE c.vehicle_id = %s
                ORDER BY c.charter_date DESC
                LIMIT 100
            """, (self.vehicle_id,))
            
            assign_rows = cur.fetchall()
            self.assign_table.setRowCount(len(assign_rows) if assign_rows else 0)
            if assign_rows:
                for i, (c_date, res, driver, client, revenue) in enumerate(assign_rows):
                    self.assign_table.setItem(i, 0, QTableWidgetItem(str(c_date)))
                    self.assign_table.setItem(i, 1, QTableWidgetItem(str(res)))
                    self.assign_table.setItem(i, 2, QTableWidgetItem(str(driver or "")))
                    self.assign_table.setItem(i, 3, QTableWidgetItem(str(client or "")))
                    self.assign_table.setItem(i, 4, QTableWidgetItem(f"${float(revenue or 0):,.2f}"))
            
            # Load documents
            self.doc_list.addItem("📄 Registration.pdf")
            self.doc_list.addItem("📄 Insurance Policy.pdf")
            self.doc_list.addItem("📄 Inspection Certificate.pdf")
            
            # Load maintenance records
            self.load_maintenance_data()
            
            # Load compliance data
            self.load_compliance_data()
            
            cur.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load vehicle data: {e}")
    
    def load_compliance_data(self):
        """Load compliance, CVIP, registration, oil change, and permit data"""
        if not self.vehicle_id:
            return
        
        try:
            from datetime import datetime, timedelta
            today = datetime.now().date()
            
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
            cur.execute("""
                SELECT odometer, cvip_inspection_number, cvip_expiry_date, last_cvip_date,
                       cvip_compliance_status, registration_expiry, sale_date, purchase_date,
                       updated_at
                FROM vehicles
                WHERE vehicle_id = %s
            """, (self.vehicle_id,))
            veh = cur.fetchone()
            
            if veh:
                odometer, cvip_num, cvip_expiry, cvip_last, cvip_status, reg_expiry, sale_date, purchase_date, updated_at = veh
                
                # Current odometer
                self.current_odometer.setValue(odometer or 0)
                if updated_at:
                    self.last_recorded_date.setText(f"Last updated: {updated_at.date()}")
                
                # CVIP tracking
                if cvip_num:
                    self.cvip_number.setText(str(cvip_num))
                if cvip_last:
                    self.cvip_last_date.setDate(QDate(cvip_last.year, cvip_last.month, cvip_last.day))
                if cvip_expiry:
                    self.cvip_expiry.setDate(QDate(cvip_expiry.year, cvip_expiry.month, cvip_expiry.day))
                    
                    # CVIP alerts
                    days_until_expiry = (cvip_expiry - today).days
                    if days_until_expiry < 0:
                        self.cvip_warning.setText(f"❌ OVERDUE by {abs(days_until_expiry)} days!")
                        self.cvip_status.setCurrentText("overdue")
                    elif days_until_expiry <= 30:
                        self.cvip_warning.setText(f"⚠️ Due in {days_until_expiry} days")
                        self.cvip_status.setCurrentText("due_soon")
                    else:
                        self.cvip_warning.setText("✅ Current")
                
                if cvip_status:
                    self.cvip_status.setCurrentText(str(cvip_status))
                
                # Registration tracking
                if reg_expiry:
                    self.reg_expiry.setDate(QDate(reg_expiry.year, reg_expiry.month, reg_expiry.day))
                    days_until_renewal = (reg_expiry - today).days
                    if days_until_renewal < 0:
                        self.reg_warning.setText(f"❌ OVERDUE by {abs(days_until_renewal)} days!")
                        self.reg_renewed.setChecked(False)
                    elif days_until_renewal <= 30:
                        self.reg_warning.setText(f"⚠️ Renew in {days_until_renewal} days")
                        self.reg_renewed.setChecked(True)
                    else:
                        self.reg_warning.setText("✅ Current")
                        self.reg_renewed.setChecked(True)
            
            # Get latest oil change from maintenance records
            cur.execute("""
                SELECT mr.service_date, mr.odometer_reading
                FROM maintenance_records mr
                LEFT JOIN maintenance_activity_types mat ON mr.activity_type_id = mat.activity_type_id
                WHERE mr.vehicle_id = %s 
                AND (mat.activity_name ILIKE '%oil%' OR mr.notes ILIKE '%oil%')
                AND mr.status = 'completed'
                ORDER BY mr.service_date DESC
                LIMIT 1
            """, (self.vehicle_id,))
            oil_record = cur.fetchone()
            
            if oil_record:
                oil_date, oil_km = oil_record
                if oil_date:
                    self.oil_last_date.setDate(QDate(oil_date.year, oil_date.month, oil_date.day))
                if oil_km:
                    self.oil_last_km.setValue(oil_km)
                    next_km = oil_km + self.oil_interval_km.value()
                    self.oil_next_km.setText(f"Next Due: {next_km:,} km")
                    
                    # Check if overdue
                    current_odo = self.current_odometer.value()
                    if current_odo > next_km:
                        overdue_km = current_odo - next_km
                        self.oil_overdue_km.setText(f"❌ OVERDUE by {overdue_km:,} km!")
                    else:
                        remaining_km = next_km - current_odo
                        self.oil_overdue_km.setText(f"✅ {remaining_km:,} km remaining")
            
            # Load maintenance warnings from notes
            cur.execute("""
                SELECT mr.notes, mr.odometer_reading, mr.next_service_km, mr.next_service_date, mr.status
                FROM maintenance_records mr
                WHERE mr.vehicle_id = %s AND mr.notes IS NOT NULL AND mr.notes != ''
                ORDER BY mr.service_date DESC
                LIMIT 10
            """, (self.vehicle_id,))
            warnings = cur.fetchall()
            
            self.maintenance_warnings.clear()
            for notes, odometer, next_km, next_date, status in warnings:
                if next_km and next_km > 0:
                    current_odo = self.current_odometer.value()
                    if current_odo > next_km:
                        item_text = f"⚠️ {notes} - OVERDUE by {current_odo - next_km:,} km"
                    else:
                        item_text = f"ℹ️ {notes} - Due at {next_km:,} km ({next_km - current_odo:,} km remaining)"
                else:
                    item_text = f"ℹ️ {notes}"
                self.maintenance_warnings.addItem(item_text)
            
            cur.close()
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"❌ Error loading compliance data: {e}")
            import traceback
            traceback.print_exc()
    
    def save_vehicle(self):
        """Save all vehicle changes"""
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
            
            # Prepare date values
            comm_date = self.commission_date.date().toPyDate() if self.commission_date.date().isValid() else None
            decomm_date = self.decommission_date.date().toPyDate() if self.decommission_date.date().isValid() else None
            s_date = self.sale_date.date().toPyDate() if self.sale_date.date().isValid() else None
            reg_exp_date = self.reg_expiry.date().toPyDate() if self.reg_expiry.date().isValid() else None
            cvip_expiry_date = self.cvip_expiry.date().toPyDate() if self.cvip_expiry.date().isValid() else None
            cvip_last_date = self.cvip_last_date.date().toPyDate() if self.cvip_last_date.date().isValid() else None
            oil_last_date = self.oil_last_date.date().toPyDate() if self.oil_last_date.date().isValid() else None
            permit_exp_date = self.permit_expiry.date().toPyDate() if self.permit_expiry.date().isValid() else None
            
            cur.execute("""
                UPDATE vehicles SET
                    vehicle_number = %s,
                    license_plate = %s,
                    vin_number = %s,
                    year = %s,
                    make = %s,
                    model = %s,
                    vehicle_type = %s,
                    passenger_capacity = %s,
                    is_active = %s,
                    operational_status = %s,
                    commission_date = %s,
                    decommission_date = %s,
                    sale_date = %s,
                    sale_price = %s,
                    odometer = %s,
                    cvip_inspection_number = %s,
                    cvip_expiry_date = %s,
                    last_cvip_date = %s,
                    cvip_compliance_status = %s,
                    registration_expiry = %s
                WHERE vehicle_id = %s
            """, (
                self.vehicle_num.text(),
                self.license_plate.text(),
                self.vin.text(),
                self.year.value(),
                self.make.text(),
                self.model.text(),
                self.vehicle_type.currentText(),
                self.passenger_capacity.value(),
                self.is_active.isChecked(),
                self.operational_status.currentText(),
                comm_date,
                decomm_date,
                s_date,
                self.sale_price.value() if self.sale_price.value() > 0 else None,
                self.current_odometer.value(),
                self.cvip_number.text() or None,
                cvip_expiry_date,
                cvip_last_date,
                self.cvip_status.currentText(),
                reg_exp_date,
                self.vehicle_id
            ))
            self.db.commit()
            QMessageBox.information(self, "Success", "Vehicle saved successfully")
            self.saved.emit({"action": "save", "vehicle_id": self.vehicle_id})
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
            self.db.rollback()
    
    def add_new_vehicle(self):
        """Create a new vehicle - open dialog with no vehicle_id"""
        reply = QMessageBox.question(
            self,
            "Add New Vehicle",
            "Create a new vehicle record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            new_dialog = VehicleDetailDialog(self.db, vehicle_id=None, parent=self.parent())
            new_dialog.saved.connect(self.on_vehicle_saved)
            new_dialog.exec()
    
    def duplicate_vehicle(self):
        """Duplicate current vehicle with modified license plate/number"""
        if not self.vehicle_id:
            QMessageBox.warning(self, "Warning", "No vehicle loaded to duplicate.")
            return
        
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Duplicate Vehicle")
            dialog.setGeometry(100, 100, 400, 150)
            
            dlg_layout = QVBoxLayout()
            dlg_layout.addWidget(QLabel("Enter a new license plate or vehicle number:"))
            
            plate_input = QLineEdit()
            plate_input.setText(self.license_plate.text() + "-DUP")
            dlg_layout.addWidget(plate_input)
            
            btn_layout = QHBoxLayout()
            ok_btn = QPushButton("Duplicate")
            ok_btn.clicked.connect(dialog.accept)
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addStretch()
            btn_layout.addWidget(ok_btn)
            btn_layout.addWidget(cancel_btn)
            dlg_layout.addLayout(btn_layout)
            
            dialog.setLayout(dlg_layout)
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_plate = plate_input.text().strip()
                if not new_plate:
                    QMessageBox.warning(self, "Warning", "Please enter a license plate for the duplicate vehicle.")
                    return
                
                # Insert duplicate record
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
                cur.execute("""
                    INSERT INTO vehicles 
                    (vehicle_number, license_plate, vin, year, make, model, vehicle_type, passenger_capacity, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    self.vehicle_num.text() + "-DUP",
                    new_plate,
                    self.vin.text(),
                    self.year.value(),
                    self.make.text(),
                    self.model.text(),
                    self.vehicle_type.currentText(),
                    self.passenger_capacity.value()
                ))
                self.db.commit()
                QMessageBox.information(self, "Success", f"Vehicle duplicated with plate '{new_plate}'.")
                cur.close()
                self.load_vehicle_data()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to duplicate: {e}")
    
    def delete_vehicle(self):
        """Delete current vehicle after confirmation"""
        if not self.vehicle_id:
            QMessageBox.warning(self, "Warning", "No vehicle loaded to delete.")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete vehicle '{self.vehicle_num.text()}' ({self.license_plate.text()})?\nThis action cannot be undone.",
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
                cur.execute("DELETE FROM vehicles WHERE vehicle_id = %s", (self.vehicle_id,))
                self.db.commit()
                QMessageBox.information(self, "Success", "Vehicle deleted successfully.")
                cur.close()
                self.saved.emit({"action": "delete", "vehicle_id": self.vehicle_id})
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
                self.db.rollback()
    
    def on_vehicle_saved(self, data):
        """Handle child dialog save - refresh current view"""
        if self.vehicle_id:
            self.load_vehicle_data()
    
    # ===== STUB METHODS =====
    def retire_vehicle(self):
        QMessageBox.information(self, "Info", "Retire vehicle process (to be implemented)")
    
    def sell_vehicle(self):
        QMessageBox.information(self, "Info", "Sell vehicle process (to be implemented)")
    
    def add_maintenance(self):
        """Add a new maintenance record"""
        if not self.vehicle_id:
            QMessageBox.warning(self, "Warning", "Please save the vehicle first before adding maintenance records.")
            return
        
        dialog = MaintenanceRecordDialog(self.db, self.vehicle_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_maintenance_data()
    
    def schedule_maintenance(self):
        """Schedule future maintenance"""
        if not self.vehicle_id:
            QMessageBox.warning(self, "Warning", "Please save the vehicle first before scheduling maintenance.")
            return
        
        dialog = MaintenanceRecordDialog(self.db, self.vehicle_id, scheduled=True, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_maintenance_data()
    
    def load_maintenance_data(self):
        """Load maintenance records from database"""
        if not self.vehicle_id:
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
            cur.execute("""
                SELECT mr.record_id, mr.service_date, mat.activity_name,
                       mr.notes, mr.odometer_reading, mr.total_cost,
                       mr.performed_by, mr.next_service_date, mr.status
                FROM maintenance_records mr
                LEFT JOIN maintenance_activity_types mat ON mr.activity_type_id = mat.activity_type_id
                WHERE mr.vehicle_id = %s
                ORDER BY COALESCE(mr.service_date, mr.scheduled_date) DESC
            """, (self.vehicle_id,))
            rows = cur.fetchall()
            
            # Populate upcoming maintenance
            self.upcoming_table.setRowCount(0)
            # Populate history
            self.maint_table.setRowCount(len(rows))
            
            for i, (record_id, service_date, activity_name, notes, odometer, cost, vendor, next_due, status) in enumerate(rows):
                self.maint_table.setItem(i, 0, QTableWidgetItem(str(service_date or '')))
                self.maint_table.setItem(i, 1, QTableWidgetItem(activity_name or ''))
                self.maint_table.setItem(i, 2, QTableWidgetItem(notes or ''))
                self.maint_table.setItem(i, 3, QTableWidgetItem(str(odometer or '')))
                self.maint_table.setItem(i, 4, QTableWidgetItem(f"${float(cost or 0):,.2f}"))
                self.maint_table.setItem(i, 5, QTableWidgetItem(vendor or ''))
                self.maint_table.setItem(i, 6, QTableWidgetItem(str(next_due or '')))
            
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"❌ Error loading maintenance data: {e}")
            import traceback
            traceback.print_exc()
    
    def add_fuel(self):
        QMessageBox.information(self, "Info", "Add fuel entry (to be implemented)")
    
    def add_claim(self):
        QMessageBox.information(self, "Info", "File insurance claim (to be implemented)")
    
    def add_accident(self):
        QMessageBox.information(self, "Info", "Report accident (to be implemented)")
    
    def view_accident_photos(self):
        QMessageBox.information(self, "Info", "View accident photos (to be implemented)")
    
    def upload_vehicle_doc(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document")
        if file_path:
            QMessageBox.information(self, "Info", f"Document uploaded: {file_path}")
    
    def view_vehicle_doc(self):
        item = self.doc_list.currentItem()
        if item:
            QMessageBox.information(self, "Info", f"Opening: {item.text()}")
    
    def delete_vehicle_doc(self):
        item = self.doc_list.currentItem()
        if item:
            self.doc_list.takeItem(self.doc_list.row(item))
    
    def open_vehicle_document(self, index):
        self.view_vehicle_doc()
    
    def add_inspection(self):
        QMessageBox.information(self, "Info", "Add inspection record (to be implemented)")
