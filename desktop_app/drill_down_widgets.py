"""
Drill-Down Detail View Widgets for Dashboard Data
Provides double-click detail views with edit, lock, cancel, and drill-down capabilities

CHARTER DETAIL: Reserve numbers, payments, orders, routing
EMPLOYEE DETAIL: See employee_drill_down.py for comprehensive employee management
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QTextEdit, QDoubleSpinBox,
    QComboBox, QDialog, QTabWidget, QMessageBox, QSpinBox, QCheckBox,
    QFormLayout, QGroupBox, QScrollArea, QHeaderView, QDialogButtonBox,
    QTimeEdit
)
from PyQt6.QtCore import Qt, QDate, QTime, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QBrush
from desktop_app.common_widgets import StandardDateEdit
from datetime import datetime
from difflib import SequenceMatcher
import os


class CharterDetailDialog(QDialog):
    """Master-detail view for a single charter with drill-down capability"""
    
    saved = pyqtSignal(dict)  # Emit when changes saved
    
    def __init__(self, db, reserve_number=None, parent=None, initial_tab=None, client_id=None):
        super().__init__(parent)
        self.db = db
        self.reserve_number = reserve_number
        self.client_id = client_id  # Pre-selected client for new charters
        self.is_locked = False
        self.charter_data = None
        
        # Initialize vehicle type/category maps (will be populated by load_vehicle_options)
        self._vehicle_types = {}
        self._vehicle_categories = {}
        
        self.setWindowTitle(f"Charter Detail - {reserve_number or 'New'}")
        self.setGeometry(100, 100, 1400, 950)
        
        layout = QVBoxLayout()
        
        # ===== TOP ACTION BUTTONS (STANDARD LAYOUT) =====
        button_layout = QHBoxLayout()
        
        # Left side: Action-specific buttons (Lock, Unlock, Cancel)
        self.lock_btn = QPushButton("🔒 Lock Charter")
        self.lock_btn.clicked.connect(self.lock_charter)
        button_layout.addWidget(self.lock_btn)
        
        self.cancel_btn = QPushButton("❌ Cancel Charter")
        self.cancel_btn.clicked.connect(self.cancel_charter)
        button_layout.addWidget(self.cancel_btn)
        
        self.unlock_btn = QPushButton("🔓 Unlock Charter")
        self.unlock_btn.clicked.connect(self.unlock_charter)
        self.unlock_btn.setEnabled(False)
        button_layout.addWidget(self.unlock_btn)
        
        button_layout.addStretch()
        
        # Right side: Standard drill-down buttons (Add, Duplicate, Delete, Save, Close)
        self.add_new_btn = QPushButton("➕ Add New")
        self.add_new_btn.clicked.connect(self.add_new_charter)
        button_layout.addWidget(self.add_new_btn)
        
        self.duplicate_btn = QPushButton("📋 Duplicate")
        self.duplicate_btn.clicked.connect(self.duplicate_charter)
        button_layout.addWidget(self.duplicate_btn)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_charter)
        button_layout.addWidget(self.delete_btn)
        
        self.save_btn = QPushButton("💾 Save Changes")
        self.save_btn.clicked.connect(self.save_charter)
        button_layout.addWidget(self.save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # ===== TABS =====
        tabs = QTabWidget()
        
        # Tab 1: Charter Master Data
        master_tab = self.create_master_tab()
        tabs.addTab(master_tab, "Charter Details")
        
        # Tab 2: Invoice Details (NEW)
        invoice_tab = self.create_invoice_details_tab()
        tabs.addTab(invoice_tab, "📄 Invoice Details")
        
        # Tab 3: Related Orders/Beverages
        orders_tab = self.create_orders_tab()
        tabs.addTab(orders_tab, "Orders & Beverages")
        
        # Tab 3.5: Beverage Printout (NEW)
        beverage_tab = self.create_beverage_printout_tab()
        tabs.addTab(beverage_tab, "🍷 Beverage Printout")
        
        # Tab 4: Routing & Charges
        routing_tab = self.create_routing_tab()
        tabs.addTab(routing_tab, "Routing & Charges")
        
        # Tab 5: Payments
        payments_tab = self.create_payments_tab()
        tabs.addTab(payments_tab, "Payments")
        
        # Expose tabs for programmatic selection
        self.tabs = tabs

        layout.addWidget(tabs)
        self.setLayout(layout)
        
        # Load dropdown options BEFORE loading data
        self.load_driver_options()
        self.load_vehicle_options()
        
        # If client_id is provided (pre-selected for new charter), load that client info
        if client_id and not reserve_number:
            self.load_client_info(client_id)
        
        # Load data if reserve_number provided
        if reserve_number:
            self.load_charter_data()

        # Optionally select a starting tab
        if initial_tab:
            tab_map = {
                'details': 0,
                'invoice': 1,
                'orders': 2,
                'routing': 3,
                'payments': 4,
            }
            idx = tab_map.get(str(initial_tab).lower())
            if idx is not None:
                self.tabs.setCurrentIndex(idx)

    def _get_allowed_payment_methods(self):
        """Fetch allowed payment methods from existing data; fall back to policy list.
        This does not enable online charging; it's only for manual recording UI.
        """
        fallback = [
            "cash",
            "check",
            "credit_card",
            "debit_card",
            "bank_transfer",
            "trade_of_services",
            "unknown",
            "credit_adjustment",
        ]
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
                SELECT DISTINCT payment_method
                FROM payments
                WHERE payment_method IS NOT NULL AND payment_method <> ''
                ORDER BY payment_method
            """)
            rows = cur.fetchall()
            cur.close()
            methods = [str(r[0]) for r in rows if r and r[0]]
            # Ensure methods intersect with known policy; preserve order
            if methods:
                policy_set = set(fallback)
                filtered = [m for m in methods if m in policy_set]
                # If DB had extra values not in policy, append them for visibility
                extras = [m for m in methods if m not in policy_set]
                return filtered + extras if filtered or extras else fallback
            return fallback
        except Exception:
            return fallback
    
    def load_driver_options(self):
        """Load all available drivers into the driver dropdown"""
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
                SELECT employee_id, full_name 
                FROM employees 
                WHERE is_active = true OR is_active IS NULL
                ORDER BY full_name
            """)
            drivers = cur.fetchall()
            cur.close()
            
            self.driver.clear()
            self.driver.addItem("")  # Add empty option
            for emp_id, name in drivers:
                self.driver.addItem(str(name or ""), emp_id)
        except Exception as e:
            # Silently fail - driver list just won't populate
            pass
    
    def load_vehicle_options(self):
        """Load all available vehicles into both vehicle dropdowns"""
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
                SELECT vehicle_id, vehicle_number, vehicle_type, vehicle_category, status
                FROM vehicles
                ORDER BY
                    CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                    CASE
                        WHEN vehicle_number ~ '^[Ll]-?\\d+$' THEN CAST(regexp_replace(vehicle_number, '[^0-9]', '', 'g') AS INT)
                        ELSE 9999
                    END,
                    vehicle_number
                """
            )
            vehicles = cur.fetchall()
            cur.close()
            
            # Store vehicle type and category for label updates
            self._vehicle_types = {}
            self._vehicle_categories = {}
            
            # Clear and populate both dropdowns
            self.vehicle.clear()
            self.vehicle_requested.clear()
            self.vehicle.addItem("")  # Add empty option
            self.vehicle_requested.addItem("")  # Add empty option
            
            for veh_id, number, vtype, vcat, status in vehicles:
                display_number = str(number or "")
                self.vehicle.addItem(display_number, veh_id)
                self.vehicle_requested.addItem(display_number, veh_id)
                self._vehicle_types[veh_id] = vtype or ""
                self._vehicle_categories[veh_id] = vcat or ""
            
            # Wire up selection callbacks for type/category labels
            self.vehicle.currentIndexChanged.connect(self._update_vehicle_type_display)
            self.vehicle_requested.currentIndexChanged.connect(self._update_vehicle_requested_display)
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            # Silently fail - vehicle list just won't populate
            pass
    
    def _update_vehicle_type_display(self):
        """Update vehicle type label when vehicle selection changes"""
        try:
            veh_id = self.vehicle.currentData()
            if veh_id and veh_id in self._vehicle_types:
                self.vehicle_type_label.setText(self._vehicle_types[veh_id])
            else:
                self.vehicle_type_label.setText("")
        except:
            self.vehicle_type_label.setText("")
    
    def _update_vehicle_requested_display(self):
        """Update vehicle requested category label when selection changes"""
        try:
            veh_id = self.vehicle_requested.currentData()
            if veh_id and veh_id in self._vehicle_categories:
                self.vehicle_requested_type_label.setText(self._vehicle_categories[veh_id])
            else:
                self.vehicle_requested_type_label.setText("")
        except:
            self.vehicle_requested_type_label.setText("")
    
    def create_master_tab(self):
        """Tab 1: Charter master data - LMSGold style layout with organized sections"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Scroll area for form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(4, 4, 4, 4)
        
        # ===== SECTION 1: RESERVATION INFORMATION =====
        sec1_title = QLabel("RESERVATION INFORMATION")
        sec1_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec1_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec1_title)
        
        # Row 1a: Reserve # and Charter Date (2 columns)
        row1a = QHBoxLayout()
        res_label = QLabel("Reserve #:")
        res_label.setMinimumWidth(100)
        self.res_num = QLineEdit()
        self.res_num.setReadOnly(True)
        self.res_num.setMaximumWidth(100)
        row1a.addWidget(res_label)
        row1a.addWidget(self.res_num)
        row1a.addSpacing(30)
        
        date_label = QLabel("Charter Date:")
        date_label.setMinimumWidth(100)
        self.charter_date = StandardDateEdit(prefer_month_text=True)
        self.charter_date.setCalendarPopup(True)
        self.charter_date.setMaximumWidth(150)
        row1a.addWidget(date_label)
        row1a.addWidget(self.charter_date)
        row1a.addStretch()
        form_layout.addLayout(row1a)
        
        # Row 1b: Client Name and Status
        row1b = QHBoxLayout()
        client_label = QLabel("Client Name:")
        client_label.setMinimumWidth(100)
        
        # Client selection with button
        client_select_layout = QHBoxLayout()
        self.client = QLineEdit()
        self.client.setReadOnly(True)
        self.client.setMaximumWidth(250)
        self.client.setPlaceholderText("Click 'Select Client' to choose...")
        client_select_layout.addWidget(self.client)
        
        select_client_btn = QPushButton("🔍 Select Client")
        select_client_btn.setMaximumWidth(130)
        select_client_btn.clicked.connect(self.select_client_dialog)
        client_select_layout.addWidget(select_client_btn)
        
        row1b.addWidget(client_label)
        row1b.addLayout(client_select_layout)
        row1b.addSpacing(30)
        
        status_label = QLabel("Status:")
        status_label.setMinimumWidth(100)
        self.status = QComboBox()
        self.status.addItems(["Confirmed", "In Progress", "Completed", "Closed", "Cancelled"])
        self.status.setMaximumWidth(150)
        row1b.addWidget(status_label)
        row1b.addWidget(self.status)
        row1b.addStretch()
        form_layout.addLayout(row1b)
        
        # Row 1c: Account and Source
        row1c = QHBoxLayout()
        account_label = QLabel("Account:")
        account_label.setMinimumWidth(100)
        self.account = QLineEdit()
        self.account.setMaximumWidth(150)
        row1c.addWidget(account_label)
        row1c.addWidget(self.account)
        row1c.addSpacing(30)
        
        source_label = QLabel("Source:")
        source_label.setMinimumWidth(100)
        self.source = QComboBox()
        self.source.addItems(["Phone", "Email", "Walk-in", "Online", "Referral", "Other"])
        self.source.setMaximumWidth(150)
        row1c.addWidget(source_label)
        row1c.addWidget(self.source)
        row1c.addStretch()
        form_layout.addLayout(row1c)
        
        # ===== SECTION 2: CHARTER DETAILS =====
        sec2_title = QLabel("CHARTER DETAILS")
        sec2_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec2_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec2_title)
        
        # Row 2a: Passengers and Pickup Time
        row2a = QHBoxLayout()
        pax_label = QLabel("Passengers:")
        pax_label.setMinimumWidth(100)
        self.passenger_count = QSpinBox()
        self.passenger_count.setMinimum(1)
        self.passenger_count.setMaximum(14)
        self.passenger_count.setMaximumWidth(100)
        row2a.addWidget(pax_label)
        row2a.addWidget(self.passenger_count)
        row2a.addSpacing(30)
        
        time_label = QLabel("Pickup Time:")
        time_label.setMinimumWidth(100)
        self.pickup_time = QTimeEdit()
        self.pickup_time.setDisplayFormat("HH:mm")
        self.pickup_time.setMaximumWidth(100)
        row2a.addWidget(time_label)
        row2a.addWidget(self.pickup_time)
        row2a.addStretch()
        form_layout.addLayout(row2a)
        
        # ===== SECTION 3: VEHICLE ASSIGNMENT =====
        sec3_title = QLabel("VEHICLE ASSIGNMENT")
        sec3_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec3_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec3_title)
        
        # Row 3a: Vehicle Requested
        row3a = QHBoxLayout()
        veh_req_label = QLabel("Vehicle Requested:")
        veh_req_label.setMinimumWidth(100)
        self.vehicle_requested = QComboBox()
        self.vehicle_requested.setMaximumWidth(180)
        self.vehicle_requested_type_label = QLabel("")
        self.vehicle_requested_type_label.setStyleSheet("color:#666; font-size: 11px;")
        self.vehicle_requested_type_label.setMaximumWidth(120)
        row3a.addWidget(veh_req_label)
        row3a.addWidget(self.vehicle_requested)
        row3a.addWidget(self.vehicle_requested_type_label)
        row3a.addStretch()
        form_layout.addLayout(row3a)
        
        # Row 3b: Vehicle Assigned
        row3b = QHBoxLayout()
        veh_label = QLabel("Vehicle Assigned:")
        veh_label.setMinimumWidth(100)
        self.vehicle = QComboBox()
        self.vehicle.setMaximumWidth(180)
        self.vehicle_type_label = QLabel("")
        self.vehicle_type_label.setStyleSheet("color:#666; font-size: 11px;")
        self.vehicle_type_label.setMaximumWidth(120)
        row3b.addWidget(veh_label)
        row3b.addWidget(self.vehicle)
        row3b.addWidget(self.vehicle_type_label)
        row3b.addStretch()
        form_layout.addLayout(row3b)
        
        # Row 3c: Driver
        row3c = QHBoxLayout()
        driver_label = QLabel("Driver:")
        driver_label.setMinimumWidth(100)
        self.driver = QComboBox()
        self.driver.setMaximumWidth(200)
        row3c.addWidget(driver_label)
        row3c.addWidget(self.driver)
        row3c.addStretch()
        form_layout.addLayout(row3c)
        
        # ===== COST CORNER (SIMPLIFIED) =====
        costcorner_title = QLabel("COST CORNER")
        costcorner_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        costcorner_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(costcorner_title)
        
        # Cost Corner - Base Charge and Extras
        costrow1 = QHBoxLayout()
        base_label = QLabel("Base Charge:")
        base_label.setMinimumWidth(100)
        self.base_charge = QDoubleSpinBox()
        self.base_charge.setMinimum(0)
        self.base_charge.setMaximum(999999)
        self.base_charge.setDecimals(2)
        self.base_charge.setPrefix("$")
        self.base_charge.setMaximumWidth(130)
        costrow1.addWidget(base_label)
        costrow1.addWidget(self.base_charge)
        costrow1.addSpacing(30)
        
        extras_label = QLabel("Extra Charges:")
        extras_label.setMinimumWidth(100)
        self.extra_charges = QDoubleSpinBox()
        self.extra_charges.setMinimum(0)
        self.extra_charges.setMaximum(999999)
        self.extra_charges.setDecimals(2)
        self.extra_charges.setPrefix("$")
        self.extra_charges.setMaximumWidth(130)
        costrow1.addWidget(extras_label)
        costrow1.addWidget(self.extra_charges)
        costrow1.addStretch()
        form_layout.addLayout(costrow1)
        sec4_title = QLabel("ROUTE INFORMATION")
        sec4_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec4_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec4_title)
        
        # Row 4a: Pickup Location
        row4a_label = QLabel("Pickup Location:")
        row4a_label.setMinimumWidth(100)
        self.pickup = QLineEdit()
        self.pickup.setPlaceholderText("Starting point")
        row4a = QHBoxLayout()
        row4a.addWidget(row4a_label)
        row4a.addWidget(self.pickup)
        form_layout.addLayout(row4a)
        
        # Row 4b: Destination
        row4b_label = QLabel("Destination:")
        row4b_label.setMinimumWidth(100)
        self.destination = QLineEdit()
        self.destination.setPlaceholderText("End point")
        row4b = QHBoxLayout()
        row4b.addWidget(row4b_label)
        row4b.addWidget(self.destination)
        form_layout.addLayout(row4b)
        
        # Row 4c: Route Description
        route_label = QLabel("Route Description:")
        route_label.setMinimumWidth(100)
        self.route_description = QLineEdit()
        self.route_description.setPlaceholderText("e.g., Leave Red Deer for Calgary, return to Red Deer")
        self.route_description.setMaximumHeight(35)
        row4c = QHBoxLayout()
        row4c.addWidget(route_label)
        row4c.addWidget(self.route_description)
        form_layout.addLayout(row4c)
        
        # ===== SECTION 5: FINANCIAL SUMMARY =====
        sec5_title = QLabel("FINANCIAL SUMMARY")
        sec5_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec5_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec5_title)
        
        # Row 5a: Amounts
        row5a = QHBoxLayout()
        
        total_label = QLabel("Total Amount:")
        total_label.setMinimumWidth(100)
        self.total_amount = QDoubleSpinBox()
        self.total_amount.setMinimum(0)
        self.total_amount.setMaximum(999999)
        self.total_amount.setDecimals(2)
        self.total_amount.setPrefix("$")
        self.total_amount.setMaximumWidth(130)
        row5a.addWidget(total_label)
        row5a.addWidget(self.total_amount)
        row5a.addSpacing(30)
        
        paid_label = QLabel("Amount Paid:")
        paid_label.setMinimumWidth(100)
        self.amount_paid = QDoubleSpinBox()
        self.amount_paid.setMinimum(0)
        self.amount_paid.setMaximum(999999)
        self.amount_paid.setDecimals(2)
        self.amount_paid.setPrefix("$")
        self.amount_paid.setReadOnly(True)
        self.amount_paid.setMaximumWidth(130)
        row5a.addWidget(paid_label)
        row5a.addWidget(self.amount_paid)
        row5a.addSpacing(30)
        
        due_label = QLabel("Balance Due:")
        due_label.setMinimumWidth(100)
        self.balance_due = QDoubleSpinBox()
        self.balance_due.setMinimum(0)
        self.balance_due.setMaximum(999999)
        self.balance_due.setDecimals(2)
        self.balance_due.setPrefix("$")
        self.balance_due.setReadOnly(True)
        self.balance_due.setMaximumWidth(130)
        row5a.addWidget(due_label)
        row5a.addWidget(self.balance_due)
        row5a.addStretch()
        form_layout.addLayout(row5a)
        
        # ===== SECTION 6: NOTES =====
        sec6_title = QLabel("NOTES")
        sec6_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec6_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec6_title)
        
        notes_row = QHBoxLayout()
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        notes_row.addWidget(self.notes)
        form_layout.addLayout(notes_row)
        
        # ===== SECTION 7: HOS (HOURS OF SERVICE) =====
        sec7_title = QLabel("HOURS OF SERVICE (HOS)")
        sec7_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec7_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec7_title)
        
        # Row 7a: Calculated Hours and Hours Worked
        row7a = QHBoxLayout()
        calc_hours_label = QLabel("Calculated Hours:")
        calc_hours_label.setMinimumWidth(100)
        self.calculated_hours = QDoubleSpinBox()
        self.calculated_hours.setMinimum(0)
        self.calculated_hours.setMaximum(24)
        self.calculated_hours.setDecimals(2)
        self.calculated_hours.setReadOnly(True)
        self.calculated_hours.setMaximumWidth(100)
        row7a.addWidget(calc_hours_label)
        row7a.addWidget(self.calculated_hours)
        row7a.addSpacing(30)
        
        worked_hours_label = QLabel("Hours Worked:")
        worked_hours_label.setMinimumWidth(100)
        self.driver_hours_worked = QDoubleSpinBox()
        self.driver_hours_worked.setMinimum(0)
        self.driver_hours_worked.setMaximum(24)
        self.driver_hours_worked.setDecimals(2)
        self.driver_hours_worked.setMaximumWidth(100)
        row7a.addWidget(worked_hours_label)
        row7a.addWidget(self.driver_hours_worked)
        row7a.addStretch()
        form_layout.addLayout(row7a)
        
        # Row 7b: Hours Rate 1 and Hours Rate 2 (duty status split)
        row7b = QHBoxLayout()
        hours1_label = QLabel("On-Duty Driving (Hours):")
        hours1_label.setMinimumWidth(100)
        self.driver_hours_1 = QDoubleSpinBox()
        self.driver_hours_1.setMinimum(0)
        self.driver_hours_1.setMaximum(24)
        self.driver_hours_1.setDecimals(2)
        self.driver_hours_1.setMaximumWidth(100)
        row7b.addWidget(hours1_label)
        row7b.addWidget(self.driver_hours_1)
        row7b.addSpacing(30)
        
        hours2_label = QLabel("On-Duty Not Driving (Hours):")
        hours2_label.setMinimumWidth(100)
        self.driver_hours_2 = QDoubleSpinBox()
        self.driver_hours_2.setMinimum(0)
        self.driver_hours_2.setMaximum(24)
        self.driver_hours_2.setDecimals(2)
        self.driver_hours_2.setMaximumWidth(100)
        row7b.addWidget(hours2_label)
        row7b.addWidget(self.driver_hours_2)
        row7b.addStretch()
        form_layout.addLayout(row7b)
        
        # ===== SECTION 8: DRIVER PAY BREAKDOWN =====
        sec8_title = QLabel("DRIVER PAY BREAKDOWN")
        sec8_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec8_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec8_title)
        
        # Row 8a: Pay Rate 1 and Pay Rate 2
        row8a = QHBoxLayout()
        pay1_label = QLabel("Driving Pay (Rate 1):")
        pay1_label.setMinimumWidth(100)
        self.driver_pay_1 = QDoubleSpinBox()
        self.driver_pay_1.setMinimum(0)
        self.driver_pay_1.setMaximum(999999)
        self.driver_pay_1.setDecimals(2)
        self.driver_pay_1.setPrefix("$")
        self.driver_pay_1.setMaximumWidth(130)
        row8a.addWidget(pay1_label)
        row8a.addWidget(self.driver_pay_1)
        row8a.addSpacing(30)
        
        pay2_label = QLabel("Non-Driving Pay (Rate 2):")
        pay2_label.setMinimumWidth(100)
        self.driver_pay_2 = QDoubleSpinBox()
        self.driver_pay_2.setMinimum(0)
        self.driver_pay_2.setMaximum(999999)
        self.driver_pay_2.setDecimals(2)
        self.driver_pay_2.setPrefix("$")
        self.driver_pay_2.setMaximumWidth(130)
        row8a.addWidget(pay2_label)
        row8a.addWidget(self.driver_pay_2)
        row8a.addStretch()
        form_layout.addLayout(row8a)
        
        # Row 8b: Base Pay and Gratuity
        row8b = QHBoxLayout()
        base_pay_label = QLabel("Base Pay:")
        base_pay_label.setMinimumWidth(100)
        self.driver_base_pay = QDoubleSpinBox()
        self.driver_base_pay.setMinimum(0)
        self.driver_base_pay.setMaximum(999999)
        self.driver_base_pay.setDecimals(2)
        self.driver_base_pay.setPrefix("$")
        self.driver_base_pay.setReadOnly(True)
        self.driver_base_pay.setMaximumWidth(130)
        row8b.addWidget(base_pay_label)
        row8b.addWidget(self.driver_base_pay)
        row8b.addSpacing(30)
        
        grat_percent_label = QLabel("Gratuity %:")
        grat_percent_label.setMinimumWidth(100)
        self.driver_gratuity_percent = QDoubleSpinBox()
        self.driver_gratuity_percent.setMinimum(0)
        self.driver_gratuity_percent.setMaximum(100)
        self.driver_gratuity_percent.setDecimals(2)
        self.driver_gratuity_percent.setSuffix("%")
        self.driver_gratuity_percent.setMaximumWidth(100)
        row8b.addWidget(grat_percent_label)
        row8b.addWidget(self.driver_gratuity_percent)
        row8b.addStretch()
        form_layout.addLayout(row8b)
        
        # Row 8c: Gratuity Amount and Total Driver Expense
        row8c = QHBoxLayout()
        grat_amount_label = QLabel("Gratuity Amount:")
        grat_amount_label.setMinimumWidth(100)
        self.driver_gratuity_amount = QDoubleSpinBox()
        self.driver_gratuity_amount.setMinimum(0)
        self.driver_gratuity_amount.setMaximum(999999)
        self.driver_gratuity_amount.setDecimals(2)
        self.driver_gratuity_amount.setPrefix("$")
        self.driver_gratuity_amount.setMaximumWidth(130)
        row8c.addWidget(grat_amount_label)
        row8c.addWidget(self.driver_gratuity_amount)
        row8c.addSpacing(30)
        
        total_expense_label = QLabel("Total Expense:")
        total_expense_label.setMinimumWidth(100)
        self.driver_total_expense = QDoubleSpinBox()
        self.driver_total_expense.setMinimum(0)
        self.driver_total_expense.setMaximum(999999)
        self.driver_total_expense.setDecimals(2)
        self.driver_total_expense.setPrefix("$")
        self.driver_total_expense.setReadOnly(True)
        self.driver_total_expense.setMaximumWidth(130)
        row8c.addWidget(total_expense_label)
        row8c.addWidget(self.driver_total_expense)
        row8c.addStretch()
        form_layout.addLayout(row8c)
        
        # ===== SECTION 9: ACCOUNTING & FLOAT RECEIPTS =====
        sec9_title = QLabel("ACCOUNTING & FLOAT RECEIPTS")
        sec9_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec9_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec9_title)
        
        # Row 9a: Retainer and Deposit
        row9a = QHBoxLayout()
        retainer_label = QLabel("Retainer:")
        retainer_label.setMinimumWidth(100)
        self.retainer_amount = QDoubleSpinBox()
        self.retainer_amount.setMinimum(0)
        self.retainer_amount.setMaximum(999999)
        self.retainer_amount.setDecimals(2)
        self.retainer_amount.setPrefix("$")
        self.retainer_amount.setMaximumWidth(130)
        row9a.addWidget(retainer_label)
        row9a.addWidget(self.retainer_amount)
        row9a.addSpacing(30)
        
        deposit_label = QLabel("Deposit:")
        deposit_label.setMinimumWidth(100)
        self.deposit = QDoubleSpinBox()
        self.deposit.setMinimum(0)
        self.deposit.setMaximum(999999)
        self.deposit.setDecimals(2)
        self.deposit.setPrefix("$")
        self.deposit.setMaximumWidth(130)
        row9a.addWidget(deposit_label)
        row9a.addWidget(self.deposit)
        row9a.addStretch()
        form_layout.addLayout(row9a)
        
        # Row 9b: Payment Status
        row9b = QHBoxLayout()
        payment_status_label = QLabel("Payment Status:")
        payment_status_label.setMinimumWidth(100)
        self.payment_status = QComboBox()
        self.payment_status.addItems(["Pending", "Partial", "Paid", "Overdue"])
        self.payment_status.setMaximumWidth(150)
        row9b.addWidget(payment_status_label)
        row9b.addWidget(self.payment_status)
        row9b.addStretch()
        form_layout.addLayout(row9b)
        
        # Row 9c: Driver Notes (instructions for driver)
        driver_notes_label = QLabel("Driver Instructions:")
        driver_notes_label.setMinimumWidth(100)
        driver_notes_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.driver_notes = QTextEdit()
        self.driver_notes.setMaximumHeight(60)
        self.driver_notes.setPlaceholderText("Directions, special requests, pickup instructions...")
        row9c = QHBoxLayout()
        row9c.addWidget(driver_notes_label)
        row9c.addWidget(self.driver_notes)
        form_layout.addLayout(row9c)
        
        # ===== SECTION 10: DISPATCHER NOTES (EMAIL/PHONE LOGS) =====
        sec10_title = QLabel("DISPATCHER NOTES (Email/Phone Logs)")
        sec10_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec10_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec10_title)
        
        # Row 10a: Dispatcher Notes (from Outlook emails, phone calls, etc.)
        dispatcher_notes_label = QLabel("Dispatcher Notes:")
        dispatcher_notes_label.setMinimumWidth(100)
        dispatcher_notes_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dispatcher_notes = QTextEdit()
        self.dispatcher_notes.setMinimumHeight(100)
        self.dispatcher_notes.setPlaceholderText("Email details, phone conversation notes, client communications...\n\nUse Outlook add-in button to auto-paste email content here.")
        row10a = QHBoxLayout()
        row10a.addWidget(dispatcher_notes_label)
        row10a.addWidget(self.dispatcher_notes)
        form_layout.addLayout(row10a)
        
        # ===== SECTION 11: CLIENT WARNING FLAGS =====
        sec11_title = QLabel("⚠️ CLIENT WARNING FLAGS")
        sec11_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec11_title.setStyleSheet("color: #d32f2f; background-color: #ffebee; border-bottom: 2px solid #c62828; padding: 6px;")
        form_layout.addWidget(sec11_title)
        
        # Row 11a: Warning display (read-only, loaded from accounts table)
        self.client_warnings_display = QTextEdit()
        self.client_warnings_display.setReadOnly(True)
        self.client_warnings_display.setMaximumHeight(60)
        self.client_warnings_display.setStyleSheet("background-color: #fff9c4; color: #f57c00; font-weight: bold;")
        self.client_warnings_display.setPlaceholderText("No warnings on file")
        form_layout.addWidget(self.client_warnings_display)
        
        form_widget.setLayout(form_layout)
        scroll.setWidget(form_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_invoice_details_tab(self):
        """Tab 2: Invoice Details with charge breakdown (compact 2-column layout)
        
        Shows:
        - Charter Charge
        - Extra Charges  
        - Beverage Total
        - GST
        - Driver
        - Vehicle
        - Payment Status
        """
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)
        
        title = QLabel("📄 Invoice Details & Breakdown")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Scroll area for compact details
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        details_widget = QWidget()
        details_layout = QVBoxLayout()
        details_layout.setSpacing(4)
        details_layout.setContentsMargins(2, 2, 2, 2)
        
        # ===== INVOICE HEADER (2-col) =====
        header_row1 = QHBoxLayout()
        date_label = QLabel("Invoice Date:")
        date_label.setMinimumWidth(100)
        self.invoice_date_display = QLineEdit()
        self.invoice_date_display.setReadOnly(True)
        self.invoice_date_display.setMaximumWidth(150)
        header_row1.addWidget(date_label)
        header_row1.addWidget(self.invoice_date_display)
        header_row1.addSpacing(30)
        
        client_label = QLabel("Client:")
        client_label.setMinimumWidth(80)
        self.invoice_client_display = QLineEdit()
        self.invoice_client_display.setReadOnly(True)
        self.invoice_client_display.setMaximumWidth(200)
        header_row1.addWidget(client_label)
        header_row1.addWidget(self.invoice_client_display)
        header_row1.addStretch()
        details_layout.addLayout(header_row1)
        
        header_row2 = QHBoxLayout()
        driver_label = QLabel("Driver:")
        driver_label.setMinimumWidth(100)
        self.invoice_driver_display = QLineEdit()
        self.invoice_driver_display.setReadOnly(True)
        self.invoice_driver_display.setMaximumWidth(200)
        header_row2.addWidget(driver_label)
        header_row2.addWidget(self.invoice_driver_display)
        header_row2.addSpacing(30)
        
        veh_label = QLabel("Vehicle:")
        veh_label.setMinimumWidth(80)
        self.invoice_vehicle_display = QLineEdit()
        self.invoice_vehicle_display.setReadOnly(True)
        self.invoice_vehicle_display.setMaximumWidth(200)
        header_row2.addWidget(veh_label)
        header_row2.addWidget(self.invoice_vehicle_display)
        header_row2.addStretch()
        details_layout.addLayout(header_row2)
        
        # ===== CHARGE BREAKDOWN (2-col) =====
        sep1 = QLabel("─" * 80)
        sep1.setStyleSheet("color: #999;")
        details_layout.addWidget(sep1)
        
        charges_title = QLabel("💰 Charge Breakdown")
        charges_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        details_layout.addWidget(charges_title)
        
        charge_row1 = QHBoxLayout()
        charter_label = QLabel("Charter Charge:")
        charter_label.setMinimumWidth(140)
        self.invoice_charter_charge = QDoubleSpinBox()
        self.invoice_charter_charge.setPrefix("$")
        self.invoice_charter_charge.setMaximum(99999.99)
        self.invoice_charter_charge.setReadOnly(True)
        self.invoice_charter_charge.setMaximumWidth(120)
        charge_row1.addWidget(charter_label)
        charge_row1.addWidget(self.invoice_charter_charge)
        charge_row1.addSpacing(30)
        
        extra_label = QLabel("Extra Charges:")
        extra_label.setMinimumWidth(140)
        self.invoice_extra_charges = QDoubleSpinBox()
        self.invoice_extra_charges.setPrefix("$")
        self.invoice_extra_charges.setMaximum(99999.99)
        self.invoice_extra_charges.setReadOnly(True)
        self.invoice_extra_charges.setMaximumWidth(120)
        charge_row1.addWidget(extra_label)
        charge_row1.addWidget(self.invoice_extra_charges)
        charge_row1.addStretch()
        details_layout.addLayout(charge_row1)
        
        charge_row2 = QHBoxLayout()
        bev_label = QLabel("Beverage Total:")
        bev_label.setMinimumWidth(140)
        self.invoice_beverage_total = QDoubleSpinBox()
        self.invoice_beverage_total.setPrefix("$")
        self.invoice_beverage_total.setMaximum(99999.99)
        self.invoice_beverage_total.setReadOnly(True)
        self.invoice_beverage_total.setMaximumWidth(120)
        charge_row2.addWidget(bev_label)
        charge_row2.addWidget(self.invoice_beverage_total)
        charge_row2.addSpacing(30)
        
        gst_label = QLabel("GST (5%):")
        gst_label.setMinimumWidth(140)
        self.invoice_gst_amount = QDoubleSpinBox()
        self.invoice_gst_amount.setPrefix("$")
        self.invoice_gst_amount.setMaximum(99999.99)
        self.invoice_gst_amount.setReadOnly(True)
        self.invoice_gst_amount.setMaximumWidth(120)
        charge_row2.addWidget(gst_label)
        charge_row2.addWidget(self.invoice_gst_amount)
        charge_row2.addStretch()
        details_layout.addLayout(charge_row2)
        
        # ===== PAYMENT SUMMARY (2-col) =====
        sep2 = QLabel("─" * 80)
        sep2.setStyleSheet("color: #999;")
        details_layout.addWidget(sep2)
        
        pay_title = QLabel("💳 Payment Summary")
        pay_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        details_layout.addWidget(pay_title)
        
        pay_row1 = QHBoxLayout()
        subtotal_label = QLabel("Subtotal:")
        subtotal_label.setMinimumWidth(140)
        self.invoice_subtotal = QDoubleSpinBox()
        self.invoice_subtotal.setPrefix("$")
        self.invoice_subtotal.setMaximum(99999.99)
        self.invoice_subtotal.setReadOnly(True)
        self.invoice_subtotal.setMaximumWidth(120)
        pay_row1.addWidget(subtotal_label)
        pay_row1.addWidget(self.invoice_subtotal)
        pay_row1.addSpacing(30)
        
        total_label = QLabel("Total:")
        total_label.setMinimumWidth(140)
        self.invoice_total = QDoubleSpinBox()
        self.invoice_total.setPrefix("$")
        self.invoice_total.setMaximum(99999.99)
        self.invoice_total.setReadOnly(True)
        self.invoice_total.setMaximumWidth(120)
        self.invoice_total.setStyleSheet("font-weight: bold; color: #006600;")
        pay_row1.addWidget(total_label)
        pay_row1.addWidget(self.invoice_total)
        pay_row1.addStretch()
        details_layout.addLayout(pay_row1)
        
        pay_row2 = QHBoxLayout()
        paid_label = QLabel("Amount Paid:")
        paid_label.setMinimumWidth(140)
        self.invoice_amount_paid_display = QDoubleSpinBox()
        self.invoice_amount_paid_display.setPrefix("$")
        self.invoice_amount_paid_display.setMaximum(99999.99)
        self.invoice_amount_paid_display.setReadOnly(True)
        self.invoice_amount_paid_display.setMaximumWidth(120)
        pay_row2.addWidget(paid_label)
        pay_row2.addWidget(self.invoice_amount_paid_display)
        pay_row2.addSpacing(30)
        
        due_label = QLabel("Amount Due:")
        due_label.setMinimumWidth(140)
        self.invoice_amount_due_display = QDoubleSpinBox()
        self.invoice_amount_due_display.setPrefix("$")
        self.invoice_amount_due_display.setMaximum(99999.99)
        self.invoice_amount_due_display.setReadOnly(True)
        self.invoice_amount_due_display.setMaximumWidth(120)
        self.invoice_amount_due_display.setStyleSheet("font-weight: bold; color: #cc0000;")
        pay_row2.addWidget(due_label)
        pay_row2.addWidget(self.invoice_amount_due_display)
        pay_row2.addStretch()
        details_layout.addLayout(pay_row2)
        
        pay_row3 = QHBoxLayout()
        status_label = QLabel("Invoice Status:")
        status_label.setMinimumWidth(140)
        self.invoice_status_display = QLineEdit()
        self.invoice_status_display.setReadOnly(True)
        self.invoice_status_display.setMaximumWidth(120)
        pay_row3.addWidget(status_label)
        pay_row3.addWidget(self.invoice_status_display)
        pay_row3.addStretch()
        details_layout.addLayout(pay_row3)
        
        details_layout.addStretch()
        details_widget.setLayout(details_layout)
        scroll.setWidget(details_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_orders_tab(self):
        """Tab 3: Related beverage and product orders (compact layout)"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)
        
        title = QLabel("Beverage & Product Orders")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Orders table (compact sizing)
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(5)
        self.orders_table.setHorizontalHeaderLabels(["Item", "Qty", "Unit Price", "Total", "Status"])
        self.orders_table.horizontalHeader().setStretchLastSection(True)
        self.orders_table.setMaximumHeight(180)
        layout.addWidget(self.orders_table)
        
        # Add/Edit buttons (compact horizontal layout)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        
        add_order_btn = QPushButton("➕ Add")
        add_order_btn.setMaximumWidth(90)
        add_order_btn.clicked.connect(self.add_order)
        btn_layout.addWidget(add_order_btn)
        
        edit_order_btn = QPushButton("✏️ Edit")
        edit_order_btn.setMaximumWidth(90)
        edit_order_btn.clicked.connect(self.edit_order)
        btn_layout.addWidget(edit_order_btn)
        
        delete_order_btn = QPushButton("🗑️ Delete")
        delete_order_btn.setMaximumWidth(90)
        delete_order_btn.clicked.connect(self.delete_order)
        btn_layout.addWidget(delete_order_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_beverage_printout_tab(self):
        """Tab 3.5: Beverage Printout with checkbox items"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Title
        title = QLabel("🍷 Beverage Service Printout")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a3d7a;")
        layout.addWidget(title)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        beverage_widget = QWidget()
        beverage_layout = QVBoxLayout()
        beverage_layout.setSpacing(8)
        beverage_layout.setContentsMargins(4, 4, 4, 4)
        
        # Section: Service Options
        service_title = QLabel("SERVICE OPTIONS")
        service_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        service_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        beverage_layout.addWidget(service_title)
        
        # Beverage Service Required checkbox
        self.beverage_required_cb = QCheckBox("Beverage Service Required")
        self.beverage_required_cb.setStyleSheet("font-size: 12px; padding: 4px;")
        beverage_layout.addWidget(self.beverage_required_cb)
        
        # Section: Beverage Items
        items_title = QLabel("BEVERAGE ITEMS")
        items_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        items_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        beverage_layout.addWidget(items_title)
        
        # Define standard beverage items with checkboxes
        beverage_items = [
            ("Water - Bottled", "water_bottled"),
            ("Water - Sparkling", "water_sparkling"),
            ("Juice - Orange", "juice_orange"),
            ("Juice - Cranberry", "juice_cranberry"),
            ("Juice - Apple", "juice_apple"),
            ("Soft Drinks - Cola", "softdrink_cola"),
            ("Soft Drinks - Lemon-Lime", "softdrink_lemonlime"),
            ("Coffee - Regular", "coffee_regular"),
            ("Coffee - Decaf", "coffee_decaf"),
            ("Tea - Hot", "tea_hot"),
            ("Wine - Red", "wine_red"),
            ("Wine - White", "wine_white"),
            ("Champagne", "champagne"),
            ("Beer - Domestic", "beer_domestic"),
            ("Beer - Imported", "beer_imported"),
            ("Spirits - Vodka", "spirits_vodka"),
            ("Spirits - Gin", "spirits_gin"),
            ("Spirits - Rum", "spirits_rum"),
            ("Spirits - Whiskey", "spirits_whiskey"),
            ("Spirits - Other", "spirits_other"),
        ]
        
        # Create checkboxes in a 2-column layout
        self.beverage_checkboxes = {}
        items_container = QWidget()
        items_grid = QVBoxLayout()
        items_grid.setSpacing(4)
        
        for i, (label, key) in enumerate(beverage_items):
            cb = QCheckBox(label)
            cb.setStyleSheet("font-size: 11px; padding: 2px;")
            self.beverage_checkboxes[key] = cb
            items_grid.addWidget(cb)
            
            # Add spacing between groups
            if i == 9 or i == 14:
                items_grid.addSpacing(8)
        
        items_container.setLayout(items_grid)
        beverage_layout.addWidget(items_container)
        
        # Section: Notes
        notes_title = QLabel("BEVERAGE NOTES")
        notes_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        notes_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        beverage_layout.addWidget(notes_title)
        
        self.beverage_notes = QTextEdit()
        self.beverage_notes.setMaximumHeight(100)
        self.beverage_notes.setPlaceholderText("Special beverage requests, allergies, preferences, etc.")
        beverage_layout.addWidget(self.beverage_notes)
        
        beverage_layout.addStretch()
        beverage_widget.setLayout(beverage_layout)
        scroll.setWidget(beverage_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def create_routing_tab(self):
        """Tab 4: Routing details with per-stop lines (compact layout)"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)
        
        title = QLabel("🗺️ Routing & Charges")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Rate Type Selection (compact single line)
        rate_layout = QHBoxLayout()
        rate_layout.setSpacing(4)
        
        self.rate_type = QComboBox()
        self.rate_type.addItems([
            "Hourly Rate",
            "Package Rate", 
            "Split Run Rate",
            "One-Way Rate",
            "Airport Transfer",
            "Custom Quote"
        ])
        self.rate_type.setMaximumWidth(140)
        self.rate_type.currentTextChanged.connect(self.on_rate_type_changed)
        rate_layout.addWidget(QLabel("Billing:"))
        rate_layout.addWidget(self.rate_type)
        
        self.hourly_rate = QDoubleSpinBox()
        self.hourly_rate.setPrefix("$")
        self.hourly_rate.setMaximum(999.99)
        self.hourly_rate.setValue(85.00)
        self.hourly_rate.setMaximumWidth(100)
        rate_layout.addWidget(QLabel("Rate:"))
        rate_layout.addWidget(self.hourly_rate)
        
        self.min_hours = QSpinBox()
        self.min_hours.setMinimum(1)
        self.min_hours.setMaximum(24)
        self.min_hours.setValue(3)
        self.min_hours.setMaximumWidth(70)
        rate_layout.addWidget(QLabel("Min Hrs:"))
        rate_layout.addWidget(self.min_hours)
        rate_layout.addStretch()
        layout.addLayout(rate_layout)
        
        # Routing Stops Table (compact)
        stops_label = QLabel("Route Stops (in order)")
        stops_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(stops_label)
        
        self.routing_table = QTableWidget()
        self.routing_table.setColumnCount(7)
        self.routing_table.setHorizontalHeaderLabels([
            "Stop #", 
            "Type", 
            "Location", 
            "Time", 
            "Dist (km)", 
            "Dur (min)",
            "Notes"
        ])
        self.routing_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.routing_table.setMaximumHeight(140)
        layout.addWidget(self.routing_table)
        
        # Stop management buttons (compact)
        stop_btn_layout = QHBoxLayout()
        stop_btn_layout.setSpacing(4)
        
        add_stop_btn = QPushButton("➕ Add")
        add_stop_btn.setMaximumWidth(85)
        add_stop_btn.clicked.connect(self.add_routing_stop)
        stop_btn_layout.addWidget(add_stop_btn)
        
        edit_stop_btn = QPushButton("✏️ Edit")
        edit_stop_btn.setMaximumWidth(85)
        edit_stop_btn.clicked.connect(self.edit_routing_stop)
        stop_btn_layout.addWidget(edit_stop_btn)
        
        delete_stop_btn = QPushButton("🗑️ Del")
        delete_stop_btn.setMaximumWidth(85)
        delete_stop_btn.clicked.connect(self.delete_routing_stop)
        stop_btn_layout.addWidget(delete_stop_btn)
        
        move_up_btn = QPushButton("⬆️")
        move_up_btn.setMaximumWidth(60)
        move_up_btn.clicked.connect(lambda: self.move_stop(-1))
        stop_btn_layout.addWidget(move_up_btn)
        
        move_down_btn = QPushButton("⬇️")
        move_down_btn.setMaximumWidth(60)
        move_down_btn.clicked.connect(lambda: self.move_stop(1))
        stop_btn_layout.addWidget(move_down_btn)
        
        calc_btn = QPushButton("🧮 Calc")
        calc_btn.setMaximumWidth(85)
        calc_btn.clicked.connect(self.calculate_routing_charges)
        stop_btn_layout.addWidget(calc_btn)
        
        stop_btn_layout.addStretch()
        layout.addLayout(stop_btn_layout)
        
        # Charges Summary (compact 2-column layout)
        charges_title = QLabel("💰 Charge Breakdown")
        charges_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(charges_title)
        
        charge_row1 = QHBoxLayout()
        charge_row1.setSpacing(4)
        
        self.base_fare = QDoubleSpinBox()
        self.base_fare.setPrefix("$")
        self.base_fare.setMaximum(99999.99)
        self.base_fare.setReadOnly(True)
        self.base_fare.setMaximumWidth(100)
        charge_row1.addWidget(QLabel("Base:"))
        charge_row1.addWidget(self.base_fare)
        charge_row1.addSpacing(15)
        
        self.distance_charge = QDoubleSpinBox()
        self.distance_charge.setPrefix("$")
        self.distance_charge.setMaximum(99999.99)
        self.distance_charge.setReadOnly(True)
        self.distance_charge.setMaximumWidth(100)
        charge_row1.addWidget(QLabel("Distance:"))
        charge_row1.addWidget(self.distance_charge)
        charge_row1.addSpacing(15)
        
        self.time_charge = QDoubleSpinBox()
        self.time_charge.setPrefix("$")
        self.time_charge.setMaximum(99999.99)
        self.time_charge.setReadOnly(True)
        self.time_charge.setMaximumWidth(100)
        charge_row1.addWidget(QLabel("Time:"))
        charge_row1.addWidget(self.time_charge)
        charge_row1.addStretch()
        layout.addLayout(charge_row1)
        
        charge_row2 = QHBoxLayout()
        charge_row2.setSpacing(4)
        
        self.extra_time_charge = QDoubleSpinBox()
        self.extra_time_charge.setPrefix("$")
        self.extra_time_charge.setMaximum(99999.99)
        self.extra_time_charge.setMaximumWidth(100)
        charge_row2.addWidget(QLabel("Extra:"))
        charge_row2.addWidget(self.extra_time_charge)
        charge_row2.addSpacing(15)
        
        self.service_charge = QDoubleSpinBox()
        self.service_charge.setPrefix("$")
        self.service_charge.setMaximum(99999.99)
        self.service_charge.setMaximumWidth(100)
        charge_row2.addWidget(QLabel("Service:"))
        charge_row2.addWidget(self.service_charge)
        charge_row2.addSpacing(15)
        
        self.gst = QDoubleSpinBox()
        self.gst.setPrefix("$")
        self.gst.setMaximum(99999.99)
        self.gst.setReadOnly(True)
        self.gst.setMaximumWidth(100)
        charge_row2.addWidget(QLabel("GST:"))
        charge_row2.addWidget(self.gst)
        charge_row2.addStretch()
        layout.addLayout(charge_row2)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def on_rate_type_changed(self, rate_type):
        """Handle rate type change"""
        if rate_type == "Hourly Rate":
            self.min_hours.setEnabled(True)
            self.hourly_rate.setEnabled(True)
        elif rate_type == "Package Rate":
            self.min_hours.setEnabled(False)
            self.hourly_rate.setEnabled(True)
        elif rate_type == "Split Run Rate":
            self.min_hours.setEnabled(False)
            self.hourly_rate.setEnabled(True)
        else:
            self.min_hours.setEnabled(False)
            self.hourly_rate.setEnabled(True)
    
    def add_routing_stop(self):
        """Add a new routing stop"""
        dialog = RoutingStopDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            stop_data = dialog.get_stop_data()
            
            row = self.routing_table.rowCount()
            self.routing_table.insertRow(row)
            
            self.routing_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.routing_table.setItem(row, 1, QTableWidgetItem(stop_data['type']))
            self.routing_table.setItem(row, 2, QTableWidgetItem(stop_data['location']))
            self.routing_table.setItem(row, 3, QTableWidgetItem(stop_data['time']))
            self.routing_table.setItem(row, 4, QTableWidgetItem(str(stop_data['distance'])))
            self.routing_table.setItem(row, 5, QTableWidgetItem(str(stop_data['duration'])))
            self.routing_table.setItem(row, 6, QTableWidgetItem(stop_data['notes']))
            
            self.renumber_stops()
    
    def edit_routing_stop(self):
        """Edit selected routing stop"""
        row = self.routing_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a stop to edit.")
            return
        
        # Get current data
        current_data = {
            'type': self.routing_table.item(row, 1).text(),
            'location': self.routing_table.item(row, 2).text(),
            'time': self.routing_table.item(row, 3).text(),
            'distance': self.routing_table.item(row, 4).text(),
            'duration': self.routing_table.item(row, 5).text(),
            'notes': self.routing_table.item(row, 6).text()
        }
        
        dialog = RoutingStopDialog(parent=self, stop_data=current_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            stop_data = dialog.get_stop_data()
            
            self.routing_table.setItem(row, 1, QTableWidgetItem(stop_data['type']))
            self.routing_table.setItem(row, 2, QTableWidgetItem(stop_data['location']))
            self.routing_table.setItem(row, 3, QTableWidgetItem(stop_data['time']))
            self.routing_table.setItem(row, 4, QTableWidgetItem(str(stop_data['distance'])))
            self.routing_table.setItem(row, 5, QTableWidgetItem(str(stop_data['duration'])))
            self.routing_table.setItem(row, 6, QTableWidgetItem(stop_data['notes']))
    
    def delete_routing_stop(self):
        """Delete selected routing stop"""
        row = self.routing_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a stop to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm", "Delete this routing stop?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.routing_table.removeRow(row)
            self.renumber_stops()
    
    def move_stop(self, direction):
        """Move stop up (-1) or down (+1)"""
        row = self.routing_table.currentRow()
        if row < 0:
            return
        
        new_row = row + direction
        if new_row < 0 or new_row >= self.routing_table.rowCount():
            return
        
        # Swap rows
        for col in range(1, self.routing_table.columnCount()):
            item1 = self.routing_table.takeItem(row, col)
            item2 = self.routing_table.takeItem(new_row, col)
            self.routing_table.setItem(row, col, item2)
            self.routing_table.setItem(new_row, col, item1)
        
        self.routing_table.setCurrentCell(new_row, 0)
        self.renumber_stops()
    
    def renumber_stops(self):
        """Renumber all stops sequentially"""
        for row in range(self.routing_table.rowCount()):
            self.routing_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
    
    def calculate_routing_charges(self):
        """Calculate total charges based on routing and rate type"""
        rate_type = self.rate_type.currentText()
        rate = self.hourly_rate.value()
        
        total_distance = 0
        total_duration = 0
        
        # Sum up all stops
        for row in range(self.routing_table.rowCount()):
            try:
                distance = float(self.routing_table.item(row, 4).text() or 0)
                duration = float(self.routing_table.item(row, 5).text() or 0)
                total_distance += distance
                total_duration += duration
            except:
                pass
        
        # Calculate based on rate type
        if rate_type == "Hourly Rate":
            min_hours = self.min_hours.value()
            actual_hours = total_duration / 60.0
            billable_hours = max(min_hours, actual_hours)
            
            self.time_charge.setValue(billable_hours * rate)
            self.base_fare.setValue(min_hours * rate)
            self.distance_charge.setValue(0)
            
        elif rate_type == "Split Run Rate":
            # Split run typically has a base rate
            self.base_fare.setValue(rate)
            self.distance_charge.setValue(total_distance * 1.50)  # $1.50/km
            self.time_charge.setValue(0)
            
        elif rate_type == "Package Rate":
            # Package is flat rate
            self.base_fare.setValue(rate)
            self.distance_charge.setValue(0)
            self.time_charge.setValue(0)
        
        else:
            # One-way or custom
            self.base_fare.setValue(rate)
            self.distance_charge.setValue(total_distance * 2.00)
            self.time_charge.setValue(0)
        
        # Calculate GST
        subtotal = (self.base_fare.value() + 
                   self.distance_charge.value() + 
                   self.time_charge.value() +
                   self.extra_time_charge.value() +
                   self.service_charge.value())
        
        gst = subtotal * 0.05
        self.gst.setValue(gst)
        
        total = subtotal + gst
        self.total_amount.setValue(total)
        
        QMessageBox.information(
            self, 
            "Charges Calculated",
            f"Rate Type: {rate_type}\n"
            f"Total Distance: {total_distance:.1f} km\n"
            f"Total Duration: {total_duration:.0f} min\n"
            f"Subtotal: ${subtotal:.2f}\n"
            f"GST: ${gst:.2f}\n"
            f"TOTAL: ${total:.2f}"
        )
    
    def create_payments_tab(self):
        """Tab 5: Payment history (Manual Record - compact layout)"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Compact title
        title = QLabel("Payment History (Manual Record)")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Hint (compact)
        hint = QLabel("Manual ledger entry only — records payments already received (cash/check/bank).")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 9px; color: #666; margin-bottom: 6px;")
        layout.addWidget(hint)
        
        # Payments table (compact)
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(6)
        self.payments_table.setHorizontalHeaderLabels(["Date", "Amount", "Method", "Reference", "Status", "Reconciled"])
        self.payments_table.horizontalHeader().setStretchLastSection(True)
        self.payments_table.setMaximumHeight(200)
        layout.addWidget(self.payments_table)
        
        # Add payment button (compact)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        add_payment_btn = QPushButton("➕ Add Payment")
        add_payment_btn.setMaximumWidth(130)
        add_payment_btn.setToolTip("Record a manually received payment")
        add_payment_btn.clicked.connect(self.add_payment)
        btn_layout.addWidget(add_payment_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def load_client_info(self, client_id):
        """Load client info and populate client field for new charter"""
        try:
            cur = self.db.cursor()
            cur.execute("""
                SELECT client_id, client_name
                FROM clients
                WHERE client_id = %s
            """, (client_id,))
            
            row = cur.fetchone()
            cur.close()
            
            if row:
                self.client.setText(row[1])  # Set client name display
                # Store client_id for saving later
                self.selected_client_id = row[0]
        except Exception as e:
            print(f"Error loading client info: {e}")
    
    def load_charter_data(self):
        """Load charter data from database"""
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
            
            # Load main charter data
            cur.execute("""
                SELECT c.reserve_number, c.charter_date, COALESCE(cl.company_name, cl.client_name),
                       c.pickup_address, c.dropoff_address, c.pickup_time,
                       c.passenger_count, e.full_name, v.vehicle_number,
                       c.booking_status, c.total_amount_due, c.notes,
                       c.vehicle_type_requested, c.client_id, c.employee_id
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                LEFT JOIN employees e ON c.employee_id = e.employee_id
                LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
                WHERE c.reserve_number = %s
            """, (self.reserve_number,))
            
            charter = cur.fetchone()
            if charter:
                res_num, c_date, client, pickup, dest, p_time, pax, driver, vehicle, status, total, notes, veh_type_req, client_id, employee_id = charter
                
                # Store IDs for saving later
                self.selected_client_id = client_id
                self.selected_employee_id = employee_id
                
                self.res_num.setText(str(res_num or ""))
                
                # Handle charter date - convert to QDate properly
                if c_date:
                    # c_date is datetime.date object from PostgreSQL
                    q_date = QDate(c_date.year, c_date.month, c_date.day)
                    self.charter_date.setDate(q_date)
                else:
                    # NULL date - set to today
                    self.charter_date.setDate(QDate.currentDate())
                
                self.client.setText(str(client or ""))
                self.pickup.setText(str(pickup or ""))
                self.destination.setText(str(dest or ""))
                
                # Handle pickup time (convert to QTime)
                if p_time:
                    try:
                        # If it's a string, parse it (HH:MM format)
                        if isinstance(p_time, str):
                            time_obj = QTime.fromString(p_time, "HH:mm")
                        else:
                            # If it's a time object, convert
                            time_obj = QTime(p_time.hour, p_time.minute)
                        self.pickup_time.setTime(time_obj)
                    except:
                        self.pickup_time.setTime(QTime(0, 0))
                else:
                    self.pickup_time.setTime(QTime(0, 0))
                
                self.passenger_count.setValue(int(pax or 1))
                
                # Set driver - find by text match
                driver_name = str(driver or "")
                driver_idx = self.driver.findText(driver_name)
                if driver_idx >= 0:
                    self.driver.setCurrentIndex(driver_idx)
                
                # Set vehicle requested - find by text match or by category
                if veh_type_req:
                    veh_req_text = str(veh_type_req or "")
                    # Try to find a vehicle with this category
                    for i in range(self.vehicle_requested.count()):
                        veh_id = self.vehicle_requested.itemData(i)
                        if veh_id and veh_id in self._vehicle_categories:
                            if self._vehicle_categories[veh_id] == veh_req_text:
                                self.vehicle_requested.setCurrentIndex(i)
                                break
                
                # Set vehicle - find by text match (handle vehicle_number and vehicle_number (type) format)
                vehicle_name = str(vehicle or "")
                vehicle_idx = self.vehicle.findText(vehicle_name)
                if vehicle_idx >= 0:
                    self.vehicle.setCurrentIndex(vehicle_idx)
                else:
                    # Try to find by partial match (in case it's stored as "LIM-001 (Coach)" format)
                    for i in range(self.vehicle.count()):
                        if vehicle_name.upper() in self.vehicle.itemText(i).upper():
                            self.vehicle.setCurrentIndex(i)
                            break
                
                # Set status - if it was "Pending", change to "Confirmed"
                display_status = str(status or "Confirmed")
                if display_status == "Pending":
                    display_status = "Confirmed"
                self.status.setCurrentText(display_status)
                self.total_amount.setValue(float(total or 0))
                self.notes.setText(str(notes or ""))
                
                # ===== POPULATE INVOICE DETAILS TAB =====
                self.invoice_date_display.setText(c_date.strftime("%m/%d/%Y") if c_date else "")
                self.invoice_client_display.setText(str(client or ""))
                self.invoice_driver_display.setText(str(driver or ""))
                self.invoice_vehicle_display.setText(str(vehicle or ""))
                
                self.charter_data = charter
            
            # Load related beverage/product orders and calculate beverage total
            beverage_total = 0.0
            try:
                cur.execute("""
                    SELECT oi.item_name, oi.quantity, oi.unit_price, oi.total, o.status
                    FROM beverage_orders o
                    JOIN beverage_order_items oi ON o.order_id = oi.order_id
                    WHERE o.reserve_number = %s
                    ORDER BY o.order_date DESC
                """, (self.reserve_number,))
                
                orders = cur.fetchall()
                self.orders_table.setRowCount(len(orders) if orders else 0)
                if orders:
                    for i, (item, qty, price, total, status) in enumerate(orders):
                        self.orders_table.setItem(i, 0, QTableWidgetItem(str(item)))
                        self.orders_table.setItem(i, 1, QTableWidgetItem(str(qty)))
                        self.orders_table.setItem(i, 2, QTableWidgetItem(f"${float(price):,.2f}"))
                        self.orders_table.setItem(i, 3, QTableWidgetItem(f"${float(total):,.2f}"))
                        self.orders_table.setItem(i, 4, QTableWidgetItem(str(status)))
                        beverage_total += float(total or 0)
            except Exception as e:
                try:
                    self.db.rollback()
                except:
                    pass
                # Table might not exist yet, just skip
                self.orders_table.setRowCount(0)
            
            # Load payments
            total_paid = 0.0
            cur.execute("""
                SELECT payment_date, amount, payment_method, reference_number, status, is_deposited
                FROM payments
                WHERE reserve_number = %s
                ORDER BY payment_date DESC
            """, (self.reserve_number,))
            
            payments = cur.fetchall()
            self.payments_table.setRowCount(len(payments) if payments else 0)
            if payments:
                for i, (p_date, amt, method, ref, p_status, recon) in enumerate(payments):
                    self.payments_table.setItem(i, 0, QTableWidgetItem(str(p_date)))
                    self.payments_table.setItem(i, 1, QTableWidgetItem(f"${float(amt):,.2f}"))
                    self.payments_table.setItem(i, 2, QTableWidgetItem(str(method)))
                    self.payments_table.setItem(i, 3, QTableWidgetItem(str(ref)))
                    
                    # Show payment status: if deposited, show "cleared", if matched to amount, show "matched", else show status
                    if recon:
                        display_status = "✓ cleared"
                    elif float(amt or 0) == float(self.total_amount.value()):
                        display_status = "✓ matched"
                    else:
                        display_status = str(p_status) if p_status else "pending"
                    
                    self.payments_table.setItem(i, 4, QTableWidgetItem(display_status))
                    self.payments_table.setItem(i, 5, QTableWidgetItem("✓" if recon else ""))
                    total_paid += float(amt or 0)
            
            # ===== CALCULATE INVOICE AMOUNTS (New Logic) =====
            # Formula: Amount Due = (Charter Charge + Extra Charges + Beverage + GST) - Amount Paid
            # If Amount Paid >= Total Charges, then Amount Due = 0 and Status = CLOSED
            
            # Get charter charge and other amounts from existing columns
            # Use rate as charter charge, and calculate from total_amount_due minus beverages/gst
            cur.execute("""
                SELECT 
                    COALESCE(rate, 0) as charter_charge,
                    COALESCE(total_amount_due, 0) as total_amount_due,
                    COALESCE(paid_amount, 0) as paid_from_column
                FROM charters
                WHERE reserve_number = %s
            """, (self.reserve_number,))
            
            charge_row = cur.fetchone()
            charter_charge = float(charge_row[0]) if charge_row else 0.0
            total_amount_from_db = float(charge_row[1]) if charge_row else 0.0
            paid_from_column = float(charge_row[2]) if charge_row else 0.0
            
            # If paid_amount is 0 in DB, use the total_paid we calculated from payments table
            if paid_from_column == 0 and total_paid > 0:
                actual_paid = total_paid
            else:
                actual_paid = max(total_paid, paid_from_column)
            
            # For now, estimate extra_charges as 0 (can be enhanced later if column is added)
            extra_charges = 0.0
            
            # Calculate GST on subtotal (5% on non-GST-exempt items)
            subtotal_for_gst = charter_charge + extra_charges + beverage_total
            gst_amount = subtotal_for_gst * 0.05
            
            # Total invoice = charter + extra + beverage + gst
            total_invoice = charter_charge + extra_charges + beverage_total + gst_amount
            
            # If total_amount_due is set in DB, use that as the authoritative amount
            if total_amount_from_db > 0:
                total_invoice = total_amount_from_db
            
            # Amount due = total - paid
            amount_due = max(0, total_invoice - actual_paid)
            
            # Determine invoice status
            if amount_due <= 0.01:  # Allow for rounding error
                invoice_status = "CLOSED"
            else:
                invoice_status = "OPEN"
            
            # Update invoice details display
            self.invoice_charter_charge.setValue(charter_charge)
            self.invoice_extra_charges.setValue(extra_charges)
            self.invoice_beverage_total.setValue(beverage_total)
            self.invoice_gst_amount.setValue(gst_amount)
            self.invoice_subtotal.setValue(subtotal_for_gst)
            self.invoice_total.setValue(total_invoice)
            self.invoice_amount_paid_display.setValue(actual_paid)
            self.invoice_amount_due_display.setValue(amount_due)
            self.invoice_status_display.setText(invoice_status)
            
            # Also update the old Amount Paid/Balance Due fields for consistency
            self.amount_paid.setValue(actual_paid)
            self.balance_due.setValue(amount_due)
            
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load charter: {e}")
    
    def save_charter(self):
        """Save changes to charter"""
        try:
            # Get the IDs from the dropdowns
            vehicle_id = self.vehicle.currentData()
            vehicle_requested_id = self.vehicle_requested.currentData()
            employee_id = self.driver.currentData()  # Get employee_id from driver dropdown
            
            # Get selected_client_id if available (set when client is loaded)
            client_id = getattr(self, 'selected_client_id', None)
            
            cur = self.db.get_cursor()
            cur.execute("""
                UPDATE charters SET
                    client_id = %s,
                    charter_date = %s,
                    pickup_address = %s,
                    dropoff_address = %s,
                    pickup_time = %s,
                    passenger_count = %s,
                    booking_status = %s,
                    employee_id = %s,
                    vehicle_id = %s,
                    vehicle_type_requested = %s,
                    notes = %s
                WHERE reserve_number = %s
            """, (
                client_id,
                self.charter_date.date().toPyDate(),  # Use Python date object for PostgreSQL
                self.pickup.text(),
                self.destination.text(),
                self.pickup_time.time().toString("HH:mm"),
                self.passenger_count.value(),
                self.status.currentText(),
                employee_id,
                vehicle_id,
                self._vehicle_categories.get(vehicle_requested_id, "") if vehicle_requested_id else None,
                self.notes.toPlainText(),
                self.reserve_number
            ))
            self.db.commit()
            QMessageBox.information(self, "Success", "Charter saved successfully")
            self.saved.emit({
                'reserve_number': self.reserve_number,
                'status': self.status.currentText()
            })
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save charter: {e}")
            self.db.rollback()
    
    def select_client_dialog(self):
        """Open improved client selection dialog"""
        from improved_client_selection_dialog import ClientSelectionDialog
        
        dialog = ClientSelectionDialog(self.db, self)
        if dialog.exec():
            self.selected_client_id = dialog.get_selected_client_id()
            client_name = dialog.get_selected_client_name()
            if self.selected_client_id and client_name:
                self.client.setText(client_name)
    
    def add_new_charter(self):
        """Create a new charter - search for client first or create new client"""
        from client_search_dialog import ClientSearchDialog
        
        search_dialog = ClientSearchDialog(self.db, self)
        result = search_dialog.exec()
        
        if result:
            # User selected or created a client
            selected_client_id = search_dialog.get_selected_client_id()
            if selected_client_id:
                # Open charter form with pre-selected client
                new_dialog = CharterDetailDialog(self.db, reserve_number=None, parent=self.parent(), client_id=selected_client_id)
                new_dialog.saved.connect(self.on_charter_saved)
                new_dialog.exec()
    
    def duplicate_charter(self):
        """Duplicate current charter with modified reserve number"""
        if not self.reserve_number:
            QMessageBox.warning(self, "Warning", "No charter loaded to duplicate.")
            return
        
        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Duplicate Charter")
            dialog.setGeometry(100, 100, 400, 150)
            
            dlg_layout = QVBoxLayout()
            dlg_layout.addWidget(QLabel("This will create a new charter with the same details.\nConfirm to proceed:"))
            
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
                # Insert duplicate record (system will assign new reserve_number)
                vehicle_requested_id = self.vehicle_requested.currentData()
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
                    INSERT INTO charters 
                    (client_id, charter_date, pickup_address, dropoff_address, pickup_time, passenger_count, booking_status, vehicle_id, vehicle_type_requested, notes, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    None,
                    self.charter_date.date().toString("MM/dd/yyyy"),
                    self.pickup.text(),
                    self.destination.text(),
                    self.pickup_time.text(),
                    self.passenger_count.value(),
                    self.status.currentText(),
                    self.vehicle.currentData(),
                    self._vehicle_categories.get(vehicle_requested_id, "") if vehicle_requested_id else None,
                    self.notes.toPlainText()
                ))
                self.db.commit()
                QMessageBox.information(self, "Success", "Charter duplicated successfully.")
                cur.close()
                self.load_charter_data()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to duplicate: {e}")
    
    def delete_charter(self):
        """Delete current charter after confirmation"""
        if not self.reserve_number:
            QMessageBox.warning(self, "Warning", "No charter loaded to delete.")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete charter '{self.reserve_number}'?\nThis action cannot be undone.",
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
                cur.execute("DELETE FROM charters WHERE reserve_number = %s", (self.reserve_number,))
                self.db.commit()
                QMessageBox.information(self, "Success", "Charter deleted successfully.")
                cur.close()
                self.saved.emit({"action": "delete", "reserve_number": self.reserve_number})
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
                self.db.rollback()
    
    def on_charter_saved(self, data):
        """Handle child dialog save - refresh current view"""
        if self.reserve_number:
            self.load_charter_data()
    
    def lock_charter(self):
        """Lock charter from further edits"""
        try:
            cur = self.db.get_cursor()
            cur.execute("UPDATE charters SET is_locked = true WHERE reserve_number = %s",
                       (self.reserve_number,))
            self.db.commit()
            self.is_locked = True
            self.lock_btn.setEnabled(False)
            self.unlock_btn.setEnabled(True)
            # Disable edit fields
            for widget in [self.pickup, self.destination, self.pickup_time, 
                          self.passenger_count, self.notes, self.status]:
                widget.setReadOnly(True) if hasattr(widget, 'setReadOnly') else widget.setEnabled(False)
            QMessageBox.information(self, "Success", "Charter locked")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Error", f"Failed to lock charter: {e}")
    
    def unlock_charter(self):
        """Unlock charter for edits"""
        try:
            cur = self.db.get_cursor()
            cur.execute("UPDATE charters SET is_locked = false WHERE reserve_number = %s",
                       (self.reserve_number,))
            self.db.commit()
            self.is_locked = False
            self.lock_btn.setEnabled(True)
            self.unlock_btn.setEnabled(False)
            # Enable edit fields
            for widget in [self.pickup, self.destination, self.pickup_time, 
                          self.passenger_count, self.notes, self.status]:
                widget.setReadOnly(False) if hasattr(widget, 'setReadOnly') else widget.setEnabled(True)
            QMessageBox.information(self, "Success", "Charter unlocked")
        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Error", f"Failed to unlock charter: {e}")
    
    def cancel_charter(self):
        """Cancel charter"""
        reply = QMessageBox.question(self, "Confirm", "Cancel this charter?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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
                cur.execute("UPDATE charters SET booking_status = 'cancelled' WHERE reserve_number = %s",
                           (self.reserve_number,))
                self.db.commit()
                self.status.setCurrentText("Cancelled")
                QMessageBox.information(self, "Success", "Charter cancelled")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to cancel charter: {e}")
                self.db.rollback()
    
    def add_order(self):
        """Add new beverage/product order - Shopping Cart"""
        if not self.reserve_number:
            QMessageBox.warning(self, "Warning", "Save charter first before adding orders.")
            return
        
        # Open shopping cart dialog
        dialog = BeverageShoppingCartDialog(self.db, self.reserve_number, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Success", "Order added to charter.")
            self.load_charter_data()  # Refresh orders display
    
    def edit_order(self):
        """Edit selected order"""
        row = self.orders_table.currentRow()
        if row >= 0:
            # TODO: Open order edit dialog
            pass
    
    def delete_order(self):
        """Delete selected order"""
        row = self.orders_table.currentRow()
        if row >= 0:
            # TODO: Delete from database
            pass
    
    def add_payment(self):
        """Add new payment"""
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle("Record Payment (Manual)")
            vbox = QVBoxLayout(dlg)
            info = QLabel("This records a payment you already received (cash/check/bank/etc.). It does not charge customers or connect to any online service.")
            info.setWordWrap(True)
            vbox.addWidget(info)

            form = QFormLayout()
            date_edit = StandardDateEdit(prefer_month_text=True)

            date_edit.setDisplayFormat("MM/dd/yyyy")
            date_edit.setCalendarPopup(True)
            date_edit.setDate(QDate.currentDate())

            amount_spin = QDoubleSpinBox()
            amount_spin.setPrefix("$")
            amount_spin.setDecimals(2)
            amount_spin.setMaximum(10_000_000.00)
            amount_spin.setMinimum(0.00)

            method_combo = QComboBox()
            allowed_methods = self._get_allowed_payment_methods()
            method_combo.addItems(allowed_methods)
            tip_methods = QLabel("Tip: eTransfer → bank_transfer; Square card → credit_card; Cash → cash")
            tip_methods.setStyleSheet("font-size: 10px; color: #666;")

            reference_edit = QLineEdit()
            status_combo = QComboBox()
            # Align with DB constraint: pending, paid, partial, failed, refunded, cancelled
            status_combo.addItems(["pending", "paid", "partial", "failed", "refunded", "cancelled"]) 
            try:
                status_combo.setCurrentText("paid")
            except Exception:
                pass

            reconciled_check = QCheckBox("Reconciled")

            form.addRow("Date", date_edit)
            form.addRow("Amount", amount_spin)
            form.addRow("Method", method_combo)
            form.addRow("", tip_methods)
            form.addRow("Reference", reference_edit)
            form.addRow("Status", status_combo)
            form.addRow("", reconciled_check)
            def _update_reference_placeholder(text: str):
                if text == "bank_transfer":
                    reference_edit.setPlaceholderText("eTransfer confirmation number")
                elif text == "credit_card":
                    reference_edit.setPlaceholderText("Square transaction #")
                else:
                    reference_edit.setPlaceholderText("Reference or memo (optional)")

            _update_reference_placeholder(method_combo.currentText())
            method_combo.currentTextChanged.connect(_update_reference_placeholder)

            vbox.addLayout(form)

            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            vbox.addWidget(buttons)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)

            if dlg.exec() == QDialog.DialogCode.Accepted:
                payment_date = date_edit.date().toString("MM/dd/yyyy")
                amount = float(amount_spin.value())
                method = method_combo.currentText()
                reference = reference_edit.text().strip()
                status = status_combo.currentText()
                reconciled = True if reconciled_check.isChecked() else False

                if amount <= 0:
                    QMessageBox.warning(self, "Validation", "Amount must be greater than zero.")
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
                    cur.execute(
                        """
                        INSERT INTO payments (
                            reserve_number, payment_date, amount, payment_method, reference, status, reconciled
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            self.reserve_number,
                            payment_date,
                            amount,
                            method,
                            reference,
                            status,
                            reconciled,
                        ),
                    )
                    self.db.commit()
                    QMessageBox.information(self, "Success", "Payment added successfully")
                    # Reload payments and balances
                    self.load_charter_data()
                except Exception as e:
                    self.db.rollback()
                    QMessageBox.critical(self, "Error", f"Failed to add payment: {e}")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to open payment dialog: {e}")


# ============================================================================
# STANDARDIZED DRILL-DOWN PATTERNS
# ============================================================================

class StandardDrillDownDialog(QDialog):
    """
    Base class for standardized drill-down dialogs.
    Provides consistent button layout, add/duplicate/delete patterns, and navigation.
    
    BUTTON LAYOUT (TOP):
    - Left: Action-specific buttons (Lock, Suspend, Retire, etc.) + Stretch
    - Right: [Add New] [Duplicate] [Delete] [Save] [Close]
    
    SUBCLASS REQUIREMENTS:
    - Override create_content_layout() to build main UI (tabs, forms, etc.)
    - Override load_record_data() to populate fields from database
    - Override save_record_data() to persist changes to database
    - Set self.record_id and self.record_label (e.g., "client_id", "client_name")
    """
    
    saved = pyqtSignal(dict)  # Emitted when record is saved
    
    def __init__(self, db, record_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.record_id = record_id
        self.record_type = "Record"  # Override in subclass (e.g., "Client", "Employee")
        self.record_label = ""  # Override in subclass (e.g., "client_id", "reserve_number")
        self.record_data = {}
        
        self.setGeometry(50, 50, 1400, 900)
        self.setWindowTitle(f"{self.record_type} Detail - {record_id or 'New'}")
        
        main_layout = QVBoxLayout()
        
        # ===== CONTENT AREA (Tabs, Forms, etc.) =====
        content = self.create_content_layout()
        main_layout.addWidget(content)
        
        # ===== STANDARD BUTTON LAYOUT (TOP) =====
        button_layout = QHBoxLayout()
        
        # Left side: Action-specific buttons (for subclasses to add)
        self.action_button_area = QHBoxLayout()
        button_layout.addLayout(self.action_button_area)
        button_layout.addStretch()
        
        # Right side: Standard buttons
        self.add_new_btn = QPushButton("➕ Add New")
        self.add_new_btn.clicked.connect(self.add_new_record)
        button_layout.addWidget(self.add_new_btn)
        
        self.duplicate_btn = QPushButton("📋 Duplicate")
        self.duplicate_btn.clicked.connect(self.duplicate_record)
        button_layout.addWidget(self.duplicate_btn)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_record)
        button_layout.addWidget(self.delete_btn)
        
        self.save_btn = QPushButton("💾 Save Changes")
        self.save_btn.clicked.connect(self.save_and_emit)
        button_layout.addWidget(self.save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        main_layout.insertLayout(0, button_layout)
        self.setLayout(main_layout)
        
        # Load record data if record_id provided
        if record_id:
            self.load_record_data()
    
    def create_content_layout(self):
        """
        Override in subclass to create main UI (QTabWidget, forms, etc.).
        Return a QWidget or QTabWidget.
        Default: empty widget.
        """
        return QWidget()
    
    def load_record_data(self):
        """Override in subclass to load record from database and populate UI fields."""
        pass
    
    def save_record_data(self):
        """Override in subclass to persist record changes to database."""
        pass
    
    def add_new_record(self):
        """Prompt user to create a new record; open a new instance of this dialog."""
        reply = QMessageBox.question(
            self,
            "Add New Record",
            f"Create a new {self.record_type.lower()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Open new dialog without record_id
            new_dialog = self.__class__(self.db, record_id=None, parent=self.parent())
            new_dialog.saved.connect(self.on_saved)
            new_dialog.exec()
    
    def duplicate_record(self):
        """Duplicate current record with user-specified identifier change."""
        if not self.record_id:
            QMessageBox.warning(self, "Warning", "No record loaded to duplicate.")
            return
        
        # Collect current record data
        record_copy = self.record_data.copy()
        
        # Show dialog to change identifier
        dialog = DuplicateRecordDialog(self.record_type, record_copy, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Create new instance and save
            try:
                # Subclass should handle the actual duplication logic
                self.perform_duplicate(dialog.new_identifier)
                QMessageBox.information(self, "Success", f"{self.record_type} duplicated successfully.")
                self.load_record_data()  # Refresh current view
            except Exception as e:
                try:
                    self.db.rollback()
                except:
                    pass
                QMessageBox.critical(self, "Error", f"Failed to duplicate: {e}")
    
    def perform_duplicate(self, new_identifier):
        """
        Override in subclass to perform actual duplication.
        new_identifier: The new name/id for the duplicated record.
        Should insert new record into database.
        """
        raise NotImplementedError("Subclass must implement perform_duplicate()")
    
    def delete_record(self):
        """Delete current record after confirmation."""
        if not self.record_id:
            QMessageBox.warning(self, "Warning", "No record loaded to delete.")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete this {self.record_type.lower()} record?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.perform_delete()
                QMessageBox.information(self, "Success", f"{self.record_type} deleted successfully.")
                self.close()
                self.saved.emit({"action": "delete", "record_id": self.record_id})
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
    
    def perform_delete(self):
        """Override in subclass to perform actual deletion."""
        raise NotImplementedError("Subclass must implement perform_delete()")
    
    def save_and_emit(self):
        """Save record and emit saved signal."""
        try:
            self.save_record_data()
            QMessageBox.information(self, "Success", f"{self.record_type} saved successfully.")
            self.saved.emit(self.record_data)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
    
    def on_saved(self, record_data):
        """Handle child dialog save (when duplicate is created)."""
        self.load_record_data()


class DuplicateRecordDialog(QDialog):
    """
    Generic dialog for duplicating a record.
    Allows user to change a key identifier (name, id, etc.).
    """
    
    def __init__(self, record_type, record_data, parent=None):
        super().__init__(parent)
        self.record_type = record_type
        self.record_data = record_data
        self.new_identifier = None
        
        self.setWindowTitle(f"Duplicate {record_type}")
        self.setGeometry(100, 100, 500, 200)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel(f"Duplicate {record_type} Record")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Info message
        info = QLabel(f"Enter a new name or identifier for the duplicate {record_type.lower()} record:")
        layout.addWidget(info)
        
        # Input field
        form = QFormLayout()
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText(f"New {record_type.lower()} name...")
        form.addRow(f"New {record_type.lower()} name:", self.identifier_input)
        layout.addLayout(form)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("✓ Duplicate")
        ok_btn.clicked.connect(self.accept_duplicate)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def accept_duplicate(self):
        """Validate and accept the new identifier."""
        new_name = self.identifier_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Warning", "Please enter a name for the duplicate record.")
            return
        
        self.new_identifier = new_name
        self.accept()


# ============================================================================
# ROUTING STOP EDITOR
# ============================================================================

class RoutingStopDialog(QDialog):
    """
    Dialog for adding or editing a single routing stop.
    Supports all stop types: pickup, drop-off, leave for, return to, extra time, split run
    """
    
    def __init__(self, parent=None, stop_data=None):
        super().__init__(parent)
        self.stop_data = stop_data or {}
        self.setWindowTitle("Add/Edit Routing Stop")
        self.setMinimumWidth(500)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout()
        
        # Stop Type
        self.stop_type = QComboBox()
        self.stop_type.addItems([
            "PICKUP AT",
            "DROP OFF AT",
            "LEAVE RED DEER FOR",
            "DROP OFF FOR SPLIT RUN AT",
            "PICK UP AT",
            "RETURN TO RED DEER AT",
            "EXTRA TIME ADDED",
            "WAYPOINT / STOP"
        ])
        if 'type' in self.stop_data:
            self.stop_type.setCurrentText(self.stop_data['type'])
        layout.addRow("Stop Type:", self.stop_type)
        
        # Location/Address
        self.location = QLineEdit()
        self.location.setPlaceholderText("Enter address or location name")
        if 'location' in self.stop_data:
            self.location.setText(self.stop_data['location'])
        layout.addRow("Location/Address:", self.location)
        
        # Time
        self.time = QLineEdit()
        self.time.setPlaceholderText("HH:MM (e.g. 14:30)")
        if 'time' in self.stop_data:
            self.time.setText(self.stop_data['time'])
        layout.addRow("Time:", self.time)
        
        # Distance
        self.distance = QDoubleSpinBox()
        self.distance.setMaximum(9999.9)
        self.distance.setSuffix(" km")
        if 'distance' in self.stop_data:
            try:
                self.distance.setValue(float(self.stop_data['distance']))
            except:
                pass
        layout.addRow("Distance:", self.distance)
        
        # Duration
        self.duration = QSpinBox()
        self.duration.setMaximum(1440)  # 24 hours in minutes
        self.duration.setSuffix(" min")
        if 'duration' in self.stop_data:
            try:
                self.duration.setValue(int(self.stop_data['duration']))
            except:
                pass
        layout.addRow("Duration:", self.duration)
        
        # Notes
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setPlaceholderText("Special instructions, gate codes, etc.")
        if 'notes' in self.stop_data:
            self.notes.setPlainText(self.stop_data['notes'])
        layout.addRow("Notes:", self.notes)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)
        
        self.setLayout(layout)
    
    def validate_and_accept(self):
        """Validate data before accepting"""
        if not self.location.text().strip():
            QMessageBox.warning(self, "Validation Error", "Location is required.")
            return
        
        self.accept()
    
    def get_stop_data(self):
        """Return stop data as dictionary"""
        return {
            'type': self.stop_type.currentText(),
            'location': self.location.text().strip(),
            'time': self.time.text().strip(),
            'distance': self.distance.value(),
            'duration': self.duration.value(),
            'notes': self.notes.toPlainText().strip()
        }


# BEVERAGE & PRODUCT SHOPPING CART
# ============================================================================

class BeverageShoppingCartDialog(QDialog):
    """
    Shopping cart for adding beverage and product orders to a charter.
    Browse items, add to cart, set quantities, and save order.
    """
    
    def __init__(self, db, reserve_number, parent=None):
        super().__init__(parent)
        self.db = db
        self.reserve_number = reserve_number
        self.cart_items = []  # List of {item_id, name, unit_price, quantity, total}
        
        self.setWindowTitle(f"🛒 Beverage & Product Order - Charter {reserve_number}")
        self.setGeometry(100, 100, 900, 600)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🛒 Shopping Cart - Add Beverages & Products")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Split layout: Product catalog on left, Cart on right
        main_split = QHBoxLayout()
        
        # ===== LEFT SIDE: PRODUCT CATALOG =====
        catalog_group = QGroupBox("📦 Available Products")
        catalog_layout = QVBoxLayout()
        
        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search products...")
        self.search_box.textChanged.connect(self.filter_products)
        search_layout.addWidget(self.search_box)
        catalog_layout.addLayout(search_layout)
        
        # Product table (images removed)
        self.product_table = QTableWidget()
        self.product_table.setColumnCount(4)
        self.product_table.setHorizontalHeaderLabels(["Item", "Category", "Unit Price", "Description"])
        header = self.product_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.product_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.product_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.product_table.doubleClicked.connect(self.add_to_cart_from_table)
        catalog_layout.addWidget(self.product_table)
        
        # Add to cart button
        add_to_cart_btn = QPushButton("➕ Add Selected to Cart")
        add_to_cart_btn.clicked.connect(self.add_to_cart_from_table)
        catalog_layout.addWidget(add_to_cart_btn)
        
        catalog_group.setLayout(catalog_layout)
        main_split.addWidget(catalog_group)
        
        # ===== RIGHT SIDE: SHOPPING CART =====
        cart_group = QGroupBox("🛒 Your Cart")
        cart_layout = QVBoxLayout()
        
        # Cart table
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(5)
        self.cart_table.setHorizontalHeaderLabels(["Item", "Unit Price", "Qty", "Total", ""])
        header = self.cart_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.cart_table.setColumnWidth(3, 110)
        self.cart_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        cart_layout.addWidget(self.cart_table)
        
        # Cart summary (GST shown for guest collection/reporting only)
        summary_layout = QFormLayout()
        
        self.our_cost_label = QLabel("$0.00")
        self.our_cost_label.setToolTip("Our wholesale cost for these items")
        summary_layout.addRow("Our Cost (wholesale):", self.our_cost_label)
        
        self.subtotal_label = QLabel("$0.00")
        self.subtotal_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.subtotal_label.setToolTip("Beverage subtotal used for charter invoice (pre-GST)")
        summary_layout.addRow("Beverage Subtotal (to invoice):", self.subtotal_label)
        
        self.gst_label = QLabel("$0.00")
        self.gst_label.setToolTip("GST for guest collection/reporting; not posted to invoice")
        summary_layout.addRow("Guest GST 5% (not invoiced):", self.gst_label)
        
        self.total_label = QLabel("$0.00")
        self.total_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.total_label.setStyleSheet("color: #27ae60;")
        self.total_label.setToolTip("Guest collection total during trip (subtotal + GST)")
        summary_layout.addRow("Guest Collection Total:", self.total_label)
        
        self.profit_label = QLabel("$0.00")
        self.profit_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.profit_label.setStyleSheet("color: #2980b9;")
        self.profit_label.setToolTip("Profit: charged price - (our cost + GST + deposit)")
        summary_layout.addRow("Our Profit (dispatcher only):", self.profit_label)
        
        cart_layout.addLayout(summary_layout)
        
        # Cart actions
        cart_actions = QHBoxLayout()
        clear_cart_btn = QPushButton("🗑️ Clear Cart")
        clear_cart_btn.clicked.connect(self.clear_cart)
        cart_actions.addWidget(clear_cart_btn)
        cart_layout.addLayout(cart_actions)
        
        cart_group.setLayout(cart_layout)
        main_split.addWidget(cart_group)
        
        layout.addLayout(main_split)
        
        # ===== BOTTOM BUTTONS =====
        button_layout = QHBoxLayout()
        
        save_order_btn = QPushButton("💾 Save Order to Charter")
        save_order_btn.clicked.connect(self.save_order)
        save_order_btn.setStyleSheet("background-color: #27ae60; color: white; padding: 8px; font-weight: bold;")
        button_layout.addWidget(save_order_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Load products
        self.load_products()
    
    def load_products(self):
        """Load available beverage and product items with descriptions"""
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
            
            # Load from beverages/products table (create if doesn't exist)
            cur.execute("""
                SELECT item_id, item_name, category, unit_price, COALESCE(description, ''),
                       our_cost, deposit_amount
                FROM beverage_products
                ORDER BY category, item_name
            """)
            
            rows = cur.fetchall()
            self.product_table.setRowCount(len(rows))
            
            for row_idx, row_data in enumerate(rows):
                item_id, name, category, price, description, our_cost, deposit_amount = row_data

                # Optional: reasonable row height
                self.product_table.setRowHeight(row_idx, 40)

                # Column 0: Item name (store all data)
                name_item = QTableWidgetItem(str(name))
                name_item.setData(Qt.ItemDataRole.UserRole, {
                    'item_id': item_id,
                    'unit_price': float(price or 0),
                    'our_cost': float(our_cost or 0),
                    'deposit': float(deposit_amount or 0)
                })
                self.product_table.setItem(row_idx, 0, name_item)

                # Columns 1-3: Product details
                self.product_table.setItem(row_idx, 1, QTableWidgetItem(str(category or "")))
                self.product_table.setItem(row_idx, 2, QTableWidgetItem(f"${price:.2f}"))

                # Column 3: Description (read-only)
                desc_item = QTableWidgetItem(str(description or ""))
                desc_item.setFlags(desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.product_table.setItem(row_idx, 3, desc_item)
            
            cur.close()
        except Exception as e:
            # If table doesn't exist, show sample products
            QMessageBox.warning(self, "Info", f"Beverage products table not found. Showing sample items.\n{e}")
            self.load_sample_products()
    
    def load_sample_products(self):
        """Load sample products if database table doesn't exist"""
        sample_products = [
            ("Bottled Water", "Beverages", 2.00, 100),
            ("Coca-Cola", "Beverages", 2.50, 50),
            ("Champagne (Bottle)", "Alcohol", 45.00, 20),
            ("Wine (Red)", "Alcohol", 35.00, 15),
            ("Wine (White)", "Alcohol", 32.00, 15),
            ("Beer (6-pack)", "Alcohol", 18.00, 30),
            ("Juice Box", "Beverages", 1.50, 80),
            ("Energy Drink", "Beverages", 3.50, 40),
            ("Chips", "Snacks", 3.00, 60),
            ("Chocolate Bar", "Snacks", 2.50, 75),
        ]
        
        self.product_table.setRowCount(len(sample_products))
        for row_idx, (name, category, price, stock) in enumerate(sample_products):
            self.product_table.setRowHeight(row_idx, 40)

            # Columns 0-3: Product details (no images)
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.ItemDataRole.UserRole, {'item_id': row_idx + 1, 'unit_price': price, 'our_cost': 0.0, 'deposit': 0.0})
            self.product_table.setItem(row_idx, 0, name_item)
            self.product_table.setItem(row_idx, 1, QTableWidgetItem(category))
            self.product_table.setItem(row_idx, 2, QTableWidgetItem(f"${price:.2f}"))
            self.product_table.setItem(row_idx, 3, QTableWidgetItem(f"In stock: {stock}"))
    
    # Images removed: no icon loading needed
    
    def filter_products(self):
        """Filter products by search text using fuzzy matching"""
        search_text = self.search_box.text().lower().strip()
        
        for row in range(self.product_table.rowCount()):
            item_name = self.product_table.item(row, 0).text().lower()
            category = self.product_table.item(row, 1).text().lower()
            
            # Fuzzy matching: show if search is empty OR similarity > 60%
            if not search_text:
                self.product_table.setRowHidden(row, False)
            else:
                # Check name similarity
                name_ratio = SequenceMatcher(None, search_text, item_name).ratio()
                # Check category similarity
                category_ratio = SequenceMatcher(None, search_text, category).ratio()
                # Check if search is substring (exact match)
                is_substring = search_text in item_name or search_text in category
                
                # Show row if: exact substring match OR fuzzy match > 60%
                if is_substring or name_ratio > 0.6 or category_ratio > 0.6:
                    self.product_table.setRowHidden(row, False)
                else:
                    self.product_table.setRowHidden(row, True)
    
    def add_to_cart_from_table(self):
        """Add selected product to cart"""
        row = self.product_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Warning", "Please select a product first.")
            return
        
        # Column 0: Item name (has data stored)
        item_name = self.product_table.item(row, 0).text()
        item_data = self.product_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        item_id = item_data['item_id']
        unit_price = item_data['unit_price']
        our_cost = item_data['our_cost']
        deposit = item_data['deposit']
        
        # Check if already in cart
        for cart_item in self.cart_items:
            if cart_item['item_id'] == item_id:
                cart_item['quantity'] += 1
                cart_item['total'] = cart_item['quantity'] * cart_item['unit_price']
                self.refresh_cart_display()
                return
        
        # Add new item to cart
        self.cart_items.append({
            'item_id': item_id,
            'name': item_name,
            'unit_price': unit_price,
            'our_cost': our_cost,
            'deposit': deposit,
            'quantity': 1,
            'total': unit_price
        })
        
        self.refresh_cart_display()
    
    def refresh_cart_display(self):
        """Refresh cart table and totals"""
        self.cart_table.setRowCount(len(self.cart_items))
        
        subtotal = 0
        
        for row_idx, item in enumerate(self.cart_items):
            # Item name
            self.cart_table.setItem(row_idx, 0, QTableWidgetItem(item['name']))
            
            # Unit price
            self.cart_table.setItem(row_idx, 1, QTableWidgetItem(f"${item['unit_price']:.2f}"))
            
            # Quantity (editable spinbox)
            qty_spin = QSpinBox()
            qty_spin.setMinimum(1)
            qty_spin.setMaximum(999)
            qty_spin.setValue(item['quantity'])
            qty_spin.valueChanged.connect(lambda val, idx=row_idx: self.update_quantity(idx, val))
            self.cart_table.setCellWidget(row_idx, 2, qty_spin)
            
            # Total
            self.cart_table.setItem(row_idx, 3, QTableWidgetItem(f"${item['total']:.2f}"))
            
            # Remove button
            remove_btn = QPushButton("❌")
            remove_btn.clicked.connect(lambda checked, idx=row_idx: self.remove_from_cart(idx))
            self.cart_table.setCellWidget(row_idx, 4, remove_btn)
            
            subtotal += item['total']
        
        # Update totals
        gst = subtotal * 0.05
        total = subtotal + gst
        
        # Calculate profit: unit_price already includes GST and deposit, so profit = charged - our_cost
        our_cost_total = sum(item.get('our_cost', 0) * item['quantity'] for item in self.cart_items)
        profit = subtotal - our_cost_total
        
        self.our_cost_label.setText(f"${our_cost_total:.2f}")
        self.subtotal_label.setText(f"${subtotal:.2f}")
        self.gst_label.setText(f"${gst:.2f}")
        self.total_label.setText(f"${total:.2f}")
        self.profit_label.setText(f"${profit:.2f}")
    
    def update_quantity(self, row_idx, new_qty):
        """Update quantity for cart item"""
        if row_idx < len(self.cart_items):
            self.cart_items[row_idx]['quantity'] = new_qty
            self.cart_items[row_idx]['total'] = new_qty * self.cart_items[row_idx]['unit_price']
            self.refresh_cart_display()
    
    def remove_from_cart(self, row_idx):
        """Remove item from cart"""
        if row_idx < len(self.cart_items):
            del self.cart_items[row_idx]
            self.refresh_cart_display()
    
    def clear_cart(self):
        """Clear all items from cart"""
        reply = QMessageBox.question(
            self,
            "Clear Cart",
            "Remove all items from cart?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.cart_items = []
            self.refresh_cart_display()
    
    def save_order(self):
        """Save order to charter"""
        if not self.cart_items:
            QMessageBox.warning(self, "Warning", "Cart is empty. Add items before saving.")
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
            
            # Insert order header
            subtotal = sum(item['total'] for item in self.cart_items)
            gst = subtotal * 0.05
            total = subtotal + gst
            
            cur.execute("""
                INSERT INTO beverage_orders 
                (reserve_number, order_date, subtotal, gst, total, status)
                VALUES (%s, NOW(), %s, %s, %s, 'pending')
                RETURNING order_id
            """, (self.reserve_number, subtotal, gst, total))
            
            order_id = cur.fetchone()[0]
            
            # Insert order items
            for item in self.cart_items:
                cur.execute("""
                    INSERT INTO beverage_order_items
                    (order_id, item_id, item_name, quantity, unit_price, total)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    order_id,
                    item['item_id'],
                    item['name'],
                    item['quantity'],
                    item['unit_price'],
                    item['total']
                ))
            
            self.db.commit()
            cur.close()
            
            QMessageBox.information(
                self,
                "Success",
                f"Order saved!\n\nItems: {len(self.cart_items)}\nTotal: ${total:.2f}"
            )
            
            self.accept()
            
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save order:\n{e}")
