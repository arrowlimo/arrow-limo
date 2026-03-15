"""
Dispatch Management Widget
Real-time booking and vehicle dispatch management
Ported from frontend/src/views/Dispatch.vue
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QComboBox, QDialog,
    QDialogButtonBox, QSpinBox, QTextEdit, QSplitter, QDoubleSpinBox,
    QCheckBox, QScrollArea, QMenu
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal

from desktop_app.common_widgets import StandardDateEdit
from PyQt6.QtGui import QColor, QFont
import psycopg2
from datetime import datetime
from decimal import Decimal
from desktop_app.drill_down_widgets import CharterDetailDialog


class DispatchManagementWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_bookings()

    def init_ui(self):
        """Initialize the dispatch UI - Simple list view (no details panel)"""
        layout = QVBoxLayout()

        # Filters (top)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Client, vehicle, driver, address...")
        self.search_input.textChanged.connect(self.filter_bookings)
        filter_layout.addWidget(self.search_input)

        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Pending", "Assigned", "Active", "Completed"])
        self.status_filter.currentTextChanged.connect(self.filter_bookings)
        filter_layout.addWidget(self.status_filter)

        filter_layout.addWidget(QLabel("Date:"))
        self.date_filter = StandardDateEdit(prefer_month_text=True)
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.dateChanged.connect(self.filter_bookings)
        filter_layout.addWidget(self.date_filter)

        new_btn = QPushButton("➕ New Charter")
        new_btn.clicked.connect(self.new_booking)
        filter_layout.addWidget(new_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Bookings table (main list)
        self.bookings_table = QTableWidget()
        self.bookings_table.setColumnCount(10)
        self.bookings_table.setHorizontalHeaderLabels([
            "Reserve #", "Date", "Client", "Vehicle Type", "Driver",
            "Status", "Passengers", "Capacity", "Pickup", "Notes"
        ])
        self.bookings_table.setSortingEnabled(True)
        self.bookings_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.bookings_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.bookings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.bookings_table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bookings_table.horizontalHeader().customContextMenuRequested.connect(self.show_column_menu)
        self.bookings_table.itemDoubleClicked.connect(self.handle_double_click)
        layout.addWidget(self.bookings_table)
        
        # View controls
        view_controls = QHBoxLayout()
        reset_view_btn = QPushButton("🔄 Reset")
        reset_view_btn.setToolTip("Reset columns to default widths")
        reset_view_btn.clicked.connect(self.reset_view)
        view_controls.addWidget(reset_view_btn)
        
        autofit_btn = QPushButton("↔️ Auto-fit")
        autofit_btn.setToolTip("Auto-resize columns to fit content")
        autofit_btn.clicked.connect(self.autofit_columns)
        view_controls.addWidget(autofit_btn)
        
        view_controls.addStretch()
        layout.addLayout(view_controls)
        
        self.setLayout(layout)
        self.current_charter_id = None

    def _create_stat_card(self, label, value, color):
        """Create a statistics card"""
        group = QGroupBox()
        group.setStyleSheet(f"QGroupBox {{ border: 2px solid {color}; border-radius: 8px; }}")
        layout = QVBoxLayout()
        value_label = QLabel(value)
        value_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label = QLabel(label)
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(value_label)
        layout.addWidget(text_label)
        group.setLayout(layout)
        group.value_label = value_label
        return group

    def load_bookings(self):
        """Load all bookings from database"""
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
                SELECT 
                    charter_id, 
                    reserve_number, 
                    charter_date::date,
                    COALESCE(client_display_name, 'Unknown') as client_name,
                    vehicle_type_requested, 
                    COALESCE(driver_name, 'Unassigned') as driver,
                    COALESCE(payment_status, 'Pending') as status,
                    passenger_load, 
                    vehicle_description,
                    pickup_address, 
                    vehicle_notes
                FROM charters
                ORDER BY charter_date DESC LIMIT 500
            """)
            
            bookings = cur.fetchall()
            self.bookings_data = bookings
            self.display_bookings(bookings)
            self.update_statistics()

        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Load Error", f"Failed to load bookings: {e}")

    def display_bookings(self, bookings):
        """Display bookings in table"""
        self.bookings_table.setRowCount(len(bookings))
        for row_idx, booking in enumerate(bookings):
            cells = [
                str(booking[1] or ""),  # reserve_number
                str(booking[2] or ""),  # charter_date
                str(booking[3] or ""),  # client_name
                str(booking[4] or ""),  # vehicle_type
                str(booking[5] or ""),  # driver_name
                str(booking[6] or "Pending"),  # status
                str(booking[7] or ""),  # passenger_load
                str(booking[8] or ""),  # vehicle_capacity
                str(booking[9] or ""),  # pickup_address
                str(booking[10] or ""),  # notes
            ]
            for col_idx, cell in enumerate(cells):
                item = QTableWidgetItem(cell)
                # Color code status
                if col_idx == 5:  # Status column
                    status = booking[6] or "Pending"
                    if status == "Active":
                        item.setForeground(QColor("#4caf50"))
                    elif status == "Completed":
                        item.setForeground(QColor("#999"))
                    elif status == "Pending":
                        item.setForeground(QColor("#ff9800"))
                self.bookings_table.setItem(row_idx, col_idx, item)

    def filter_bookings(self):
        """Filter bookings based on search criteria"""
        search_text = self.search_input.text().lower()
        status_filter = self.status_filter.currentText()
        date_filter = self.date_filter.date().toString("MM/dd/yyyy")

        filtered = []
        for booking in self.bookings_data:
            # Apply search filter
            if search_text:
                if not any([
                    search_text in (booking[3] or "").lower(),  # client
                    search_text in (booking[4] or "").lower(),  # vehicle
                    search_text in (booking[5] or "").lower(),  # driver
                    search_text in (booking[9] or "").lower(),  # pickup
                    search_text in (booking[10] or "").lower(),  # notes
                ]):
                    continue

            # Apply status filter
            if status_filter != "All":
                if (booking[6] or "Pending").lower() != status_filter.lower():
                    continue

            # Apply date filter (optional - include all if no specific date selected)
            filtered.append(booking)

        self.display_bookings(filtered)

    def handle_double_click(self, item):
        """Handle double-click on table - open charter booking dialog"""
        row = item.row()
        booking = self.bookings_data[row] if row < len(self.bookings_data) else None
        
        if booking:
            reserve_number = booking[1]  # reserve_number is second column in query
            
            # Open charter detail dialog
            try:
                dialog = CharterDetailDialog(self.db, reserve_number=str(reserve_number), parent=self)
                dialog.exec()
                # Refresh the table after closing dialog
                self.load_bookings()
            except Exception as e:
                try:
                    self.db.rollback()
                except:
                    pass
                QMessageBox.warning(self, "Error", f"Failed to open charter details: {e}")

    def delete_booking(self):
        """Delete selected booking"""
        if not self.current_charter_id:
            QMessageBox.warning(self, "No Selection", "Please select a booking first.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete this booking?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Rollback any failed transactions first
                try:
                    self.db.rollback()
                except:
                    pass
                
                cur = self.db.get_cursor()
                cur.execute("DELETE FROM charters WHERE charter_id = %s", (self.current_charter_id,))
                self.db.commit()
                QMessageBox.information(self, "Success", "Booking deleted!")
                self.load_bookings()
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def new_booking(self):
        """Create new booking (placeholder)"""
        QMessageBox.information(self, "New Booking", "Booking creation will be implemented via modal form.")

    def open_selected_charter_orders_tab(self):
        """Open the Charter detail dialog focused on the Orders & Beverages tab for the selected booking."""
        selected = self.bookings_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a booking first.")
            return

        row = self.bookings_table.row(selected[0])
        booking = self.bookings_data[row] if row < len(self.bookings_data) else None
        if not booking:
            QMessageBox.warning(self, "No Selection", "Please select a booking first.")
            return

        reserve_number = booking[1]
        if not reserve_number:
            QMessageBox.warning(self, "Missing Reserve #", "Selected booking has no reserve number.")
            return

        try:
            dlg = CharterDetailDialog(self.db, reserve_number=str(reserve_number), parent=self, initial_tab='orders')
            dlg.exec()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Open Charter Failed", f"Could not open charter: {e}")

    def update_statistics(self):
        """Update statistics cards - DISABLED (stat cards removed per user request)"""
        # Statistics cards have been removed from the UI
        # This method is now a no-op to prevent errors
        pass

    def show_column_menu(self, pos):
        """Show context menu for column visibility toggling"""
        menu = QMenu(self)
        
        # Add "Show All Columns" action
        show_all = menu.addAction("Show All Columns")
        show_all.triggered.connect(lambda: self.toggle_all_columns(True))
        
        # Add "Hide All Columns" action
        hide_all = menu.addAction("Hide All Columns")
        hide_all.triggered.connect(lambda: self.toggle_all_columns(False))
        
        menu.addSeparator()
        
        # Add toggle action for each column
        for col in range(self.bookings_table.columnCount()):
            header_text = self.bookings_table.horizontalHeaderItem(col).text()
            action = menu.addAction(header_text)
            action.setCheckable(True)
            action.setChecked(not self.bookings_table.isColumnHidden(col))
            action.triggered.connect(lambda checked, c=col: self.bookings_table.setColumnHidden(c, not checked))
        
        menu.exec(self.bookings_table.horizontalHeader().mapToGlobal(pos))
    
    def toggle_all_columns(self, visible):
        """Show or hide all columns"""
        for col in range(self.bookings_table.columnCount()):
            self.bookings_table.setColumnHidden(col, not visible)
    
    def reset_view(self):
        """Reset columns to default widths and visibility"""
        # Default column widths
        default_widths = [120, 100, 200, 150, 150, 100, 80, 80, 250, 200]
        
        # Show all columns and set widths
        for col in range(self.bookings_table.columnCount()):
            self.bookings_table.setColumnHidden(col, False)
            if col < len(default_widths):
                self.bookings_table.setColumnWidth(col, default_widths[col])
        
        QMessageBox.information(self, "View Reset", "Column widths and visibility reset to defaults.")
    
    def autofit_columns(self):
        """Auto-resize all visible columns to fit content"""
        self.bookings_table.resizeColumnsToContents()
        QMessageBox.information(self, "Columns Resized", "All columns auto-fitted to content.")

    def load_full_charter_details(self, charter_id):
        """Load complete charter details from database for the details panel"""
        try:
            cur = self.db.get_cursor()
            
            # Get main charter details
            cur.execute("""
                SELECT 
                    reserve_number,
                    charter_date::date,
                    client_display_name,
                    vehicle_type_requested,
                    vehicle_assigned,
                    driver_name,
                    passenger_load,
                    pickup_time,
                    pickup_address,
                    dropoff_address,
                    route_description,
                    is_out_of_town,
                    charter_price,
                    extra_charges,
                    total_amount_due,
                    balance,
                    client_notes,
                    vehicle_notes,
                    payment_status
                FROM charters
                WHERE charter_id = %s
            """, (charter_id,))
            
            result = cur.fetchone()
            if result:
                self.detail_reserve.setText(str(result[0] or ""))
                self.detail_date.setText(str(result[1] or ""))
                self.detail_client.setText(str(result[2] or ""))
                self.detail_vehicle_requested.setText(str(result[3] or ""))
                self.detail_vehicle_assigned.setText(str(result[4] or ""))
                self.detail_driver.setText(str(result[5] or ""))
                self.detail_passengers.setValue(result[6] or 0)
                self.detail_pickup_time.setText(str(result[7] or ""))
                self.detail_pickup_location.setText(str(result[8] or ""))
                self.detail_destination.setText(str(result[9] or ""))
                self.detail_route_description.setPlainText(str(result[10] or ""))
                self.detail_out_of_town.setChecked(result[11] or False)
                self.detail_base_charge.setValue(float(result[12] or 0.0))
                self.detail_extra_charges.setValue(float(result[13] or 0.0))
                self.detail_total_amount.setText(f"${float(result[14] or 0.0):.2f}")
                self.detail_balance_due.setText(f"${float(result[15] or 0.0):.2f}")
                self.detail_client_notes.setPlainText(str(result[16] or ""))
                self.detail_dispatch_notes.setPlainText(str(result[17] or ""))
                
                # Set status
                status = str(result[18] or "pending").lower()
                for i in range(self.detail_status.count()):
                    if self.detail_status.itemText(i).lower() == status:
                        self.detail_status.setCurrentIndex(i)
                        break
            
            # Load beverages for this charter
            cur.execute("""
                SELECT order_line_item, quantity, unit_price
                FROM orders
                WHERE charter_id = %s AND order_category = 'beverage'
                ORDER BY order_line_number
            """, (charter_id,))
            
            beverages = cur.fetchall()
            self.beverage_table.setRowCount(len(beverages))
            bev_total = 0.0
            for idx, (item, qty, price) in enumerate(beverages):
                self.beverage_table.setItem(idx, 0, QTableWidgetItem(str(item or "")))
                self.beverage_table.setItem(idx, 1, QTableWidgetItem(str(qty or "")))
                price_val = float(price or 0.0)
                self.beverage_table.setItem(idx, 2, QTableWidgetItem(f"${price_val:.2f}"))
                bev_total += price_val
            
            self.beverage_total.setText(f"${bev_total:.2f}")
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading charter details: {e}")

    def insert_route_between(self):
        """Insert a new route/stop between pickup and dropoff"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Insert Route Between Pickup & Dropoff")
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        location_label = QLabel("New Location/Stop:")
        location_input = QLineEdit()
        location_input.setPlaceholderText("e.g., Hotel, Restaurant, Airport")
        form_layout.addRow(location_label, location_input)
        
        order_label = QLabel("Insert Position:")
        order_combo = QComboBox()
        order_combo.addItems(["After Pickup", "Before Dropoff"])
        form_layout.addRow(order_label, order_combo)
        
        layout.addLayout(form_layout)
        
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.setLayout(layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_location = location_input.text().strip()
            if new_location:
                # Append to route description
                current_route = self.detail_route_description.toPlainText()
                if order_combo.currentText() == "After Pickup":
                    new_route = f"{new_location} → {current_route}"
                else:
                    new_route = f"{current_route} → {new_location}"
                self.detail_route_description.setPlainText(new_route)
                QMessageBox.information(self, "Route Updated", "Route has been updated. Click 'Save Changes' to commit.")
            else:
                QMessageBox.warning(self, "Empty Location", "Please enter a location.")
    
