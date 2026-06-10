"""
Drill-Down Detail View Widgets for Dashboard Data
Provides double-click detail views with edit, lock, cancel,
and drill-down capabilities

CHARTER DETAIL: Reserve numbers, payments, orders, routing
EMPLOYEE DETAIL: See employee_drill_down.py for comprehensive employee
management
"""

import logging
import re
from datetime import datetime
from difflib import SequenceMatcher

import psycopg2
import psycopg2.errors

logger = logging.getLogger(__name__)
from common_widgets import StandardDateEdit
from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, QLocale, Qt, QTime, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class CharterDetailDialog(QDialog):
    """Master-detail view for a single charter with drill-down capability"""

    saved = pyqtSignal(dict)  # Emit when changes saved

    def __init__(
        self,
        db,
        reserve_number=None,
        parent=None,
        initial_tab=None,
        client_id=None,
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.reserve_number = reserve_number
        self.client_id = client_id  # Pre-selected client for new charters
        self.is_locked = False
        self.charter_data = None
        self._load_retry_count = 0  # Track retries to prevent infinite loops

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

        # Right side: Standard drill-down buttons (Add, Duplicate, Delete,
        # Save, Close)
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

        # Tab 2: Driver-facing fields (HOS, pay, instructions)
        driver_tab = self.create_driver_info_tab()
        tabs.addTab(driver_tab, "🧑‍✈️ Driver Info")

        # Tab 3: Invoice Details (NEW)
        invoice_tab = self.create_invoice_details_tab()
        tabs.addTab(invoice_tab, "📄 Invoice Details")

        # Tab 4: Edit Tables (charge defaults, charter types)
        edit_tables_tab = self.create_edit_tables_tab()
        tabs.addTab(edit_tables_tab, "🧰 Edit Tables")

        # Tab 5: Related Orders/Beverages
        orders_tab = self.create_orders_tab()
        tabs.addTab(orders_tab, "Orders & Beverages")

        # Tab 6: Beverage card details (data-driven)
        beverage_tab = self.create_beverage_printout_tab()
        tabs.addTab(beverage_tab, "🍷 Beverage Card Details")

        # Tab 7: Payments
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

        # If client_id is provided (pre-selected for new charter), load that
        # client info
        if client_id and not reserve_number:
            self.load_client_info(client_id)

        # Load data if reserve_number provided
        if reserve_number:
            self.load_charter_data()

        # Optionally select a starting tab
        if initial_tab:
            tab_map = {
                "details": 0,
                "driver": 1,
                "invoice": 2,
                "edit": 3,
                "orders": 4,
                "routing": 0,
                "payments": 6,
            }
            idx = tab_map.get(str(initial_tab).lower())
            if idx is not None:
                self.tabs.setCurrentIndex(idx)
        else:
            # Driver/chauffeur users should land directly on driver-facing fields.
            try:
                auth_user = getattr(parent, "auth_user", {}) if parent else {}
                role_value = str(auth_user.get("role", "")).strip().lower()
                if role_value in {"driver", "chauffeur", "chauffeur_driver"}:
                    self.tabs.setCurrentIndex(1)
            except Exception as exc:
                logger.debug(
                    "Unable to apply default driver tab selection: %s", exc
                )

        # Wire up signals for split-run auto-population
        self._setup_split_run_signals()
        self._setup_auto_sync_signals()
        self._update_trip_boundary_labels(False)

    def _get_allowed_payment_methods(self) -> list[str]:
        """Fetch allowed payment methods from existing data; fall back to
        policy list.
        This only supports manual recording; no online charging is enabled.
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
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT DISTINCT payment_method
                    FROM payments
                    WHERE payment_method IS NOT NULL AND payment_method <> ''
                    ORDER BY payment_method
                """)
                rows = cur.fetchall()
                methods = [str(r[0]) for r in rows if r and r[0]]
                # Ensure methods intersect with known policy; preserve order
                if methods:
                    policy_set = set(fallback)
                    filtered = [m for m in methods if m in policy_set]
                    # If DB had extra values not in policy, append them for
                    # visibility
                    extras = [m for m in methods if m not in policy_set]
                    return (
                        filtered + extras if filtered or extras else fallback
                    )
                return fallback
        except Exception as e:
            logger.error(f"Failed to get allowed payment methods: {e}")
            return fallback

    def load_driver_options(self) -> None:
        """Load all available drivers into the driver dropdown"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'employees'
                    """)
                employee_columns = {row[0] for row in cur.fetchall()}

                name_expr = (
                    "TRIM(COALESCE(full_name, CONCAT(COALESCE(first_name,''), "
                    "' ', COALESCE(last_name,''))))"
                )
                if "full_name" not in employee_columns:
                    name_expr = (
                        "TRIM(CONCAT(COALESCE(first_name,''), "
                        "' ', COALESCE(last_name,'')))"
                    )

                where_parts = []
                role_parts = []
                if "is_chauffeur" in employee_columns:
                    role_parts.append("is_chauffeur = true")
                if "employee_category" in employee_columns:
                    role_parts.append(
                        "COALESCE(employee_category,'') ILIKE '%driver%'"
                    )
                if "position" in employee_columns:
                    role_parts.append("COALESCE(position,'') ILIKE '%driver%'")
                if "role" in employee_columns:
                    role_parts.append("COALESCE(role,'') ILIKE '%driver%'")
                if role_parts:
                    where_parts.append(f"({' OR '.join(role_parts)})")

                status_parts = []
                if "is_active" in employee_columns:
                    status_parts.append("COALESCE(is_active, true) = true")
                if "employment_status" in employee_columns:
                    status_parts.append(
                        "COALESCE(employment_status, 'active') <> 'inactive'"
                    )
                if status_parts:
                    where_parts.append(f"({' OR '.join(status_parts)})")

                where_sql = (
                    f"WHERE {' AND '.join(where_parts)} "
                    if where_parts
                    else ""
                )
                cur.execute(f"""
                    SELECT employee_id, {name_expr} AS display_name
                    FROM employees
                    {where_sql}
                    ORDER BY display_name, employee_id
                    """)
                drivers = cur.fetchall()

            self.driver.clear()
            self.driver.addItem("")  # Add empty option
            for emp_id, name in drivers:
                display_name = str(name or "").strip()
                display_label = (
                    f"{display_name} ({emp_id})"
                    if display_name
                    else str(emp_id)
                )
                self.driver.addItem(display_label, emp_id)
        except Exception as e:
            logger.error(f"Failed to load driver options: {e}")
            # Silently fail - driver list just won't populate

    def _read_routing_rows(self) -> list[dict]:
        rows = []
        for row in range(self.routing_table.rowCount()):
            row_data = {
                "type": (
                    self.routing_table.item(row, 1).text().strip()
                    if self.routing_table.item(row, 1)
                    else ""
                ),
                "location": (
                    self.routing_table.item(row, 2).text()
                    if self.routing_table.item(row, 2)
                    else ""
                ),
                "time": (
                    self.routing_table.item(row, 3).text()
                    if self.routing_table.item(row, 3)
                    else ""
                ),
                "notes": (
                    self.routing_table.item(row, 4).text()
                    if self.routing_table.item(row, 4)
                    else ""
                ),
            }
            rows.append(row_data)
        return rows

    def _write_routing_rows(self, rows) -> None:
        self.routing_table.setRowCount(0)
        for row_data in rows:
            row = self.routing_table.rowCount()
            self.routing_table.insertRow(row)
            self.routing_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.routing_table.setItem(
                row, 1, QTableWidgetItem(row_data.get("type", ""))
            )
            self.routing_table.setItem(
                row, 2, QTableWidgetItem(row_data.get("location", ""))
            )
            self.routing_table.setItem(
                row, 3, QTableWidgetItem(row_data.get("time", ""))
            )
            self.routing_table.setItem(
                row, 4, QTableWidgetItem(row_data.get("notes", ""))
            )

    @staticmethod
    def _is_type_like(type_text: str, *needles: str) -> bool:
        value = (type_text or "").strip().lower()
        return any(n in value for n in needles)

    @staticmethod
    def _qtime_to_minutes(qtime: QTime) -> int:
        return int(qtime.hour()) * 60 + int(qtime.minute())

    @staticmethod
    def _text_time_to_minutes(text: str) -> int | None:
        raw = (text or "").strip()
        if not raw:
            return None
        parsed = QTime.fromString(raw[:5], "HH:mm")
        if parsed.isValid():
            return int(parsed.hour()) * 60 + int(parsed.minute())
        return None

    def _routing_duration_minutes(self) -> int:
        """Compute usage minutes from pickup/dropoff, excluding split idle windows."""
        start_min = self._qtime_to_minutes(self.pickup_time.time())
        end_min = self._qtime_to_minutes(self.dropoff_time.time())
        if end_min < start_min:
            end_min += 24 * 60
        total_minutes = max(0, end_min - start_min)

        rows = self._read_routing_rows() if hasattr(self, "routing_table") else []
        split_drop = None
        split_pick = None
        split_idle = 0

        for row in rows:
            tval = self._text_time_to_minutes(row.get("time", ""))
            if tval is None:
                continue
            rtype = (row.get("type") or "").strip().lower()
            if "drop off for split run" in rtype:
                split_drop = tval
            elif "split" in rtype and "pick up" in rtype:
                split_pick = tval

            if split_drop is not None and split_pick is not None:
                if split_pick < split_drop:
                    split_pick += 24 * 60
                split_idle += max(0, split_pick - split_drop)
                split_drop = None
                split_pick = None

        return max(0, total_minutes - split_idle)

    def _setup_auto_sync_signals(self) -> None:
        """Wire key controls so routing, billing, and invoice details stay synchronized."""
        try:
            self._syncing_routing_times = False
            self._syncing_calc = False

            self.pickup_time.timeChanged.connect(self._sync_routing_boundary_times)
            self.dropoff_time.timeChanged.connect(self._sync_routing_boundary_times)

            if hasattr(self, "routing_table"):
                self.routing_table.itemChanged.connect(self._on_routing_item_changed)

            for widget in (
                self.hourly_rate,
                self.min_hours,
                self.package_price,
                self.package_hours,
                self.vehicle_pay_extra_time,
                self.vehicle_pay_standby,
            ):
                widget.valueChanged.connect(
                    lambda *_: self._calculate_routing_charges_core(notify=False)
                )

            self.billing_type.currentTextChanged.connect(
                lambda *_: self._calculate_routing_charges_core(notify=False)
            )
            self.out_of_town_cb.stateChanged.connect(
                lambda *_: self._calculate_routing_charges_core(notify=False)
            )
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
    def _sync_routing_boundary_times(self) -> None:
        """Push pickup/dropoff time edits into first/last routing rows."""
        if getattr(self, "_syncing_routing_times", False):
            return
        if not hasattr(self, "routing_table") or self.routing_table.rowCount() < 1:
            return

        self._syncing_routing_times = True
        try:
            start_text = self.pickup_time.time().toString("HH:mm")
            end_text = self.dropoff_time.time().toString("HH:mm")

            start_item = self.routing_table.item(0, 3) or QTableWidgetItem("")
            start_item.setText(start_text)
            self.routing_table.setItem(0, 3, start_item)

            last_row = self.routing_table.rowCount() - 1
            end_item = self.routing_table.item(last_row, 3) or QTableWidgetItem("")
            end_item.setText(end_text)
            self.routing_table.setItem(last_row, 3, end_item)
        finally:
            self._syncing_routing_times = False

    def _on_routing_item_changed(self, item) -> None:
        """When routing boundary times are edited, sync back to pickup/dropoff fields."""
        if getattr(self, "_syncing_routing_times", False):
            return
        if item is None or item.column() != 3:
            return
        if not hasattr(self, "routing_table") or self.routing_table.rowCount() < 1:
            return

        row = item.row()
        first_row = 0
        last_row = self.routing_table.rowCount() - 1
        if row not in (first_row, last_row):
            self._calculate_routing_charges_core(notify=False)
            return

        qtime = QTime.fromString((item.text() or "")[:5], "HH:mm")
        if not qtime.isValid():
            self._calculate_routing_charges_core(notify=False)
            return

        self._syncing_routing_times = True
        try:
            if row == first_row:
                self.pickup_time.setTime(qtime)
            elif row == last_row:
                self.dropoff_time.setTime(qtime)
        finally:
            self._syncing_routing_times = False

        self._calculate_routing_charges_core(notify=False)

    def _resolve_driver_employee_id(self) -> object:
        """Resolve selected/typed driver value to employee_id."""
        selected_id = self.driver.currentData()
        if selected_id is not None:
            return selected_id

        typed = self.driver.currentText().strip().lower()
        if not typed:
            return None

        for i in range(self.driver.count()):
            label = self.driver.itemText(i).strip().lower()
            if not label:
                continue
            if typed == label or typed in label:
                return self.driver.itemData(i)

        return None

    def load_vehicle_options(self) -> None:
        """Load all available vehicles into assigned-vehicle dropdown

        Uses vehicle_id as the link/foreign key (primary key in vehicles table)
        VIN number is unique identifier for each vehicle
        Displays vehicle_number (not license plate) for user-friendly selection
        """
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT vehicle_id, vehicle_number, vehicle_type,
                    vehicle_category, status
                    FROM vehicles
                    ORDER BY
                        CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                        CASE
                            WHEN vehicle_number ~ '^[Ll]-?\\d+$'
                                THEN CAST(
                                    regexp_replace(
                                        vehicle_number,
                                        '[^0-9]',
                                        '',
                                        'g'
                                    ) AS INT
                                )
                            ELSE 9999
                        END,
                        vehicle_number
                    """)
                vehicles = cur.fetchall()

                # Store vehicle type for label updates
                self._vehicle_types = {}

                # Clear and populate assigned vehicle dropdown
                self.vehicle.clear()
                self.vehicle.addItem("")  # Add empty option

                for veh_id, number, vtype, vcat, status in vehicles:
                    # Display vehicle_number (e.g., "L-5"), store vehicle_id as
                    # data
                    display_number = str(number or "")
                    self.vehicle.addItem(display_number, veh_id)
                    self._vehicle_types[veh_id] = vtype or ""

                # Wire up selection callbacks for type label
                self.vehicle.currentIndexChanged.connect(
                    self._update_vehicle_type_display
                )

        except Exception as e:
            logger.error(f"Failed to load vehicle options: {e}")
            # Silently fail - vehicle list just won't populate

    def _update_vehicle_type_display(self) -> None:
        """Update vehicle type label when vehicle selection changes"""
        try:
            veh_id = self.vehicle.currentData()
            if veh_id and veh_id in self._vehicle_types:
                self.vehicle_type_label.setText(self._vehicle_types[veh_id])
            else:
                self.vehicle_type_label.setText("")
        except Exception:
            self.vehicle_type_label.setText("")

    def load_vehicle_requested_options(self) -> None:
        """Load vehicle type options from the vehicle default pay table"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT DISTINCT vehicle_type
                    FROM vehicle_pricing_defaults
                    WHERE vehicle_type IS NOT NULL AND vehicle_type <> ''
                    ORDER BY vehicle_type
                """)
                rows = cur.fetchall()

                self.vehicle_requested.clear()
                self.vehicle_requested.addItem("")
                for (vehicle_type,) in rows:
                    self.vehicle_requested.addItem(str(vehicle_type))
        except Exception as e:
            logger.error(f"Failed to load vehicle requested options: {e}")
            # If pricing table is not available, fall back to empty list
            self.vehicle_requested.clear()
            self.vehicle_requested.addItem("")

    def load_vehicle_pricing_defaults(self) -> None:
        """Load vehicle pricing defaults for the pay table fields"""
        self._vehicle_pricing_defaults = {}
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT vehicle_type, charter_type_code, hourly_rate,
                    package_rate,
                           package_hours, minimum_hours, extra_time_rate,
                           standby_rate,
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
        except Exception as e:
            logger.error(f"Failed to load vehicle pricing defaults: {e}")
            self._vehicle_pricing_defaults = {}

    def load_charter_type_options(self) -> None:
        """Load charter type list for run type selection"""
        self.charter_type.clear()
        self.charter_type.addItem("", "")
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT type_code, type_name
                    FROM charter_types
                    WHERE is_active = true
                    ORDER BY display_order
                """)
                rows = cur.fetchall()
                for code, name in rows:
                    label = f"{code} - {name}" if name else str(code)
                    self.charter_type.addItem(label, str(code or ""))
        except Exception as e:
            logger.error(f"Failed to load charter type options: {e}")
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
                ("OTHER", "Other"),
            ]
            for code, name in fallback_types:
                label = f"{code} - {name}"
                self.charter_type.addItem(label, code)

    def apply_vehicle_pricing_defaults(self) -> None:
        """Apply pricing defaults based on selected vehicle type and charter"
        "type"""

        vehicle_type = self.vehicle_requested.currentText().strip()
        charter_code = str(self.charter_type.currentData() or "").strip()
        if not vehicle_type:
            return

        # Try exact match on vehicle + charter type; otherwise first match by
        # vehicle
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

    def toggle_custom_rate(self) -> None:
        """Enable/disable custom rate inputs"""
        enabled = self.custom_rate_cb.isChecked()
        self.custom_rate_type.setEnabled(enabled)
        self.custom_rate_amount.setEnabled(enabled)

    def toggle_billing_fields(self, *_) -> None:
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

        # Extra Time and Standby (shown when either Hourly or Package is
        # selected)
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

    def ensure_charge_defaults_table(self) -> None:
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
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS charter_charge_defaults (
                        id SERIAL PRIMARY KEY,
                        charge_name VARCHAR(200) NOT NULL,
                        type_label VARCHAR(50),
                        default_amount NUMERIC(12,2) DEFAULT 0,
                        is_taxable BOOLEAN DEFAULT TRUE,
                        is_active BOOLEAN DEFAULT TRUE,
                        display_order INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW())
                """)
                # Rename old column names if this table was created with the old schema
                cur.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='description'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='charge_name'
                        ) THEN
                            ALTER TABLE charter_charge_defaults
                                RENAME COLUMN description TO charge_name;
                        END IF;
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='charge_type'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='type_label'
                        ) THEN
                            ALTER TABLE charter_charge_defaults
                                RENAME COLUMN charge_type TO type_label;
                        END IF;
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='default_price'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='default_amount'
                        ) THEN
                            ALTER TABLE charter_charge_defaults
                                RENAME COLUMN default_price TO default_amount;
                        END IF;
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='default_listed'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='is_taxable'
                        ) THEN
                            ALTER TABLE charter_charge_defaults
                                RENAME COLUMN default_listed TO is_taxable;
                        END IF;
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='sort_order'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='charter_charge_defaults'
                              AND column_name='display_order'
                        ) THEN
                            ALTER TABLE charter_charge_defaults
                                RENAME COLUMN sort_order TO display_order;
                        END IF;
                    END$$
                """)
                cur.execute("SELECT COUNT(*) FROM charter_charge_defaults")
                count = cur.fetchone()[0] or 0
                if count == 0:
                    for idx, (desc, ctype, price, listed) in enumerate(
                        default_seed, start=1
                    ):
                        cur.execute(
                            """
                            INSERT INTO charter_charge_defaults
                            (charge_name, type_label, default_amount,
                            is_taxable, display_order)
                            VALUES (%s, %s, %s, %s, %s)
                        """,
                            (desc, ctype, price, listed, idx),
                        )
        except Exception as e:
            logger.error(f"Failed to ensure charge defaults table: {e}")

    def load_charge_defaults(self) -> None:
        """Load charge defaults for charge breakdown and edit table"""
        self._charge_defaults = []
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT id, charge_name, type_label, default_amount,
                    is_taxable, is_active
                    FROM charter_charge_defaults
                    ORDER BY display_order, id
                """)
                rows = cur.fetchall()
                for row in rows:
                    self._charge_defaults.append(
                        {
                            "id": row[0],
                            "description": row[1],
                            "charge_type": row[2] or "Hr",
                            "default_price": float(row[3] or 0),
                            "default_listed": bool(row[4]),
                            "is_active": bool(row[5]),
                        }
                    )
        except Exception as e:
            logger.error(f"Failed to load charge defaults: {e}")
            self._charge_defaults = [
                {
                    "id": None,
                    "description": "Charter Fee",
                    "charge_type": "Hr",
                    "default_price": 0,
                    "default_listed": True,
                    "is_active": True,
                },
                {
                    "id": None,
                    "description": "Gratuity",
                    "charge_type": "%",
                    "default_price": 18,
                    "default_listed": True,
                    "is_active": True,
                },
            ]

        # Populate add-charge combo
        if hasattr(self, "charge_default_combo"):
            self.charge_default_combo.clear()
            for item in self._charge_defaults:
                if item.get("is_active", True):
                    self.charge_default_combo.addItem(
                        item["description"], item
                    )

        # Populate default rows in charge table
        if hasattr(self, "charge_table"):
            self.charge_table.setRowCount(0)
            for item in self._charge_defaults:
                if item.get("default_listed") and item.get("is_active", True):
                    self.add_charge_row(
                        item["description"],
                        item.get("charge_type", "Hr"),
                        item.get("default_price", 0),
                    )
            self.ensure_gst_row()
            self.recalculate_charge_totals()

        if hasattr(self, "charge_defaults_table"):
            self.load_charge_defaults_table()

    def add_charge_row(self, description, charge_type="Hr", fee=0.0) -> None:
        """Add a row to the charge breakdown table"""
        row = self.charge_table.rowCount()
        self.charge_table.insertRow(row)

        desc_item = QTableWidgetItem(str(description))
        self.charge_table.setItem(row, 0, desc_item)

        type_combo = QComboBox()
        type_combo.addItems(
            ["Hr", "Pkg", "Cust", "Daily", "%", "Each", "Total"]
        )
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

    def add_charge_from_defaults(self) -> None:
        """Add a charge row from defaults (duplicates allowed)"""
        item = self.charge_default_combo.currentData()
        if not item:
            return
        self.add_charge_row(
            item.get("description", "Charge"),
            item.get("charge_type", "Hr"),
            item.get("default_price", 0),
        )
        self.recalculate_charge_totals()

    def remove_selected_charge(self) -> None:
        """Remove selected charge row"""
        row = self.charge_table.currentRow()
        if row < 0:
            return
        desc_item = self.charge_table.item(row, 0)
        if desc_item and desc_item.text() == "GST":
            QMessageBox.information(
                self,
                "Info",
                "GST row is auto-calculated and cannot be removed.",
            )
            return
        self.charge_table.removeRow(row)
        self.recalculate_charge_totals()

    def _move_charge_row(self, direction: int) -> None:
        """Move selected charge row up (-1) or down (+1)"""
        row = self.charge_table.currentRow()
        if row < 0:
            return
        target = row + direction
        if target < 0 or target >= self.charge_table.rowCount():
            return
        # Swap descriptions
        desc_a = self.charge_table.item(row, 0)
        desc_b = self.charge_table.item(target, 0)
        text_a = desc_a.text() if desc_a else ""
        text_b = desc_b.text() if desc_b else ""
        self.charge_table.setItem(row, 0, QTableWidgetItem(text_b))
        self.charge_table.setItem(target, 0, QTableWidgetItem(text_a))
        # Swap type combos
        type_a = self.charge_table.cellWidget(row, 1)
        type_b = self.charge_table.cellWidget(target, 1)
        val_a = type_a.currentText() if isinstance(type_a, QComboBox) else "Hr"
        val_b = type_b.currentText() if isinstance(type_b, QComboBox) else "Hr"
        if isinstance(type_a, QComboBox):
            type_a.setCurrentText(val_b)
        if isinstance(type_b, QComboBox):
            type_b.setCurrentText(val_a)
        # Swap fee spinboxes
        fee_a = self.charge_table.cellWidget(row, 2)
        fee_b = self.charge_table.cellWidget(target, 2)
        amt_a = fee_a.value() if isinstance(fee_a, QDoubleSpinBox) else 0.0
        amt_b = fee_b.value() if isinstance(fee_b, QDoubleSpinBox) else 0.0
        if isinstance(fee_a, QDoubleSpinBox):
            fee_a.setValue(amt_b)
        if isinstance(fee_b, QDoubleSpinBox):
            fee_b.setValue(amt_a)
        self.charge_table.setCurrentCell(target, 0)

    def ensure_gst_row(self) -> None:
        """Ensure GST row exists in the charge table"""
        for row in range(self.charge_table.rowCount()):
            item = self.charge_table.item(row, 0)
            if item and item.text() == "GST":
                return
        self.add_charge_row("GST", "%", 0.0)

    def recalculate_charge_totals(self) -> None:
        """Recalculate totals and GST based on charge table"""
        base_subtotal = 0.0
        subtotal = 0.0
        gst_row = None
        charter_fee_total = 0.0
        extra_fee_total = 0.0
        beverage_total = 0.0
        percent_rows = []
        self._invoice_row_calc = {}
        for row in range(self.charge_table.rowCount()):
            desc_item = self.charge_table.item(row, 0)
            desc = desc_item.text() if desc_item else ""
            type_widget = self.charge_table.cellWidget(row, 1)
            charge_type = (
                type_widget.currentText()
                if isinstance(type_widget, QComboBox)
                else ""
            )
            fee_widget = self.charge_table.cellWidget(row, 2)
            fee_val = (
                fee_widget.value()
                if isinstance(fee_widget, QDoubleSpinBox)
                else 0.0
            )
            if desc == "GST":
                gst_row = row
                continue

            desc_lower = desc.strip().lower()

            if charge_type == "%":
                percent_rows.append((row, desc, fee_val))
                continue

            line_total = float(fee_val)
            base_subtotal += line_total
            self._invoice_row_calc[row] = {
                "rate": float(fee_val),
                "units": 1.0,
                "total": line_total,
                "is_percent": False,
                "percent": None,
            }

            if desc_lower == "charter fee":
                charter_fee_total += line_total
            elif "extra" in desc_lower:
                extra_fee_total += line_total
            elif "beverage" in desc_lower:
                beverage_total += line_total

        percent_total = 0.0
        for row, desc, pct in percent_rows:
            pct_amount = (base_subtotal * float(pct or 0.0)) / 100.0
            percent_total += pct_amount
            self._invoice_row_calc[row] = {
                "rate": float(pct or 0.0),
                "units": base_subtotal,
                "total": pct_amount,
                "is_percent": True,
                "percent": float(pct or 0.0),
            }
            if (desc or "").strip().lower() == "gratuity":
                extra_fee_total += pct_amount

        subtotal = base_subtotal + percent_total
        self._invoice_percent_base = base_subtotal

        gst_amount = 0.0
        if hasattr(self, "include_gst_cb") and self.include_gst_cb.isChecked():
            gst_amount = subtotal * 0.05

        if gst_row is not None:
            gst_widget = self.charge_table.cellWidget(gst_row, 2)
            if isinstance(gst_widget, QDoubleSpinBox):
                gst_widget.setValue(gst_amount)
            self._invoice_row_calc[gst_row] = {
                "rate": 5.0,
                "units": subtotal,
                "total": gst_amount,
                "is_percent": True,
                "percent": 5.0,
            }

        total = subtotal + gst_amount
        self.total_amount.setValue(total)
        (
            self.invoice_subtotal.setValue(subtotal)
            if hasattr(self, "invoice_subtotal")
            else None
        )
        (
            self.invoice_total.setValue(total)
            if hasattr(self, "invoice_total")
            else None
        )
        if hasattr(self, "invoice_charter_charge"):
            self.invoice_charter_charge.setValue(round(charter_fee_total, 2))
        if hasattr(self, "invoice_extra_charges"):
            self.invoice_extra_charges.setValue(round(extra_fee_total, 2))
        if hasattr(self, "invoice_beverage_total"):
            self.invoice_beverage_total.setValue(round(beverage_total, 2))
        if hasattr(self, "invoice_gst_amount"):
            self.invoice_gst_amount.setValue(round(gst_amount, 2))

        if hasattr(self, "invoice_amount_paid_display") and hasattr(self, "invoice_amount_due_display"):
            paid_val = float(self.invoice_amount_paid_display.value())
            due_val = max(0.0, float(total) - paid_val)
            self.invoice_amount_due_display.setValue(due_val)
            if hasattr(self, "invoice_status_display"):
                self.invoice_status_display.setText("CLOSED" if due_val <= 0.01 else "OPEN")
            if hasattr(self, "invoice_paid_status_display"):
                self.invoice_paid_status_display.setText("CLOSED" if due_val <= 0.01 else "OPEN")
            if hasattr(self, "balance_due"):
                self.balance_due.setValue(due_val)
        self.sync_invoice_charge_table()

    def set_charge_fee(self, description, amount) -> None:
        """Set fee for a charge row by description"""
        for row in range(self.charge_table.rowCount()):
            desc_item = self.charge_table.item(row, 0)
            if desc_item and desc_item.text() == description:
                fee_widget = self.charge_table.cellWidget(row, 2)
                if isinstance(fee_widget, QDoubleSpinBox):
                    fee_widget.setValue(float(amount or 0))
                return

    def sync_invoice_charge_table(self) -> None:
        """Mirror charge breakdown into invoice details tab"""
        if not hasattr(self, "invoice_charge_table"):
            return
        self.invoice_charge_table.setRowCount(0)
        for row in range(self.charge_table.rowCount()):
            desc_item = self.charge_table.item(row, 0)
            desc = desc_item.text() if desc_item else ""
            type_widget = self.charge_table.cellWidget(row, 1)
            fee_widget = self.charge_table.cellWidget(row, 2)
            charge_type = (
                type_widget.currentText()
                if isinstance(type_widget, QComboBox)
                else ""
            )
            fee_val = (
                fee_widget.value()
                if isinstance(fee_widget, QDoubleSpinBox)
                else 0.0
            )
            calc = getattr(self, "_invoice_row_calc", {}).get(row, {})
            is_percent = bool(calc.get("is_percent"))
            line_total = float(calc.get("total", fee_val))

            if is_percent:
                rate_text = f"{float(calc.get('percent', fee_val)):.1f}%"
                units_text = f"${float(calc.get('units', 0.0)):,.2f}"
            else:
                rate_text = f"${float(calc.get('rate', fee_val)):,.2f}"
                units_val = float(calc.get("units", 1.0))
                units_text = f"{units_val:.2f}" if abs(units_val - 1.0) > 0.001 else "1"

                desc_lower = (desc or "").strip().lower()
                if desc_lower == "charter fee":
                    units_val = float(getattr(self, "_last_billable_hours", units_val) or units_val)
                    rate_val = float(self.hourly_rate.value()) if hasattr(self, "hourly_rate") else float(calc.get("rate", fee_val))
                    rate_text = f"${rate_val:,.2f}"
                    units_text = f"{units_val:.2f} hrs"
                    line_total = rate_val * units_val
                elif "extra time" in desc_lower:
                    overtime = float(getattr(self, "_last_overtime_hours", 0.0) or 0.0)
                    extra_rate = float(getattr(self, "_last_extra_rate", 0.0) or 0.0)
                    if overtime > 0 and extra_rate > 0:
                        rate_text = f"${extra_rate:,.2f}"
                        units_text = f"{overtime:.2f} hrs"
                        line_total = overtime * extra_rate

            irow = self.invoice_charge_table.rowCount()
            self.invoice_charge_table.insertRow(irow)
            self.invoice_charge_table.setItem(irow, 0, QTableWidgetItem(desc))
            self.invoice_charge_table.setItem(
                irow, 1, QTableWidgetItem(charge_type)
            )
            self.invoice_charge_table.setItem(
                irow, 2, QTableWidgetItem(rate_text)
            )
            self.invoice_charge_table.setItem(
                irow, 3, QTableWidgetItem(units_text)
            )
            self.invoice_charge_table.setItem(
                irow, 4, QTableWidgetItem(f"${line_total:,.2f}")
            )

    def create_edit_tables_tab(self) -> QWidget:
        """Tab: Edit default tables used in charter details"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("Edit Charter Tables")
        title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel(
            "Charge Defaults (description, type, price, default listed)"
        )
        subtitle.setStyleSheet("color:#555; font-size: 11px;")
        layout.addWidget(subtitle)

        self.charge_defaults_table = QTableWidget()
        self.charge_defaults_table.setColumnCount(5)
        self.charge_defaults_table.setHorizontalHeaderLabels(
            ["Description", "Type", "Price", "Default", "Active"]
        )
        self.charge_defaults_table.horizontalHeader().setStretchLastSection(
            True
        )
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

    def load_charge_defaults_table(self) -> None:
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

            price_item = QTableWidgetItem(
                f"{float(item.get('default_price', 0)):.2f}"
            )
            self.charge_defaults_table.setItem(row, 2, price_item)

            default_item = QTableWidgetItem(
                "Yes" if item.get("default_listed") else "No"
            )
            self.charge_defaults_table.setItem(row, 3, default_item)

            active_item = QTableWidgetItem(
                "Yes" if item.get("is_active") else "No"
            )
            self.charge_defaults_table.setItem(row, 4, active_item)

    def add_charge_default_row(self) -> None:
        """Add empty charge default row"""
        row = self.charge_defaults_table.rowCount()
        self.charge_defaults_table.insertRow(row)
        self.charge_defaults_table.setItem(row, 0, QTableWidgetItem(""))
        self.charge_defaults_table.setItem(row, 1, QTableWidgetItem("Hr"))
        self.charge_defaults_table.setItem(row, 2, QTableWidgetItem("0.00"))
        self.charge_defaults_table.setItem(row, 3, QTableWidgetItem("Yes"))
        self.charge_defaults_table.setItem(row, 4, QTableWidgetItem("Yes"))

    def delete_charge_default_row(self) -> None:
        """Delete selected default row"""
        row = self.charge_defaults_table.currentRow()
        if row < 0:
            return
        self.charge_defaults_table.removeRow(row)

    def save_charge_defaults_table(self) -> None:
        """Save charge defaults back to DB"""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                for row in range(self.charge_defaults_table.rowCount()):
                    desc_item = self.charge_defaults_table.item(row, 0)
                    type_item = self.charge_defaults_table.item(row, 1)
                    price_item = self.charge_defaults_table.item(row, 2)
                    default_item = self.charge_defaults_table.item(row, 3)
                    active_item = self.charge_defaults_table.item(row, 4)

                    description = desc_item.text().strip() if desc_item else ""
                    if not description:
                        continue
                    charge_type = (
                        type_item.text().strip() if type_item else "Hr"
                    )
                    try:
                        price = float(price_item.text() if price_item else 0)
                    except Exception:
                        price = 0.0
                    default_listed = (
                        (default_item.text().strip().lower() == "yes")
                        if default_item
                        else True
                    )
                    is_active = (
                        (active_item.text().strip().lower() == "yes")
                        if active_item
                        else True
                    )

                    row_id = (
                        desc_item.data(Qt.ItemDataRole.UserRole)
                        if desc_item
                        else None
                    )
                    if row_id:
                        cur.execute(
                            """
                            UPDATE charter_charge_defaults
                            SET charge_name = %s, type_label = %s,
                            default_amount = %s,
                                is_taxable = %s, is_active = %s,
                                updated_at = NOW()
                            WHERE id = %s
                        """,
                            (
                                description,
                                charge_type,
                                price,
                                default_listed,
                                is_active,
                                row_id,
                            ),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO charter_charge_defaults
                            (charge_name, type_label, default_amount,
                            is_taxable, is_active)
                            VALUES (%s, %s, %s, %s, %s)
                            RETURNING id
                        """,
                            (
                                description,
                                charge_type,
                                price,
                                default_listed,
                                is_active,
                            ),
                        )
                        new_id = cur.fetchone()[0]
                        desc_item.setData(Qt.ItemDataRole.UserRole, new_id)

                self.load_charge_defaults()
                QMessageBox.information(
                    self, "Saved", "Charge defaults saved."
                )
        except Exception as e:
            logger.error(f"Failed to save charge defaults: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to save defaults: {e}"
            )

    def create_master_tab(self) -> QWidget:
        """Tab 1: Charter master data - LMSGold style layout with organized"
        "sections"""

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
        sec1_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
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
        self.status.addItems(
            ["Confirmed", "In Progress", "Completed", "Closed", "Cancelled"]
        )
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
        self.source.addItems(
            ["Phone", "Email", "Walk-in", "Online", "Referral", "Other"]
        )
        self.source.setMaximumWidth(150)
        row1c.addWidget(source_label)
        row1c.addWidget(self.source)
        row1c.addStretch()
        form_layout.addLayout(row1c)

        # ===== SECTION 2: CHARTER DETAILS =====
        sec2_title = QLabel("CHARTER DETAILS")
        sec2_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec2_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
        form_layout.addWidget(sec2_title)

        # Row 1.5a: Pickup Location + Time
        row1_5a = QHBoxLayout()
        self.pickup_label = QLabel("Pickup:")
        self.pickup_label.setMinimumWidth(100)
        self.pickup = QLineEdit()
        self.pickup.setMaximumWidth(400)
        self.pickup.setPlaceholderText("Pickup address or location...")
        row1_5a.addWidget(self.pickup_label)
        row1_5a.addWidget(self.pickup)
        row1_5a.addSpacing(30)

        self.pickup_time_label = QLabel("Time:")
        self.pickup_time_label.setMinimumWidth(40)
        self.pickup_time = QTimeEdit()
        self.pickup_time.setLocale(QLocale(QLocale.Language.English,
                                           QLocale.Country.UnitedKingdom))
        self.pickup_time.setDisplayFormat("HH:mm")
        self.pickup_time.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.pickup_time.setReadOnly(False)
        self.pickup_time.setMaximumWidth(100)
        row1_5a.addWidget(self.pickup_time_label)
        row1_5a.addWidget(self.pickup_time)
        row1_5a.addStretch()
        form_layout.addLayout(row1_5a)

        # Row 1.5b: Destination + Time
        row1_5b = QHBoxLayout()
        self.destination_label = QLabel("Destination:")
        self.destination_label.setMinimumWidth(100)
        self.destination = QLineEdit()
        self.destination.setMaximumWidth(400)
        self.destination.setPlaceholderText(
            "Destination address or location..."
        )
        row1_5b.addWidget(self.destination_label)
        row1_5b.addWidget(self.destination)
        row1_5b.addSpacing(30)

        self.dropoff_time_label = QLabel("Time:")
        self.dropoff_time_label.setMinimumWidth(40)
        self.dropoff_time = QTimeEdit()
        self.dropoff_time.setLocale(QLocale(QLocale.Language.English,
                                            QLocale.Country.UnitedKingdom))
        self.dropoff_time.setDisplayFormat("HH:mm")
        self.dropoff_time.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.dropoff_time.setReadOnly(False)
        self.dropoff_time.setMaximumWidth(100)
        row1_5b.addWidget(self.dropoff_time_label)
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
        self.billing_type.currentTextChanged.connect(
            self.toggle_billing_fields
        )
        self.billing_type.currentIndexChanged.connect(
            self.toggle_billing_fields
        )
        row2a.addWidget(self.billing_type)

        row2a.addSpacing(30)

        charter_type_label = QLabel("Charter Type:")
        charter_type_label.setMinimumWidth(100)
        self.charter_type = QComboBox()
        self.charter_type.setMaximumWidth(180)
        self.charter_type.currentIndexChanged.connect(
            self.apply_vehicle_pricing_defaults
        )
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
        self.vehicle_requested.currentIndexChanged.connect(
            self.apply_vehicle_pricing_defaults
        )
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
        sec3_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
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
        self.driver.setEditable(True)
        self.driver.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.driver.setMaximumWidth(200)
        row3b.addWidget(driver_label)
        row3b.addWidget(self.driver)
        row3b.addStretch()
        form_layout.addLayout(row3b)

        sec4_title = QLabel("ROUTING & CHARGES")
        sec4_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec4_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
        form_layout.addWidget(sec4_title)

        routing_widget = self.create_routing_tab()
        form_layout.addWidget(routing_widget)

        # ===== COST CORNER (SIMPLIFIED) =====
        costcorner_title = QLabel("COST CORNER")
        costcorner_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        costcorner_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
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
        self.beverage_confirm_table.setHorizontalHeaderLabels(
            ["Item", "Type", "Ordered"]
        )
        self.beverage_confirm_table.horizontalHeader().setStretchLastSection(
            True
        )
        self.beverage_confirm_table.setMaximumHeight(140)
        form_layout.addWidget(self.beverage_confirm_table)

        # ===== SECTION 5: FINANCIAL SUMMARY =====
        sec5_title = QLabel("FINANCIAL SUMMARY")
        sec5_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec5_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
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
        sec6_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
        form_layout.addWidget(sec6_title)

        notes_row = QHBoxLayout()
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        notes_row.addWidget(self.notes)
        form_layout.addLayout(notes_row)

        moved_hint = QLabel(
            "Driver-related fields moved to the Driver Info tab for faster driver entry."
        )
        moved_hint.setStyleSheet("color:#555; font-size: 11px;")
        form_layout.addWidget(moved_hint)

        # ===== SECTION 10: DISPATCHER NOTES (EMAIL/PHONE LOGS) =====
        sec10_title = QLabel("DISPATCHER NOTES (Email/Phone Logs)")
        sec10_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec10_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
        form_layout.addWidget(sec10_title)

        # Row 10a: Dispatcher Notes (from Outlook emails, phone calls, etc.)
        dispatcher_notes_label = QLabel("Dispatcher Notes:")
        dispatcher_notes_label.setMinimumWidth(100)
        dispatcher_notes_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dispatcher_notes = QTextEdit()
        self.dispatcher_notes.setMinimumHeight(100)
        self.dispatcher_notes.setPlaceholderText(
            "Email details, phone conversation notes, client"
            "communications...\n\nUse Outlook add-in button to auto-paste"
            "email content here."
        )
        row10a = QHBoxLayout()
        row10a.addWidget(dispatcher_notes_label)
        row10a.addWidget(self.dispatcher_notes)
        form_layout.addLayout(row10a)

        # ===== SECTION 11: CLIENT WARNING FLAGS =====
        sec11_title = QLabel("⚠️ CLIENT WARNING FLAGS")
        sec11_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec11_title.setStyleSheet(
            "color: #d32f2f; background-color: #ffebee; border-bottom: 2px"
            "solid #c62828; padding: 6px;"
        )
        form_layout.addWidget(sec11_title)

        # Row 11a: Warning display (read-only, loaded from accounts table)
        self.client_warnings_display = QTextEdit()
        self.client_warnings_display.setReadOnly(True)
        self.client_warnings_display.setMaximumHeight(60)
        self.client_warnings_display.setStyleSheet(
            "background-color: #fff9c4; color: #f57c00; font-weight: bold;"
        )
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

    def create_driver_info_tab(self) -> QWidget:
        """Tab: Driver-facing information entry (HOS, pay, and instructions)."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        driver_widget = QWidget()
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)
        form_layout.setContentsMargins(4, 4, 4, 4)

        # ===== SECTION 7: HOS (HOURS OF SERVICE) =====
        sec7_title = QLabel("HOURS OF SERVICE (HOS)")
        sec7_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec7_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
        form_layout.addWidget(sec7_title)

        row7a = QHBoxLayout()
        calc_hours_label = QLabel("Calculated Hours:")
        calc_hours_label.setMinimumWidth(120)
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
        worked_hours_label.setMinimumWidth(120)
        self.driver_hours_worked = QDoubleSpinBox()
        self.driver_hours_worked.setMinimum(0)
        self.driver_hours_worked.setMaximum(24)
        self.driver_hours_worked.setDecimals(2)
        self.driver_hours_worked.setMaximumWidth(100)
        row7a.addWidget(worked_hours_label)
        row7a.addWidget(self.driver_hours_worked)
        row7a.addStretch()
        form_layout.addLayout(row7a)

        row7b = QHBoxLayout()
        hours1_label = QLabel("On-Duty Driving (Hours):")
        hours1_label.setMinimumWidth(120)
        self.driver_hours_1 = QDoubleSpinBox()
        self.driver_hours_1.setMinimum(0)
        self.driver_hours_1.setMaximum(24)
        self.driver_hours_1.setDecimals(2)
        self.driver_hours_1.setMaximumWidth(100)
        row7b.addWidget(hours1_label)
        row7b.addWidget(self.driver_hours_1)
        row7b.addSpacing(30)

        hours2_label = QLabel("On-Duty Not Driving (Hours):")
        hours2_label.setMinimumWidth(120)
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
        sec8_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
        form_layout.addWidget(sec8_title)

        row8a = QHBoxLayout()
        pay1_label = QLabel("Driving Pay (Rate 1):")
        pay1_label.setMinimumWidth(120)
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
        pay2_label.setMinimumWidth(120)
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

        row8b = QHBoxLayout()
        base_pay_label = QLabel("Base Pay:")
        base_pay_label.setMinimumWidth(120)
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
        grat_percent_label.setMinimumWidth(120)
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

        row8c = QHBoxLayout()
        grat_amount_label = QLabel("Gratuity Amount:")
        grat_amount_label.setMinimumWidth(120)
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
        total_expense_label.setMinimumWidth(120)
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

        # ===== SECTION 9: ACCOUNTING & DRIVER INSTRUCTIONS =====
        sec9_title = QLabel("ACCOUNTING & DRIVER INSTRUCTIONS")
        sec9_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        sec9_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
        form_layout.addWidget(sec9_title)

        row9a = QHBoxLayout()
        retainer_label = QLabel("Retainer:")
        retainer_label.setMinimumWidth(120)
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
        deposit_label.setMinimumWidth(120)
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

        row9b = QHBoxLayout()
        payment_status_label = QLabel("Payment Status:")
        payment_status_label.setMinimumWidth(120)
        self.payment_status = QComboBox()
        self.payment_status.addItems(["Pending", "Partial", "Paid", "Overdue"])
        self.payment_status.setMaximumWidth(150)
        row9b.addWidget(payment_status_label)
        row9b.addWidget(self.payment_status)
        row9b.addStretch()
        form_layout.addLayout(row9b)

        driver_notes_label = QLabel("Driver Instructions:")
        driver_notes_label.setMinimumWidth(120)
        driver_notes_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.driver_notes = QTextEdit()
        self.driver_notes.setMaximumHeight(120)
        self.driver_notes.setPlaceholderText(
            "Directions, special requests, pickup instructions..."
        )
        row9c = QHBoxLayout()
        row9c.addWidget(driver_notes_label)
        row9c.addWidget(self.driver_notes)
        form_layout.addLayout(row9c)

        form_layout.addStretch()
        driver_widget.setLayout(form_layout)
        scroll.setWidget(driver_widget)
        layout.addWidget(scroll)
        widget.setLayout(layout)
        return widget

    def create_invoice_details_tab(self) -> QWidget:
        """Tab 2: Invoice Details with charge breakdown (compact 2-column
        layout)

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
        self.separate_beverage_invoice_cb = QCheckBox(
            "Separate beverage invoice"
        )
        header_row3.addWidget(self.separate_beverage_invoice_cb)
        self.include_gst_cb = QCheckBox("Include GST (5%)")
        self.include_gst_cb.setChecked(True)
        self.include_gst_cb.toggled.connect(self.recalculate_charge_totals)
        header_row3.addWidget(self.include_gst_cb)
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
        self.invoice_charge_table.setColumnCount(5)
        self.invoice_charge_table.setHorizontalHeaderLabels(
            ["Charge", "Type", "Rate", "Units/%", "Total"]
        )
        self.invoice_charge_table.setColumnWidth(0, 160)
        self.invoice_charge_table.setColumnWidth(1, 80)
        self.invoice_charge_table.setColumnWidth(2, 90)
        self.invoice_charge_table.setColumnWidth(3, 90)
        self.invoice_charge_table.setColumnWidth(4, 90)
        self.invoice_charge_table.setMaximumHeight(160)
        self.invoice_charge_table.setFixedWidth(560)
        details_layout.addWidget(self.invoice_charge_table)

        # Beverage items list (GST included per line)
        beverage_items_title = QLabel("Beverage Items (GST included)")
        beverage_items_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        details_layout.addWidget(beverage_items_title)

        self.invoice_beverage_table = QTableWidget()
        self.invoice_beverage_table.setColumnCount(4)
        self.invoice_beverage_table.setHorizontalHeaderLabels(
            ["Item", "Qty", "Unit Price", "Line Total"]
        )
        self.invoice_beverage_table.setColumnWidth(0, 180)
        self.invoice_beverage_table.setColumnWidth(1, 60)
        self.invoice_beverage_table.setColumnWidth(2, 100)
        self.invoice_beverage_table.setColumnWidth(3, 120)
        self.invoice_beverage_table.setMaximumHeight(160)
        self.invoice_beverage_table.setFixedWidth(520)
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
        self.invoice_amount_due_display.setStyleSheet(
            "font-weight: bold; color: #cc0000;"
        )
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

    def create_orders_tab(self) -> QWidget:
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
        self.orders_table.setHorizontalHeaderLabels(
            ["Item", "Qty", "Unit Price", "Total", "Status"]
        )
        self.orders_table.horizontalHeader().setStretchLastSection(True)
        self.orders_table.setMaximumHeight(180)
        self.orders_table.setFixedWidth(520)
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

    def create_beverage_printout_tab(self) -> QWidget:
        """Tab 3.5: Beverage card details from beverage order data."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Title
        title = QLabel("🍷 Beverage Card Details")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a3d7a;")
        layout.addWidget(title)

        # Service + totals summary
        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(18)
        summary_grid.setVerticalSpacing(6)

        self.beverage_service_status = QLabel("No")
        self.beverage_service_status.setStyleSheet("font-weight: bold;")
        summary_grid.addWidget(QLabel("Beverage Service Required:"), 0, 0)
        summary_grid.addWidget(self.beverage_service_status, 0, 1)

        self.beverage_items_count = QLabel("0")
        self.beverage_items_count.setStyleSheet("font-weight: bold;")
        summary_grid.addWidget(QLabel("Total Items:"), 0, 2)
        summary_grid.addWidget(self.beverage_items_count, 0, 3)

        self.beverage_card_subtotal = QLabel("$0.00")
        self.beverage_card_subtotal.setStyleSheet("font-weight: bold;")
        summary_grid.addWidget(QLabel("Subtotal (Pre-GST):"), 1, 0)
        summary_grid.addWidget(self.beverage_card_subtotal, 1, 1)

        self.beverage_card_gst = QLabel("$0.00")
        self.beverage_card_gst.setStyleSheet("font-weight: bold;")
        summary_grid.addWidget(QLabel("GST (5%):"), 1, 2)
        summary_grid.addWidget(self.beverage_card_gst, 1, 3)

        self.beverage_card_total = QLabel("$0.00")
        self.beverage_card_total.setStyleSheet(
            "font-weight: bold; color: #0f5f2f;"
        )
        summary_grid.addWidget(QLabel("Total (GST Included):"), 2, 0)
        summary_grid.addWidget(self.beverage_card_total, 2, 1)

        layout.addLayout(summary_grid)

        details_title = QLabel("Ordered Beverage Details")
        details_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        details_title.setStyleSheet(
            "color: #1a3d7a; border-bottom: 2px solid #e0e0e0; padding: 4px;"
        )
        layout.addWidget(details_title)

        self.beverage_card_table = QTableWidget()
        self.beverage_card_table.setColumnCount(6)
        self.beverage_card_table.setHorizontalHeaderLabels(
            ["Item", "Category", "Qty", "Unit Price", "Total", "Status"]
        )
        self.beverage_card_table.setColumnWidth(0, 180)
        self.beverage_card_table.setColumnWidth(1, 100)
        self.beverage_card_table.setColumnWidth(2, 60)
        self.beverage_card_table.setColumnWidth(3, 90)
        self.beverage_card_table.setColumnWidth(4, 90)
        self.beverage_card_table.setColumnWidth(5, 100)
        self.beverage_card_table.horizontalHeader().setStretchLastSection(True)
        self.beverage_card_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.beverage_card_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        layout.addWidget(self.beverage_card_table)

        hint = QLabel(
            "This view reflects beverage order rows linked to this charter."
        )
        hint.setStyleSheet("color: #666666; font-size: 11px;")
        layout.addWidget(hint)

        widget.setLayout(layout)
        return widget

    def create_routing_tab(self) -> QWidget:
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

        # Split Run Details
        split_layout = QHBoxLayout()
        split_layout.setSpacing(4)
        split_layout.addWidget(QLabel("Split Run Details:"))
        self.split_run_details_input = QLineEdit()
        self.split_run_details_input.setPlaceholderText(
            "Client split run details / notes"
        )
        self.split_run_details_input.setMaximumWidth(260)
        split_layout.addWidget(self.split_run_details_input)

        split_layout.addWidget(QLabel("RUN FIRST:"))
        self.split_run_dropoff_time = QTimeEdit()
        self.split_run_dropoff_time.setLocale(QLocale(QLocale.Language.English,
                                                      QLocale.Country.UnitedKingdom))
        self.split_run_dropoff_time.setDisplayFormat("HH:mm")
        self.split_run_dropoff_time.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.split_run_dropoff_time.setReadOnly(False)
        self.split_run_dropoff_time.setMaximumWidth(80)
        split_layout.addWidget(self.split_run_dropoff_time)

        split_layout.addWidget(QLabel("Duration:"))
        self.split_run_duration = QSpinBox()
        self.split_run_duration.setMinimum(1)
        self.split_run_duration.setMaximum(8)
        self.split_run_duration.setValue(2)
        self.split_run_duration.setSuffix(" hrs")
        self.split_run_duration.setMaximumWidth(80)
        self.split_run_duration.valueChanged.connect(
            self._on_split_run_duration_changed
        )
        split_layout.addWidget(self.split_run_duration)

        split_layout.addWidget(QLabel("RUN LAST:"))
        self.split_run_pickup_time = QTimeEdit()
        self.split_run_pickup_time.setLocale(QLocale(QLocale.Language.English,
                                                     QLocale.Country.UnitedKingdom))
        self.split_run_pickup_time.setDisplayFormat("HH:mm")
        self.split_run_pickup_time.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.split_run_pickup_time.setReadOnly(False)
        self.split_run_pickup_time.setMaximumWidth(80)
        split_layout.addWidget(self.split_run_pickup_time)

        add_split_btn = QPushButton("➕ Add Split Run Stops")
        add_split_btn.setMaximumWidth(170)
        add_split_btn.clicked.connect(self._add_split_run_stops)
        split_layout.addWidget(add_split_btn)

        split_layout.addStretch()
        layout.addLayout(split_layout)

        # ===== MAIN TWO-COLUMN LAYOUT: ROUTING (LEFT) + CHARGES (RIGHT) =====
        main_content = QHBoxLayout()
        main_content.setSpacing(8)

        # ===== LEFT COLUMN: ROUTING STOPS =====
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)

        # Routing Stops Table (compact)
        stops_label = QLabel("Route Stops (in order)")
        stops_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        left_layout.addWidget(stops_label)

        self.routing_table = QTableWidget()
        self.routing_table.setColumnCount(5)
        self.routing_table.setHorizontalHeaderLabels(
            ["Route #", "Type", "Location", "Time", "Notes"]
        )
        self.routing_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.routing_table.setMinimumHeight(200)
        self.routing_table.setMaximumHeight(240)
        self.routing_table.setFixedWidth(520)
        left_layout.addWidget(self.routing_table)

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
        left_layout.addLayout(stop_btn_layout)
        left_layout.addStretch()

        main_content.addLayout(left_layout)

        # ===== RIGHT COLUMN: CHARGES & INVOICE DETAILS (STACKED) =====
        right_layout = QVBoxLayout()
        right_layout.setSpacing(4)

        # Charges Breakdown Table (Invoice line items)
        charges_title = QLabel("💰 Charge Breakdown (Invoice Items)")
        charges_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        right_layout.addWidget(charges_title)

        self.charge_table = QTableWidget()
        self.charge_table.setColumnCount(3)
        self.charge_table.setHorizontalHeaderLabels(["Charge", "Type", "Fee"])
        self.charge_table.setColumnWidth(0, 200)
        self.charge_table.setColumnWidth(1, 80)
        self.charge_table.setColumnWidth(2, 120)
        self.charge_table.setMinimumHeight(180)
        self.charge_table.setMaximumHeight(200)
        self.charge_table.setFixedWidth(520)
        right_layout.addWidget(self.charge_table)

        charge_controls = QHBoxLayout()
        charge_controls.setSpacing(6)
        charge_controls.addWidget(QLabel("Add Charge:"))
        self.charge_default_combo = QComboBox()
        self.charge_default_combo.setMaximumWidth(180)
        charge_controls.addWidget(self.charge_default_combo)

        add_charge_btn = QPushButton("➕ Add")
        add_charge_btn.setMaximumWidth(70)
        add_charge_btn.clicked.connect(self.add_charge_from_defaults)
        charge_controls.addWidget(add_charge_btn)

        remove_charge_btn = QPushButton("🗑️ Rm")
        remove_charge_btn.setMaximumWidth(70)
        remove_charge_btn.clicked.connect(self.remove_selected_charge)
        charge_controls.addWidget(remove_charge_btn)

        grat_label = QLabel("Grat %:")
        charge_controls.addWidget(grat_label)
        self.gratuity_percent_input_rt = QDoubleSpinBox()
        self.gratuity_percent_input_rt.setMinimum(0)
        self.gratuity_percent_input_rt.setMaximum(100)
        self.gratuity_percent_input_rt.setDecimals(1)
        self.gratuity_percent_input_rt.setSuffix("%")
        self.gratuity_percent_input_rt.setMaximumWidth(60)
        self.gratuity_percent_input_rt.setValue(18.0)
        self.gratuity_percent_input_rt.valueChanged.connect(
            self._apply_gratuity_percent
        )
        charge_controls.addWidget(self.gratuity_percent_input_rt)

        recalc_btn = QPushButton("🧮 Recalc")
        recalc_btn.setMaximumWidth(70)
        recalc_btn.clicked.connect(self.recalculate_charge_totals)
        charge_controls.addWidget(recalc_btn)

        charge_up_btn = QPushButton("⬆️ Up")
        charge_up_btn.setMaximumWidth(60)
        charge_up_btn.clicked.connect(lambda: self._move_charge_row(-1))
        charge_controls.addWidget(charge_up_btn)

        charge_down_btn = QPushButton("⬇️ Down")
        charge_down_btn.setMaximumWidth(65)
        charge_down_btn.clicked.connect(lambda: self._move_charge_row(1))
        charge_controls.addWidget(charge_down_btn)

        charge_controls.addStretch()
        right_layout.addLayout(charge_controls)

        right_layout.addStretch()
        main_content.addLayout(right_layout)

        layout.addLayout(main_content)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _apply_gratuity_percent(self) -> None:
        """Sync gratuity percent control to charge table row."""
        if not hasattr(self, "charge_table"):
            return
        percent_val = (
            self.gratuity_percent_input_rt.value()
            if hasattr(self, "gratuity_percent_input_rt")
            else 0.0
        )

        # Find or add gratuity row
        gratuity_row = None
        for row in range(self.charge_table.rowCount()):
            desc_item = self.charge_table.item(row, 0)
            if desc_item and desc_item.text() == "Gratuity":
                gratuity_row = row
                break
        if gratuity_row is None:
            self.add_charge_row("Gratuity", "%", percent_val)
            self.recalculate_charge_totals()
            return

        type_widget = self.charge_table.cellWidget(gratuity_row, 1)
        if isinstance(type_widget, QComboBox):
            type_widget.setCurrentText("%")
        fee_widget = self.charge_table.cellWidget(gratuity_row, 2)
        if isinstance(fee_widget, QDoubleSpinBox):
            fee_widget.setValue(percent_val)
        self.recalculate_charge_totals()

    def on_rate_type_changed(self, rate_type) -> None:
        """Handle rate type change"""
        if rate_type == "Hr":
            self.min_hours.setEnabled(True)
            self.hourly_rate.setEnabled(True)
        elif rate_type in ("Pkg", "Daily") or rate_type == "Cust":
            self.min_hours.setEnabled(False)
            self.hourly_rate.setEnabled(True)
        else:
            self.min_hours.setEnabled(False)
            self.hourly_rate.setEnabled(True)

    def on_out_of_town_changed(self) -> None:
        """Update top boundary labels and keep routing boundary labels generic."""

        is_out_of_town = self.out_of_town_cb.isChecked()
        self._update_trip_boundary_labels(is_out_of_town)
        rows = self._read_routing_rows()
        if not rows:
            rows = [
                {
                    "type": "Pick up at",
                    "location": self.pickup.text().strip() if hasattr(self, "pickup") else "",
                    "time": self.pickup_time.time().toString("HH:mm") if hasattr(self, "pickup_time") else "",
                    "notes": "",
                },
                {
                    "type": "Drop off at",
                    "location": self.destination.text().strip() if hasattr(self, "destination") else "",
                    "time": self.dropoff_time.time().toString("HH:mm") if hasattr(self, "dropoff_time") else "",
                    "notes": "",
                },
            ]

        rows[0]["type"] = "Pick up at"
        rows[-1]["type"] = "Drop off at"
        self._write_routing_rows(rows)
        self._sync_routing_boundary_times()
        self._calculate_routing_charges_core(notify=False)

    def _update_trip_boundary_labels(self, is_out_of_town: bool) -> None:
        """Top section labels for pickup/dropoff become leave/return wording."""
        if hasattr(self, "pickup_label"):
            self.pickup_label.setText(
                "Leave Red Deer:" if is_out_of_town else "Pickup:"
            )
        if hasattr(self, "destination_label"):
            self.destination_label.setText(
                "Return to Red Deer:" if is_out_of_town else "Destination:"
            )
        if hasattr(self, "pickup_time_label"):
            self.pickup_time_label.setText(
                "By:" if is_out_of_town else "Time:"
            )
        if hasattr(self, "dropoff_time_label"):
            self.dropoff_time_label.setText(
                "By:" if is_out_of_town else "Time:"
            )

    def add_routing_stop(self) -> None:
        """Add a new routing stop"""
        dialog = RoutingStopDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            stop_data = dialog.get_stop_data()

            row = self.routing_table.rowCount()
            self.routing_table.insertRow(row)

            self.routing_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.routing_table.setItem(
                row, 1, QTableWidgetItem(stop_data["type"])
            )
            self.routing_table.setItem(
                row, 2, QTableWidgetItem(stop_data["location"])
            )
            self.routing_table.setItem(
                row, 3, QTableWidgetItem(stop_data["time"])
            )
            self.routing_table.setItem(
                row, 4, QTableWidgetItem(stop_data["notes"])
            )

            self.renumber_stops()

    def _add_split_run_stops(self) -> None:
        """Insert split-run child stops between pickup and drop-off/return"
        "rows."""

        details = (
            self.split_run_details_input.text().strip()
            if hasattr(self, "split_run_details_input")
            else ""
        )
        drop_time = (
            self.split_run_dropoff_time.time().toString("HH:mm")
            if hasattr(self, "split_run_dropoff_time")
            else ""
        )
        pick_time = (
            self.split_run_pickup_time.time().toString("HH:mm")
            if hasattr(self, "split_run_pickup_time")
            else ""
        )

        rows = self._read_routing_rows()
        if not rows:
            self.on_out_of_town_changed()
            rows = self._read_routing_rows()

        # Remove existing split-run rows before inserting updated ones
        rows = [
            row
            for row in rows
            if not self._is_type_like(row.get("type", ""), "split run")
        ]

        insert_at = next(
            (
                i
                for i, row in enumerate(rows)
                if self._is_type_like(row.get("type", ""), "drop off")
                or self._is_type_like(
                    row.get("type", ""), "return to red deer"
                )
            ),
            len(rows),
        )

        split_rows = [
            {
                "type": "Drop off for Split Run at",
                "location": "",
                "time": drop_time,
                "notes": details,
            },
            {
                "type": "Pick up at",
                "location": "",
                "time": pick_time,
                "notes": details,
            },
        ]
        rows[insert_at:insert_at] = split_rows
        self._write_routing_rows(rows)

    def _on_split_run_duration_changed(self) -> None:
        """When split run duration changes, auto-calculate end time."""
        if not hasattr(self, "split_run_duration"):
            return
        if not hasattr(self, "split_run_dropoff_time"):
            return
        if not hasattr(self, "split_run_pickup_time"):
            return

        start_time = self.split_run_dropoff_time.time()
        duration_hours = self.split_run_duration.value()

        # Calculate end time = start_time + duration_hours
        end_time = start_time.addSecs(duration_hours * 3600)
        self.split_run_pickup_time.setTime(end_time)

    def _on_rate_type_split_run_selected(self) -> None:
        """When user selects 'Split Run' rate type, auto-populate split-run"
        "fields from charter run_start/run_end."""

        if not hasattr(self, "charter_run_start") or not hasattr(
            self, "charter_run_end"
        ):
            return

        if not hasattr(self, "split_run_dropoff_time") or not hasattr(
            self, "split_run_pickup_time"
        ):
            return

        # Get run_start and run_end from stored charter data
        run_start = self.charter_run_start
        run_end = self.charter_run_end

        if run_start:
            try:
                # Parse start time (could be string or time object)
                if isinstance(run_start, str):
                    qtime_start = QTime.fromString(run_start, "HH:mm")
                else:
                    qtime_start = QTime(run_start.hour, run_start.minute)
                self.split_run_dropoff_time.setTime(qtime_start)
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
        if run_end:
            try:
                # Parse end time
                if isinstance(run_end, str):
                    qtime_end = QTime.fromString(run_end, "HH:mm")
                else:
                    qtime_end = QTime(run_end.hour, run_end.minute)
                self.split_run_pickup_time.setTime(qtime_end)

                # Calculate duration in hours
                if run_start and run_end:
                    if isinstance(run_start, str):
                        qtime_start = QTime.fromString(run_start, "HH:mm")
                    else:
                        qtime_start = QTime(run_start.hour, run_start.minute)

                    start_secs = (
                        qtime_start.hour() * 3600 + qtime_start.minute() * 60
                    )
                    end_secs = (
                        qtime_end.hour() * 3600 + qtime_end.minute() * 60
                    )

                    duration_secs = end_secs - start_secs
                    if duration_secs > 0:
                        duration_hours = round(duration_secs / 3600)
                        if duration_hours > 0:
                            self.split_run_duration.setValue(
                                min(8, max(1, duration_hours))
                            )
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
        # Also auto-insert RUN FIRST and RUN LAST stops
        if run_start and run_end:
            try:
                start_str = (
                    run_start
                    if isinstance(run_start, str)
                    else QTime(run_start.hour, run_start.minute).toString(
                        "HH:mm"
                    )
                )
                end_str = (
                    run_end
                    if isinstance(run_end, str)
                    else QTime(run_end.hour, run_end.minute).toString("HH:mm")
                )

                # Clear existing stops and insert new ones
                self.routing_table.setRowCount(0)
                self._add_split_run_stops()
                QMessageBox.information(
                    self,
                    "Split Run Setup",
                    f"Auto-populated RUN FIRST at {start_str} and RUN LAST at"
                    f"{end_str}.",
                )
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    def _setup_split_run_signals(self) -> None:
        """Set up signal connections for split-run auto-population when rate"
        "type changes."""

        try:
            # Find the rate type or billing type combo in the form and connect
            # it
            # The billing_type combo should trigger split-run population when
            # "Split Run" is selected
            if hasattr(self, "billing_type"):
                # Connect to the billing_type combo's currentTextChanged signal
                self.billing_type.currentTextChanged.connect(
                    self._on_billing_type_changed
                )
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
    def _on_billing_type_changed(self, text) -> None:
        """Handle when billing type combo changes."""
        if text and "split" in text.lower():
            self._on_rate_type_split_run_selected()

        self.renumber_stops()

    def edit_routing_stop(self) -> None:
        """Edit selected routing stop"""
        row = self.routing_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "Warning", "Please select a stop to edit."
            )
            return

        # Get current data
        current_data = {
            "type": self.routing_table.item(row, 1).text(),
            "location": self.routing_table.item(row, 2).text(),
            "time": self.routing_table.item(row, 3).text(),
            "notes": self.routing_table.item(row, 4).text(),
        }

        dialog = RoutingStopDialog(parent=self, stop_data=current_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            stop_data = dialog.get_stop_data()

            self.routing_table.setItem(
                row, 1, QTableWidgetItem(stop_data["type"])
            )
            self.routing_table.setItem(
                row, 2, QTableWidgetItem(stop_data["location"])
            )
            self.routing_table.setItem(
                row, 3, QTableWidgetItem(stop_data["time"])
            )
            self.routing_table.setItem(
                row, 4, QTableWidgetItem(stop_data["notes"])
            )

    def delete_routing_stop(self) -> None:
        """Delete selected routing stop"""
        row = self.routing_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "Warning", "Please select a stop to delete."
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm",
            "Delete this routing stop?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.routing_table.removeRow(row)
            self.renumber_stops()

    def move_stop(self, direction) -> None:
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

    def renumber_stops(self) -> None:
        """Renumber all stops sequentially"""
        for row in range(self.routing_table.rowCount()):
            self.routing_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

    def calculate_routing_charges(self) -> None:
        """Manual recalc button handler."""
        self._calculate_routing_charges_core(notify=True)

    def _calculate_routing_charges_core(self, notify: bool = False) -> None:
        """Calculate charter/extra charges from time, billing type, and routing."""
        if getattr(self, "_syncing_calc", False):
            return
        self._syncing_calc = True
        try:
            billing_type = (self.billing_type.currentText() or "").strip()
            is_hourly = billing_type == "Hourly"
            is_package = billing_type == "Package"

            total_minutes = self._routing_duration_minutes()
            actual_hours = round(total_minutes / 60.0, 2)
            if hasattr(self, "calculated_hours"):
                self.calculated_hours.setValue(actual_hours)

            rate = float(self.hourly_rate.value() if hasattr(self, "hourly_rate") else 0.0)
            min_hours = float(self.min_hours.value() if hasattr(self, "min_hours") else 0.0)
            package_price = float(self.package_price.value() if hasattr(self, "package_price") else 0.0)
            package_hours = float(self.package_hours.value() if hasattr(self, "package_hours") else 0.0)
            extra_rate = float(
                self.vehicle_pay_extra_time.value()
                if hasattr(self, "vehicle_pay_extra_time")
                else rate
            )

            charter_fee = 0.0
            extra_time_fee = 0.0
            billable_hours = max(0.0, actual_hours)
            overtime_hours = 0.0

            if is_hourly:
                billable_hours = max(min_hours, actual_hours)
                charter_fee = billable_hours * rate
                overtime_hours = 0.0
                extra_time_fee = 0.0
            elif is_package:
                charter_fee = package_price
                overtime_hours = max(0.0, actual_hours - max(0.0, package_hours))
                extra_time_fee = overtime_hours * (extra_rate or rate)
                billable_hours = max(0.0, package_hours)
            else:
                billable_hours = max(0.0, actual_hours)
                charter_fee = billable_hours * rate

            self.set_charge_fee("Charter Fee", round(charter_fee, 2))
            self.set_charge_fee("Extra Time", round(extra_time_fee, 2))

            self._last_actual_hours = actual_hours
            self._last_billable_hours = billable_hours
            self._last_overtime_hours = overtime_hours
            self._last_extra_rate = float(extra_rate or rate)
            self._last_billing_type = billing_type

            self.recalculate_charge_totals()

            # Keep summary amount boxes aligned with invoice totals.
            if hasattr(self, "invoice_charter_charge"):
                self.invoice_charter_charge.setValue(round(charter_fee + extra_time_fee, 2))
            if hasattr(self, "total_amount") and hasattr(self, "invoice_total"):
                self.total_amount.setValue(float(self.invoice_total.value()))

            if notify:
                mode = "Hourly" if is_hourly else "Package" if is_package else "Custom"
                QMessageBox.information(
                    self,
                    "Charges Calculated",
                    f"Billing Type: {mode}\n"
                    f"Usage Hours: {actual_hours:.2f}\n"
                    f"Charter Fee: ${charter_fee:,.2f}\n"
                    f"Extra Time: ${extra_time_fee:,.2f}",
                )
        finally:
            self._syncing_calc = False

    def create_payments_tab(self) -> QWidget:
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
        hint = QLabel(
            "Manual ledger entry only — records payments already received"
            "(cash/check/bank)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 9px; color: #666; margin-bottom: 6px;")
        layout.addWidget(hint)

        # Payments table (compact)
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(6)
        self.payments_table.setHorizontalHeaderLabels(
            ["Date", "Amount", "Method", "Reference", "Status", "Reconciled"]
        )
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

    def load_client_info(self, client_id) -> None:
        """Load client info and populate client field for new charter"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT client_id, client_name
                    FROM clients
                    WHERE client_id = %s
                """,
                    (client_id,),
                )

                row = cur.fetchone()

                if row:
                    self.client.setText(row[1])  # Set client name display
                    # Store client_id for saving later
                    self.selected_client_id = row[0]
        except Exception as e:
            logger.error(f"Error loading client info: {e}")

    def load_charter_data(self) -> None:
        """Load charter data from database"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'charters'
                          AND column_name = 'dropoff_time'
                    )
                """)
                has_dropoff_time = bool(cur.fetchone()[0])
                dropoff_time_select = (
                    "c.dropoff_time"
                    if has_dropoff_time
                    else "c.workshift_end::time AS dropoff_time"
                )

                # Load main charter data (including split-run times)
                cur.execute(
                    f"""
                    SELECT c.reserve_number, c.charter_date,
                    COALESCE(cl.company_name, cl.client_name),
                           c.pickup_address, c.dropoff_address, c.pickup_time,
                           {dropoff_time_select},
                           c.passenger_count, e.full_name, v.vehicle_number,
                           c.status, c.total_amount_due, c.notes,
                           c.vehicle, c.client_id, c.employee_id,
                           c.workshift_start,
                           c.workshift_end
                    FROM charters c
                    LEFT JOIN clients cl ON c.client_id = cl.client_id
                    LEFT JOIN employees e ON c.employee_id = e.employee_id
                    LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
                    WHERE c.reserve_number = %s
                """,
                    (self.reserve_number,),
                )

                charter = cur.fetchone()
            # DatabaseContext.__exit__ closed cur. Reopen for all subsequent
            # data loading.
            cur = self.db.get_cursor()
            if charter:
                (
                    res_num,
                    c_date,
                    client,
                    pickup,
                    dest,
                    p_time,
                    d_time,
                    pax,
                    driver,
                    vehicle_num,
                    status,
                    total,
                    notes,
                    vehicle,
                    client_id,
                    employee_id,
                    split_run_start,
                    split_run_end,
                ) = charter

                # Store IDs and split-run times for later use (especially
                # split-run)
                self.selected_client_id = client_id
                self.selected_employee_id = employee_id
                # Store for split-run auto-population (workshift_start)
                self.charter_run_start = split_run_start
                # Store for split-run auto-population (workshift_end)
                self.charter_run_end = split_run_end

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
                # Sanitize destination: LMS stored time-only as OLE epoch
                # '1899-12-30 HH:MM:SS'
                # in the dropoff_address column — clear it; the time is
                # already in dropoff_time.
                if (
                    dest
                    and isinstance(dest, str)
                    and re.match(r"^1899-12-30\s", dest)
                ):
                    self.destination.setText("")
                else:
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
                    except Exception:
                        self.pickup_time.setTime(QTime(0, 0))
                else:
                    self.pickup_time.setTime(QTime(0, 0))

                # Handle dropoff time (convert to QTime)
                if d_time:
                    try:
                        # If it's a string, parse it (HH:MM format)
                        if isinstance(d_time, str):
                            time_obj = QTime.fromString(d_time, "HH:mm")
                        else:
                            # If it's a time object, convert
                            time_obj = QTime(d_time.hour, d_time.minute)
                        self.dropoff_time.setTime(time_obj)
                    except Exception:
                        self.dropoff_time.setTime(QTime(0, 0))
                else:
                    self.dropoff_time.setTime(QTime(0, 0))

                self.passenger_count.setValue(int(pax or 1))

                # Set driver - prefer employee_id, then fallback to name match
                driver_name = str(driver or "")
                driver_idx = self.driver.findData(employee_id)
                if driver_idx < 0:
                    driver_idx = self.driver.findText(
                        driver_name, Qt.MatchFlag.MatchContains
                    )
                if driver_idx >= 0:
                    self.driver.setCurrentIndex(driver_idx)

                # Set vehicle requested by type text (use vehicle column since
                # vehicle_type_requested was removed)
                if vehicle:
                    veh_text = str(vehicle or "")
                    idx = self.vehicle_requested.findText(veh_text)
                    if idx >= 0:
                        self.vehicle_requested.setCurrentIndex(idx)
                    self.apply_vehicle_pricing_defaults()

                # Set vehicle - find by text match (handle vehicle_number and
                # vehicle_number (type) format)
                vehicle_name = str(vehicle_num or vehicle or "")
                vehicle_idx = self.vehicle.findText(vehicle_name)
                if vehicle_idx >= 0:
                    self.vehicle.setCurrentIndex(vehicle_idx)
                else:
                    # Try to find by partial match (in case it's stored as
                    # "LIM-001 (Coach)" format)
                    for i in range(self.vehicle.count()):
                        if (
                            vehicle_name.upper()
                            in self.vehicle.itemText(i).upper()
                        ):
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
                self.invoice_date_display.setText(
                    c_date.strftime("%m/%d/%Y") if c_date else ""
                )
                self.invoice_client_display.setText(str(client or ""))
                self.invoice_driver_display.setText(str(driver or ""))
                self.invoice_vehicle_display.setText(str(vehicle or ""))
                self.invoice_reserve_display.setText(
                    str(res_num or self.reserve_number or "")
                )

                self.charter_data = charter

            # Load related beverage/product orders and calculate beverage total
            beverage_total = 0.0
            try:
                cur.execute(
                    """
                    SELECT oi.item_name, oi.quantity, oi.unit_price, oi.total,
                    o.status,
                           COALESCE(b.category, '')
                    FROM beverage_orders o
                    JOIN beverage_order_items oi ON o.order_id = oi.order_id
                          LEFT JOIN beverage_products b ON oi.item_id = b.item_id
                    WHERE o.reserve_number = %s
                    ORDER BY o.order_date DESC
                """,
                    (self.reserve_number,),
                )

                orders = cur.fetchall()
                self.orders_table.setRowCount(len(orders) if orders else 0)
                if orders:
                    beverage_qty_total = 0
                    for i, (
                        item,
                        qty,
                        price,
                        total,
                        status,
                        category,
                    ) in enumerate(orders):
                        self.orders_table.setItem(
                            i, 0, QTableWidgetItem(str(item))
                        )
                        self.orders_table.setItem(
                            i, 1, QTableWidgetItem(str(qty))
                        )
                        self.orders_table.setItem(
                            i, 2, QTableWidgetItem(f"${float(price):,.2f}")
                        )
                        self.orders_table.setItem(
                            i, 3, QTableWidgetItem(f"${float(total):,.2f}")
                        )
                        self.orders_table.setItem(
                            i, 4, QTableWidgetItem(str(status))
                        )
                        try:
                            beverage_total += float(total or 0)
                        except Exception as _e:
                            logger.debug('Suppressed: %s', _e)
                        try:
                            beverage_qty_total += int(qty or 0)
                        except Exception as _e:
                            logger.debug('Suppressed: %s', _e)
                    # Invoice beverage items (GST included per line)
                    self.invoice_beverage_table.setRowCount(len(orders))
                    for i, (
                        item,
                        qty,
                        price,
                        total,
                        status,
                        category,
                    ) in enumerate(orders):
                        self.invoice_beverage_table.setItem(
                            i, 0, QTableWidgetItem(str(item))
                        )
                        self.invoice_beverage_table.setItem(
                            i, 1, QTableWidgetItem(str(qty))
                        )
                        self.invoice_beverage_table.setItem(
                            i, 2, QTableWidgetItem(f"${float(price):,.2f}")
                        )
                        self.invoice_beverage_table.setItem(
                            i, 3, QTableWidgetItem(f"${float(total):,.2f}")
                        )

                    # Populate client confirmation list (no prices)
                    self.beverage_confirm_table.setRowCount(len(orders))
                    for i, (
                        item,
                        qty,
                        price,
                        total,
                        status,
                        category,
                    ) in enumerate(orders):
                        self.beverage_confirm_table.setItem(
                            i, 0, QTableWidgetItem(str(item))
                        )
                        self.beverage_confirm_table.setItem(
                            i, 1, QTableWidgetItem(str(category))
                        )
                        self.beverage_confirm_table.setItem(
                            i, 2, QTableWidgetItem(str(qty))
                        )

                    # Populate Beverage Card Details tab
                    self.beverage_service_status.setText("Yes")
                    self.beverage_items_count.setText(str(beverage_qty_total))
                    self.beverage_card_table.setRowCount(len(orders))
                    for i, (
                        item,
                        qty,
                        price,
                        total,
                        status,
                        category,
                    ) in enumerate(orders):
                        self.beverage_card_table.setItem(
                            i, 0, QTableWidgetItem(str(item))
                        )
                        self.beverage_card_table.setItem(
                            i, 1, QTableWidgetItem(str(category or ""))
                        )
                        self.beverage_card_table.setItem(
                            i, 2, QTableWidgetItem(str(qty))
                        )
                        self.beverage_card_table.setItem(
                            i, 3, QTableWidgetItem(f"${float(price):,.2f}")
                        )
                        self.beverage_card_table.setItem(
                            i, 4, QTableWidgetItem(f"${float(total):,.2f}")
                        )
                        self.beverage_card_table.setItem(
                            i, 5, QTableWidgetItem(str(status))
                        )

                    subtotal = beverage_total / 1.05 if beverage_total else 0.0
                    gst_amount = beverage_total - subtotal
                    self.beverage_card_subtotal.setText(
                        f"${subtotal:,.2f}"
                    )
                    self.beverage_card_gst.setText(f"${gst_amount:,.2f}")
                    self.beverage_card_total.setText(
                        f"${beverage_total:,.2f}"
                    )
                else:
                    self.beverage_confirm_table.setRowCount(0)
                    self.invoice_beverage_table.setRowCount(0)
                    self.beverage_service_status.setText("No")
                    self.beverage_items_count.setText("0")
                    self.beverage_card_subtotal.setText("$0.00")
                    self.beverage_card_gst.setText("$0.00")
                    self.beverage_card_total.setText("$0.00")
                    self.beverage_card_table.setRowCount(0)
            except Exception as e:
                logger.error(f"Failed to load beverage orders: {e}")
                self.beverage_confirm_table.setRowCount(0)
                self.orders_table.setRowCount(0)
                beverage_total = 0.0
                self.invoice_beverage_table.setRowCount(0)
                self.beverage_service_status.setText("No")
                self.beverage_items_count.setText("0")
                self.beverage_card_subtotal.setText("$0.00")
                self.beverage_card_gst.setText("$0.00")
                self.beverage_card_total.setText("$0.00")
                self.beverage_card_table.setRowCount(0)

            # Load saved charges from charter_charges table (LMS + current
            # system)
            try:
                with DatabaseContext(self.db, auto_commit=False) as cur_cc:
                    cur_cc.execute(
                        """
                        SELECT description, amount, rate, charge_type
                        FROM charter_charges
                        WHERE reserve_number = %s
                        ORDER BY COALESCE(sequence, 999), charge_id
                    """,
                        (self.reserve_number,),
                    )
                    saved_charges = cur_cc.fetchall()
                if saved_charges and hasattr(self, "charge_table"):
                    self.charge_table.setRowCount(0)
                    has_gst_row = False
                    gratuity_pct = None
                    for row_desc, row_amount, row_rate, row_charge_type in saved_charges:
                        # Strip embedded [calc:...] metadata from description
                        import re as _re
                        clean_desc = _re.sub(r'\s*\[calc:[^\]]*\]', '', row_desc or '').strip()
                        desc_lower = clean_desc.lower()
                        # Skip beverage — set separately from beverage_orders
                        if "beverage" in desc_lower:
                            continue
                        # Map LMS 'Service Fee' to UI 'Charter Fee'
                        display_name = clean_desc
                        if clean_desc == "Service Fee":
                            display_name = "Charter Fee"
                        elif clean_desc in ("G.S.T.", "GST", "Tax"):
                            display_name = "GST"
                            has_gst_row = True
                        db_charge_type = (row_charge_type or "").lower()
                        is_percent = (
                            "gratuity" in desc_lower
                            or db_charge_type == "gratuity"
                            or display_name == "GST"
                        )
                        ui_type = "%" if is_percent else "Hr"
                        # For percent rows, use rate (the percent value) not amount (dollar value)
                        if is_percent and db_charge_type == "gratuity":
                            spinbox_val = float(row_rate or 0)
                            gratuity_pct = spinbox_val
                        else:
                            spinbox_val = float(row_amount or 0)
                        self.add_charge_row(
                            display_name, ui_type, spinbox_val
                        )
                    if not has_gst_row:
                        self.ensure_gst_row()
                    # Sync the gratuity percent spinbox if loaded from DB
                    if gratuity_pct is not None and hasattr(self, "gratuity_percent_input_rt"):
                        self.gratuity_percent_input_rt.blockSignals(True)
                        self.gratuity_percent_input_rt.setValue(gratuity_pct)
                        self.gratuity_percent_input_rt.blockSignals(False)
            except Exception as _ex:
                logger.warning(
                    f"Could not load charter_charges for"
                    f"{self.reserve_number}: {_ex}"
                )

            self.set_charge_fee("Beverage Order", beverage_total)
            self.recalculate_charge_totals()

            # Initialize total_paid before calculating from payments table
            total_paid = 0.0

            try:
                cur.execute(
                    """
                    SELECT payment_date, amount, payment_method,
                    reference_number, status, is_deposited
                    FROM payments
                    WHERE reserve_number = %s
                       OR charter_id = (
                           SELECT charter_id
                           FROM charters
                           WHERE reserve_number = %s
                       )
                    ORDER BY payment_date DESC
                """,
                    (self.reserve_number, self.reserve_number),
                )

                payments = cur.fetchall()
                self.payments_table.setRowCount(
                    len(payments) if payments else 0
                )
                if payments:
                    for i, (
                        p_date,
                        amt,
                        method,
                        ref,
                        p_status,
                        recon,
                    ) in enumerate(payments):
                        self.payments_table.setItem(
                            i, 0, QTableWidgetItem(str(p_date))
                        )
                        self.payments_table.setItem(
                            i, 1, QTableWidgetItem(f"${float(amt):,.2f}")
                        )
                        self.payments_table.setItem(
                            i, 2, QTableWidgetItem(str(method))
                        )
                        self.payments_table.setItem(
                            i, 3, QTableWidgetItem(str(ref))
                        )

                        # Show payment status: if deposited, show "cleared", if
                        # matched to amount, show "matched", else show status
                        if recon:
                            display_status = "✓ cleared"
                        elif float(amt or 0) == float(
                            self.total_amount.value()
                        ):
                            display_status = "✓ matched"
                        else:
                            display_status = (
                                str(p_status) if p_status else "pending"
                            )

                        self.payments_table.setItem(
                            i, 4, QTableWidgetItem(display_status)
                        )
                        self.payments_table.setItem(
                            i, 5, QTableWidgetItem("✓" if recon else "")
                        )
                        total_paid += float(amt or 0)
            except Exception as e:
                logger.error(f"Failed to load payments: {e}")
                self.payments_table.setRowCount(0)
                total_paid = 0.0

            # ===== CALCULATE INVOICE AMOUNTS (New Logic) =====
            # Formula: Amount Due = (Charter Charge + Extra Charges + Beverage
            # + GST) - Amount Paid
            # If Amount Paid >= Total Charges, then Amount Due = 0 and Status =
            # CLOSED

            # Get charter charge and other amounts from existing columns
            # Use rate as charter charge, and calculate from total_amount_due
            # minus beverages/gst
            try:
                cur.execute(
                    """
                    SELECT
                        COALESCE(rate, 0) as charter_charge,
                        COALESCE(total_amount_due, 0) as total_amount_due,
                            COALESCE(amount_paid, 0) as paid_from_column
                    FROM charters
                    WHERE reserve_number = %s
                """,
                    (self.reserve_number,),
                )

                charge_row = cur.fetchone()
                charter_charge = float(charge_row[0]) if charge_row else 0.0
                total_amount_from_db = (
                    float(charge_row[1]) if charge_row else 0.0
                )
                paid_from_column = float(charge_row[2]) if charge_row else 0.0
            except Exception as e:
                logger.error(f"Failed to load charter charge amounts: {e}")
                charter_charge = 0.0
                total_amount_from_db = 0.0
                paid_from_column = 0.0

            # If paid_amount is 0 in DB, use the total_paid we calculated from
            # payments table
            if paid_from_column == 0 and total_paid > 0:
                actual_paid = total_paid
            else:
                actual_paid = max(total_paid, paid_from_column)

            # For now, estimate extra_charges as 0 (can be enhanced later if
            # column is added)
            extra_charges = 0.0

            # Calculate GST on subtotal (5% on non-GST-exempt items)
            subtotal_for_gst = charter_charge + extra_charges + beverage_total
            gst_amount = subtotal_for_gst * 0.05

            # Total invoice = charter + extra + beverage + gst
            total_invoice = (
                charter_charge + extra_charges + beverage_total + gst_amount
            )

            # If total_amount_due is set in DB, use that as the authoritative
            # amount
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

            # Also update the old Amount Paid/Balance Due fields for
            # consistency
            self.amount_paid.setValue(actual_paid)
            self.balance_due.setValue(amount_due)

            # Load extra charter fields not in main SELECT (charter_type,
            # billing/package details, rates, account number).
            try:
                cur.execute(
                    """
                    SELECT charter_type, charter_fee_type, package_rate,
                           quoted_hours, extra_time_rate, standby_rate,
                           account_number, hourly_rate, minimum_hours
                    FROM charters
                    WHERE reserve_number = %s
                    """,
                    (self.reserve_number,),
                )
                extra_row = cur.fetchone()
                if extra_row:
                    (
                        db_charter_type, db_fee_type, db_pkg_rate,
                        db_pkg_hrs, db_extra_rate, db_standby_rate,
                        db_acct_num, db_hourly_rate, db_min_hours,
                    ) = extra_row
                    # charter_type combo
                    if db_charter_type:
                        idx = self.charter_type.findText(str(db_charter_type))
                        if idx >= 0:
                            self.charter_type.setCurrentIndex(idx)
                    # billing_type combo (hourly / package)
                    fee_map = {"hourly": "Hourly", "package": "Package"}
                    bt = fee_map.get((db_fee_type or "").lower(), "Hourly")
                    self.billing_type.blockSignals(True)
                    self.billing_type.setCurrentText(bt)
                    self.billing_type.blockSignals(False)
                    # package rate and hours
                    self.package_price.setValue(float(db_pkg_rate or 0))
                    self.package_hours.setValue(float(db_pkg_hrs or 0))
                    # extra-time and standby rates
                    self.vehicle_pay_extra_time.setValue(float(db_extra_rate or 0))
                    self.vehicle_pay_standby.setValue(float(db_standby_rate or 0))
                    # hourly rate and min hours (override vehicle defaults)
                    if db_hourly_rate:
                        self.hourly_rate.setValue(float(db_hourly_rate))
                    if db_min_hours:
                        self.min_hours.setValue(int(db_min_hours))
                    # account number
                    self.account.setText(str(db_acct_num or ""))
                    # apply visibility based on billing type
                    self.toggle_billing_fields()
            except Exception as _ex:
                logger.warning("Failed to load extra charter fields: %s", _ex)

            # Load routing data from charter_routes table
            self.load_routing_data()
            self._sync_routing_boundary_times()
            self._calculate_routing_charges_core(notify=False)

        except psycopg2.errors.InsufficientPrivilege as e:
            logger.error(f"Database permission error: {e}")
            QMessageBox.critical(
                self, "Error", f"Database permission error: {e}"
            )
            self.close()
        except Exception as e:
            logger.error(f"Failed to load charter: {e}")
            # get_cursor() call
            err_msg = str(e)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load charter: {err_msg}\n\nIf this persists, try"
                f"reloading the dispatch board.",
            )

    def save_charter(self) -> None:
        """Save changes to charter"""
        try:
            self._calculate_routing_charges_core(notify=False)
            # Get the IDs from the dropdowns
            vehicle_id = self.vehicle.currentData()
            vehicle_requested_text = (
                self.vehicle_requested.currentText().strip()
            )
            employee_id = self._resolve_driver_employee_id()

            # Get selected_client_id if available (set when client is loaded)
            client_id = getattr(self, "selected_client_id", None)
            dropoff_time_value = (
                self.dropoff_time.time().toString("HH:mm")
                if self.dropoff_time.time().isValid()
                else None
            )

            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'charters'
                          AND column_name = 'dropoff_time'
                    )
                """)
                has_dropoff_time = bool(cur.fetchone()[0])
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'charters'
                          AND column_name = 'vehicle_type_requested'
                    )
                """)
                has_vehicle_type_requested = bool(cur.fetchone()[0])
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                        AND table_name = 'charters'
                    """
                )
                charter_columns = {r[0] for r in cur.fetchall()}

                set_clauses = [
                    "client_id = %s",
                    "charter_date = %s",
                    "pickup_address = %s",
                    "dropoff_address = %s",
                    "pickup_time = %s",
                    "passenger_count = %s",
                    "status = %s",
                    "employee_id = %s",
                    "vehicle_id = %s",
                    "notes = %s",
                ]
                params = [
                    client_id,
                    self.charter_date.date().toPyDate(),
                    # Use Python date object for PostgreSQL
                    self.pickup.text(),
                    self.destination.text(),
                    self.pickup_time.time().toString("HH:mm"),
                    self.passenger_count.value(),
                    self.status.currentText(),
                    employee_id,
                    vehicle_id,
                    self.notes.toPlainText(),
                ]

                if has_vehicle_type_requested:
                    set_clauses.append("vehicle_type_requested = %s")
                    params.append(vehicle_requested_text or None)

                if has_dropoff_time:
                    set_clauses.append("dropoff_time = %s")
                    dropoff_db_value = dropoff_time_value
                else:
                    set_clauses.append("workshift_end = %s")
                    dropoff_db_value = None
                    if dropoff_time_value:
                        charter_date_value = (
                            self.charter_date.date().toPyDate()
                        )
                        dropoff_time_obj = datetime.strptime(
                            dropoff_time_value, "%H:%M"
                        ).time()
                        # Advance the workshift_end date by one day when the
                        # dropoff time is before the pickup time (midnight rollover).
                        pickup_str = self.pickup_time.time().toString("HH:mm")
                        pickup_obj = datetime.strptime(pickup_str, "%H:%M").time()
                        if dropoff_time_obj < pickup_obj:
                            from datetime import timedelta as _td
                            charter_date_value = charter_date_value + _td(days=1)
                        dropoff_db_value = datetime.combine(
                            charter_date_value, dropoff_time_obj
                        )
                params.append(dropoff_db_value)

                # Persist billing/invoice values when columns are available.
                if "hourly_rate" in charter_columns:
                    set_clauses.append("hourly_rate = %s")
                    params.append(float(self.hourly_rate.value()))
                if "minimum_hours" in charter_columns:
                    set_clauses.append("minimum_hours = %s")
                    params.append(float(self.min_hours.value()))
                if "rate" in charter_columns:
                    charter_charge_value = float(self.invoice_charter_charge.value())
                    set_clauses.append("rate = %s")
                    params.append(charter_charge_value)
                if "total_amount_due" in charter_columns:
                    set_clauses.append("total_amount_due = %s")
                    params.append(float(self.invoice_total.value()))
                if "is_out_of_town" in charter_columns and hasattr(self, "out_of_town_cb"):
                    set_clauses.append("is_out_of_town = %s")
                    params.append(bool(self.out_of_town_cb.isChecked()))
                if "charter_type" in charter_columns:
                    set_clauses.append("charter_type = %s")
                    params.append(self.charter_type.currentText().strip() or None)
                if "charter_fee_type" in charter_columns:
                    _billing = self.billing_type.currentText().strip().lower()
                    set_clauses.append("charter_fee_type = %s")
                    params.append(_billing or None)
                if "package_rate" in charter_columns:
                    set_clauses.append("package_rate = %s")
                    params.append(float(self.package_price.value()))
                if "quoted_hours" in charter_columns:
                    set_clauses.append("quoted_hours = %s")
                    params.append(float(self.package_hours.value()))
                if "extra_time_rate" in charter_columns:
                    set_clauses.append("extra_time_rate = %s")
                    params.append(float(self.vehicle_pay_extra_time.value()))
                if "standby_rate" in charter_columns:
                    set_clauses.append("standby_rate = %s")
                    params.append(float(self.vehicle_pay_standby.value()))
                if "account_number" in charter_columns:
                    set_clauses.append("account_number = %s")
                    params.append(self.account.text().strip() or None)

                query = (
                    "UPDATE charters SET\n                            "
                    + ",\n                            ".join(set_clauses)
                    + "\n                        WHERE reserve_number = %s"
                )
                params.append(self.reserve_number)
                cur.execute(query, tuple(params))

                # Persist routing rows so time/address edits are not lost.
                cur.execute(
                    "SELECT charter_id FROM charters WHERE reserve_number = %s",
                    (self.reserve_number,),
                )
                row = cur.fetchone()
                charter_id = row[0] if row else None
                if charter_id and hasattr(self, "routing_table"):
                    cur.execute(
                        "DELETE FROM charter_routes WHERE charter_id = %s",
                        (charter_id,),
                    )

                    def _event_code_from_label(label: str) -> str:
                        val = (label or "").strip().lower()
                        if "leave red deer" in val:
                            return "depart_red_deer"
                        if "return to red deer" in val:
                            return "return_red_deer"
                        if "split run" in val and "drop off" in val:
                            return "split_dropoff"
                        if "split" in val and "pick up" in val:
                            return "split_pickup"
                        if "pick" in val:
                            return "pickup"
                        if "drop" in val:
                            return "dropoff"
                        return "stop"

                    for idx in range(self.routing_table.rowCount()):
                        label_item = self.routing_table.item(idx, 1)
                        addr_item = self.routing_table.item(idx, 2)
                        time_item = self.routing_table.item(idx, 3)
                        notes_item = self.routing_table.item(idx, 4)

                        type_label = label_item.text().strip() if label_item else "Stop at"
                        address = addr_item.text().strip() if addr_item else ""
                        stop_time = time_item.text().strip() if time_item else ""
                        route_notes = notes_item.text().strip() if notes_item else ""

                        cur.execute(
                            """
                            INSERT INTO charter_routes
                            (charter_id, route_sequence, event_type_code, address, stop_time, route_notes)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                charter_id,
                                idx + 1,
                                _event_code_from_label(type_label),
                                address or None,
                                stop_time or None,
                                route_notes or None,
                            ),
                        )
                QMessageBox.information(
                    self, "Success", "Charter saved successfully"
                )
                self.saved.emit(
                    {
                        "reserve_number": self.reserve_number,
                        "status": self.status.currentText(),
                    }
                )
        except Exception as e:
            logger.error(f"Failed to save charter: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save charter: {e}")

    def load_routing_data(self) -> None:
        """Load routing stops from charter_routes table and populate"
        "routing_table display"""

        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT route_sequence, event_type_code, address, stop_time,
                    route_notes
                    FROM charter_routes
                    WHERE charter_id = (SELECT charter_id FROM charters WHERE
                    reserve_number = %s)
                    ORDER BY route_sequence
                    """,
                    (self.reserve_number,),
                )
                routes = cur.fetchall()

            if not routes:
                return

            self.routing_table.setRowCount(0)

            is_out_of_town = False
            if routes:
                first_code = (routes[0][1] or "").lower()
                is_out_of_town = first_code in (
                    "depart_red_deer",
                    "leave_red_deer",
                    "leave_red_deer_for",
                )
            if hasattr(self, "out_of_town_cb"):
                self.out_of_town_cb.blockSignals(True)
                self.out_of_town_cb.setChecked(is_out_of_town)
                self.out_of_town_cb.blockSignals(False)
            self._update_trip_boundary_labels(is_out_of_town)

            type_labels = {
                "pickup": "Pickup at",
                "dropo": "Drop off at",
                "stop": "Stop at",
            }

            for seq, event_type, location, time_val, notes in routes:
                row = self.routing_table.rowCount()
                self.routing_table.insertRow(row)

                self.routing_table.setItem(row, 0, QTableWidgetItem(str(seq)))

                type_label = type_labels.get(event_type, "Stop at")
                if seq == 1:
                    type_label = "Pick up at"
                elif seq == len(routes):
                    type_label = "Drop off at"
                self.routing_table.setItem(
                    row, 1, QTableWidgetItem(type_label)
                )

                self.routing_table.setItem(
                    row, 2, QTableWidgetItem(location or "")
                )

                time_str = ""
                if time_val:
                    try:
                        time_str = (
                            time_val.strftime("%H:%M")
                            if hasattr(time_val, "strftime")
                            else str(time_val)
                        )
                    except Exception:
                        time_str = str(time_val)
                self.routing_table.setItem(row, 3, QTableWidgetItem(time_str))

                self.routing_table.setItem(
                    row, 4, QTableWidgetItem(notes or "")
                )

        except Exception as e:
            logger.warning(
                f"Failed to load routing data for {self.reserve_number}: {e}"
            )

    def select_client_dialog(self) -> None:
        """Open improved client selection dialog"""
        from improved_client_selection_dialog import ClientSelectionDialog

        dialog = ClientSelectionDialog(self.db, self)
        if dialog.exec():
            self.selected_client_id = dialog.get_selected_client_id()
            client_name = dialog.get_selected_client_name()
            if self.selected_client_id and client_name:
                self.client.setText(client_name)

    def add_new_charter(self) -> None:
        """Create a new charter - search for client first or create new"
        "client"""

        from client_search_dialog import ClientSearchDialog

        search_dialog = ClientSearchDialog(self.db, self)
        result = search_dialog.exec()

        if result:
            # User selected or created a client
            selected_client_id = search_dialog.get_selected_client_id()
            if selected_client_id:
                # Open charter form with pre-selected client
                new_dialog = CharterDetailDialog(
                    self.db,
                    reserve_number=None,
                    parent=self.parent(),
                    client_id=selected_client_id,
                )
                new_dialog.saved.connect(self.on_charter_saved)
                new_dialog.exec()

    def duplicate_charter(self) -> None:
        """Duplicate current charter with modified reserve number"""
        if not self.reserve_number:
            QMessageBox.warning(
                self, "Warning", "No charter loaded to duplicate."
            )
            return

        try:
            dialog = QDialog(self)
            dialog.setWindowTitle("Duplicate Charter")
            dialog.setGeometry(100, 100, 400, 150)

            dlg_layout = QVBoxLayout()
            dlg_layout.addWidget(
                QLabel(
                    "This will create a new charter with the same"
                    "details.\nConfirm to proceed:"
                )
            )

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
                # Insert duplicate record (system will assign new
                # reserve_number)
                vehicle_requested_text = (
                    self.vehicle_requested.currentText().strip()
                )

                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        """
                        INSERT INTO charters
                        (client_id, charter_date, pickup_address,
                        dropoff_address, pickup_time, passenger_count, status,
                        vehicle_id, vehicle, notes, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                        (
                            None,
                            self.charter_date.date().toString("MM/dd/yyyy"),
                            self.pickup.text(),
                            self.destination.text(),
                            self.pickup_time.text(),
                            self.passenger_count.value(),
                            self.status.currentText(),
                            self.vehicle.currentData(),
                            vehicle_requested_text or None,
                            self.notes.toPlainText(),
                        ),
                    )
                    QMessageBox.information(
                        self, "Success", "Charter duplicated successfully."
                    )
                    self.load_charter_data()
        except Exception as e:
            logger.error(f"Failed to duplicate charter: {e}")
            QMessageBox.critical(self, "Error", f"Failed to duplicate: {e}")

    def delete_charter(self) -> None:
        """Delete current charter after confirmation"""
        if not self.reserve_number:
            QMessageBox.warning(
                self, "Warning", "No charter loaded to delete."
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete charter '{self.reserve_number}'?\nThis action cannot be"
            f"undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        "DELETE FROM charters WHERE reserve_number = %s",
                        (self.reserve_number,),
                    )
                    QMessageBox.information(
                        self, "Success", "Charter deleted successfully."
                    )
                    self.saved.emit(
                        {
                            "action": "delete",
                            "reserve_number": self.reserve_number,
                        }
                    )
                    self.close()
            except Exception as e:
                logger.error(f"Failed to delete charter: {e}")
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def on_charter_saved(self, data) -> None:
        """Handle child dialog save - refresh current view"""
        if self.reserve_number:
            self.load_charter_data()

    def lock_charter(self) -> None:
        """Lock charter from further edits"""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE charters SET locked = true WHERE reserve_number ="
                    "%s",
                    (self.reserve_number,),
                )
                self.is_locked = True
                self.lock_btn.setEnabled(False)
                self.unlock_btn.setEnabled(True)
                # Disable edit fields
                for widget in [
                    self.pickup,
                    self.destination,
                    self.pickup_time,
                    self.passenger_count,
                    self.notes,
                    self.status,
                ]:
                    (
                        widget.setReadOnly(True)
                        if hasattr(widget, "setReadOnly")
                        else widget.setEnabled(False)
                    )
                QMessageBox.information(self, "Success", "Charter locked")
        except Exception as e:
            logger.error(f"Failed to lock charter: {e}")
            QMessageBox.critical(self, "Error", f"Failed to lock charter: {e}")

    def unlock_charter(self) -> None:
        """Unlock charter for edits"""
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute(
                    "UPDATE charters SET locked = false WHERE reserve_number"
                    "= %s",
                    (self.reserve_number,),
                )
                self.is_locked = False
                self.lock_btn.setEnabled(True)
                self.unlock_btn.setEnabled(False)
                # Enable edit fields
                for widget in [
                    self.pickup,
                    self.destination,
                    self.pickup_time,
                    self.passenger_count,
                    self.notes,
                    self.status,
                ]:
                    (
                        widget.setReadOnly(False)
                        if hasattr(widget, "setReadOnly")
                        else widget.setEnabled(True)
                    )
                QMessageBox.information(self, "Success", "Charter unlocked")
        except Exception as e:
            logger.error(f"Failed to unlock charter: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to unlock charter: {e}"
            )

    def cancel_charter(self) -> None:
        """Cancel charter"""
        reply = QMessageBox.question(
            self,
            "Confirm",
            "Cancel this charter?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with DatabaseContext(self.db, auto_commit=True) as cur:
                    cur.execute(
                        "UPDATE charters SET status = 'cancelled', cancelled"
                        "= true WHERE reserve_number = %s",
                        (self.reserve_number,),
                    )
                    self.status.setCurrentText("Cancelled")
                    QMessageBox.information(
                        self, "Success", "Charter cancelled"
                    )
            except Exception as e:
                logger.error(f"Failed to cancel charter: {e}")
                QMessageBox.critical(
                    self, "Error", f"Failed to cancel charter: {e}"
                )

    def add_order(self) -> None:
        """Add new beverage/product order - Shopping Cart"""
        if not self.reserve_number:
            QMessageBox.warning(
                self, "Warning", "Save charter first before adding orders."
            )
            return

        # Open shopping cart dialog
        dialog = BeverageShoppingCartDialog(
            self.db, self.reserve_number, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(self, "Success", "Order added to charter.")
            self.load_charter_data()  # Refresh orders display

    def edit_order(self) -> None:
        """Edit selected order"""
        row = self.orders_table.currentRow()
        if row >= 0:
            # TODO: Open order edit dialog
            pass

    def delete_order(self) -> None:
        """Delete selected order"""
        row = self.orders_table.currentRow()
        if row >= 0:
            # TODO: Delete from database
            pass

    def add_payment(self) -> None:
        """Add new payment"""
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle("Record Payment (Manual)")
            vbox = QVBoxLayout(dlg)
            info = QLabel(
                "This records a payment you already received"
                "(cash/check/bank/etc.). It does not charge customers or"
                "connect to any online service."
            )
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
            tip_methods = QLabel(
                "Tip: eTransfer → bank_transfer; Square card → credit_card;"
                "Cash → cash"
            )
            tip_methods.setStyleSheet("font-size: 10px; color: #666;")

            reference_edit = QLineEdit()
            status_combo = QComboBox()
            # Align with DB constraint: pending, paid, partial, failed,
            # refunded, cancelled
            status_combo.addItems(
                [
                    "pending",
                    "paid",
                    "partial",
                    "failed",
                    "refunded",
                    "cancelled",
                ]
            )
            try:
                status_combo.setCurrentText("paid")
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
            reconciled_check = QCheckBox("Deposited / Reconciled")

            form.addRow("Date", date_edit)
            form.addRow("Amount", amount_spin)
            form.addRow("Method", method_combo)
            form.addRow("", tip_methods)
            form.addRow("Reference", reference_edit)
            form.addRow("Status", status_combo)
            form.addRow("", reconciled_check)

            def _update_reference_placeholder(text: str) -> None:
                if text == "bank_transfer":
                    reference_edit.setPlaceholderText(
                        "eTransfer confirmation number"
                    )
                elif text == "credit_card":
                    reference_edit.setPlaceholderText("Square transaction #")
                else:
                    reference_edit.setPlaceholderText(
                        "Reference or memo (optional)"
                    )

            _update_reference_placeholder(method_combo.currentText())
            method_combo.currentTextChanged.connect(
                _update_reference_placeholder
            )

            vbox.addLayout(form)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel
            )
            vbox.addWidget(buttons)
            buttons.accepted.connect(dlg.accept)
            buttons.rejected.connect(dlg.reject)

            # Set focus to amount field (not date field)
            amount_spin.setFocus()

            # Add Enter key handler for reference field to submit dialog
            def handle_reference_enter() -> None:
                if reference_edit.hasFocus():
                    dlg.accept()

            reference_edit.returnPressed.connect(handle_reference_enter)

            if dlg.exec() == QDialog.DialogCode.Accepted:
                payment_date = datetime.strptime(
                    date_edit.date().toString("yyyy-MM-dd"), "%Y-%m-%d"
                ).date()
                amount = float(amount_spin.value())
                method = method_combo.currentText()
                reference = reference_edit.text().strip()
                status = status_combo.currentText()
                reconciled = True if reconciled_check.isChecked() else False

                if amount <= 0:
                    QMessageBox.warning(
                        self, "Validation", "Amount must be greater than zero."
                    )
                    return

                try:
                    with DatabaseContext(self.db, auto_commit=True) as cur:
                        cur.execute(
                            """
                            INSERT INTO payments (
                                reserve_number,
                                charter_id,
                                payment_date,
                                amount,
                                payment_method,
                                reference_number,
                                status,
                                is_deposited
                            )
                            VALUES (
                                %s,
                                (SELECT charter_id FROM charters WHERE
                                reserve_number = %s),
                                %s,
                                %s,
                                %s,
                                %s,
                                %s,
                                %s
                            )
                            """,
                            (
                                self.reserve_number,
                                self.reserve_number,
                                payment_date,
                                amount,
                                method,
                                reference,
                                status,
                                reconciled,
                            ),
                        )
                        QMessageBox.information(
                            self, "Success", "Payment added successfully"
                        )
                        # Reload payments and balances
                        self.load_charter_data()
                except Exception as e:
                    logger.error(f"Failed to add payment: {e}")
                    QMessageBox.critical(
                        self, "Error", f"Failed to add payment: {e}"
                    )
        except Exception as e:
            logger.error(f"Failed to open payment dialog: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to open payment dialog: {e}"
            )


# ============================================================================
# STANDARDIZED DRILL-DOWN PATTERNS
# ============================================================================


class StandardDrillDownDialog(QDialog):
    """
    Base class for standardized drill-down dialogs.
    Provides consistent button layout, add/duplicate/delete patterns,
    and navigation.

    BUTTON LAYOUT (TOP):
    - Left: Action-specific buttons (Lock, Suspend, Retire, etc.) + Stretch
    - Right: [Add New] [Duplicate] [Delete] [Save] [Close]

    SUBCLASS REQUIREMENTS:
    - Override create_content_layout() to build main UI (tabs, forms, etc.)
    - Override load_record_data() to populate fields from database
    - Override save_record_data() to persist changes to database
        - Set self.record_id and self.record_label
            (e.g., "client_id", "client_name")
    """

    saved = pyqtSignal(dict)  # Emitted when record is saved

    def __init__(self, db, record_id=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.record_id = record_id
        # Override in subclass (e.g., "Client", "Employee")
        self.record_type = "Record"
        # Override in subclass (e.g., "client_id", "reserve_number")
        self.record_label = ""
        self.record_data = {}

        self.setGeometry(50, 50, 1400, 900)
        self.setWindowTitle(
            f"{self.record_type} Detail - {record_id or 'New'}"
        )

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

    def create_content_layout(self) -> QWidget:
        """
        Override in subclass to create main UI (QTabWidget, forms, etc.).
        Return a QWidget or QTabWidget.
        Default: empty widget.
        """
        return QWidget()

    def load_record_data(self) -> None:
        """Override in subclass to load record from database and populate UI"
        "fields."""

    def save_record_data(self) -> None:
        """Override in subclass to persist record changes to database."""

    def add_new_record(self) -> None:
        """Prompt user to create a new record; open a new instance of this"
        "dialog."""

        reply = QMessageBox.question(
            self,
            "Add New Record",
            f"Create a new {self.record_type.lower()}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Open new dialog without record_id
            new_dialog = self.__class__(
                self.db, record_id=None, parent=self.parent()
            )
            new_dialog.saved.connect(self.on_saved)
            new_dialog.exec()

    def duplicate_record(self) -> None:
        """Duplicate current record with user-specified identifier change."""
        if not self.record_id:
            QMessageBox.warning(
                self, "Warning", "No record loaded to duplicate."
            )
            return

        # Collect current record data
        record_copy = self.record_data.copy()

        # Show dialog to change identifier
        dialog = DuplicateRecordDialog(
            self.record_type, record_copy, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Create new instance and save
            try:
                # Subclass should handle the actual duplication logic
                self.perform_duplicate(dialog.new_identifier)
                QMessageBox.information(
                    self,
                    "Success",
                    f"{self.record_type} duplicated successfully.",
                )
                self.load_record_data()  # Refresh current view
            except Exception as e:
                logger.error(f"Failed to duplicate {self.record_type}: {e}")
                QMessageBox.critical(
                    self, "Error", f"Failed to duplicate: {e}"
                )

    def perform_duplicate(self, new_identifier) -> None:
        """
        Override in subclass to perform actual duplication.
        new_identifier: The new name/id for the duplicated record.
        Should insert new record into database.
        """
        raise NotImplementedError(
            "Subclass must implement perform_duplicate()"
        )

    def delete_record(self) -> None:
        """Delete current record after confirmation."""
        if not self.record_id:
            QMessageBox.warning(self, "Warning", "No record loaded to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete this {self.record_type.lower()} record?\nThis action"
            f"cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.perform_delete()
                QMessageBox.information(
                    self,
                    "Success",
                    f"{self.record_type} deleted successfully.",
                )
                self.close()
                self.saved.emit(
                    {"action": "delete", "record_id": self.record_id}
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def perform_delete(self) -> None:
        """Override in subclass to perform actual deletion."""
        raise NotImplementedError("Subclass must implement perform_delete()")

    def save_and_emit(self) -> None:
        """Save record and emit saved signal."""
        try:
            self.save_record_data()
            QMessageBox.information(
                self, "Success", f"{self.record_type} saved successfully."
            )
            self.saved.emit(self.record_data)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def on_saved(self, record_data) -> None:
        """Handle child dialog save (when duplicate is created)."""
        self.load_record_data()


class DuplicateRecordDialog(QDialog):
    """
    Generic dialog for duplicating a record.
    Allows user to change a key identifier (name, id, etc.).
    """

    def __init__(self, record_type, record_data, parent=None) -> None:
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
        info = QLabel(
            f"Enter a new name or identifier for the duplicate"
            f"{record_type.lower()} record:"
        )
        layout.addWidget(info)

        # Input field
        form = QFormLayout()
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText(
            f"New {record_type.lower()} name..."
        )
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

    def accept_duplicate(self) -> None:
        """Validate and accept the new identifier."""
        new_name = self.identifier_input.text().strip()
        if not new_name:
            QMessageBox.warning(
                self,
                "Warning",
                "Please enter a name for the duplicate record.",
            )
            return

        self.new_identifier = new_name
        self.accept()


# ============================================================================
# ROUTING STOP EDITOR
# ============================================================================


class RoutingStopDialog(QDialog):
    """
    Dialog for adding or editing a single routing stop.
    Supports all stop types: pickup, drop-off, leave for, return to,
    extra time, split run
    """

    def __init__(self, parent=None, stop_data=None) -> None:
        super().__init__(parent)
        self.stop_data = stop_data or {}
        self.setWindowTitle("Add/Edit Routing Stop")
        self.setMinimumWidth(500)
        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QFormLayout()

        # Stop Type
        self.stop_type = QComboBox()
        self.stop_type.addItems(
            [
                "PICKUP AT",
                "DROP OFF AT",
                "LEAVE RED DEER FOR",
                "DROP OFF FOR SPLIT RUN AT",
                "PICK UP AT",
                "RETURN TO RED DEER AT",
                "EXTRA TIME ADDED",
                "WAYPOINT / STOP",
            ]
        )
        if "type" in self.stop_data:
            self.stop_type.setCurrentText(self.stop_data["type"])
        layout.addRow("Stop Type:", self.stop_type)

        # Details
        self.location = QLineEdit()
        self.location.setPlaceholderText("Enter address or location name")
        if "location" in self.stop_data:
            self.location.setText(self.stop_data["location"])
        layout.addRow("Details:", self.location)

        # Time
        self.time = QLineEdit()
        self.time.setPlaceholderText("HH:MM (e.g. 14:30)")
        if "time" in self.stop_data:
            self.time.setText(self.stop_data["time"])
        layout.addRow("Time:", self.time)

        # Driver Notes
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setPlaceholderText(
            "Driver notes, special instructions, gate codes, etc."
        )
        if "notes" in self.stop_data:
            self.notes.setPlainText(self.stop_data["notes"])
        layout.addRow("Driver Notes:", self.notes)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self.setLayout(layout)

    def validate_and_accept(self) -> None:
        """Validate data before accepting"""
        if not self.location.text().strip():
            QMessageBox.warning(
                self, "Validation Error", "Location is required."
            )
            return

        self.accept()

    def get_stop_data(self) -> dict:
        """Return stop data as dictionary"""
        return {
            "type": self.stop_type.currentText(),
            "location": self.location.text().strip(),
            "time": self.time.text().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


# BEVERAGE & PRODUCT SHOPPING CART
# ============================================================================


class BeverageShoppingCartDialog(QDialog):
    """
    Shopping cart for adding beverage and product orders to a charter.
    Browse items, add to cart, set quantities, and save order.
    """

    def __init__(self, db, reserve_number, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.reserve_number = reserve_number
        # List of {item_id, name, unit_price, quantity, total}
        self.cart_items = []

        self.setWindowTitle(
            f"🛒 Beverage & Product Order - Charter {reserve_number}"
        )
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
        self.product_table.setHorizontalHeaderLabels(
            ["Item", "Category", "Unit Price", "Description"]
        )
        header = self.product_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.product_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.product_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
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
        self.cart_table.setHorizontalHeaderLabels(
            ["Item", "Unit Price", "Qty", "Total", ""]
        )
        header = self.cart_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.cart_table.setColumnWidth(3, 110)
        self.cart_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        cart_layout.addWidget(self.cart_table)

        # Cart summary (GST shown for guest collection/reporting only)
        summary_layout = QFormLayout()

        self.our_cost_label = QLabel("$0.00")
        self.our_cost_label.setToolTip("Our wholesale cost for these items")
        summary_layout.addRow("Our Cost (wholesale):", self.our_cost_label)

        self.subtotal_label = QLabel("$0.00")
        self.subtotal_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.subtotal_label.setToolTip(
            "Beverage subtotal used for charter invoice (pre-GST)"
        )
        summary_layout.addRow(
            "Beverage Subtotal (to invoice):", self.subtotal_label
        )

        self.gst_label = QLabel("$0.00")
        self.gst_label.setToolTip(
            "GST for guest collection/reporting; not posted to invoice"
        )
        summary_layout.addRow("Guest GST 5% (not invoiced):", self.gst_label)

        self.total_label = QLabel("$0.00")
        self.total_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.total_label.setStyleSheet("color: #27ae60;")
        self.total_label.setToolTip(
            "Guest collection total during trip (subtotal + GST)"
        )
        summary_layout.addRow("Guest Collection Total:", self.total_label)

        self.profit_label = QLabel("$0.00")
        self.profit_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.profit_label.setStyleSheet("color: #2980b9;")
        self.profit_label.setToolTip(
            "Profit: charged price - (our cost + GST + deposit)"
        )
        summary_layout.addRow(
            "Our Profit (dispatcher only):", self.profit_label
        )

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
        save_order_btn.setStyleSheet(
            "background-color: #27ae60; color: white; padding: 8px;"
            "font-weight: bold;"
        )
        button_layout.addWidget(save_order_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Load products
        self.load_products()

    def load_products(self) -> None:
        """Load available beverage and product items with descriptions"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Load from beverages/products table (create if doesn't exist)
                cur.execute("""
                      SELECT item_id, item_name, category, unit_price,
                          COALESCE(description, ''),
                           our_cost, deposit_amount
                    FROM beverage_products
                    ORDER BY category, item_name
                """)

                rows = cur.fetchall()
                self.product_table.setRowCount(len(rows))

                for row_idx, row_data in enumerate(rows):
                    (
                        item_id,
                        name,
                        category,
                        price,
                        description,
                        our_cost,
                        deposit_amount,
                    ) = row_data

                    # Optional: reasonable row height
                    self.product_table.setRowHeight(row_idx, 40)

                    # Column 0: Item name (store all data)
                    name_item = QTableWidgetItem(str(name))
                    name_item.setData(
                        Qt.ItemDataRole.UserRole,
                        {
                            "item_id": item_id,
                            "unit_price": float(price or 0),
                            "our_cost": float(our_cost or 0),
                            "deposit": float(deposit_amount or 0),
                        },
                    )
                    self.product_table.setItem(row_idx, 0, name_item)

                    # Columns 1-3: Product details
                    self.product_table.setItem(
                        row_idx, 1, QTableWidgetItem(str(category or ""))
                    )
                    self.product_table.setItem(
                        row_idx, 2, QTableWidgetItem(f"${price:.2f}")
                    )

                    # Column 3: Description (read-only)
                    desc_item = QTableWidgetItem(str(description or ""))
                    desc_item.setFlags(
                        desc_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                    )
                    self.product_table.setItem(row_idx, 3, desc_item)

        except Exception as e:
            logger.error(f"Failed to load products: {e}")
            # If table doesn't exist, show sample products
            QMessageBox.warning(
                self,
                "Info",
                f"Beverage products table not found. Showing sample"
                f"items.\n{e}",
            )
            self.load_sample_products()

    def load_sample_products(self) -> None:
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
        for row_idx, (name, category, price, stock) in enumerate(
            sample_products
        ):
            self.product_table.setRowHeight(row_idx, 40)

            # Columns 0-3: Product details (no images)
            name_item = QTableWidgetItem(name)
            name_item.setData(
                Qt.ItemDataRole.UserRole,
                {
                    "item_id": row_idx + 1,
                    "unit_price": price,
                    "our_cost": 0.0,
                    "deposit": 0.0,
                },
            )
            self.product_table.setItem(row_idx, 0, name_item)
            self.product_table.setItem(row_idx, 1, QTableWidgetItem(category))
            self.product_table.setItem(
                row_idx, 2, QTableWidgetItem(f"${price:.2f}")
            )
            self.product_table.setItem(
                row_idx, 3, QTableWidgetItem(f"In stock: {stock}")
            )

    # Images removed: no icon loading needed

    def filter_products(self) -> None:
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
                name_ratio = SequenceMatcher(
                    None, search_text, item_name
                ).ratio()
                # Check category similarity
                category_ratio = SequenceMatcher(
                    None, search_text, category
                ).ratio()
                # Check if search is substring (exact match)
                is_substring = (
                    search_text in item_name or search_text in category
                )

                # Show row if: exact substring match OR fuzzy match > 60%
                if is_substring or name_ratio > 0.6 or category_ratio > 0.6:
                    self.product_table.setRowHidden(row, False)
                else:
                    self.product_table.setRowHidden(row, True)

    def add_to_cart_from_table(self) -> None:
        """Add selected product to cart"""
        row = self.product_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "Warning", "Please select a product first."
            )
            return

        # Column 0: Item name (has data stored)
        item_name = self.product_table.item(row, 0).text()
        item_data = self.product_table.item(row, 0).data(
            Qt.ItemDataRole.UserRole
        )

        item_id = item_data["item_id"]
        unit_price = item_data["unit_price"]
        our_cost = item_data["our_cost"]
        deposit = item_data["deposit"]

        # Check if already in cart
        for cart_item in self.cart_items:
            if cart_item["item_id"] == item_id:
                cart_item["quantity"] += 1
                cart_item["total"] = (
                    cart_item["quantity"] * cart_item["unit_price"]
                )
                self.refresh_cart_display()
                return

        # Add new item to cart
        self.cart_items.append(
            {
                "item_id": item_id,
                "name": item_name,
                "unit_price": unit_price,
                "our_cost": our_cost,
                "deposit": deposit,
                "quantity": 1,
                "total": unit_price,
            }
        )

        self.refresh_cart_display()

    def refresh_cart_display(self) -> None:
        """Refresh cart table and totals"""
        self.cart_table.setRowCount(len(self.cart_items))

        subtotal = 0

        for row_idx, item in enumerate(self.cart_items):
            # Item name
            self.cart_table.setItem(row_idx, 0, QTableWidgetItem(item["name"]))

            # Unit price
            self.cart_table.setItem(
                row_idx, 1, QTableWidgetItem(f"${item['unit_price']:.2f}")
            )

            # Quantity (editable spinbox)
            qty_spin = QSpinBox()
            qty_spin.setMinimum(1)
            qty_spin.setMaximum(999)
            qty_spin.setValue(item["quantity"])
            qty_spin.valueChanged.connect(
                lambda val, idx=row_idx: self.update_quantity(idx, val)
            )
            self.cart_table.setCellWidget(row_idx, 2, qty_spin)

            # Total
            self.cart_table.setItem(
                row_idx, 3, QTableWidgetItem(f"${item['total']:.2f}")
            )

            # Remove button
            remove_btn = QPushButton("❌")
            remove_btn.clicked.connect(
                lambda checked, idx=row_idx: self.remove_from_cart(idx)
            )
            self.cart_table.setCellWidget(row_idx, 4, remove_btn)

            subtotal += item["total"]

        # Update totals
        gst = subtotal * 0.05
        total = subtotal + gst

        # Calculate profit: unit_price already includes GST and deposit, so
        # profit = charged - our_cost
        our_cost_total = sum(
            item.get("our_cost", 0) * item["quantity"]
            for item in self.cart_items
        )
        profit = subtotal - our_cost_total

        self.our_cost_label.setText(f"${our_cost_total:.2f}")
        self.subtotal_label.setText(f"${subtotal:.2f}")
        self.gst_label.setText(f"${gst:.2f}")
        self.total_label.setText(f"${total:.2f}")
        self.profit_label.setText(f"${profit:.2f}")

    def update_quantity(self, row_idx, new_qty) -> None:
        """Update quantity for cart item"""
        if row_idx < len(self.cart_items):
            self.cart_items[row_idx]["quantity"] = new_qty
            self.cart_items[row_idx]["total"] = (
                new_qty * self.cart_items[row_idx]["unit_price"]
            )
            self.refresh_cart_display()

    def remove_from_cart(self, row_idx) -> None:
        """Remove item from cart"""
        if row_idx < len(self.cart_items):
            del self.cart_items[row_idx]
            self.refresh_cart_display()

    def clear_cart(self) -> None:
        """Clear all items from cart"""
        reply = QMessageBox.question(
            self,
            "Clear Cart",
            "Remove all items from cart?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.cart_items = []
            self.refresh_cart_display()

    def save_order(self) -> None:
        """Save order to charter"""
        if not self.cart_items:
            QMessageBox.warning(
                self, "Warning", "Cart is empty. Add items before saving."
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                # Insert order header
                subtotal = sum(item["total"] for item in self.cart_items)
                gst = subtotal * 0.05
                total = subtotal + gst

                cur.execute(
                    """
                    INSERT INTO beverage_orders
                    (reserve_number, order_date, subtotal, gst, total, status)
                    VALUES (%s, NOW(), %s, %s, %s, 'pending')
                    RETURNING order_id
                """,
                    (self.reserve_number, subtotal, gst, total),
                )

                order_id = cur.fetchone()[0]

                # Insert order items
                for item in self.cart_items:
                    cur.execute(
                        """
                        INSERT INTO beverage_order_items
                        (order_id, item_id, item_name, quantity, unit_price,
                        total)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                        (
                            order_id,
                            item["item_id"],
                            item["name"],
                            item["quantity"],
                            item["unit_price"],
                            item["total"],
                        ),
                    )

                QMessageBox.information(
                    self,
                    "Success",
                    f"Order saved!\n\nItems: {len(self.cart_items)}\nTotal:"
                    f"${total:.2f}",
                )

                self.accept()

        except Exception as e:
            logger.error(f"Failed to save order: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save order:\n{e}")


# ============================================================================
# PRE-RUN CHECKLIST DIALOG
# ============================================================================

class PreRunChecklistDialog(QDialog):
    """
    Checklist popup shown for Booked charters within 48 hours of departure.
    State is persisted to the charter_checklists DB table.
    """

    ITEMS = [
        ("driver_confirmed",   "Driver confirmed"),
        ("vehicle_confirmed",  "Vehicle confirmed"),
        ("client_contacted",   "Client contacted"),
        ("deposit_received",   "Deposit / payment received"),
    ]

    def __init__(self, db, charter_id: int, reserve_number: str = "", parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.charter_id = charter_id
        self.reserve_number = reserve_number
        self.setWindowTitle(f"Pre-Run Checklist \u2014 {reserve_number}")
        self.setMinimumWidth(360)
        self._ensure_table()
        self._setup_ui()
        self._load_state()

    def _ensure_table(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS charter_checklists (
                        charter_id        INTEGER PRIMARY KEY,
                        driver_confirmed  BOOLEAN DEFAULT FALSE,
                        vehicle_confirmed BOOLEAN DEFAULT FALSE,
                        client_contacted  BOOLEAN DEFAULT FALSE,
                        deposit_received  BOOLEAN DEFAULT FALSE,
                        updated_at        TIMESTAMP DEFAULT NOW()
                    )
                """)
        except Exception as e:
            logger.error(f"charter_checklists create failed: {e}")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        header = QLabel(f"<b>Pre-run checklist for {self.reserve_number}</b>")
        layout.addWidget(header)
        layout.addWidget(QLabel("Confirm all items before the run departs:"))

        self._checks: dict = {}
        for key, label in self.ITEMS:
            cb = QCheckBox(label)
            self._checks[key] = cb
            layout.addWidget(cb)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        btn_box.accepted.connect(self._save_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _load_state(self) -> None:
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    "SELECT driver_confirmed, vehicle_confirmed, client_contacted, deposit_received "
                    "FROM charter_checklists WHERE charter_id=%s",
                    (self.charter_id,),
                )
                row = cur.fetchone()
                if row:
                    keys = [k for k, _ in self.ITEMS]
                    for key, val in zip(keys, row):
                        if key in self._checks:
                            self._checks[key].setChecked(bool(val))
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)
    def _save_and_accept(self) -> None:
        vals = {k: self._checks[k].isChecked() for k, _ in self.ITEMS}
        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                cur.execute("""
                    INSERT INTO charter_checklists
                        (charter_id, driver_confirmed, vehicle_confirmed, client_contacted, deposit_received, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (charter_id) DO UPDATE SET
                        driver_confirmed  = EXCLUDED.driver_confirmed,
                        vehicle_confirmed = EXCLUDED.vehicle_confirmed,
                        client_contacted  = EXCLUDED.client_contacted,
                        deposit_received  = EXCLUDED.deposit_received,
                        updated_at        = NOW()
                """, (
                    self.charter_id,
                    vals["driver_confirmed"],
                    vals["vehicle_confirmed"],
                    vals["client_contacted"],
                    vals["deposit_received"],
                ))
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))
        self.accept()
