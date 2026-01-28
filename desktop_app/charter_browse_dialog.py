"""
Charter Browse Dialog: Search and select charters by reserve number, client name, or date
Replaces the standalone charter lookup tab for better security and UX
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QDateEdit
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QFont
from datetime import datetime


class CharterBrowseDialog(QDialog):
    """Search and select a charter"""
    
    charter_selected = pyqtSignal(str)  # Emits reserve_number
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.selected_reserve = None
        
        self.setWindowTitle("Browse Charters")
        self.setGeometry(200, 200, 1000, 600)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # ===== SEARCH SECTION =====
        search_group_title = QLabel("SEARCH CRITERIA")
        search_group_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        search_group_title.setStyleSheet("color: #1a3d7a;")
        layout.addWidget(search_group_title)
        
        search_layout = QHBoxLayout()
        
        # Reserve Number
        res_label = QLabel("Reserve #:")
        res_label.setMinimumWidth(80)
        self.reserve_input = QLineEdit()
        self.reserve_input.setPlaceholderText("e.g., 019233")
        self.reserve_input.setMaximumWidth(150)
        search_layout.addWidget(res_label)
        search_layout.addWidget(self.reserve_input)
        
        search_layout.addSpacing(20)
        
        # Client Name
        client_label = QLabel("Client Name:")
        client_label.setMinimumWidth(80)
        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("e.g., John Smith")
        self.client_input.setMaximumWidth(200)
        search_layout.addWidget(client_label)
        search_layout.addWidget(self.client_input)
        
        search_layout.addSpacing(20)
        
        # Charter Date
        date_label = QLabel("Charter Date:")
        date_label.setMinimumWidth(80)
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setMaximumWidth(150)
        search_layout.addWidget(date_label)
        search_layout.addWidget(self.date_input)
        
        search_layout.addSpacing(20)
        
        # Search Button
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self.search_charters)
        search_layout.addWidget(self.search_btn)
        
        search_layout.addStretch()
        layout.addLayout(search_layout)
        
        layout.addSpacing(10)
        
        # ===== RESULTS TABLE =====
        results_title = QLabel("SEARCH RESULTS (Double-click to select)")
        results_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        results_title.setStyleSheet("color: #1a3d7a;")
        layout.addWidget(results_title)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "Reserve #", "Client", "Charter Date", "Passengers", "Vehicle", "Total Due", "Status"
        ])
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.doubleClicked.connect(self.on_charter_selected)
        self.results_table.resizeColumnsToContents()
        layout.addWidget(self.results_table)
        
        # ===== BUTTONS =====
        button_layout = QHBoxLayout()
        
        select_btn = QPushButton("✓ Select")
        select_btn.clicked.connect(self.on_charter_selected)
        button_layout.addWidget(select_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def search_charters(self):
        """Search for charters based on criteria"""
        reserve = self.reserve_input.text().strip()
        client = self.client_input.text().strip()
        charter_date = self.date_input.date().toPyDate() if self.date_input.date().isValid() else None
        
        if not reserve and not client and not charter_date:
            QMessageBox.warning(self, "Search Error", "Please enter at least one search criterion")
            return
        
        try:
            cur = self.db.cursor()
            
            # Build dynamic SQL query
            query = """
                SELECT c.reserve_number, 
                       COALESCE(a.company_name, a.last_name || ', ' || a.first_name, 'Unknown') as client,
                       c.charter_date,
                       c.passenger_count,
                       c.vehicle_type_requested,
                       COALESCE(c.total_amount_due, 0) as total_due,
                       c.status
                FROM charters c
                LEFT JOIN accounts a ON c.client_id = a.account_id
                WHERE 1=1
            """
            
            params = []
            
            if reserve:
                query += " AND c.reserve_number ILIKE %s"
                params.append(f"%{reserve}%")
            
            if client:
                query += """ AND (
                    COALESCE(a.company_name, '') ILIKE %s
                    OR COALESCE(a.last_name || ', ' || a.first_name, '') ILIKE %s
                )"""
                params.append(f"%{client}%")
                params.append(f"%{client}%")
            
            if charter_date:
                query += " AND c.charter_date = %s"
                params.append(charter_date)
            
            query += " ORDER BY c.charter_date DESC, c.reserve_number LIMIT 100"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            cur.close()
            
            # Populate table
            self.results_table.setRowCount(0)
            
            if not rows:
                QMessageBox.information(self, "No Results", "No charters found matching the criteria")
                return
            
            for row_num, row_data in enumerate(rows):
                self.results_table.insertRow(row_num)
                for col_num, value in enumerate(row_data):
                    item = QTableWidgetItem(str(value) if value else "")
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.results_table.setItem(row_num, col_num, item)
            
            self.results_table.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "Search Error", f"Error searching charters: {str(e)}")
    
    def on_charter_selected(self):
        """Handle charter selection"""
        selected_rows = self.results_table.selectedIndexes()
        
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a charter")
            return
        
        # Get reserve number from first column of selected row
        row = selected_rows[0].row()
        reserve_cell = self.results_table.item(row, 0)
        
        if reserve_cell:
            self.selected_reserve = reserve_cell.text()
            self.charter_selected.emit(self.selected_reserve)
            self.accept()
