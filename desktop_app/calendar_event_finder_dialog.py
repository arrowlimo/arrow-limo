"""
Calendar Event Finder Dialog
Find upcoming calendar events to create charters from
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt
from difflib import SequenceMatcher
import re


class CalendarEventFinderDialog(QDialog):
    """Find calendar events and fuzzy match clients"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.selected_event = None
        self.selected_client_id = None
        self.selected_client_name = None
        
        self.setWindowTitle("Calendar Events - Create from Booking")
        self.setGeometry(150, 150, 1000, 400)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Select a calendar event to create charter from:"))
        header_layout.addStretch()
        
        use_now_btn = QPushButton("⏰ Use Current Time (Now)")
        use_now_btn.clicked.connect(self.use_current_time)
        header_layout.addWidget(use_now_btn)
        
        layout.addLayout(header_layout)
        
        # Events table
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(7)
        self.events_table.setHorizontalHeaderLabels([
            "Date", "Time", "Client", "Driver", "Vehicle", "Notes", "Matched"
        ])
        self.events_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.events_table.itemDoubleClicked.connect(self.select_event)
        layout.addWidget(self.events_table)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        select_btn = QPushButton("✓ Use This Event")
        select_btn.clicked.connect(self.select_event)
        button_layout.addWidget(select_btn)
        
        skip_btn = QPushButton("⊙ Skip & Find Client")
        skip_btn.clicked.connect(self.skip_calendar)
        button_layout.addWidget(skip_btn)
        
        cancel_btn = QPushButton("✕ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.load_upcoming_events()
    
    def load_upcoming_events(self):
        """Load upcoming calendar events"""
        try:
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT 
                    event_id,
                    event_date::date,
                    event_time,
                    event_title,
                    driver_name,
                    vehicle_type,
                    event_notes
                FROM calendar_events
                WHERE event_date >= CURRENT_DATE
                  AND event_status != 'cancelled'
                ORDER BY event_date, event_time
                LIMIT 50
            """)
            
            events = cur.fetchall()
            self.events_data = events
            self.display_events(events)
            
            if not events:
                QMessageBox.information(self, "No Events", "No upcoming calendar events found.")
                self.skip_calendar()
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            # Table might not exist yet, just skip calendar
            print(f"Calendar table not found or error: {e}")
            self.skip_calendar()
    
    def display_events(self, events):
        """Display events in table"""
        self.events_table.setRowCount(len(events))
        
        for row_idx, event in enumerate(events):
            event_id, date, time, title, driver, vehicle, notes = event
            
            # Fuzzy match client name
            matched_client = self.fuzzy_match_client(title)
            matched_name = matched_client[1] if matched_client else "No match"
            
            cells = [
                str(date or ""),
                str(time or ""),
                str(title or ""),
                str(driver or ""),
                str(vehicle or ""),
                str(notes or "")[:50],  # Truncate long notes
                matched_name,
            ]
            
            for col_idx, cell in enumerate(cells):
                item = QTableWidgetItem(cell)
                self.events_table.setItem(row_idx, col_idx, item)
    
    def fuzzy_match_client(self, client_name_text):
        """Fuzzy match event client name to database clients"""
        if not client_name_text or not client_name_text.strip():
            return None
        
        try:
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            cur.execute("SELECT client_id, client_name FROM clients ORDER BY client_name")
            
            clients = cur.fetchall()
            best_match = None
            best_ratio = 0.0
            
            for client_id, db_client_name in clients:
                if not db_client_name:
                    continue
                
                # Simple fuzzy match using SequenceMatcher
                ratio = SequenceMatcher(None, client_name_text.lower(), db_client_name.lower()).ratio()
                
                if ratio > best_ratio and ratio > 0.6:  # At least 60% match
                    best_ratio = ratio
                    best_match = (client_id, db_client_name, ratio)
            
            return best_match
        
        except Exception as e:
            print(f"Fuzzy match error: {e}")
            return None
    
    def parse_cc_from_notes(self, notes_text):
        """Parse CC info from calendar notes (Last 4 digits, type: VISA/MC/AMEX)"""
        if not notes_text:
            return None
        
        try:
            # Pattern 1: "CC: 1234" or "CC: 4242"
            cc_pattern = r'(?:CC|Card|cc)[\s:]*(\d{4})'
            cc_match = re.search(cc_pattern, notes_text, re.IGNORECASE)
            
            cc_last4 = None
            if cc_match:
                cc_last4 = cc_match.group(1)
            
            # Pattern 2: "VISA", "MC", "MASTERCARD", "AMEX", "AMERICAN EXPRESS"
            cc_type_pattern = r'(?:VISA|MASTERCARD|MC|AMEX|AMERICAN\s+EXPRESS)'
            cc_type_match = re.search(cc_type_pattern, notes_text, re.IGNORECASE)
            
            cc_type = None
            if cc_type_match:
                matched_text = cc_type_match.group(0).upper()
                if 'AMEX' in matched_text or 'AMERICAN' in matched_text:
                    cc_type = 'AMEX'
                elif 'MASTERCARD' in matched_text or matched_text == 'MC':
                    cc_type = 'MasterCard'
                elif 'VISA' in matched_text:
                    cc_type = 'VISA'
            
            if cc_last4 or cc_type:
                return {'last4': cc_last4, 'type': cc_type}
            
            return None
        
        except Exception as e:
            print(f"CC parsing error: {e}")
            return None
    
    def select_event(self):
        """Select event and fuzzy match client"""
        selected = self.events_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an event.")
            return
        
        row = self.events_table.row(selected[0])
        if row < 0 or row >= len(self.events_data):
            return
        
        event = self.events_data[row]
        event_id, date, time, title, driver, vehicle, notes = event
        
        # Fuzzy match client
        matched = self.fuzzy_match_client(title)
        
        if matched:
            self.selected_client_id = matched[0]
            self.selected_client_name = matched[1]
        else:
            QMessageBox.warning(self, "No Match", f"Could not find client for '{title}'. Please select manually.")
            return
        
        # Parse CC info from notes if present
        cc_info = self.parse_cc_from_notes(notes)
        
        self.selected_event = {
            'date': date,
            'time': time,
            'driver': driver,
            'vehicle': vehicle,
            'notes': notes,
            'client_name': title,
            'cc_last4': cc_info.get('last4') if cc_info else None,
            'cc_type': cc_info.get('type') if cc_info else None,
        }
        
        self.accept()
    
    def skip_calendar(self):
        """Skip calendar and go to client finder"""
        self.selected_event = None
        self.selected_client_id = None
        self.accept()
    
    def use_current_time(self):
        """Use current date/time (Now)"""
        from datetime import datetime, date
        
        # Return a special event marker for "now"
        self.selected_event = {
            'date': date.today(),
            'time': datetime.now().time(),
            'driver': None,
            'vehicle': None,
            'notes': None,
            'client_name': None,
            'is_now': True
        }
        
        # Need to select client first
        self.selected_client_id = None
        self.accept()
