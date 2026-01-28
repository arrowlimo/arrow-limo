"""
Enhanced Charter Dashboard with Drill-Down and Filtering
Demonstrates the new drill-down capability across all charter-related dashboards
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QDoubleSpinBox, QComboBox, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
from datetime import datetime
from table_mixins import DrillDownTableMixin
from drill_down_widgets import CharterDetailDialog
from driver_calendar_widget import DriverCalendarWidget
from dispatcher_calendar_widget import DispatcherCalendarWidget
from desktop_app.ui_standards import enable_fuzzy_search


class DateInput(QLineEdit):
    """Flexible date input field that accepts multiple formats like Excel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        today = QDate.currentDate()
        self._current_date = today
        self.setText(today.toString("MM/dd/yyyy"))
        self.setPlaceholderText("MM/DD/YYYY or Jan 01 2012")
        self.setMaxLength(50)  # Allow long text formats
        
        # Validation color support
        self._validation_state = 'valid'
        self.setStyleSheet("QLineEdit { border: 1px solid #ccc; background-color: white; }")
        
        # Rich tooltip with format examples
        self.setToolTip(
            "<b>📅 Date Input</b><br>"
            "<font color='green'><b>Flexible formats:</b></font><br>"
            "• 01/15/2012 or 01-15-2012<br>"
            "• Jan 01 2012 or January 1 2012<br>"
            "• 20120115 (compact)<br>"
            "• 2012-01-15 (ISO)<br>"
            "<font color='blue'><b>Shortcuts:</b> t=today, y=yesterday</font><br>"
            "Just type and press Enter or Tab"
        )
    
    def setDate(self, date):
        """Set date and update display"""
        self._current_date = date
        self.setText(date.toString("MM/dd/yyyy"))
    
    def getDate(self):
        """Get current date as QDate"""
        return self._current_date
    
    def focusInEvent(self, event):
        """Select all text when field gets focus for easy replacement"""
        super().focusInEvent(event)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self.selectAll)
    
    def mouseDoubleClickEvent(self, event):
        """Allow double-click to position cursor for editing"""
        super().mouseDoubleClickEvent(event)
    
    def focusOutEvent(self, event):
        """Parse and format when user leaves the field"""
        super().focusOutEvent(event)
        self._parse_and_format()
    
    def keyPressEvent(self, event):
        """Handle shortcuts and Enter key"""
        text = self.text().strip()
        
        # Shortcuts
        if text.lower() == 't' and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            self.setDate(QDate.currentDate())
            self.setStyleSheet("QLineEdit { border: 2px solid green; background-color: #f0fff0; }")
            event.accept()
            return
        elif text.lower() == 'y' and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            self.setDate(QDate.currentDate().addDays(-1))
            self.setStyleSheet("QLineEdit { border: 2px solid green; background-color: #f0fff0; }")
            event.accept()
            return
        
        super().keyPressEvent(event)
    
    def _parse_and_format(self):
        """Parse flexible date formats and format for database storage"""
        text = self.text().strip()

        if not text:
            self.setText(self._current_date.toString("MM/dd/yyyy"))
            self.setStyleSheet("QLineEdit { border: 1px solid #ccc; background-color: white; }")
            return

        # Try multiple formats
        parsed = None
        
        # Format 1: MM/dd/yyyy or MM-dd-yyyy
        for fmt in ["MM/dd/yyyy", "MM-dd-yyyy", "M/d/yyyy", "M-d-yyyy"]:
            parsed = QDate.fromString(text, fmt)
            if parsed.isValid():
                break
        
        # Format 2: yyyymmdd (compact)
        if not parsed or not parsed.isValid():
            if len(text) == 8 and text.isdigit():
                parsed = QDate.fromString(text, "yyyyMMdd")
        
        # Format 3: "Jan 01 2012" or "January 1 2012"
        if not parsed or not parsed.isValid():
            for fmt in ["MMM dd yyyy", "MMMM d yyyy", "MMM d yyyy", "MMMM dd yyyy"]:
                parsed = QDate.fromString(text, fmt)
                if parsed.isValid():
                    break
        
        # Format 4: "01 Jan 2012" (day first)
        if not parsed or not parsed.isValid():
            for fmt in ["dd MMM yyyy", "d MMM yyyy", "dd MMMM yyyy", "d MMMM yyyy"]:
                parsed = QDate.fromString(text, fmt)
                if parsed.isValid():
                    break
        
        # Format 5: ISO format yyyy-MM-dd
        if not parsed or not parsed.isValid():
            parsed = QDate.fromString(text, "yyyy-MM-dd")
        
        # If valid, update and format
        if parsed and parsed.isValid():
            self._current_date = parsed
            self.setText(parsed.toString("MM/dd/yyyy"))
            self._validation_state = 'valid'
            self.setStyleSheet("QLineEdit { border: 2px solid green; background-color: #f0fff0; }")
        else:
            # Invalid date - restore previous
            self.setText(self._current_date.toString("MM/dd/yyyy"))
            self._validation_state = 'error'
            self.setStyleSheet("QLineEdit { border: 2px solid red; background-color: #fff0f0; }")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: self.setStyleSheet("QLineEdit { border: 1px solid #ccc; background-color: white; }"))


class EnhancedCharterListWidget(QWidget, DrillDownTableMixin):
    """
    Enhanced charter list with:
    - Double-click to open detail view
    - Inline filtering
    - Lock/unlock, cancel, edit actions
    - Balance due filtering
    """
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._data_loaded = False
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("📋 Charter Management - Enhanced")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Filter by:"))
        
        # Reserve number filter
        self.res_filter = QLineEdit()
        self.res_filter.setPlaceholderText("Reserve #...")
        self.res_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Reserve #:"))
        filter_layout.addWidget(self.res_filter)
        self.res_filter.setMaximumWidth(120)
        
        # Client name filter (fuzzy)
        self.client_filter = QLineEdit()
        self.client_filter.setPlaceholderText("Client name...")
        self.client_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Client:"))
        filter_layout.addWidget(self.client_filter)
        self.client_filter.setMinimumWidth(150)
        
        # Date range filters with quick presets
        filter_layout.addWidget(QLabel("📅 Date:"))
        
        # Quick preset buttons
        today_btn = QPushButton("Today")
        today_btn.setMaximumWidth(70)
        today_btn.clicked.connect(self._set_date_today)
        filter_layout.addWidget(today_btn)
        
        week_btn = QPushButton("Week")
        week_btn.setMaximumWidth(70)
        week_btn.clicked.connect(self._set_date_week)
        filter_layout.addWidget(week_btn)
        
        month_btn = QPushButton("Month")
        month_btn.setMaximumWidth(70)
        month_btn.clicked.connect(self._set_date_month)
        filter_layout.addWidget(month_btn)
        
        year_btn = QPushButton("Year")
        year_btn.setMaximumWidth(70)
        year_btn.clicked.connect(self._set_date_year)
        filter_layout.addWidget(year_btn)
        
        filter_layout.addWidget(QLabel("From:"))
        self.date_from = DateInput()
        self.date_from.textChanged.connect(self._on_date_from_changed)
        filter_layout.addWidget(self.date_from)
        self.date_from.setMaximumWidth(120)
        
        filter_layout.addWidget(QLabel("To:"))
        self.date_to = DateInput()
        self.date_to.textChanged.connect(self._on_date_to_changed)
        filter_layout.addWidget(self.date_to)
        self.date_to.setMaximumWidth(120)
        
        clear_dates_btn = QPushButton("Clear")
        clear_dates_btn.clicked.connect(self._clear_dates)
        clear_dates_btn.setMaximumWidth(70)
        filter_layout.addWidget(clear_dates_btn)
        
        # Balance filter
        filter_layout.addWidget(QLabel("Min Balance:"))
        self.balance_filter = QDoubleSpinBox()
        self.balance_filter.setMinimum(0)
        self.balance_filter.setMaximum(999999)
        self.balance_filter.setValue(0)
        self.balance_filter.valueChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.balance_filter)
        self.balance_filter.setMaximumWidth(100)
        
        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Pending", "Confirmed", "In Progress", "Completed", "Cancelled"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.status_filter)
        self.status_filter.setMaximumWidth(120)
        
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Charter table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Reserve #", "Client", "Date", "Driver", "Vehicle",
            "Status", "Total Due", "Balance Due"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(self.on_charter_double_clicked)
        self.table.setSortingEnabled(True)  # ✅ Enable sorting on all columns
        layout.addWidget(self.table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        new_charter_btn = QPushButton("➕ New Charter")
        new_charter_btn.clicked.connect(self.create_new_charter)
        button_layout.addWidget(new_charter_btn)
        
        edit_btn = QPushButton("✏️ Edit Selected")
        edit_btn.clicked.connect(self.edit_selected)
        button_layout.addWidget(edit_btn)
        
        lock_btn = QPushButton("🔒 Lock Selected")
        lock_btn.clicked.connect(self.lock_selected)
        button_layout.addWidget(lock_btn)
        
        cancel_btn = QPushButton("❌ Cancel Selected")
        cancel_btn.clicked.connect(self.cancel_selected)
        button_layout.addWidget(cancel_btn)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_data)
        button_layout.addWidget(refresh_btn)

        # Calendars (accessible from Booking)
        cal_btn = QPushButton("🗓️ Driver Calendar")
        cal_btn.clicked.connect(self.open_driver_calendar)
        button_layout.addWidget(cal_btn)

        disp_cal_btn = QPushButton("🗓️ Dispatcher Calendar")
        disp_cal_btn.clicked.connect(self.open_dispatcher_calendar)
        button_layout.addWidget(disp_cal_btn)
        
        layout.addLayout(button_layout)
        
        # Status bar
        self.status_label = QLabel("Ready - Filters apply automatically as you type")
        self.status_label.setStyleSheet("color: #555; font-style: italic;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        # DON'T load data during __init__ - use lazy loading when widget is shown
    
    def _set_date_today(self):
        """Set date range to today only"""
        today = QDate.currentDate()
        self.date_from.setDate(today)
        self.date_to.setDate(today)
        self.load_data()
    
    def _set_date_week(self):
        """Set date range to this week (Mon-Sun)"""
        today = QDate.currentDate()
        # Monday of this week
        monday = today.addDays(1 - today.dayOfWeek())
        # Sunday of this week
        sunday = monday.addDays(6)
        self.date_from.setDate(monday)
        self.date_to.setDate(sunday)
        self.load_data()
    
    def _set_date_month(self):
        """Set date range to this month"""
        today = QDate.currentDate()
        # First day of month
        first = QDate(today.year(), today.month(), 1)
        # Last day of month
        next_month = today.month() + 1 if today.month() < 12 else 1
        next_year = today.year() if today.month() < 12 else today.year() + 1
        last = QDate(next_year, next_month, 1).addDays(-1)
        self.date_from.setDate(first)
        self.date_to.setDate(last)
        self.load_data()
    
    def _set_date_year(self):
        """Set date range to this year"""
        today = QDate.currentDate()
        # First day of year
        jan1 = QDate(today.year(), 1, 1)
        # Last day of year (or today if current year)
        dec31 = QDate(today.year(), 12, 31)
        self.date_from.setDate(jan1)
        self.date_to.setDate(dec31 if dec31 <= today else today)
        self.load_data()
    
    def _on_date_from_changed(self):
        """Auto-fill 'To' date when 'From' date is completed, then reload data"""
        from_text = self.date_from.text()
        to_text = self.date_to.text()
        
        # If From date is valid (10 chars) and To date is empty or still default (today), auto-fill
        if len(from_text) == 10:
            parsed_from = QDate.fromString(from_text, "MM/dd/yyyy")
            if parsed_from.isValid():
                # Only auto-fill if To is empty or hasn't been manually changed
                if not to_text or len(to_text) < 10:
                    self.date_to.setDate(parsed_from)
                
                # Reload data with new date filter
                self.load_data()
    
    def _on_date_to_changed(self):
        """Reload data when 'To' date is completed"""
        to_text = self.date_to.text()
        
        if len(to_text) == 10:
            parsed_to = QDate.fromString(to_text, "MM/dd/yyyy")
            if parsed_to.isValid():
                self.load_data()
    
    def _clear_dates(self):
        """Clear both date fields and reset to today"""
        today = QDate.currentDate()
        self.date_from.setDate(today)
        self.date_to.setDate(today)
    
    def showEvent(self, event):
        """Load data when widget is first shown (lazy loading)"""
        super().showEvent(event)
        if not self._data_loaded:
            self.load_data()
            self._data_loaded = True
    
    def load_data(self):
        """Load charters from database with optional filters applied"""
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
            
            # Build WHERE clause for SQL filtering
            where_clauses = []
            params = []
            
            # Parse date filters from DateInput fields
            date_from_text = self.date_from.text().strip()
            date_to_text = self.date_to.text().strip()
            
            if len(date_from_text) == 10:
                date_from_obj = QDate.fromString(date_from_text, "MM/dd/yyyy")
                if date_from_obj.isValid():
                    where_clauses.append("c.charter_date >= %s")
                    params.append(date_from_obj.toString("yyyy-MM-dd"))
            
            if len(date_to_text) == 10:
                date_to_obj = QDate.fromString(date_to_text, "MM/dd/yyyy")
                if date_to_obj.isValid():
                    where_clauses.append("c.charter_date <= %s")
                    params.append(date_to_obj.toString("yyyy-MM-dd"))
            
            # Build WHERE clause
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Load charters with SQL-level date filtering
            query = f"""
                SELECT 
                    c.reserve_number,
                    COALESCE(cl.company_name, cl.client_name),
                    c.charter_date::date,
                    e.full_name,
                    v.vehicle_number,
                    c.booking_status,
                    c.total_amount_due,
                    COALESCE(c.total_amount_due - 
                        (SELECT COALESCE(SUM(amount), 0) FROM payments 
                         WHERE reserve_number = c.reserve_number), 
                        c.total_amount_due) as balance_due
                FROM charters c
                LEFT JOIN clients cl ON c.client_id = cl.client_id
                LEFT JOIN employees e ON c.employee_id = e.employee_id
                LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
                WHERE {where_sql}
                ORDER BY c.charter_date DESC
            """
            
            cur.execute(query, params)
            
            rows = cur.fetchall()
            self.all_data = rows  # Store for filtering
            
            self.table.setRowCount(len(rows))
            
            for i, row in enumerate(rows):
                res_num, client, date, driver, vehicle, status, total, balance = row
                
                self.table.setItem(i, 0, QTableWidgetItem(str(res_num or "")))
                self.table.setItem(i, 1, QTableWidgetItem(str(client or "")))
                self.table.setItem(i, 2, QTableWidgetItem(str(date or "")))
                self.table.setItem(i, 3, QTableWidgetItem(str(driver or "")))
                self.table.setItem(i, 4, QTableWidgetItem(str(vehicle or "")))
                self.table.setItem(i, 5, QTableWidgetItem(str(status or "")))
                self.table.setItem(i, 6, QTableWidgetItem(f"${float(total or 0):,.2f}"))
                self.table.setItem(i, 7, QTableWidgetItem(f"${float(balance or 0):,.2f}"))
            
            # Apply client-side filters after loading
            self.apply_filters()
            
            cur.close()
            self.db.commit()
        except Exception as e:
            try:
                self.db.rollback()
            except:
                try:
                    self.db.rollback()
                except:
                    pass
                pass
            QMessageBox.critical(self, "Error", f"Failed to load charters: {e}")
            self.status_label.setText(f"Error: {e}")
    
    def apply_filters(self):
        """Apply filters to table"""
        res_filter = self.res_filter.text().lower()
        client_filter = self.client_filter.text().lower()
        balance_min = self.balance_filter.value()
        status_filter = self.status_filter.currentText()
        
        # Parse date filters (DateInput format: MM/DD/YYYY -> convert to comparable format)
        date_from_obj = None
        date_to_obj = None
        try:
            date_from_text = self.date_from.text().strip()
            if date_from_text and len(date_from_text) == 10:
                date_from_obj = QDate.fromString(date_from_text, "MM/dd/yyyy")
        except:
            try:
                self.db.rollback()
            except:
                pass
            pass
        
        try:
            date_to_text = self.date_to.text().strip()
            if date_to_text and len(date_to_text) == 10:
                date_to_obj = QDate.fromString(date_to_text, "MM/dd/yyyy")
        except:
            try:
                self.db.rollback()
            except:
                pass
            pass
        
        visible_count = 0
        for i in range(self.table.rowCount()):
            res_num = self.table.item(i, 0).text().lower()
            client_name = self.table.item(i, 1).text().lower()
            date_str = self.table.item(i, 2).text()
            status = self.table.item(i, 5).text()
            balance_text = self.table.item(i, 7).text()
            balance = float(balance_text.replace("$", "").replace(",", "")) if balance_text else 0
            
            # Apply filters
            show = True
            
            # Reserve number filter
            if res_filter and res_filter not in res_num:
                show = False
            
            # Client name filter (fuzzy match)
            if client_filter and client_filter not in client_name:
                show = False
            
            # Date range filters (compare QDate objects)
            if date_from_obj and date_from_obj.isValid():
                row_date = QDate.fromString(date_str, "yyyy-MM-dd")
                if row_date.isValid() and row_date < date_from_obj:
                    show = False
            
            if date_to_obj and date_to_obj.isValid():
                row_date = QDate.fromString(date_str, "yyyy-MM-dd")
                if row_date.isValid() and row_date > date_to_obj:
                    show = False
            
            # Balance filter
            if balance < balance_min:
                show = False
            
            # Status filter
            if status_filter != "All" and status != status_filter:
                show = False
            
            self.table.setRowHidden(i, not show)
            if show:
                visible_count += 1
        
        # Update status with filter info
        if visible_count == self.table.rowCount():
            self.status_label.setText(f"Showing all {visible_count} charters - Auto-filtering as you type")
        else:
            self.status_label.setText(f"⚡ Showing {visible_count} of {self.table.rowCount()} charters (filtered)")
        self.status_label.setStyleSheet("color: #555; font-style: italic;")
    
    def on_charter_double_clicked(self, index):
        """Open charter detail on double-click"""
        row = index.row()
        if row >= 0:
            res_num = self.table.item(row, 0).text()
            self.open_charter_detail(res_num)
    
    def open_charter_detail(self, reserve_number):
        """Open charter detail dialog"""
        dialog = CharterDetailDialog(self.db, reserve_number, self)
        result = dialog.exec()
        if result:
            self.load_data()  # Refresh after changes
    
    def create_new_charter(self):
        """Create new charter"""
        dialog = CharterDetailDialog(self.db, None, self)
        result = dialog.exec()
        if result:
            self.load_data()
    
    def edit_selected(self):
        """Edit selected charter"""
        row = self.table.currentRow()
        if row >= 0:
            res_num = self.table.item(row, 0).text()
            self.open_charter_detail(res_num)
        else:
            QMessageBox.warning(self, "Warning", "Please select a charter first")
    
    def lock_selected(self):
        """Lock selected charter"""
        row = self.table.currentRow()
        if row >= 0:
            res_num = self.table.item(row, 0).text()
            try:
                cur = self.db.get_cursor()
                cur.execute("UPDATE charters SET is_locked = true WHERE reserve_number = %s",
                           (res_num,))
                self.db.commit()
                QMessageBox.information(self, "Success", f"Charter {res_num} locked")
                self.load_data()
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Error", f"Failed to lock charter: {e}")
        else:
            QMessageBox.warning(self, "Warning", "Please select a charter first")
    
    def cancel_selected(self):
        """Cancel selected charter"""
        row = self.table.currentRow()
        if row >= 0:
            res_num = self.table.item(row, 0).text()
            reply = QMessageBox.question(self, "Confirm", f"Cancel charter {res_num}?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    cur = self.db.get_cursor()
                    cur.execute("UPDATE charters SET booking_status = 'cancelled' WHERE reserve_number = %s",
                               (res_num,))
                    self.db.commit()
                    QMessageBox.information(self, "Success", f"Charter {res_num} cancelled")
                    self.load_data()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to cancel charter: {e}")
                    self.db.rollback()
        else:
            QMessageBox.warning(self, "Warning", "Please select a charter first")

    # ===== Calendars =====
    def open_driver_calendar(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Driver Calendar")
        lay = QVBoxLayout(dlg)
        lay.addWidget(DriverCalendarWidget(self.db))
        dlg.resize(1100, 700)
        dlg.exec()

    def open_dispatcher_calendar(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Dispatcher Calendar")
        lay = QVBoxLayout(dlg)
        lay.addWidget(DispatcherCalendarWidget(self.db))
        dlg.resize(1100, 700)
        dlg.exec()
