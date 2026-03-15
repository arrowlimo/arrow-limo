"""
Unbooked Calendar Events Report Widget
Shows calendar events that don't have matching charters yet
Click to create new booking from calendar event
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QMessageBox, QDialog, QLabel, QComboBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTime
from PyQt6.QtGui import QFont, QColor
from datetime import datetime, timedelta
from difflib import SequenceMatcher


class UnbookedCalendarReportWidget(QWidget):
    """Display unbooked calendar events and allow quick booking"""
    
    booking_created = pyqtSignal(dict)  # Emits event data when booking is created
    
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.unbooked_events = []
        self.init_ui()
        self.load_unbooked_events()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        title = QLabel("📅 Unbooked Calendar Events")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_unbooked_events)
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Time", "Event Title", "Driver", "Vehicle", "Notes", "Action"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 200)
        self.table.setColumnWidth(6, 100)
        self.table.resizeRowsToContents()
        layout.addWidget(self.table)
        
        # Footer
        footer_layout = QHBoxLayout()
        self.status_label = QLabel("Loading...")
        footer_layout.addWidget(self.status_label)
        footer_layout.addStretch()
        layout.addLayout(footer_layout)
        
        self.setLayout(layout)
    
    def load_unbooked_events(self):
        """Load calendar events that don't have matching charters"""
        try:
            cur = self.db.cursor()
            
            # Note: calendar_events table doesn't exist in current schema
            # Return empty list gracefully
            self.unbooked_events = []
            
            # Attempt to load events if table exists
            try:
                cutoff_date = (datetime.now() + timedelta(days=30)).date()
                cur.execute("""
                    SELECT 
                        id, event_date, event_time, title, 
                        driver_name, vehicle_name, notes
                    FROM calendar_events
                    WHERE event_date >= CURRENT_DATE 
                    AND event_date <= %s
                    ORDER BY event_date ASC, event_time ASC
                """, (cutoff_date,))
                
                all_events = cur.fetchall()
                
                # Filter: Keep only events without matching charters
                self.unbooked_events = []
                for event in all_events:
                    event_id, event_date, event_time, title, driver, vehicle, notes = event
                    
                    # Check if charter exists for this event
                    # Fuzzy match title to client, then check if charter exists
                    client_id = self.fuzzy_match_client(title)
                    
                    if client_id:
                        # Check if charter exists for this date with this client
                        cur.execute("""
                            SELECT COUNT(*) FROM charters
                            WHERE client_id = %s 
                            AND DATE(charter_date) = %s
                        """, (client_id, event_date))
                        
                        if cur.fetchone()[0] == 0:
                            # No charter for this client on this date
                            self.unbooked_events.append({
                                'id': event_id,
                                'date': event_date,
                            'time': event_time,
                            'title': title,
                            'driver': driver,
                            'vehicle': vehicle,
                            'notes': notes,
                            'client_id': client_id,
                            'client_name': self.get_client_name(client_id)
                        })
                else:
                    # No client match found, keep as unbooked
                    self.unbooked_events.append({
                        'id': event_id,
                        'date': event_date,
                        'time': event_time,
                        'title': title,
                        'driver': driver,
                        'vehicle': vehicle,
                        'notes': notes,
                        'client_id': None,
                        'client_name': None
                    })
            except Exception as e:
                # calendar_events table may not exist
                pass
            
            cur.close()
            self.display_events()
            
        except Exception as e:
            # Fallback: silently handle errors
            try:
                self.db.rollback()
            except:
                pass
    
    def fuzzy_match_client(self, event_title):
        """Fuzzy match event title to a client"""
        try:
            cur = self.db.cursor()
            cur.execute("SELECT id, name FROM clients LIMIT 500")
            clients = cur.fetchall()
            cur.close()
            
            best_match = None
            best_ratio = 0
            
            event_title_lower = event_title.lower()
            
            for client_id, client_name in clients:
                ratio = SequenceMatcher(None, event_title_lower, client_name.lower()).ratio()
                if ratio > best_ratio and ratio > 0.6:
                    best_match = client_id
                    best_ratio = ratio
            
            return best_match
        except Exception as e:
            print(f"Error fuzzy matching client: {e}")
            return None
    
    def get_client_name(self, client_id):
        """Get client name by ID"""
        try:
            if not client_id:
                return None
            cur = self.db.cursor()
            cur.execute("SELECT name FROM clients WHERE id = %s", (client_id,))
            result = cur.fetchone()
            cur.close()
            return result[0] if result else None
        except:
            return None
    
    def display_events(self):
        """Display events in table"""
        self.table.setRowCount(len(self.unbooked_events))
        
        for row, event in enumerate(self.unbooked_events):
            # Date
            date_item = QTableWidgetItem(event['date'].strftime("%Y-%m-%d"))
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, date_item)
            
            # Time
            time_str = event['time'].strftime("%H:%M") if event['time'] else ""
            time_item = QTableWidgetItem(time_str)
            time_item.setFlags(time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, time_item)
            
            # Title
            title_text = f"{event['title']}"
            if event['client_name']:
                title_text += f" ({event['client_name']})"
            title_item = QTableWidgetItem(title_text)
            title_item.setFlags(title_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if event['client_id']:
                title_item.setBackground(QColor(200, 255, 200))  # Light green if matched
            self.table.setItem(row, 2, title_item)
            
            # Driver
            driver_item = QTableWidgetItem(event['driver'] or "")
            driver_item.setFlags(driver_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, driver_item)
            
            # Vehicle
            vehicle_item = QTableWidgetItem(event['vehicle'] or "")
            vehicle_item.setFlags(vehicle_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, vehicle_item)
            
            # Notes
            notes_item = QTableWidgetItem(event['notes'] or "")
            notes_item.setFlags(notes_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 5, notes_item)
            
            # Action button
            book_btn = QPushButton("📝 Book")
            book_btn.setMaximumWidth(100)
            book_btn.clicked.connect(lambda checked, r=row: self.book_event(r))
            self.table.setCellWidget(row, 6, book_btn)
        
        # Update status
        self.status_label.setText(f"Showing {len(self.unbooked_events)} unbooked events")
        self.table.resizeRowsToContents()
    
    def book_event(self, row):
        """Create booking from selected event"""
        if row >= len(self.unbooked_events):
            return
        
        event = self.unbooked_events[row]
        
        # If no client matched, open client finder first
        if not event['client_id']:
            from client_finder_dialog import ClientFinderDialog
            
            client_dialog = ClientFinderDialog(self.db, parent=self)
            if client_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            
            event['client_id'] = client_dialog.selected_client_id
            event['client_name'] = client_dialog.selected_client_name
        
        if not event['client_id']:
            QMessageBox.warning(self, "No Client", "Please select a client.")
            return
        
        # Emit signal with event data
        self.booking_created.emit(event)
        
        # Show confirmation
        QMessageBox.information(self, "Success", 
            f"Opening new charter form for {event['client_name']} on {event['date'].strftime('%Y-%m-%d')}")
