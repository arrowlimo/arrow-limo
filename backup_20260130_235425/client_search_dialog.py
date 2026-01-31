"""
Client Search Dialog with Fuzzy Matching
Used for searching existing clients or creating new client before charter creation
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QTableWidget, 
    QTableWidgetItem, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class ClientSearchDialog(QDialog):
    """Dialog to search and select existing client or create new one"""
    
    client_selected = pyqtSignal(int)  # Signal with client_id
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._selected_client_id = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("Select or Create Client")
        self.setGeometry(200, 200, 700, 500)
        
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("<h2>Find Client for New Charter</h2>")
        layout.addWidget(title)
        
        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type client name, phone, or email (fuzzy search)...")
        self.search_input.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "ID", "Client Name", "Phone", "Email", "Account #"
        ])
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.doubleClicked.connect(self.on_client_double_clicked)
        layout.addWidget(self.results_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        select_btn = QPushButton("✅ Select Client")
        select_btn.clicked.connect(self.select_client)
        button_layout.addWidget(select_btn)
        
        new_btn = QPushButton("➕ Create New Client")
        new_btn.clicked.connect(self.create_new_client)
        button_layout.addWidget(new_btn)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("Start typing to search for clients...")
        self.status_label.setStyleSheet("color: #666; font-style: italic; font-size: 10px;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
    
    def on_search_changed(self, text):
        """Search for clients matching text (fuzzy match)"""
        self.results_table.setRowCount(0)
        
        if not text or len(text) < 2:
            self.status_label.setText("Type at least 2 characters to search...")
            return
        
        try:
            search_term = f"%{text}%"
            cur = self.db.get_cursor()
            
            # Fuzzy search across name, phone, email
            cur.execute("""
                SELECT client_id, client_name, phone, email, account_number
                FROM clients
                WHERE client_name ILIKE %s
                   OR phone ILIKE %s
                   OR email ILIKE %s
                ORDER BY client_name ASC
                LIMIT 50
            """, (search_term, search_term, search_term))
            
            rows = cur.fetchall()
            cur.close()
            
            if rows:
                for row in rows:
                    client_id, name, phone, email, account_num = row
                    self.results_table.insertRow(self.results_table.rowCount())
                    
                    # ID (hidden, but stored)
                    id_item = QTableWidgetItem(str(client_id))
                    id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.results_table.setItem(self.results_table.rowCount() - 1, 0, id_item)
                    
                    # Name
                    name_item = QTableWidgetItem(name or "")
                    name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.results_table.setItem(self.results_table.rowCount() - 1, 1, name_item)
                    
                    # Phone
                    phone_item = QTableWidgetItem(phone or "")
                    phone_item.setFlags(phone_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.results_table.setItem(self.results_table.rowCount() - 1, 2, phone_item)
                    
                    # Email
                    email_item = QTableWidgetItem(email or "")
                    email_item.setFlags(email_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.results_table.setItem(self.results_table.rowCount() - 1, 3, email_item)
                    
                    # Account #
                    acct_item = QTableWidgetItem(account_num or "")
                    acct_item.setFlags(acct_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.results_table.setItem(self.results_table.rowCount() - 1, 4, acct_item)
                
                self.status_label.setText(f"Found {len(rows)} clients. Double-click to select, or click 'Select Client' button.")
            else:
                self.status_label.setText("No clients found matching your search.")
        
        except Exception as e:
            self.status_label.setText(f"❌ Search error: {str(e)[:50]}")
            print(f"Error searching clients: {e}")
    
    def on_client_double_clicked(self, index):
        """Handle double-click on client row"""
        self.select_client()
    
    def select_client(self):
        """Select the currently selected row"""
        row = self.results_table.currentRow()
        if row >= 0:
            client_id = int(self.results_table.item(row, 0).text())
            self._selected_client_id = client_id
            self.client_selected.emit(client_id)
            self.accept()
        else:
            QMessageBox.warning(self, "Warning", "Please select a client first or create a new one.")
    
    def create_new_client(self):
        """Create a new client"""
        from improved_customer_widget import QuickAddClientDialog
        
        dialog = QuickAddClientDialog(self.db, self)
        result = dialog.exec()
        
        if result:
            new_client_id = dialog.get_created_client_id()
            if new_client_id:
                self._selected_client_id = new_client_id
                self.client_selected.emit(new_client_id)
                self.accept()
    
    def get_selected_client_id(self):
        """Return the selected client ID"""
        return self._selected_client_id
