"""
Advanced charter search and lookup dialog with multi-criteria filtering, sorting, and drill-down.
"""
import psycopg2
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QDateEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QCheckBox, QSpinBox, QHeaderView,
    QMessageBox, QTabWidget, QWidget, QSplitter
)
from PyQt6.QtCore import Qt, QDate, QDateTime
from PyQt6.QtGui import QFont, QColor
from datetime import datetime, timedelta


class AdvancedCharterSearchDialog(QDialog):
    """Advanced charter search with filtering, sorting, and drill-down."""
    
    def __init__(self, db_connection, parent=None):
        super().__init__(parent)
        self.db = db_connection
        self.navigation_stack = []  # Track drill-down navigation
        self.current_charter_id = None
        self.setWindowTitle("Advanced Charter Search")
        self.setGeometry(100, 100, 1400, 700)
        self.setStyleSheet("QDialog { background-color: #f0f0f0; }")
        self.init_ui()
        self.load_charters()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # ===== FILTER PANEL =====
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        # Charter Number
        filter_layout.addWidget(QLabel("Charter #:"))
        self.charter_num_input = QLineEdit()
        self.charter_num_input.setPlaceholderText("e.g., 006717 or 18720")
        self.charter_num_input.setMaximumWidth(120)
        self.charter_num_input.textChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.charter_num_input)
        
        # Driver
        filter_layout.addWidget(QLabel("Driver:"))
        self.driver_combo = QComboBox()
        self.driver_combo.setMaximumWidth(150)
        self.driver_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.driver_combo)
        
        # Vehicle filter with type display
        filter_layout.addWidget(QLabel("Vehicle:"))
        self.vehicle_combo = QComboBox()
        try:
            self.vehicle_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        except Exception:
            pass
        self.vehicle_combo.setMinimumContentsLength(4)
        self.vehicle_combo.setMaximumWidth(140)
        self.vehicle_combo.currentTextChanged.connect(self.on_filter_changed)
        self.vehicle_type_label = QLabel("")
        self.vehicle_type_label.setStyleSheet("color:#555; padding-left:6px;")
        veh_row = QHBoxLayout()
        veh_row.setContentsMargins(0,0,0,0)
        veh_row.setSpacing(6)
        veh_row.addWidget(self.vehicle_combo)
        veh_row.addWidget(QLabel("Type:"))
        veh_row.addWidget(self.vehicle_type_label)
        veh_widget = QWidget()
        veh_widget.setLayout(veh_row)
        filter_layout.addWidget(veh_widget)
        
        # Status
        filter_layout.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All", "pending", "confirmed", "completed", "cancelled", "closed"])
        self.status_combo.setMaximumWidth(120)
        self.status_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.status_combo)
        
        # Date Range
        filter_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        self.date_from.setMaximumWidth(120)
        self.date_from.dateChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.date_from)
        
        filter_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate().addDays(30))
        self.date_to.setMaximumWidth(120)
        self.date_to.dateChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.date_to)
        
        # Balance filter
        filter_layout.addWidget(QLabel("Balance > $:"))
        self.balance_min = QSpinBox()
        self.balance_min.setMaximum(100000)
        self.balance_min.setMaximumWidth(80)
        self.balance_min.valueChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.balance_min)
        
        # Show only unpaid
        self.unpaid_only = QCheckBox("Unpaid Only")
        self.unpaid_only.stateChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.unpaid_only)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # ===== SORT PANEL =====
        sort_layout = QHBoxLayout()
        sort_layout.addWidget(QLabel("Sort by:"))
        self.sort1_combo = QComboBox()
        self.sort1_combo.addItems(["Date (Newest)", "Date (Oldest)", "Balance (High)", "Balance (Low)", "Reserve #", "Driver", "Vehicle"])
        self.sort1_combo.setMaximumWidth(150)
        self.sort1_combo.currentTextChanged.connect(self.on_filter_changed)
        sort_layout.addWidget(self.sort1_combo)
        
        sort_layout.addWidget(QLabel("Then by:"))
        self.sort2_combo = QComboBox()
        self.sort2_combo.addItems(["None", "Vehicle", "Driver", "Reserve #", "Balance (High)", "Balance (Low)"])
        self.sort2_combo.setMaximumWidth(150)
        self.sort2_combo.currentTextChanged.connect(self.on_filter_changed)
        sort_layout.addWidget(self.sort2_combo)
        
        sort_layout.addWidget(QLabel("Then by:"))
        self.sort3_combo = QComboBox()
        self.sort3_combo.addItems(["None", "Vehicle", "Driver", "Reserve #", "Time"])
        self.sort3_combo.setMaximumWidth(150)
        self.sort3_combo.currentTextChanged.connect(self.on_filter_changed)
        sort_layout.addWidget(self.sort3_combo)
        
        sort_layout.addStretch()
        layout.addLayout(sort_layout)
        
        # ===== RESULTS TABLE =====
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(10)
        self.results_table.setHorizontalHeaderLabels([
            "Reserve #", "Charter ID", "Date", "Time", "Driver", "Vehicle", "Status", "Total Due", "Paid", "Balance"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setSelectionBehavior(self.results_table.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(self.results_table.SelectionMode.SingleSelection)
        self.results_table.doubleClicked.connect(self.on_table_double_click)
        self.results_table.setMaximumHeight(400)
        layout.addWidget(QLabel("Results (double-click to drill-down):"))
        layout.addWidget(self.results_table)
        
        # ===== BUTTON PANEL =====
        button_layout = QHBoxLayout()
        
        self.view_btn = QPushButton("View Charter Form")
        self.view_btn.clicked.connect(self.on_view_charter)
        button_layout.addWidget(self.view_btn)
        
        self.vehicle_btn = QPushButton("View Vehicle Details")
        self.vehicle_btn.clicked.connect(self.on_view_vehicle)
        button_layout.addWidget(self.vehicle_btn)
        
        self.driver_btn = QPushButton("View Driver Info")
        self.driver_btn.clicked.connect(self.on_view_driver)
        button_layout.addWidget(self.driver_btn)
        
        button_layout.addStretch()
        
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self.on_back)
        self.back_btn.setEnabled(False)
        button_layout.addWidget(self.back_btn)
        
        self.close_btn = QPushButton("Close All")
        self.close_btn.clicked.connect(self.close_all_dialogs)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_charters(self):
        """Load all charters and populate combos."""
        try:
            cur = self.db.get_cursor()
            
            # Load drivers
            cur.execute("SELECT DISTINCT driver FROM charters WHERE driver IS NOT NULL AND driver != '' ORDER BY driver")
            drivers = [row[0] for row in cur.fetchall()]
            self.driver_combo.addItems(["All"] + drivers)
            
            # Load vehicles with active-first, numeric L ordering
            cur.execute("""
                SELECT DISTINCT v.vehicle_number
                FROM charters c
                LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
                WHERE v.vehicle_number IS NOT NULL AND v.vehicle_number != ''
                ORDER BY
                    CASE WHEN v.status = 'active' THEN 0 ELSE 1 END,
                    CASE
                        WHEN v.vehicle_number ~ '^[Ll]-?\d+$' THEN CAST(regexp_replace(v.vehicle_number, '[^0-9]', '', 'g') AS INT)
                        ELSE 9999
                    END,
                    v.vehicle_number
            """)
            vehicles = [row[0] for row in cur.fetchall()]
            self.vehicle_combo.addItems(["All"] + vehicles)
            
            cur.close()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Error", f"Failed to load charters: {e}")
    
    def on_filter_changed(self):
        """Rebuild results table when filters change."""
        self.load_filtered_charters()
    
    def load_filtered_charters(self):
        """Apply filters and populate results table."""
        try:
            cur = self.db.get_cursor()
            
            # Build WHERE clause
            where_clauses = []
            params = []
            
            charter_num = self.charter_num_input.text().strip()
            if charter_num:
                where_clauses.append("(reserve_number ILIKE %s OR CAST(charter_id AS TEXT) ILIKE %s)")
                params.extend([f"%{charter_num}%", f"%{charter_num}%"])
            
            if self.driver_combo.currentText() != "All":
                where_clauses.append("driver = %s")
                params.append(self.driver_combo.currentText())
            
            if self.vehicle_combo.currentText() != "All":
                where_clauses.append("vehicle = %s")
                params.append(self.vehicle_combo.currentText())
            
            if self.status_combo.currentText() != "All":
                where_clauses.append("status = %s")
                params.append(self.status_combo.currentText())
            
            if self.date_from.date():
                where_clauses.append("charter_date >= %s")
                params.append(self.date_from.date())
            
            if self.date_to.date():
                where_clauses.append("charter_date <= %s")
                params.append(self.date_to.date())
            
            if self.balance_min.value() > 0:
                where_clauses.append("balance >= %s")
                params.append(self.balance_min.value())
            
            if self.unpaid_only.isChecked():
                where_clauses.append("balance > 0")
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Build ORDER BY
            order_parts = []
            sort_map = {
                "Date (Newest)": "charter_date DESC",
                "Date (Oldest)": "charter_date ASC",
                "Balance (High)": "balance DESC",
                "Balance (Low)": "balance ASC",
                "Reserve #": "reserve_number ASC",
                "Driver": "driver ASC",
                "Vehicle": "vehicle ASC",
                "Time": "pickup_time ASC",
                "None": None,
            }
            
            for combo in [self.sort1_combo, self.sort2_combo, self.sort3_combo]:
                sort_key = sort_map.get(combo.currentText())
                if sort_key:
                    order_parts.append(sort_key)
            
            order_sql = f"ORDER BY {', '.join(order_parts)}" if order_parts else "ORDER BY charter_date DESC"
            
            sql = f"""
                SELECT charter_id, reserve_number, charter_date, pickup_time, driver, vehicle, status, 
                       total_amount_due, paid_amount, balance
                FROM charters
                WHERE {where_sql}
                {order_sql}
                LIMIT 500
            """
            
            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.close()
            
            self.results_table.setRowCount(len(rows))
            for row_idx, (cid, res_num, cdate, ctime, driver, vehicle, status, total, paid, balance) in enumerate(rows):
                self.results_table.setItem(row_idx, 0, QTableWidgetItem(str(res_num or "")))
                self.results_table.setItem(row_idx, 1, QTableWidgetItem(str(cid)))
                self.results_table.setItem(row_idx, 2, QTableWidgetItem(str(cdate.strftime("%Y-%m-%d") if cdate else "")))
                self.results_table.setItem(row_idx, 3, QTableWidgetItem(str(ctime.strftime("%H:%M") if ctime else "")))
                self.results_table.setItem(row_idx, 4, QTableWidgetItem(str(driver or "")))
                self.results_table.setItem(row_idx, 5, QTableWidgetItem(str(vehicle or "")))
                self.results_table.setItem(row_idx, 6, QTableWidgetItem(str(status or "")))
                self.results_table.setItem(row_idx, 7, QTableWidgetItem(f"${total:,.2f}" if total else "$0.00"))
                self.results_table.setItem(row_idx, 8, QTableWidgetItem(f"${paid:,.2f}" if paid else "$0.00"))
                balance_item = QTableWidgetItem(f"${balance:,.2f}" if balance else "$0.00")
                if balance and balance > 0:
                    balance_item.setBackground(QColor(255, 200, 200))
                self.results_table.setItem(row_idx, 9, balance_item)
        
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Error", f"Failed to load charters: {e}")
    
    def on_table_double_click(self, index):
        """Handle double-click on table results."""
        if not index.isValid():
            return
        row = index.row()
        col = index.column()
        
        # Get charter_id from column 1
        charter_id_item = self.results_table.item(row, 1)
        if charter_id_item:
            self.current_charter_id = int(charter_id_item.text())
            
            # Column 0 = Reserve #, open charter form
            # Column 4 = Driver, open driver info
            # Column 5 = Vehicle, open vehicle info
            if col == 0 or col == 1:  # Reserve # or Charter ID
                self.on_view_charter()
            elif col == 4:  # Driver
                self.on_view_driver()
            elif col == 5:  # Vehicle
                self.on_view_vehicle()
    
    def on_view_charter(self):
        """Open full charter form for selected row."""
        row = self.results_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Select a charter row first")
            return
        
        charter_id_item = self.results_table.item(row, 1)
        if charter_id_item:
            self.current_charter_id = int(charter_id_item.text())
            # Signal to parent to load charter in form
            if hasattr(self.parent(), 'load_charter_by_id'):
                self.parent().load_charter_by_id(self.current_charter_id)
            QMessageBox.information(self, "Info", f"Charter {self.current_charter_id} loaded in form. You can now edit or review.")
    
    def on_view_vehicle(self):
        """Open vehicle details for selected charter."""
        row = self.results_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Select a charter row first")
            return
        
        vehicle_item = self.results_table.item(row, 5)
        if vehicle_item and vehicle_item.text():
            vehicle_name = vehicle_item.text()
            try:
                cur = self.db.get_cursor()
                cur.execute("SELECT * FROM vehicles WHERE vehicle_name = %s", (vehicle_name,))
                vehicle_row = cur.fetchone()
                cur.close()
                
                if vehicle_row:
                    msg = f"Vehicle: {vehicle_name}\n\nDetails:\n{vehicle_row}"
                    QMessageBox.information(self, "Vehicle Information", msg)
                else:
                    QMessageBox.warning(self, "Error", f"Vehicle '{vehicle_name}' not found")
            except Exception as e:
                try:
                    self.db.rollback()
                except:
                    pass
                QMessageBox.warning(self, "Error", f"Failed to load vehicle: {e}")
    
    def on_view_driver(self):
        """Open driver info for selected charter."""
        row = self.results_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Select a charter row first")
            return
        
        driver_item = self.results_table.item(row, 4)
        if driver_item and driver_item.text():
            driver_name = driver_item.text()
            try:
                cur = self.db.get_cursor()
                cur.execute("""
                    SELECT employee_id, first_name, last_name, email, phone, status, hire_date
                    FROM employees
                    WHERE CONCAT(first_name, ' ', last_name) = %s
                    LIMIT 1
                """, (driver_name,))
                driver_row = cur.fetchone()
                cur.close()
                
                if driver_row:
                    emp_id, fname, lname, email, phone, status, hire_date = driver_row
                    msg = f"Driver: {fname} {lname}\nID: {emp_id}\nEmail: {email}\nPhone: {phone}\nStatus: {status}\nHire Date: {hire_date}"
                    QMessageBox.information(self, "Driver Information", msg)
                else:
                    QMessageBox.warning(self, "Error", f"Driver '{driver_name}' not found")
            except Exception as e:
                try:
                    self.db.rollback()
                except:
                    pass
                QMessageBox.warning(self, "Error", f"Failed to load driver: {e}")
    
    def on_back(self):
        """Navigate back in drill-down stack."""
        if self.navigation_stack:
            self.navigation_stack.pop()
    
    def close_all_dialogs(self):
        """Close all dialogs."""
        self.close()
