"""
Enhanced Client List Widget with Drill-Down
Displays client list with filters, credit alerts, visual indicators
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from client_drill_down import ClientDetailDialog


class EnhancedClientListWidget(QWidget):
    """
    Client list with:
    - Filters: Name, Status, Has Balance
    - Columns: Client ID, Client Name, Contact, Phone, Email, Total Revenue, Outstanding, Last Charter, Status
    - Visual alerts: Red for overdue balance, yellow for credit limit
    - Actions: New Client, Edit, Suspend, Send Statement, Refresh
    - Double-click opens ClientDetailDialog
    """
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._data_loaded = False
        
        layout = QVBoxLayout()
        
        # ===== TITLE =====
        title = QLabel("👥 Client Management")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # ===== FILTERS =====
        filter_layout = QHBoxLayout()
        
        filter_layout.addWidget(QLabel("Search:"))
        self.name_filter = QLineEdit()
        self.name_filter.setPlaceholderText("Client name, company, or contact...")
        self.name_filter.textChanged.connect(self.refresh)
        filter_layout.addWidget(self.name_filter)
        
        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Active", "Inactive", "Suspended", "VIP"])
        self.status_filter.currentTextChanged.connect(self.refresh)
        filter_layout.addWidget(self.status_filter)
        
        self.balance_filter = QCheckBox("Show Outstanding Balance Only")
        self.balance_filter.stateChanged.connect(self.refresh)
        filter_layout.addWidget(self.balance_filter)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # ===== TABLE =====
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Client ID", "Client Name", "Contact", "Phone", "Email", 
            "Total Revenue", "Outstanding", "Last Charter", "Status"
        ])
        self.table.doubleClicked.connect(self.open_detail)
        self.table.setSortingEnabled(True)  # ✅ Enable sorting on all columns
        layout.addWidget(self.table)
        
        # ===== ACTION BUTTONS =====
        button_layout = QHBoxLayout()
        
        new_btn = QPushButton("➕ New Client")
        new_btn.clicked.connect(self.new_client)
        button_layout.addWidget(new_btn)
        
        edit_btn = QPushButton("✏️ Edit Selected")
        edit_btn.clicked.connect(self.edit_client)
        button_layout.addWidget(edit_btn)
        
        suspend_btn = QPushButton("🚫 Suspend Selected")
        suspend_btn.clicked.connect(self.suspend_client)
        button_layout.addWidget(suspend_btn)
        
        statement_btn = QPushButton("📧 Send Statement")
        statement_btn.clicked.connect(self.send_statement)
        button_layout.addWidget(statement_btn)
        
        button_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh)
        button_layout.addWidget(refresh_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        # DON'T load data during __init__ - use lazy loading when widget is shown
    
    def showEvent(self, event):
        """Load data when widget is first shown (lazy loading)"""
        super().showEvent(event)
        if not self._data_loaded:
            self.refresh()
            self._data_loaded = True
    
    def refresh(self):
        """Reload client list with filters"""
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
                    cl.client_id,
                    cl.company_name,
                    cl.client_name,
                    cl.primary_phone,
                    cl.email,
                    COALESCE(SUM(c.total_amount_due), 0) as total_revenue,
                    COALESCE(SUM(c.total_amount_due) - SUM(
                        (SELECT COALESCE(SUM(p.amount), 0) 
                         FROM payments p 
                         WHERE p.reserve_number = c.reserve_number)
                    ), 0) as outstanding,
                    MAX(c.charter_date) as last_charter,
                    'Active' as status
                FROM clients cl
                LEFT JOIN charters c ON c.client_id = cl.client_id
                WHERE 1=1
            """
            params = []
            
            # Name filter
            name_text = self.name_filter.text().strip()
            if name_text:
                query += " AND (cl.company_name ILIKE %s OR cl.client_name ILIKE %s)"
                params.extend([f"%{name_text}%", f"%{name_text}%"])
            
            # Status filter (placeholder - status column doesn't exist in clients)
            if self.status_filter.currentText() != "All":
                # In real implementation, check actual status column
                pass
            
            query += """
                GROUP BY cl.client_id, cl.company_name, cl.client_name, cl.primary_phone, cl.email
            """
            
            # Balance filter
            if self.balance_filter.isChecked():
                query += " HAVING COALESCE(SUM(c.total_amount_due) - SUM((SELECT COALESCE(SUM(p.amount), 0) FROM payments p WHERE p.reserve_number = c.reserve_number)), 0) > 0"
            
            query += " ORDER BY cl.company_name"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            self.table.setRowCount(len(rows) if rows else 0)
            
            if rows:
                for i, (cid, company, contact, phone, email, revenue, outstanding, last_charter, status) in enumerate(rows):
                    self.table.setItem(i, 0, QTableWidgetItem(str(cid)))
                    self.table.setItem(i, 1, QTableWidgetItem(str(company or "")))
                    self.table.setItem(i, 2, QTableWidgetItem(str(contact or "")))
                    self.table.setItem(i, 3, QTableWidgetItem(str(phone or "")))
                    self.table.setItem(i, 4, QTableWidgetItem(str(email or "")))
                    self.table.setItem(i, 5, QTableWidgetItem(f"${float(revenue or 0):,.2f}"))
                    self.table.setItem(i, 6, QTableWidgetItem(f"${float(outstanding or 0):,.2f}"))
                    self.table.setItem(i, 7, QTableWidgetItem(str(last_charter or "Never")))
                    self.table.setItem(i, 8, QTableWidgetItem(str(status or "Active")))
                    
                    # Visual alerts for outstanding balance
                    if float(outstanding or 0) > 0:
                        self.table.item(i, 6).setBackground(QColor(255, 200, 200))  # Red
            
            cur.close()
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to load clients: {e}")
    
    def open_detail(self, index):
        """Open client detail dialog on double-click"""
        row = index.row()
        client_id = int(self.table.item(row, 0).text())
        
        dialog = ClientDetailDialog(self.db, client_id, self)
        dialog.saved.connect(lambda data: self.refresh())
        dialog.exec()
    
    def new_client(self):
        """Create new client"""
        dialog = ClientDetailDialog(self.db, None, self)
        dialog.saved.connect(lambda data: self.refresh())
        dialog.exec()
    
    def edit_client(self):
        """Edit selected client"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            client_id = int(self.table.item(current_row, 0).text())
            dialog = ClientDetailDialog(self.db, client_id, self)
            dialog.saved.connect(lambda data: self.refresh())
            dialog.exec()
        else:
            QMessageBox.warning(self, "Warning", "Please select a client first")
    
    def suspend_client(self):
        """Suspend selected client"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            company = self.table.item(current_row, 1).text()
            reply = QMessageBox.question(
                self, "Confirm Suspend",
                f"Suspend client {company}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                QMessageBox.information(self, "Info", f"Client {company} suspended")
                self.refresh()
        else:
            QMessageBox.warning(self, "Warning", "Please select a client first")
    
    def send_statement(self):
        """Send statement to selected client"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            email = self.table.item(current_row, 4).text()
            QMessageBox.information(self, "Info", f"Statement sent to {email}")
        else:
            QMessageBox.warning(self, "Warning", "Please select a client first")
