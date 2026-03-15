"""
Client Finder Dialog
Search for existing clients or create new ones
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt


class ClientFinderDialog(QDialog):
    """Find existing client or create new one"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.selected_client_id = None
        self.selected_client_name = None
        
        self.setWindowTitle("Find or Create Client")
        self.setGeometry(150, 150, 900, 500)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        # ===== SEARCH SECTION =====
        search_group = QGroupBox("Find Existing Client")
        search_layout = QHBoxLayout()
        
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Client name, phone, email...")
        self.search_input.textChanged.connect(self.search_clients)
        search_layout.addWidget(self.search_input)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # ===== RESULTS TABLE =====
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "Client ID", "Name", "Phone", "Email", "Address"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.itemDoubleClicked.connect(self.select_client_from_table)
        layout.addWidget(self.results_table)
        
        # ===== ACTION BUTTONS =====
        button_layout = QHBoxLayout()
        
        select_btn = QPushButton("✓ Select Client")
        select_btn.clicked.connect(self.select_client_from_table)
        button_layout.addWidget(select_btn)
        
        new_client_btn = QPushButton("➕ New Client")
        new_client_btn.clicked.connect(self.create_new_client)
        button_layout.addWidget(new_client_btn)
        
        cancel_btn = QPushButton("✕ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        self.load_all_clients()
    
    def load_all_clients(self):
        """Load all clients into table, grouping children under parents"""
        try:
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            # Load all clients with their parent info
            cur.execute("""
                SELECT 
                    c.client_id,
                    COALESCE(c.company_name, c.client_name) as display_name,
                    c.client_name,
                    c.primary_phone,
                    c.email,
                    c.address_line1,
                    c.parent_client_id
                FROM clients c
                ORDER BY 
                    COALESCE(c.parent_client_id, c.client_id),
                    c.client_id
                LIMIT 500
            """)
            
            rows = cur.fetchall()
            self.clients_data = rows
            self.display_clients(rows)
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.warning(self, "Load Error", f"Failed to load clients: {e}")
    
    def display_clients(self, clients):
        """Display clients in table with children grouped under parents"""
        self.results_table.setRowCount(len(clients))
        for row_idx, client in enumerate(clients):
            client_id, display_name, full_name, phone, email, address, parent_id = client
            
            # Add indentation for child accounts
            is_child = parent_id and parent_id > 0
            prefix = "  └─ " if is_child else ""
            
            cells = [
                str(client_id or ""),  # client_id
                prefix + str(display_name or ""),  # name with indentation
                str(phone or ""),  # phone
                str(email or ""),  # email
                str(address or ""),  # address
            ]
            for col_idx, cell in enumerate(cells):
                item = QTableWidgetItem(cell)
                if col_idx == 0:  # Store ID
                    item.setData(Qt.ItemDataRole.UserRole, str(client_id))
                self.results_table.setItem(row_idx, col_idx, item)
            
            # Light formatting for child accounts
            if is_child:
                for col in range(self.results_table.columnCount()):
                    item = self.results_table.item(row_idx, col)
                    if item:
                        font = item.font()
                        font.setItalic(True)
                        item.setFont(font)
    
    def search_clients(self):
        """Filter clients based on search text, including parent and child relationships"""
        search_text = self.search_input.text().lower().strip()
        
        if not search_text:
            self.display_clients(self.clients_data)
            return
        
        # Find matching clients
        matching_ids = set()
        parent_child_map = {}  # Track parent-child relationships
        
        for client in self.clients_data:
            client_id, display_name, full_name, phone, email, address, parent_id = client
            
            # Check if this client matches
            if any([
                search_text in (display_name or "").lower(),
                search_text in (full_name or "").lower(),
                search_text in (phone or "").lower(),
                search_text in (email or "").lower(),
            ]):
                matching_ids.add(client_id)
                # Also add parent if searching for a child
                if parent_id and parent_id > 0:
                    matching_ids.add(parent_id)
        
        # When parent matches, include all children
        for client in self.clients_data:
            client_id, display_name, full_name, phone, email, address, parent_id = client
            if parent_id and parent_id in matching_ids:
                matching_ids.add(client_id)
        
        # Display matching clients and their families
        filtered = [c for c in self.clients_data if c[0] in matching_ids]
        filtered.sort(key=lambda x: (x[6] or 0, x[0]))  # Sort by parent_id then client_id
        
        self.display_clients(filtered)
    
    def select_client_from_table(self):
        """Select client from table and close dialog"""
        selected = self.results_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a client from the list.")
            return
        
        row = self.results_table.row(selected[0])
        if row < 0 or row >= self.results_table.rowCount():
            return
        
        # Get client ID and name from table
        client_id_item = self.results_table.item(row, 0)
        client_name_item = self.results_table.item(row, 1)
        
        if client_id_item and client_name_item:
            self.selected_client_id = int(client_id_item.text())
            self.selected_client_name = client_name_item.text()
            self.accept()
    
    def create_new_client(self):
        """Create new client"""
        from desktop_app.client_input_dialog import ClientInputDialog
        
        dialog = ClientInputDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get the new client ID from the dialog
            if dialog.new_client_id:
                self.selected_client_id = dialog.new_client_id
                self.selected_client_name = dialog.new_client_name
                self.accept()


class ClientInputDialog(QDialog):
    """Quick client input dialog"""
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.new_client_id = None
        self.new_client_name = None
        
        self.setWindowTitle("New Client")
        self.setGeometry(200, 200, 500, 300)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        form_layout.addRow("Client Name:", self.name_input)
        
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("(XXX) XXX-XXXX")
        form_layout.addRow("Phone:", self.phone_input)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        form_layout.addRow("Email:", self.email_input)
        
        self.address_input = QLineEdit()
        form_layout.addRow("Address:", self.address_input)
        
        self.city_input = QLineEdit()
        form_layout.addRow("City:", self.city_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Save Client")
        save_btn.clicked.connect(self.save_client)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("✕ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def save_client(self):
        """Save new client to database"""
        client_name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        city = self.city_input.text().strip()
        
        if not client_name:
            QMessageBox.warning(self, "Missing Name", "Please enter client name.")
            return
        
        try:
            try:
                self.db.rollback()
            except:
                pass
            
            cur = self.db.get_cursor()
            
            # Generate account number from client name
            account_number = f"ACC-{client_name[:3].upper()}-{int(__import__('time').time()) % 10000}"
            
            # Insert new client
            cur.execute("""
                INSERT INTO clients (
                    account_number, 
                    client_name, 
                    primary_phone, 
                    email, 
                    address_line1, 
                    city, 
                    company_name, 
                    is_company
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING client_id
            """, (
                account_number,
                client_name,
                phone or None,
                email or None,
                address or None,
                city or None,
                client_name,  # Use name as company_name for now
                False  # Default to individual
            ))
            
            result = cur.fetchone()
            self.new_client_id = result[0]
            self.new_client_name = client_name
            
            self.db.commit()
            QMessageBox.information(self, "Success", f"Client '{client_name}' created successfully!")
            self.accept()
            
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(self, "Error", f"Failed to create client: {e}")
