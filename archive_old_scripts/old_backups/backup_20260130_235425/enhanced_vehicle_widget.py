"""
Enhanced Vehicle List Widget with Drill-Down
Displays fleet with filters, alerts for maintenance, visual indicators
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from vehicle_drill_down import VehicleDetailDialog


class EnhancedVehicleListWidget(QWidget):
    """
    Fleet list with:
    - Filters: Make, Type, Status
    - Columns: Vehicle #, Plate, Make/Model, Year, Type, Mileage, Status, Next Service, Issues
    - Visual alerts: Red for overdue service, yellow for upcoming
    - Actions: New Vehicle, Edit, Retire, Refresh
    - Double-click opens VehicleDetailDialog
    """
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._data_loaded = False
        
        layout = QVBoxLayout()
        
        # ===== BREADCRUMB NAVIGATION =====
        breadcrumb_layout = QHBoxLayout()
        back_btn = QPushButton("⬅ Back to Navigator")
        back_btn.setMaximumWidth(150)
        back_btn.clicked.connect(self.go_back)
        breadcrumb_layout.addWidget(back_btn)
        breadcrumb_layout.addWidget(QLabel("📍 Fleet Management › Vehicle List"))
        breadcrumb_layout.addStretch()
        layout.addLayout(breadcrumb_layout)
        
        # ===== TITLE =====
        title = QLabel("🚗 Fleet Management")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # ===== ACTION BUTTONS AT TOP =====
        button_layout = QHBoxLayout()
        
        new_btn = QPushButton("➕ New Vehicle")
        new_btn.clicked.connect(self.new_vehicle)
        button_layout.addWidget(new_btn)
        
        edit_btn = QPushButton("✏️ Edit Selected")
        edit_btn.clicked.connect(self.edit_vehicle)
        button_layout.addWidget(edit_btn)
        
        retire_btn = QPushButton("🚫 Retire Selected")
        retire_btn.clicked.connect(self.retire_vehicle)
        button_layout.addWidget(retire_btn)
        
        inactive_btn = QPushButton("⏸️ Mark Inactive")
        inactive_btn.clicked.connect(self.mark_inactive)
        button_layout.addWidget(inactive_btn)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh)
        button_layout.addWidget(refresh_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # ===== FILTERS =====
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Make:"))
        self.make_filter = QLineEdit()
        self.make_filter.setPlaceholderText("Any make...")
        self.make_filter.textChanged.connect(self.refresh)
        filter_layout.addWidget(self.make_filter)
        
        filter_layout.addWidget(QLabel("Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All Types", "Sedan", "SUV", "Limousine", "Stretch Limo", "Van", "Bus"])
        self.type_filter.currentTextChanged.connect(self.refresh)
        filter_layout.addWidget(self.type_filter)
        
        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Active", "In Service", "Out of Service", "Retired"])
        self.status_filter.currentTextChanged.connect(self.refresh)
        filter_layout.addWidget(self.status_filter)
        
        self.service_alert_filter = QCheckBox("Show Service Alerts Only")
        self.service_alert_filter.stateChanged.connect(self.refresh)
        filter_layout.addWidget(self.service_alert_filter)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # ===== TABLE =====
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Vehicle ID", "Vehicle #", "Plate", "Make/Model", "Year", 
            "Type", "Mileage", "Status", "Next Service Due", "Alerts"
        ])
        self.table.doubleClicked.connect(self.open_detail)
        self.table.setSortingEnabled(True)  # ✅ Enable sorting on all columns
        layout.addWidget(self.table)
        
        self.setLayout(layout)
        # DON'T load data during __init__ - use lazy loading when widget is shown
    
    def showEvent(self, event):
        """Load data when widget is first shown (lazy loading)"""
        super().showEvent(event)
        if not self._data_loaded:
            self.refresh()
            self._data_loaded = True
    
    def go_back(self):
        """Return to Navigator tab"""
        parent = self.parent()
        while parent and not hasattr(parent, 'tabs'):
            parent = parent.parent()
        if parent and hasattr(parent, 'tabs'):
            parent.tabs.setCurrentIndex(0)  # Navigator is tab 0
    
    def refresh(self):
        """Reload vehicle list with filters"""
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
                    v.vehicle_id,
                    v.vehicle_number,
                    v.license_plate,
                    CONCAT(v.make, ' ', v.model) as make_model,
                    v.year,
                    v.vehicle_type,
                    COALESCE(v.odometer, 0) as current_mileage,
                    COALESCE(v.operational_status, 'active') as status,
                    v.next_service_due,
                    0 as alert_count
                FROM vehicles v
                WHERE 1=1
            """
            params = []
            
            # Make filter
            make_text = self.make_filter.text().strip()
            if make_text:
                query += " AND v.make ILIKE %s"
                params.append(f"%{make_text}%")
            
            # Type filter
            if self.type_filter.currentText() != "All Types":
                query += " AND v.vehicle_type = %s"
                params.append(self.type_filter.currentText())
            
            # Status filter (placeholder - status column doesn't exist)
            if self.status_filter.currentText() != "All":
                # Map UI status to database operational_status
                db_status = self.status_filter.currentText().lower()
                if db_status == "in service":
                    db_status = "in_service"
                query += " AND COALESCE(v.operational_status, 'active') = %s"
                params.append(db_status)
            
            query += " ORDER BY v.vehicle_number"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            self.table.setRowCount(len(rows) if rows else 0)
            
            if rows:
                for i, (vid, vnum, plate, make_model, yr, vtype, mileage, status, next_svc, alerts) in enumerate(rows):
                    self.table.setItem(i, 0, QTableWidgetItem(str(vid)))
                    self.table.setItem(i, 1, QTableWidgetItem(str(vnum or "")))
                    self.table.setItem(i, 2, QTableWidgetItem(str(plate or "")))
                    self.table.setItem(i, 3, QTableWidgetItem(str(make_model or "")))
                    self.table.setItem(i, 4, QTableWidgetItem(str(yr or "")))
                    self.table.setItem(i, 5, QTableWidgetItem(str(vtype or "")))
                    self.table.setItem(i, 6, QTableWidgetItem(f"{int(mileage or 0):,}"))
                    self.table.setItem(i, 7, QTableWidgetItem(str(status or "Active")))
                    self.table.setItem(i, 8, QTableWidgetItem(str(next_svc or "N/A")))
                    self.table.setItem(i, 9, QTableWidgetItem(str(alerts or 0)))
                    
                    # Visual alerts
                    # Placeholder: In real implementation, check next_service vs today
                    # if next_service < today: red
                    # if next_service < today + 7 days: yellow
            
            cur.close()
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load vehicles: {e}")
    
    def open_detail(self, index):
        """Open vehicle detail dialog on double-click"""
        row = index.row()
        vehicle_id = int(self.table.item(row, 0).text())
        
        dialog = VehicleDetailDialog(self.db, vehicle_id, self)
        dialog.saved.connect(lambda data: self.refresh())
        dialog.exec()
    
    def new_vehicle(self):
        """Create new vehicle"""
        dialog = VehicleDetailDialog(self.db, None, self)
        dialog.saved.connect(lambda data: self.refresh())
        dialog.exec()
    
    def edit_vehicle(self):
        """Edit selected vehicle"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            vehicle_id = int(self.table.item(current_row, 0).text())
            dialog = VehicleDetailDialog(self.db, vehicle_id, self)
            dialog.saved.connect(lambda data: self.refresh())
            dialog.exec()
        else:
            QMessageBox.warning(self, "Warning", "Please select a vehicle first")
    
    def retire_vehicle(self):
        """Retire selected vehicle"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            vehicle_id = int(self.table.item(current_row, 0).text())
            vehicle_num = self.table.item(current_row, 1).text()
            reply = QMessageBox.question(
                self, "Confirm Retire",
                f"Retire vehicle {vehicle_num}? This will set its status to retired.",
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
                    cur.execute("""
                        UPDATE vehicles 
                        SET operational_status = 'retired', 
                            is_active = FALSE,
                            lifecycle_status = 'decommissioned',
                            decommission_date = CURRENT_DATE
                        WHERE vehicle_id = %s
                    """, (vehicle_id,))
                    self.db.commit()
                    QMessageBox.information(self, "Success", f"Vehicle {vehicle_num} retired ✅")
                    self.refresh()
                except Exception as e:
                    try:
                        self.db.rollback()
                    except:
                        pass
                    QMessageBox.critical(self, "Error", f"Failed to retire vehicle: {e}")
        else:
            QMessageBox.warning(self, "Warning", "Please select a vehicle first")
    
    def mark_inactive(self):
        """Mark selected vehicle as inactive"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            vehicle_id = int(self.table.item(current_row, 0).text())
            vehicle_num = self.table.item(current_row, 1).text()
            reply = QMessageBox.question(
                self, "Confirm Mark Inactive",
                f"Mark vehicle {vehicle_num} as inactive? It can be reactivated later.",
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
                    cur.execute("""
                        UPDATE vehicles 
                        SET operational_status = 'out_of_service', 
                            is_active = FALSE
                        WHERE vehicle_id = %s
                    """, (vehicle_id,))
                    self.db.commit()
                    QMessageBox.information(self, "Success", f"Vehicle {vehicle_num} marked inactive ✅")
                    self.refresh()
                except Exception as e:
                    try:
                        self.db.rollback()
                    except:
                        pass
                    QMessageBox.critical(self, "Error", f"Failed to mark vehicle inactive: {e}")
        else:
            QMessageBox.warning(self, "Warning", "Please select a vehicle first")
