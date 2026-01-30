"""
Dispatch Management Widget
Simple booking list view - drill-down to full charter form
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QComboBox, QMenu, QDialog
)
from PyQt6.QtCore import Qt, QDate

from desktop_app.common_widgets import StandardDateEdit
from PyQt6.QtGui import QColor


class DispatchManagementWidget(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.load_bookings()

    def init_ui(self):
        """Initialize the dispatch UI - Simple list view"""
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
        self.bookings_data = []

    def load_bookings(self):
        """Load all bookings from database"""
        try:
            try:
                self.db.rollback()
            except:
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

            filtered.append(booking)

        self.display_bookings(filtered)
    
    def handle_double_click(self, item):
        """Handle double-click on table - open charter booking form (auto-filled)"""
        row = item.row()
        if row < 0 or row >= len(self.bookings_data):
            return
            
        booking = self.bookings_data[row]
        charter_id = booking[0]  # charter_id
        
        # Open charter form with existing data
        try:
            from main import CharterFormWidget
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Charter Booking - {booking[1]}")
            dialog.setGeometry(100, 100, 1400, 800)
            
            layout = QVBoxLayout()
            charter_form = CharterFormWidget(self.db, charter_id=charter_id)
            charter_form.saved.connect(lambda: self.on_charter_saved(dialog))
            layout.addWidget(charter_form)
            dialog.setLayout(layout)
            
            dialog.exec()
            # Refresh the table after closing dialog
            self.load_bookings()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Error", f"Failed to open charter: {e}")

    def new_booking(self):
        """Create new booking - check calendar first, then client finder, then open charter form"""
        try:
            from calendar_event_finder_dialog import CalendarEventFinderDialog
            from client_finder_dialog import ClientFinderDialog
            from main import CharterFormWidget
            from datetime import datetime, date
            
            # Step 1: Check for calendar events
            calendar_dialog = CalendarEventFinderDialog(self.db, parent=self)
            if calendar_dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled
            
            event_data = calendar_dialog.selected_event
            client_id = calendar_dialog.selected_client_id
            client_name = calendar_dialog.selected_client_name
            
            # Step 2: If "Now" button was clicked, need to select client
            if event_data and event_data.get('is_now'):
                client_dialog = ClientFinderDialog(self.db, parent=self)
                if client_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                client_id = client_dialog.selected_client_id
                client_name = client_dialog.selected_client_name
                event_data = {
                    'date': date.today(),
                    'time': datetime.now().time(),
                    'driver': None,
                    'vehicle': None,
                    'notes': None
                }
            # Step 3: If no calendar event, open client finder
            elif not event_data:
                client_dialog = ClientFinderDialog(self.db, parent=self)
                if client_dialog.exec() != QDialog.DialogCode.Accepted:
                    return
                client_id = client_dialog.selected_client_id
                client_name = client_dialog.selected_client_name
                event_data = None
            
            if not client_id:
                QMessageBox.warning(self, "No Client", "Please select or create a client.")
                return
            
            # Step 4: Open charter form with pre-filled data
            dialog = QDialog(self)
            dialog.setWindowTitle(f"New Charter - {client_name}")
            dialog.setGeometry(100, 100, 1400, 800)
            
            layout = QVBoxLayout()
            charter_form = CharterFormWidget(self.db, charter_id=None, client_id=client_id)
            
            # Pre-fill with calendar event data if available
            if event_data:
                self.prefill_charter_from_event(charter_form, event_data)
            
            charter_form.saved.connect(lambda: self.on_charter_saved(dialog))
            layout.addWidget(charter_form)
            dialog.setLayout(layout)
            
            dialog.exec()
            # Refresh the table after closing dialog
            self.load_bookings()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to create charter: {e}")
    
    def prefill_charter_from_event(self, charter_form, event_data):
        """Pre-fill charter form fields from calendar event data"""
        try:
            from datetime import datetime, date
            from PyQt6.QtCore import QDate, QTime
            
            if event_data.get('date'):
                date_obj = event_data['date']
                if hasattr(charter_form, 'charter_date'):
                    charter_form.charter_date.setDate(QDate(date_obj.year, date_obj.month, date_obj.day))
            
            if event_data.get('time'):
                time_obj = event_data['time']
                if hasattr(charter_form, 'pickup_time'):
                    charter_form.pickup_time.setTime(QTime(time_obj.hour, time_obj.minute))
            
            if event_data.get('driver'):
                if hasattr(charter_form, 'driver_combo'):
                    for i in range(charter_form.driver_combo.count()):
                        if event_data['driver'] in charter_form.driver_combo.itemText(i):
                            charter_form.driver_combo.setCurrentIndex(i)
                            break
            
            if event_data.get('vehicle'):
                if hasattr(charter_form, 'vehicle_combo'):
                    for i in range(charter_form.vehicle_combo.count()):
                        if event_data['vehicle'] in charter_form.vehicle_combo.itemText(i):
                            charter_form.vehicle_combo.setCurrentIndex(i)
                            break
            
            if event_data.get('notes'):
                if hasattr(charter_form, 'dispatcher_notes'):
                    charter_form.dispatcher_notes.setPlainText(event_data['notes'])
        
        except Exception as e:
            print(f"Error prefilling from event: {e}")

    def on_charter_saved(self, dialog):
        """Callback when charter is saved"""
        dialog.accept()

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
