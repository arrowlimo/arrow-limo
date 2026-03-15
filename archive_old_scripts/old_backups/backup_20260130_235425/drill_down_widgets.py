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
    QTimeEdit, QRadioButton, QButtonGroup
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

        # Ensure we are not in an aborted transaction state
        try:
            self.db.rollback()
        except Exception:
            pass
        
        # Initialize maps (populated by loaders)
        self._vehicle_types = {}
        self._vehicle_pricing_defaults = {}
        self._charter_types = []
        self._charge_defaults = []
        
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
        
        # Tab 3: Edit Tables (charge defaults, charter types)
        edit_tables_tab = self.create_edit_tables_tab()
        tabs.addTab(edit_tables_tab, "🧰 Edit Tables")

        # Tab 4: Related Orders/Beverages
        orders_tab = self.create_orders_tab()
        tabs.addTab(orders_tab, "Orders & Beverages")
        
        # Tab 4.5: Beverage Printout (NEW)
        beverage_tab = self.create_beverage_printout_tab()
        tabs.addTab(beverage_tab, "🍷 Beverage Printout")
        
        # Tab 5: Payments
        payments_tab = self.create_payments_tab()
        tabs.addTab(payments_tab, "Payments")
        
        # Expose tabs for programmatic selection
        self.tabs = tabs

        layout.addWidget(tabs)
        self.setLayout(layout)
        
        # Load dropdown options BEFORE loading data
        self.ensure_charge_defaults_table()
        self.load_driver_options()
        self.load_vehicle_options()
        self.load_vehicle_requested_options()
        self.load_vehicle_pricing_defaults()
        self.load_charter_type_options()
        self.load_charge_defaults()
        
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
                'edit': 2,
                'orders': 3,
                'routing': 0,
                'payments': 5,
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
        """Load all available vehicles into assigned-vehicle dropdown"""
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
            
            # Store vehicle type for label updates
            self._vehicle_types = {}
            
            # Clear and populate assigned vehicle dropdown
            self.vehicle.clear()
            self.vehicle.addItem("")  # Add empty option
            
            for veh_id, number, vtype, vcat, status in vehicles:
                display_number = str(number or "")
                self.vehicle.addItem(display_number, veh_id)
                self._vehicle_types[veh_id] = vtype or ""
            
            # Wire up selection callbacks for type label
            self.vehicle.currentIndexChanged.connect(self._update_vehicle_type_display)
            
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
    
    def load_vehicle_requested_options(self):
        """Load vehicle type options from the vehicle default pay table"""
        try:
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
                SELECT DISTINCT vehicle_type
                FROM vehicle_pricing_defaults
                WHERE vehicle_type IS NOT NULL AND vehicle_type <> ''
                ORDER BY vehicle_type
            """)
            rows = cur.fetchall()
            cur.close()

            self.vehicle_requested.clear()
            self.vehicle_requested.addItem("")
            for (vehicle_type,) in rows:
                self.vehicle_requested.addItem(str(vehicle_type))
        except Exception:
            # If pricing table is not available, fall back to empty list
            self.vehicle_requested.clear()
            self.vehicle_requested.addItem("")

    def load_vehicle_pricing_defaults(self):
        """Load vehicle pricing defaults for the pay table fields"""
        self._vehicle_pricing_defaults = {}
        try:
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
                SELECT vehicle_type, charter_type_code, hourly_rate, package_rate,
                       package_hours, minimum_hours, extra_time_rate, standby_rate,
                       split_run_before_hours, split_run_after_hours
                FROM vehicle_pricing_defaults
                WHERE is_active = true
                ORDER BY vehicle_type, charter_type_code
            """)
            for row in cur.fetchall():
                key = (str(row[0] or ""), str(row[1] or ""))
                self._vehicle_pricing_defaults[key] = {
                    "hourly_rate": float(row[2] or 0),
                    "package_rate": float(row[3] or 0),
                    "package_hours": float(row[4] or 0),
                    "minimum_hours": int(row[5] or 0),
                    "extra_time_rate": float(row[6] or 0),
                    "standby_rate": float(row[7] or 0),
                    "split_run_before_hours": float(row[8] or 0),
                    "split_run_after_hours": float(row[9] or 0),
                }
            cur.close()
        except Exception:
            self._vehicle_pricing_defaults = {}

    def load_charter_type_options(self):
        """Load charter type list for run type selection"""
        self.charter_type.clear()
        self.charter_type.addItem("", "")
        try:
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
                SELECT type_code, type_name
                FROM charter_types
                WHERE is_active = true
                ORDER BY display_order
            """)
            rows = cur.fetchall()
            cur.close()
            for code, name in rows:
                label = f"{code} - {name}" if name else str(code)
                self.charter_type.addItem(label, str(code or ""))
        except Exception:
            # Fallback list
            fallback_types = [
                ("AIRPORT_CGY", "Airport Pickup - Calgary"),
                ("AIRPORT_EDM", "Airport Pickup - Edmonton"),
                ("AIRPORT_RD", "Airport Pickup - Red Deer"),
                ("WEDDING", "Wedding"),
                ("CORP", "Corporate Event"),
                ("CONCERT", "Concert"),
                ("PROM", "Prom"),
                ("BACHELOR", "Bachelor Party"),
                ("TOUR", "Tour"),
                ("FUNERAL", "Funeral"),
                ("OTHER", "Other")
            ]
            for code, name in fallback_types:
                label = f"{code} - {name}"
                self.charter_type.addItem(label, code)

    def apply_vehicle_pricing_defaults(self):
        """Apply pricing defaults based on selected vehicle type and charter type"""
        vehicle_type = self.vehicle_requested.currentText().strip()
        charter_code = str(self.charter_type.currentData() or "").strip()
        if not vehicle_type:
            return

        # Try exact match on vehicle + charter type; otherwise first match by vehicle
        data = self._vehicle_pricing_defaults.get((vehicle_type, charter_code))
        if not data:
            for (v_type, _), values in self._vehicle_pricing_defaults.items():
                if v_type == vehicle_type:
                    data = values
                    break

        if not data:
            return

        self.vehicle_pay_hourly.setValue(data.get("hourly_rate", 0))
        self.vehicle_pay_package.setValue(data.get("package_rate", 0))
        self.vehicle_pay_package_hours.setValue(data.get("package_hours", 0))
        self.vehicle_pay_extra_time.setValue(data.get("extra_time_rate", 0))
        self.vehicle_pay_standby.setValue(data.get("standby_rate", 0))

        # Also update billing rate/min hours defaults and new checkbox fields
        self.hourly_rate.setValue(data.get("hourly_rate", 0))
        self.min_hours.setValue(int(data.get("minimum_hours", 0)))
        self.package_price.setValue(data.get("package_rate", 0))
        self.package_hours.setValue(data.get("package_hours", 0))
        
        # Recalculate charges after updating vehicle pricing
        self.recalculate_charge_totals()


    def toggle_custom_rate(self):
        """Enable/disable custom rate inputs"""
        enabled = self.custom_rate_cb.isChecked()
        self.custom_rate_type.setEnabled(enabled)
        self.custom_rate_amount.setEnabled(enabled)
    
    def toggle_billing_fields(self, *_):
        """Show/hide billing fields based on Billing Type selection"""
        billing_type = (self.billing_type.currentText() or "").strip()
        is_hourly = billing_type == "Hourly"
        is_package = billing_type == "Package"
        
        # Hourly Rate and Min Hours (shown when Hourly is selected)
        self.hourly_rate_label.setVisible(is_hourly)
        self.hourly_rate.setVisible(is_hourly)
        self.min_hours_label.setVisible(is_hourly)
        self.min_hours.setVisible(is_hourly)
        
        # Package Price and Hours (shown when Package is selected)
        self.package_price_label.setVisible(is_package)
        self.package_price.setVisible(is_package)
        self.package_hours_label.setVisible(is_package)
        self.package_hours.setVisible(is_package)
        
        # Extra Time and Standby (shown when either Hourly or Package is selected)
        show_extras = is_hourly or is_package
        self.extra_time_label.setVisible(show_extras)
        self.vehicle_pay_extra_time.setVisible(show_extras)
        self.standby_label.setVisible(show_extras)
        self.vehicle_pay_standby.setVisible(show_extras)
        
        # Also update old pay table fields visibility
        self.vehicle_pay_hourly.setVisible(is_hourly)
        self.vehicle_pay_package.setVisible(is_package)
        self.vehicle_pay_package_hours.setVisible(is_package)
        
        # Recalculate charges when billing type changes
        self.recalculate_charge_totals()
    
    def on_rate_type_changed(self, rate_type=None):
        """Handle billing type changes (legacy compatibility for dropdown-based code)"""
        if rate_type:
            if rate_type in ("Hr", "Hourly"):
                self.billing_type.setCurrentText("Hourly")
            elif rate_type in ("Pkg", "Daily", "Package"):
                self.billing_type.setCurrentText("Package")

    def ensure_charge_defaults_table(self):
        """Ensure charge defaults table exists and is seeded"""
        default_seed = [
            ("Charter Fee", "Hr", 0.0, True),
            ("Gratuity", "%", 18.0, True),
            ("Extra Time", "Hr", 0.0, True),
            ("Beverage Order", "Each", 0.0, True),
            ("Broken Glassware", "Total", 0.0, False),
            ("Bodily Fluid Cleanup", "Total", 0.0, False),
            ("Extra Cleanup", "Total", 0.0, False),
            ("Smoking", "Total", 0.0, False),
            ("Damage to Vehicle/Equipment", "Total", 0.0, False),
            ("Open Emergency Exit", "Total", 0.0, False),
        ]
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS charter_charge_defaults (
                    id SERIAL PRIMARY KEY,
                    description TEXT NOT NULL,
                    charge_type TEXT,
                    default_price NUMERIC(12,2) DEFAULT 0,
                    default_listed BOOLEAN DEFAULT TRUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("SELECT COUNT(*) FROM charter_charge_defaults")
            count = cur.fetchone()[0] or 0
            if count == 0:
                for idx, (desc, ctype, price, listed) in enumerate(default_seed, start=1):
                    cur.execute("""
                        INSERT INTO charter_charge_defaults
                        (description, charge_type, default_price, default_listed, sort_order)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (desc, ctype, price, listed, idx))
            self.db.commit()
            cur.close()
        except Exception:
            try:
                self.db.rollback()
            except:
                pass

    def load_charge_defaults(self):
        """Load charge defaults for charge breakdown and edit table"""
        self._charge_defaults = []
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT id, description, charge_type, default_price, default_listed, is_active
                FROM charter_charge_defaults
                ORDER BY sort_order, id
            """)
            rows = cur.fetchall()
            cur.close()
            for row in rows:
                self._charge_defaults.append({
                    "id": row[0],
                    "description": row[1],
                    "charge_type": row[2] or "Hr",
                    "default_price": float(row[3] or 0),
                    "default_listed": bool(row[4]),
                    "is_active": bool(row[5])
                })
        except Exception:
            self._charge_defaults = [
                {"id": None, "description": "Charter Fee", "charge_type": "Hr", "default_price": 0, "default_listed": True, "is_active": True},
                {"id": None, "description": "Gratuity", "charge_type": "%", "default_price": 18, "default_listed": True, "is_active": True},
            ]

        # Populate add-charge combo
        if hasattr(self, "charge_default_combo"):
            self.charge_default_combo.clear()
            for item in self._charge_defaults:
                if item.get("is_active", True):
                    self.charge_default_combo.addItem(item["description"], item)

        # Populate default rows in charge table
        if hasattr(self, "charge_table"):
            self.charge_table.setRowCount(0)
            for item in self._charge_defaults:
                if item.get("default_listed") and item.get("is_active", True):
                    self.add_charge_row(item["description"], item.get("charge_type", "Hr"), item.get("default_price", 0))
            self.ensure_gst_row()
            self.recalculate_charge_totals()

        if hasattr(self, "charge_defaults_table"):
            self.load_charge_defaults_table()

    def add_charge_row(self, description, charge_type="Hr", fee=0.0):
        """Add a row to the charge breakdown table"""
        row = self.charge_table.rowCount()
        self.charge_table.insertRow(row)

        desc_item = QTableWidgetItem(str(description))
        self.charge_table.setItem(row, 0, desc_item)

        type_combo = QComboBox()
        type_combo.addItems(["Hr", "Pkg", "Cust", "Daily", "%", "Each", "Total"])
        if charge_type in ["Hr", "Pkg", "Cust", "Daily", "%", "Each", "Total"]:
            type_combo.setCurrentText(charge_type)
        self.charge_table.setCellWidget(row, 1, type_combo)

        fee_spin = QDoubleSpinBox()
        fee_spin.setPrefix("$")
        fee_spin.setMaximum(999999)
        fee_spin.setDecimals(2)
        fee_spin.setValue(float(fee or 0))
        fee_spin.valueChanged.connect(self.recalculate_charge_totals)
        self.charge_table.setCellWidget(row, 2, fee_spin)

    def add_charge_from_defaults(self):
        """Add a charge row from defaults (duplicates allowed)"""
        item = self.charge_default_combo.currentData()
        if not item:
            return
        self.add_charge_row(item.get("description", "Charge"), item.get("charge_type", "Hr"), item.get("default_price", 0))
        self.recalculate_charge_totals()

    def remove_selected_charge(self):
        """Remove selected charge row"""
        row = self.charge_table.currentRow()
        if row < 0:
            return
        desc_item = self.charge_table.item(row, 0)
        if desc_item and desc_item.text() == "GST":
            QMessageBox.information(self, "Info", "GST row is auto-calculated and cannot be removed.")
            return
        self.charge_table.removeRow(row)
        self.recalculate_charge_totals()

    def ensure_gst_row(self):
        """Ensure GST row exists in the charge table"""
        for row in range(self.charge_table.rowCount()):
            item = self.charge_table.item(row, 0)
            if item and item.text() == "GST":
                return
        self.add_charge_row("GST", "%", 0.0)

    def recalculate_charge_totals(self):
        """Recalculate totals and GST based on charge table"""
        subtotal = 0.0
        gst_row = None
        for row in range(self.charge_table.rowCount()):
            desc_item = self.charge_table.item(row, 0)
            desc = desc_item.text() if desc_item else ""
            fee_widget = self.charge_table.cellWidget(row, 2)
            fee_val = fee_widget.value() if isinstance(fee_widget, QDoubleSpinBox) else 0.0
            if desc == "GST":
                gst_row = row
                continue
            subtotal += fee_val

        gst_amount = 0.0
        if self.include_gst_cb.isChecked():
            gst_amount = subtotal * 0.05

        if gst_row is not None:
            gst_widget = self.charge_table.cellWidget(gst_row, 2)
            if isinstance(gst_widget, QDoubleSpinBox):
                gst_widget.setValue(gst_amount)

        total = subtotal + gst_amount
        self.total_amount.setValue(total)
        self.invoice_subtotal.setValue(subtotal) if hasattr(self, "invoice_subtotal") else None
        self.invoice_total.setValue(total) if hasattr(self, "invoice_total") else None
        self.sync_invoice_charge_table()

    def set_charge_fee(self, description, amount):
        """Set fee for a charge row by description"""
        for row in range(self.charge_table.rowCount()):
            desc_item = self.charge_table.item(row, 0)
            if desc_item and desc_item.text() == description:
                fee_widget = self.charge_table.cellWidget(row, 2)
                if isinstance(fee_widget, QDoubleSpinBox):
                    fee_widget.setValue(float(amount or 0))
                return

    def sync_invoice_charge_table(self):
        """Mirror charge breakdown into invoice details tab"""
        if not hasattr(self, "invoice_charge_table"):
            return
        self.invoice_charge_table.setRowCount(0)
        for row in range(self.charge_table.rowCount()):
            desc_item = self.charge_table.item(row, 0)
            desc = desc_item.text() if desc_item else ""
            type_widget = self.charge_table.cellWidget(row, 1)
            fee_widget = self.charge_table.cellWidget(row, 2)
            charge_type = type_widget.currentText() if isinstance(type_widget, QComboBox) else ""
            fee_val = fee_widget.value() if isinstance(fee_widget, QDoubleSpinBox) else 0.0

            irow = self.invoice_charge_table.rowCount()
            self.invoice_charge_table.insertRow(irow)
            self.invoice_charge_table.setItem(irow, 0, QTableWidgetItem(desc))
            self.invoice_charge_table.setItem(irow, 1, QTableWidgetItem(charge_type))
            self.invoice_charge_table.setItem(irow, 2, QTableWidgetItem(f"${fee_val:,.2f}"))

    def create_edit_tables_tab(self):
        """Tab: Edit default tables used in charter details"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Edit Charter Tables")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("Charge Defaults (description, type, price, default listed)")
        subtitle.setStyleSheet("color:#555; font-size: 11px;")
        layout.addWidget(subtitle)

        self.charge_defaults_table = QTableWidget()
        self.charge_defaults_table.setColumnCount(5)
        self.charge_defaults_table.setHorizontalHeaderLabels(["Description", "Type", "Price", "Default", "Active"])
        self.charge_defaults_table.horizontalHeader().setStretchLastSection(True)
        self.charge_defaults_table.setMaximumHeight(260)
        layout.addWidget(self.charge_defaults_table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Add Row")
        add_btn.clicked.connect(self.add_charge_default_row)
        btn_layout.addWidget(add_btn)

        del_btn = QPushButton("🗑️ Delete Row")
        del_btn.clicked.connect(self.delete_charge_default_row)
        btn_layout.addWidget(del_btn)

        save_btn = QPushButton("💾 Save Defaults")
        save_btn.clicked.connect(self.save_charge_defaults_table)
        btn_layout.addWidget(save_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def load_charge_defaults_table(self):
        """Load charge defaults into edit table"""
        self.charge_defaults_table.setRowCount(0)
        for item in self._charge_defaults:
            row = self.charge_defaults_table.rowCount()
            self.charge_defaults_table.insertRow(row)
            desc_item = QTableWidgetItem(item.get("description", ""))
            desc_item.setData(Qt.ItemDataRole.UserRole, item.get("id"))
            self.charge_defaults_table.setItem(row, 0, desc_item)

            type_item = QTableWidgetItem(item.get("charge_type", "Hr"))
            self.charge_defaults_table.setItem(row, 1, type_item)

            price_item = QTableWidgetItem(f"{float(item.get('default_price', 0)):.2f}")
            self.charge_defaults_table.setItem(row, 2, price_item)

            default_item = QTableWidgetItem("Yes" if item.get("default_listed") else "No")
            self.charge_defaults_table.setItem(row, 3, default_item)

            active_item = QTableWidgetItem("Yes" if item.get("is_active") else "No")
            self.charge_defaults_table.setItem(row, 4, active_item)

    def add_charge_default_row(self):
        """Add empty charge default row"""
        row = self.charge_defaults_table.rowCount()
        self.charge_defaults_table.insertRow(row)
        self.charge_defaults_table.setItem(row, 0, QTableWidgetItem(""))
        self.charge_defaults_table.setItem(row, 1, QTableWidgetItem("Hr"))
        self.charge_defaults_table.setItem(row, 2, QTableWidgetItem("0.00"))
        self.charge_defaults_table.setItem(row, 3, QTableWidgetItem("Yes"))
        self.charge_defaults_table.setItem(row, 4, QTableWidgetItem("Yes"))

    def delete_charge_default_row(self):
        """Delete selected default row"""
        row = self.charge_defaults_table.currentRow()
        if row < 0:
            return
        self.charge_defaults_table.removeRow(row)

    def save_charge_defaults_table(self):
        """Save charge defaults back to DB"""
        try:
            cur = self.db.get_cursor()
            for row in range(self.charge_defaults_table.rowCount()):
                desc_item = self.charge_defaults_table.item(row, 0)
                type_item = self.charge_defaults_table.item(row, 1)
                price_item = self.charge_defaults_table.item(row, 2)
                default_item = self.charge_defaults_table.item(row, 3)
                active_item = self.charge_defaults_table.item(row, 4)

                description = desc_item.text().strip() if desc_item else ""
                if not description:
                    continue
                charge_type = type_item.text().strip() if type_item else "Hr"
                try:
                    price = float(price_item.text() if price_item else 0)
                except Exception:
                    price = 0.0
                default_listed = (default_item.text().strip().lower() == "yes") if default_item else True
                is_active = (active_item.text().strip().lower() == "yes") if active_item else True

                row_id = desc_item.data(Qt.ItemDataRole.UserRole) if desc_item else None
                if row_id:
                    cur.execute("""
                        UPDATE charter_charge_defaults
                        SET description = %s, charge_type = %s, default_price = %s,
                            default_listed = %s, is_active = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (description, charge_type, price, default_listed, is_active, row_id))
                else:
                    cur.execute("""
                        INSERT INTO charter_charge_defaults
                        (description, charge_type, default_price, default_listed, is_active)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (description, charge_type, price, default_listed, is_active))
                    new_id = cur.fetchone()[0]
                    desc_item.setData(Qt.ItemDataRole.UserRole, new_id)

            self.db.commit()
            cur.close()
            self.load_charge_defaults()
            QMessageBox.information(self, "Saved", "Charge defaults saved.")
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to save defaults: {e}")
    
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
        
        # Row 1.5a: Pickup Location + Time
        row1_5a = QHBoxLayout()
        pickup_label = QLabel("Pickup:")
        pickup_label.setMinimumWidth(100)
        self.pickup = QLineEdit()
        self.pickup.setMaximumWidth(400)
        self.pickup.setPlaceholderText("Pickup address or location...")
        row1_5a.addWidget(pickup_label)
        row1_5a.addWidget(self.pickup)
        row1_5a.addSpacing(30)

        pickup_time_label = QLabel("Time:")
        pickup_time_label.setMinimumWidth(40)
        self.pickup_time = QTimeEdit()
        self.pickup_time.setDisplayFormat("HH:mm")
        self.pickup_time.setMaximumWidth(100)
        row1_5a.addWidget(pickup_time_label)
        row1_5a.addWidget(self.pickup_time)
        row1_5a.addStretch()
        form_layout.addLayout(row1_5a)
        
        # Row 1.5b: Destination + Time
        row1_5b = QHBoxLayout()
        dest_label = QLabel("Destination:")
        dest_label.setMinimumWidth(100)
        self.destination = QLineEdit()
        self.destination.setMaximumWidth(400)
        self.destination.setPlaceholderText("Destination address or location...")
        row1_5b.addWidget(dest_label)
        row1_5b.addWidget(self.destination)
        row1_5b.addSpacing(30)

        dropoff_time_label = QLabel("Time:")
        dropoff_time_label.setMinimumWidth(40)
        self.dropoff_time = QTimeEdit()
        self.dropoff_time.setDisplayFormat("HH:mm")
        self.dropoff_time.setMaximumWidth(100)
        row1_5b.addWidget(dropoff_time_label)
        row1_5b.addWidget(self.dropoff_time)
        row1_5b.addStretch()
        form_layout.addLayout(row1_5b)
        
        # Row 2a: Billing Type (List) and Charter Type
        row2a = QHBoxLayout()
        billing_label = QLabel("Billing Type:")
        billing_label.setMinimumWidth(100)
        billing_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        row2a.addWidget(billing_label)

        self.billing_type = QComboBox()
        self.billing_type.addItems(["Hourly", "Package"])
        self.billing_type.setMaximumWidth(120)
        self.billing_type.currentTextChanged.connect(self.toggle_billing_fields)
        self.billing_type.currentIndexChanged.connect(self.toggle_billing_fields)
        row2a.addWidget(self.billing_type)

        row2a.addSpacing(30)
        
        charter_type_label = QLabel("Charter Type:")
        charter_type_label.setMinimumWidth(100)
        self.charter_type = QComboBox()
        self.charter_type.setMaximumWidth(180)
        self.charter_type.currentIndexChanged.connect(self.apply_vehicle_pricing_defaults)
        row2a.addWidget(charter_type_label)
        row2a.addWidget(self.charter_type)
        row2a.addStretch()
        form_layout.addLayout(row2a)
        
        # Row 2b: Hourly Rate (visible when Hourly checked)
        row2b = QHBoxLayout()
        self.hourly_rate_label = QLabel("Hourly Rate:")
        self.hourly_rate_label.setMinimumWidth(100)
        row2b.addWidget(self.hourly_rate_label)
        self.hourly_rate = QDoubleSpinBox()
        self.hourly_rate.setPrefix("$")
        self.hourly_rate.setMaximum(9999.99)
        self.hourly_rate.setMaximumWidth(120)
        row2b.addWidget(self.hourly_rate)
        row2b.addSpacing(30)
        
        self.min_hours_label = QLabel("Min Hours:")
        self.min_hours_label.setMinimumWidth(100)
        row2b.addWidget(self.min_hours_label)
        self.min_hours = QSpinBox()
        self.min_hours.setMinimum(1)
        self.min_hours.setMaximum(24)
        self.min_hours.setMaximumWidth(80)
        row2b.addWidget(self.min_hours)
        row2b.addStretch()
        form_layout.addLayout(row2b)
        
        # Row 2b2: Package Price and Hours (visible when Package checked)
        row2b2 = QHBoxLayout()
        self.package_price_label = QLabel("Package Price:")
        self.package_price_label.setMinimumWidth(100)
        row2b2.addWidget(self.package_price_label)
        self.package_price = QDoubleSpinBox()
        self.package_price.setPrefix("$")
        self.package_price.setMaximum(999999)
        self.package_price.setMaximumWidth(120)
        row2b2.addWidget(self.package_price)
        row2b2.addSpacing(30)
        
        self.package_hours_label = QLabel("Package Hours:")
        self.package_hours_label.setMinimumWidth(100)
        row2b2.addWidget(self.package_hours_label)
        self.package_hours = QDoubleSpinBox()
        self.package_hours.setMaximum(24)
        self.package_hours.setDecimals(2)
        self.package_hours.setMaximumWidth(80)
        row2b2.addWidget(self.package_hours)
        row2b2.addStretch()
        form_layout.addLayout(row2b2)
        
        # Row 2c: Custom Rate (special deal)
        row2c = QHBoxLayout()
        self.custom_rate_cb = QCheckBox("Custom Rate")
        self.custom_rate_cb.stateChanged.connect(self.toggle_custom_rate)
        row2c.addWidget(self.custom_rate_cb)
        
        self.custom_rate_type = QComboBox()
        self.custom_rate_type.addItems(["Per Hour", "Flat Rate"])
        self.custom_rate_type.setMaximumWidth(120)
        row2c.addWidget(self.custom_rate_type)
        
        self.custom_rate_amount = QDoubleSpinBox()
        self.custom_rate_amount.setPrefix("$")
        self.custom_rate_amount.setMaximum(999999)
        self.custom_rate_amount.setDecimals(2)
        self.custom_rate_amount.setMaximumWidth(120)
        row2c.addWidget(self.custom_rate_amount)
        row2c.addStretch()
        form_layout.addLayout(row2c)
        self.toggle_custom_rate()
        
        # Row 2d: Vehicle Requested + Pay Table (default pricing)
        row2d = QHBoxLayout()
        veh_req_label = QLabel("Vehicle Requested:")
        veh_req_label.setMinimumWidth(100)
        self.vehicle_requested = QComboBox()
        self.vehicle_requested.setMaximumWidth(180)
        self.vehicle_requested.currentIndexChanged.connect(self.apply_vehicle_pricing_defaults)
        row2d.addWidget(veh_req_label)
        row2d.addWidget(self.vehicle_requested)
        row2d.addSpacing(20)
        
        self.vehicle_pay_hourly = QDoubleSpinBox()
        self.vehicle_pay_hourly.setPrefix("$")
        self.vehicle_pay_hourly.setMaximum(9999.99)
        self.vehicle_pay_hourly.setMaximumWidth(100)
        row2d.addWidget(QLabel("Hourly:"))
        row2d.addWidget(self.vehicle_pay_hourly)
        
        self.vehicle_pay_package = QDoubleSpinBox()
        self.vehicle_pay_package.setPrefix("$")
        self.vehicle_pay_package.setMaximum(999999)
        self.vehicle_pay_package.setMaximumWidth(100)
        row2d.addWidget(QLabel("Package:"))
        row2d.addWidget(self.vehicle_pay_package)
        
        self.vehicle_pay_package_hours = QDoubleSpinBox()
        self.vehicle_pay_package_hours.setMaximum(24)
        self.vehicle_pay_package_hours.setDecimals(2)
        self.vehicle_pay_package_hours.setMaximumWidth(80)
        row2d.addWidget(QLabel("Pkg Hrs:"))
        row2d.addWidget(self.vehicle_pay_package_hours)
        row2d.addStretch()
        form_layout.addLayout(row2d)
        
        # Row 2e: Extra Time and Standby (visible for both Hourly and Package)
        row2e = QHBoxLayout()
        self.extra_time_label = QLabel("Extra Time Rate:")
        self.extra_time_label.setMinimumWidth(100)
        row2e.addWidget(self.extra_time_label)
        self.vehicle_pay_extra_time = QDoubleSpinBox()
        self.vehicle_pay_extra_time.setPrefix("$")
        self.vehicle_pay_extra_time.setMaximum(9999.99)
        self.vehicle_pay_extra_time.setMaximumWidth(100)
        row2e.addWidget(self.vehicle_pay_extra_time)
        row2e.addSpacing(30)
        
        self.standby_label = QLabel("Standby Rate:")
        self.standby_label.setMinimumWidth(100)
        row2e.addWidget(self.standby_label)
        self.vehicle_pay_standby = QDoubleSpinBox()
        self.vehicle_pay_standby.setPrefix("$")
        self.vehicle_pay_standby.setMaximum(9999.99)
        self.vehicle_pay_standby.setMaximumWidth(100)
        row2e.addWidget(self.vehicle_pay_standby)
        row2e.addStretch()
        form_layout.addLayout(row2e)
        
        # Row 2f: Passengers
        row2f = QHBoxLayout()
        pax_label = QLabel("Passengers:")
        pax_label.setMinimumWidth(100)
        self.passenger_count = QSpinBox()
        self.passenger_count.setMinimum(1)
        self.passenger_count.setMaximum(14)
        self.passenger_count.setMaximumWidth(100)
        row2f.addWidget(pax_label)
        row2f.addWidget(self.passenger_count)
        row2f.addStretch()
        form_layout.addLayout(row2f)
        
        # ===== SECTION 3: VEHICLE ASSIGNMENT =====
        sec3_title = QLabel("VEHICLE ASSIGNMENT")
        sec3_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec3_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec3_title)
        
        # Row 3a: Vehicle Assigned
        row3a = QHBoxLayout()
        veh_label = QLabel("Vehicle Assigned:")
        veh_label.setMinimumWidth(100)
        self.vehicle = QComboBox()
        self.vehicle.setMaximumWidth(180)
        self.vehicle_type_label = QLabel("")
        self.vehicle_type_label.setStyleSheet("color:#666; font-size: 11px;")
        self.vehicle_type_label.setMaximumWidth(120)
        row3a.addWidget(veh_label)
        row3a.addWidget(self.vehicle)
        row3a.addWidget(self.vehicle_type_label)
        row3a.addStretch()
        form_layout.addLayout(row3a)
        
        # Row 3b: Driver
        row3b = QHBoxLayout()
        driver_label = QLabel("Driver:")
        driver_label.setMinimumWidth(100)
        self.driver = QComboBox()
        self.driver.setMaximumWidth(200)
        row3b.addWidget(driver_label)
        row3b.addWidget(self.driver)
        row3b.addStretch()
        form_layout.addLayout(row3b)
        
        sec4_title = QLabel("ROUTING & CHARGES")
        sec4_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec4_title.setStyleSheet("color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;")
        form_layout.addWidget(sec4_title)

        routing_widget = self.create_routing_tab()
        form_layout.addWidget(routing_widget)

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

        # Cost Corner - Beverage Confirmation List
        bev_confirm_title = QLabel("Beverage Items (Client Confirmation)")
        bev_confirm_title.setStyleSheet("color:#555; font-size: 11px;")
        form_layout.addWidget(bev_confirm_title)

        self.beverage_confirm_table = QTableWidget()
        self.beverage_confirm_table.setColumnCount(3)
        self.beverage_confirm_table.setHorizontalHeaderLabels(["Item", "Type", "Ordered"])
        self.beverage_confirm_table.horizontalHeader().setStretchLastSection(True)
        self.beverage_confirm_table.setMaximumHeight(140)
        form_layout.addWidget(self.beverage_confirm_table)
        
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
        
        # Initialize billing field visibility (default: Hourly)
        self.billing_type.setCurrentText("Hourly")
        self.toggle_billing_fields()
        
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
        reserve_label = QLabel("Reserve #:")
        reserve_label.setMinimumWidth(100)
        self.invoice_reserve_display = QLineEdit()
        self.invoice_reserve_display.setReadOnly(True)
        self.invoice_reserve_display.setMaximumWidth(150)
        header_row1.addWidget(reserve_label)
        header_row1.addWidget(self.invoice_reserve_display)
        header_row1.addSpacing(30)

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

        header_row3 = QHBoxLayout()
        paid_label = QLabel("Paid Status:")
        paid_label.setMinimumWidth(100)
        self.invoice_paid_status_display = QLineEdit()
        self.invoice_paid_status_display.setReadOnly(True)
        self.invoice_paid_status_display.setMaximumWidth(150)
        header_row3.addWidget(paid_label)
        header_row3.addWidget(self.invoice_paid_status_display)

        self.print_customer_copy_cb = QCheckBox("Print customer copy")
        header_row3.addWidget(self.print_customer_copy_cb)
        self.separate_beverage_invoice_cb = QCheckBox("Separate beverage invoice")
        header_row3.addWidget(self.separate_beverage_invoice_cb)
        header_row3.addStretch()
        details_layout.addLayout(header_row3)
        
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

        # Invoice charge items (read-only mirror)
        invoice_items_title = QLabel("Invoice Items")
        invoice_items_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        details_layout.addWidget(invoice_items_title)

        self.invoice_charge_table = QTableWidget()
        self.invoice_charge_table.setColumnCount(3)
        self.invoice_charge_table.setHorizontalHeaderLabels(["Charge", "Type", "Fee"])
        self.invoice_charge_table.setColumnWidth(0, 200)
        self.invoice_charge_table.setColumnWidth(1, 80)
        self.invoice_charge_table.setColumnWidth(2, 120)
        self.invoice_charge_table.setMaximumHeight(160)
        details_layout.addWidget(self.invoice_charge_table)

        # Beverage items list (GST included per line)
        beverage_items_title = QLabel("Beverage Items (GST included)")
        beverage_items_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        details_layout.addWidget(beverage_items_title)

        self.invoice_beverage_table = QTableWidget()
        self.invoice_beverage_table.setColumnCount(4)
        self.invoice_beverage_table.setHorizontalHeaderLabels(["Item", "Qty", "Unit Price", "Line Total"])
        self.invoice_beverage_table.setColumnWidth(0, 180)
        self.invoice_beverage_table.setColumnWidth(1, 60)
        self.invoice_beverage_table.setColumnWidth(2, 100)
        self.invoice_beverage_table.setColumnWidth(3, 120)
        self.invoice_beverage_table.setMaximumHeight(160)
        details_layout.addWidget(self.invoice_beverage_table)
        
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
        
        # Out of Town toggle
        out_layout = QHBoxLayout()
        out_layout.setSpacing(4)
        self.out_of_town_cb = QCheckBox("Out of Town")
        self.out_of_town_cb.setChecked(False)
        self.out_of_town_cb.stateChanged.connect(self.on_out_of_town_changed)
        out_layout.addWidget(self.out_of_town_cb)
        out_layout.addStretch()
        layout.addLayout(out_layout)
        
        # Routing Stops Table (compact)
        stops_label = QLabel("Route Stops (in order)")
        stops_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(stops_label)
        
        self.routing_table = QTableWidget()
        self.routing_table.setColumnCount(5)
        self.routing_table.setHorizontalHeaderLabels([
            "Route #",
            "Type",
            "Location",
            "Time",
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
        
        # Charges Breakdown Table (Invoice line items)
        charges_title = QLabel("💰 Charge Breakdown (Invoice Items)")
        charges_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(charges_title)

        self.charge_table = QTableWidget()
        self.charge_table.setColumnCount(3)
        self.charge_table.setHorizontalHeaderLabels(["Charge", "Type", "Fee"])
        self.charge_table.setColumnWidth(0, 200)
        self.charge_table.setColumnWidth(1, 80)
        self.charge_table.setColumnWidth(2, 120)
        self.charge_table.setMaximumHeight(200)
        layout.addWidget(self.charge_table)

        charge_controls = QHBoxLayout()
        charge_controls.setSpacing(6)
        charge_controls.addWidget(QLabel("Add Charge:"))
        self.charge_default_combo = QComboBox()
        self.charge_default_combo.setMaximumWidth(220)
        charge_controls.addWidget(self.charge_default_combo)

        add_charge_btn = QPushButton("➕ Add")
        add_charge_btn.setMaximumWidth(90)
        add_charge_btn.clicked.connect(self.add_charge_from_defaults)
        charge_controls.addWidget(add_charge_btn)

        remove_charge_btn = QPushButton("🗑️ Remove")
        remove_charge_btn.setMaximumWidth(110)
        remove_charge_btn.clicked.connect(self.remove_selected_charge)
        charge_controls.addWidget(remove_charge_btn)

        self.include_gst_cb = QCheckBox("Include GST (5%)")
        self.include_gst_cb.setChecked(True)
        self.include_gst_cb.stateChanged.connect(self.recalculate_charge_totals)
        charge_controls.addWidget(self.include_gst_cb)

        recalc_btn = QPushButton("🧮 Recalc")
        recalc_btn.setMaximumWidth(90)
        recalc_btn.clicked.connect(self.recalculate_charge_totals)
        charge_controls.addWidget(recalc_btn)

        charge_controls.addStretch()
        layout.addLayout(charge_controls)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def on_rate_type_changed(self, rate_type):
        """Handle rate type change"""
        if rate_type == "Hr":
            self.min_hours.setEnabled(True)
            self.hourly_rate.setEnabled(True)
        elif rate_type in ("Pkg", "Daily"):
            self.min_hours.setEnabled(False)
            self.hourly_rate.setEnabled(True)
        elif rate_type == "Cust":
            self.min_hours.setEnabled(False)
            self.hourly_rate.setEnabled(True)
        else:
            self.min_hours.setEnabled(False)
            self.hourly_rate.setEnabled(True)
    
    def on_out_of_town_changed(self):
        """Handle Out of Town checkbox toggle - update first and last route labels"""
        is_out_of_town = self.out_of_town_cb.isChecked()
        
        # Update first route label
        if self.routing_table.rowCount() > 0:
            first_label = "Leave Red Deer" if is_out_of_town else "Pickup at"
            self.routing_table.item(0, 0).setText(first_label)
        
        # Update last route label
        if self.routing_table.rowCount() > 1:
            last_row = self.routing_table.rowCount() - 1
            last_label = "Return to Red Deer" if is_out_of_town else "Drop off at"
            self.routing_table.item(last_row, 0).setText(last_label)
    
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
            self.routing_table.setItem(row, 4, QTableWidgetItem(stop_data['notes']))
            
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
            'notes': self.routing_table.item(row, 4).text()
        }
        
        dialog = RoutingStopDialog(parent=self, stop_data=current_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            stop_data = dialog.get_stop_data()
            
            self.routing_table.setItem(row, 1, QTableWidgetItem(stop_data['type']))
            self.routing_table.setItem(row, 2, QTableWidgetItem(stop_data['location']))
            self.routing_table.setItem(row, 3, QTableWidgetItem(stop_data['time']))
            self.routing_table.setItem(row, 4, QTableWidgetItem(stop_data['notes']))
    
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
        """Calculate total charges based on routing and billing type"""
        billing_type = self.billing_type.currentText()
        is_hourly = billing_type == "Hourly"
        is_package = billing_type == "Package"
        rate = self.hourly_rate.value()

        total_duration = 0

        # Base calculation for charter fee
        charter_fee = 0.0
        if is_hourly:
            min_hours = self.min_hours.value()
            actual_hours = total_duration / 60.0
            billable_hours = max(min_hours, actual_hours)
            charter_fee = billable_hours * rate
        elif is_package:
            charter_fee = self.package_price.value()
        else:
            charter_fee = rate

        self.set_charge_fee("Charter Fee", charter_fee)
        self.recalculate_charge_totals()

        QMessageBox.information(
            self,
            "Charges Calculated",
            f"Billing Type: {'Hourly' if is_hourly else 'Package' if is_package else 'Custom'}\n"
            f"Charter Fee: ${charter_fee:.2f}"
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
            try:
                self.db.rollback()
            except Exception:
                pass
            cur = self.db.get_cursor()
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
            try:
                self.db.rollback()
            except Exception:
                pass
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
                
                # Set vehicle requested by type text (from pricing defaults)
                if veh_type_req:
                    veh_req_text = str(veh_type_req or "")
                    idx = self.vehicle_requested.findText(veh_req_text)
                    if idx >= 0:
                        self.vehicle_requested.setCurrentIndex(idx)
                    else:
                        self.vehicle_requested.addItem(veh_req_text)
                        self.vehicle_requested.setCurrentIndex(self.vehicle_requested.count() - 1)
                    self.apply_vehicle_pricing_defaults()
                
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
                self.invoice_reserve_display.setText(str(res_num or self.reserve_number or ""))
                
                self.charter_data = charter
            
            # Load related beverage/product orders and calculate beverage total
            beverage_total = 0.0
            try:
                cur.execute("""
                    SELECT oi.item_name, oi.quantity, oi.unit_price, oi.total, o.status,
                           COALESCE(b.category, '')
                    FROM beverage_orders o
                    JOIN beverage_order_items oi ON o.order_id = oi.order_id
                    LEFT JOIN beverages b ON oi.item_id = b.beverage_id
                    WHERE o.reserve_number = %s
                    ORDER BY o.order_date DESC
                """, (self.reserve_number,))
                
                orders = cur.fetchall()
                self.orders_table.setRowCount(len(orders) if orders else 0)
                if orders:
                    for i, (item, qty, price, total, status, category) in enumerate(orders):
                        self.orders_table.setItem(i, 0, QTableWidgetItem(str(item)))
                        self.orders_table.setItem(i, 1, QTableWidgetItem(str(qty)))
                        self.orders_table.setItem(i, 2, QTableWidgetItem(f"${float(price):,.2f}"))
                        self.orders_table.setItem(i, 3, QTableWidgetItem(f"${float(total):,.2f}"))
                        self.orders_table.setItem(i, 4, QTableWidgetItem(str(status)))
                        try:
                            beverage_total += float(total or 0)
                        except Exception:
                            pass

                    # Invoice beverage items (GST included per line)
                    self.invoice_beverage_table.setRowCount(len(orders))
                    for i, (item, qty, price, total, status, category) in enumerate(orders):
                        self.invoice_beverage_table.setItem(i, 0, QTableWidgetItem(str(item)))
                        self.invoice_beverage_table.setItem(i, 1, QTableWidgetItem(str(qty)))
                        self.invoice_beverage_table.setItem(i, 2, QTableWidgetItem(f"${float(price):,.2f}"))
                        self.invoice_beverage_table.setItem(i, 3, QTableWidgetItem(f"${float(total):,.2f}"))

                    # Populate client confirmation list (no prices)
                    self.beverage_confirm_table.setRowCount(len(orders))
                    for i, (item, qty, price, total, status, category) in enumerate(orders):
                        self.beverage_confirm_table.setItem(i, 0, QTableWidgetItem(str(item)))
                        self.beverage_confirm_table.setItem(i, 1, QTableWidgetItem(str(category)))
                        self.beverage_confirm_table.setItem(i, 2, QTableWidgetItem(str(qty)))
                else:
                    self.beverage_confirm_table.setRowCount(0)
                    self.invoice_beverage_table.setRowCount(0)
            except Exception:
                self.beverage_confirm_table.setRowCount(0)
                self.orders_table.setRowCount(0)
                beverage_total = 0.0
                self.invoice_beverage_table.setRowCount(0)

            self.set_charge_fee("Beverage Order", beverage_total)
            self.recalculate_charge_totals()
            
            # Initialize total_paid before calculating from payments table
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
            self.invoice_paid_status_display.setText(invoice_status)
            
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
            vehicle_requested_text = self.vehicle_requested.currentText().strip()
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
                vehicle_requested_text or None,
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
                vehicle_requested_text = self.vehicle_requested.currentText().strip()
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
                    vehicle_requested_text or None,
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
        
        # Details
        self.location = QLineEdit()
        self.location.setPlaceholderText("Enter address or location name")
        if 'location' in self.stop_data:
            self.location.setText(self.stop_data['location'])
        layout.addRow("Details:", self.location)

        # Time
        self.time = QLineEdit()
        self.time.setPlaceholderText("HH:MM (e.g. 14:30)")
        if 'time' in self.stop_data:
            self.time.setText(self.stop_data['time'])
        layout.addRow("Time:", self.time)

        # Driver Notes
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setPlaceholderText("Driver notes, special instructions, gate codes, etc.")
        if 'notes' in self.stop_data:
            self.notes.setPlainText(self.stop_data['notes'])
        layout.addRow("Driver Notes:", self.notes)
        
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
