"""
Quick charter lookup widget - allows fast lookup and drill-down from charter number.
"""
import os
import psycopg2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QCompleter
)
from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import QFont


class QuickCharterLookupWidget(QWidget):
    """Quick lookup widget for charter by reserve number or charter ID."""
    
    def __init__(self, db_connection, parent=None):
        super().__init__(parent)
        self.db = db_connection
        self.parent_widget = parent
        self.init_ui()
        self.populate_autocomplete()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(8)
        
        # Label
        label = QLabel("Quick Charter Lookup:")
        label_font = QFont()
        label_font.setBold(True)
        label.setFont(label_font)
        layout.addWidget(label)
        
        # Input field with autocomplete
        self.charter_input = QLineEdit()
        self.charter_input.setPlaceholderText("Enter reserve # (006717) or charter ID (18720)...")
        self.charter_input.setMaximumWidth(400)
        self.charter_input.returnPressed.connect(self.on_lookup)
        layout.addWidget(self.charter_input)
        
        # Lookup button
        self.lookup_btn = QPushButton("Lookup")
        self.lookup_btn.clicked.connect(self.on_lookup)
        self.lookup_btn.setMaximumWidth(100)
        layout.addWidget(self.lookup_btn)
        
        # Advanced search button
        self.advanced_btn = QPushButton("Advanced Search")
        self.advanced_btn.clicked.connect(self.on_advanced_search)
        self.advanced_btn.setMaximumWidth(150)
        layout.addWidget(self.advanced_btn)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def populate_autocomplete(self):
        """Populate autocomplete suggestions from database."""
        try:
            # Handle both psycopg2 connections and custom connection objects
            if hasattr(self.db, 'cursor'):
                cur = self.db.cursor()
                close_cursor = True
            else:
                # Assume self.db is already a cursor or has a different interface
                import psycopg2
                conn = psycopg2.connect(
                    host=os.getenv("DB_HOST", "localhost"),
                    dbname=os.getenv("DB_NAME", "almsdata"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", "***REDACTED***"),
                )
                cur = conn.cursor()
                close_cursor = True
                
            cur.execute("""
                SELECT COALESCE(reserve_number, CAST(charter_id AS TEXT))
                FROM charters
                WHERE reserve_number IS NOT NULL OR charter_id IS NOT NULL
                ORDER BY reserve_number
                LIMIT 500
            """)
            suggestions = [row[0] for row in cur.fetchall()]
            if close_cursor:
                cur.close()
            
            model = QStringListModel(suggestions)
            completer = QCompleter(model)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.charter_input.setCompleter(completer)
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading autocomplete: {e}")
    
    def on_lookup(self):
        """Lookup charter by number or ID."""
        query = self.charter_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Error", "Enter a charter number or ID")
            return
        
        try:
            # Handle both psycopg2 connections and custom connection objects
            if hasattr(self.db, 'cursor'):
                cur = self.db.cursor()
                close_cursor = True
            else:
                # Fallback: create a new connection
                conn = psycopg2.connect(
                    host=os.getenv("DB_HOST", "localhost"),
                    dbname=os.getenv("DB_NAME", "almsdata"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", "***REDACTED***"),
                )
                cur = conn.cursor()
                close_cursor = True
            
            # Try exact match first
            cur.execute("""
                SELECT charter_id, reserve_number, charter_date, driver, vehicle, status, balance
                FROM charters
                WHERE reserve_number = %s OR CAST(charter_id AS TEXT) = %s
                LIMIT 1
            """, (query, query))
            
            row = cur.fetchone()
            
            # Try partial match if no exact match
            if not row:
                cur.execute("""
                    SELECT charter_id, reserve_number, charter_date, driver, vehicle, status, balance
                    FROM charters
                    WHERE reserve_number ILIKE %s OR CAST(charter_id AS TEXT) ILIKE %s
                    ORDER BY charter_date DESC
                    LIMIT 1
                """, (f"%{query}%", f"%{query}%"))
                row = cur.fetchone()
            
            if close_cursor:
                cur.close()
            
            if row:
                charter_id = row[0]
                # Load directly without confirmation
                if hasattr(self.parent_widget, 'load_charter_by_id'):
                    self.parent_widget.load_charter_by_id(charter_id)
                elif hasattr(self, 'parent') and hasattr(self.parent(), 'load_charter_by_id'):
                    self.parent().load_charter_by_id(charter_id)
            else:
                QMessageBox.information(self, "Not Found", f"No charter found for '{query}'")
        
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Lookup failed: {e}")
    
    def on_advanced_search(self):
        """Open advanced search dialog."""
        from advanced_charter_search_dialog import AdvancedCharterSearchDialog
        
        dialog = AdvancedCharterSearchDialog(self.db, self)
        dialog.exec()
