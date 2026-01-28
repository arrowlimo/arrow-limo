"""
Dispatch Management Widget
Real-time booking and vehicle dispatch management
Ported from frontend/src/views/Dispatch.vue
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QComboBox, QDialog,
    QDialogButtonBox, QSpinBox, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt, QDate

from desktop_app.common_widgets import StandardDateEdit
from PyQt6.QtGui import QColor, QFont
import psycopg2
from datetime import datetime
from desktop_app.drill_down_widgets import CharterDetailDialog


class DispatchManagementWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_bookings()

    def init_ui(self):
        """Initialize the dispatch UI"""
        layout = QVBoxLayout()

        # Statistics - REMOVED per user request (balloon cards not needed)
        # stats_layout = QHBoxLayout()
        # self.stat_active = self._create_stat_card("Active Bookings", "0", "#4caf50")
        # self.stat_available = self._create_stat_card("Available Vehicles", "0", "#2196f3")
        # self.stat_pending = self._create_stat_card("Pending Assignments", "0", "#ff9800")
        # self.stat_routes = self._create_stat_card("Active Routes", "0", "#9c27b0")
        # stats_layout.addWidget(self.stat_active)
        # stats_layout.addWidget(self.stat_available)
        # stats_layout.addWidget(self.stat_pending)
        # stats_layout.addWidget(self.stat_routes)
        # layout.addLayout(stats_layout)

        # Filters
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

        new_btn = QPushButton("➕ New Booking")
        new_btn.clicked.connect(self.new_booking)
        filter_layout.addWidget(new_btn)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Bookings table
        self.bookings_table = QTableWidget()
        self.bookings_table.setColumnCount(10)
        self.bookings_table.setHorizontalHeaderLabels([
            "Reserve #", "Date", "Client", "Vehicle Type", "Driver",
            "Status", "Passengers", "Capacity", "Pickup", "Notes"
        ])
        # Enable sorting by clicking column headers
        self.bookings_table.setSortingEnabled(True)
        # Enable horizontal scroll bar
        self.bookings_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.bookings_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        # Set resize mode to interactive for manual column sizing
        self.bookings_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Enable context menu for column operations
        self.bookings_table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bookings_table.horizontalHeader().customContextMenuRequested.connect(self.show_column_menu)
        self.bookings_table.itemSelectionChanged.connect(self.show_booking_details)
        self.bookings_table.itemDoubleClicked.connect(self.handle_double_click)
        layout.addWidget(self.bookings_table)
        
        # View controls
        view_controls = QHBoxLayout()
        reset_view_btn = QPushButton("🔄 Reset View")
        reset_view_btn.setToolTip("Reset columns to default widths and visibility")
        reset_view_btn.clicked.connect(self.reset_view)
        view_controls.addWidget(reset_view_btn)
        
        autofit_btn = QPushButton("↔️ Auto-fit Columns")
        autofit_btn.setToolTip("Automatically resize all columns to fit content")
        autofit_btn.clicked.connect(self.autofit_columns)
        view_controls.addWidget(autofit_btn)
        
        view_controls.addStretch()
        layout.addLayout(view_controls)

        # Details panel
        details_group = QGroupBox("Booking Details")
        details_layout = QFormLayout()
        
        self.detail_reserve = QLineEdit()
        self.detail_reserve.setReadOnly(True)
        self.detail_date = QLineEdit()
        self.detail_date.setReadOnly(True)
        self.detail_client = QLineEdit()
        self.detail_client.setReadOnly(True)
        self.detail_vehicle = QLineEdit()
        self.detail_vehicle.setReadOnly(True)
        self.detail_driver = QLineEdit()
        self.detail_driver.setReadOnly(True)
        self.detail_status = QComboBox()
        self.detail_status.addItems(["Pending", "Assigned", "Active", "Completed"])
        self.detail_passengers = QSpinBox()
        self.detail_passengers.setMaximum(99)
        self.detail_pickup = QTextEdit()
        self.detail_pickup.setFixedHeight(40)
        self.detail_notes = QTextEdit()
        self.detail_notes.setFixedHeight(60)

        button_layout = QHBoxLayout()
        update_btn = QPushButton("💾 Update Status")
        update_btn.clicked.connect(self.update_booking_status)
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.clicked.connect(self.delete_booking)
        open_charter_btn = QPushButton("🔎 Open Charter (Orders tab)")
        open_charter_btn.clicked.connect(self.open_selected_charter_orders_tab)
        button_layout.addWidget(update_btn)
        button_layout.addWidget(delete_btn)
        button_layout.addWidget(open_charter_btn)
        button_layout.addStretch()

        details_layout.addRow("Reserve Number", self.detail_reserve)
        details_layout.addRow("Charter Date", self.detail_date)
        details_layout.addRow("Client", self.detail_client)
        details_layout.addRow("Vehicle", self.detail_vehicle)
        details_layout.addRow("Driver", self.detail_driver)
        details_layout.addRow("Status", self.detail_status)
        details_layout.addRow("Passengers", self.detail_passengers)
        details_layout.addRow("Pickup Address", self.detail_pickup)
        details_layout.addRow("Notes", self.detail_notes)
        details_layout.addRow(button_layout)

        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

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

    def show_booking_details(self):
        """Show selected booking details"""
        selected = self.bookings_table.selectedItems()
        if not selected:
            return

        row = self.bookings_table.row(selected[0])
        booking = self.bookings_data[row] if row < len(self.bookings_data) else None

        if booking:
            self.current_charter_id = booking[0]
            self.detail_reserve.setText(str(booking[1] or ""))
            self.detail_date.setText(str(booking[2] or ""))
            self.detail_client.setText(str(booking[3] or ""))
            self.detail_vehicle.setText(str(booking[4] or ""))
            self.detail_driver.setText(str(booking[5] or ""))
    
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

    def update_booking_status(self):
        """Update booking status"""
        if not self.current_charter_id:
            QMessageBox.warning(self, "No Selection", "Please select a booking first.")
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
                "UPDATE charters SET payment_status = %s, vehicle_notes = %s WHERE charter_id = %s",
                (self.detail_status.currentText().lower(), self.detail_notes.toPlainText(), self.current_charter_id)
            )
            self.db.commit()
            QMessageBox.information(self, "Success", "Booking updated!")
            self.load_bookings()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to update: {e}")

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
