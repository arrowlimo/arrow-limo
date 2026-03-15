"""
Improved Client Selection Dialog with fuzzy search and Company/Individual distinction
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QMessageBox, QRadioButton, QButtonGroup, QListWidget, QListWidgetItem,
    QCompleter, QAbstractItemModel
)
from PyQt6.QtCore import Qt, QStringListModel, pyqtSignal
from PyQt6.QtGui import QFont


class ClientSelectionDialog(QDialog):
    """Dialog for selecting or creating a client with fuzzy search"""
    
    client_selected = pyqtSignal(int, str, str)  # client_id, client_name, company_type
    
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._selected_client_id = None
        self._selected_client_name = None
        self._selected_company_type = None
        
        self.setWindowTitle("Select or Add Client")
        self.setGeometry(200, 200, 600, 500)
        self.init_ui()
        self.load_clients()
    
    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("<h2>Select Client for Charter</h2>")
        layout.addWidget(title)
        
        # Client Type Selection (Company/Individual)
        type_layout = QHBoxLayout()
        type_label = QLabel("Client Type:")
        type_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        type_layout.addWidget(type_label)
        
        self.type_group = QButtonGroup()
        self.company_radio = QRadioButton("Company/Organization")
        self.individual_radio = QRadioButton("Individual")
        self.company_radio.setChecked(True)
        
        self.type_group.addButton(self.company_radio, 0)
        self.type_group.addButton(self.individual_radio, 1)
        
        type_layout.addWidget(self.company_radio)
        type_layout.addWidget(self.individual_radio)
        type_layout.addStretch()
        layout.addLayout(type_layout)
        
        # Search Box
        search_layout = QHBoxLayout()
        search_label = QLabel("Search by name:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to search (fuzzy match)...")
        self.search_input.textChanged.connect(self.on_search_changed)
        self.search_input.returnPressed.connect(self.select_first_match)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Results List
        results_label = QLabel("Matching Clients:")
        layout.addWidget(results_label)
        
        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.on_client_selected)
        self.results_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.results_list)
        
        # Selected Info Display
        self.selected_info = QLabel("")
        self.selected_info.setStyleSheet("color: #0066cc; font-weight: bold;")
        layout.addWidget(self.selected_info)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        create_new_btn = QPushButton("➕ Create New Client")
        create_new_btn.clicked.connect(self.create_new_client)
        button_layout.addWidget(create_new_btn)
        
        select_btn = QPushButton("✅ Select")
        select_btn.clicked.connect(self.accept)
        button_layout.addWidget(select_btn)
        
        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Focus search input
        self.search_input.setFocus()
    
    def load_clients(self):
        """Load all clients from database for searching"""
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT client_id, client_name, db_customer_type
                FROM clients
                WHERE client_name IS NOT NULL
                ORDER BY client_name
            """)
            self.all_clients = cur.fetchall()
            cur.close()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load clients: {e}")
            self.all_clients = []
    
    def on_search_changed(self, text):
        """Filter clients based on search text"""
        self.results_list.clear()
        
        if not text.strip():
            return
        
        search_text = text.lower()
        matches = []
        
        # Fuzzy search - score based on relevance
        for client_id, client_name, company_type in self.all_clients:
            name_lower = (client_name or "").lower()
            
            # Exact match
            if search_text in name_lower:
                score = 100
            # Word start match
            elif any(word.startswith(search_text) for word in name_lower.split()):
                score = 50
            # Contains all chars in order (fuzzy)
            elif all(c in name_lower for c in search_text):
                score = 25
            else:
                continue
            
            matches.append((score, client_id, client_name, company_type))
        
        # Sort by score (descending) and name
        matches.sort(key=lambda x: (-x[0], x[2]))
        
        # Add to list (show top 20)
        for score, client_id, client_name, company_type in matches[:20]:
            item_text = f"{client_name}  [{company_type}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, (client_id, client_name, company_type))
            self.results_list.addItem(item)
    
    def on_client_selected(self, item):
        """Handle client selection from list"""
        client_id, client_name, company_type = item.data(Qt.ItemDataRole.UserRole)
        self._selected_client_id = client_id
        self._selected_client_name = client_name
        self._selected_company_type = company_type
        
        # Update display
        self.selected_info.setText(f"✓ Selected: {client_name} ({company_type})")
    
    def select_first_match(self):
        """Select first match when user presses Enter"""
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)
            self.on_client_selected(self.results_list.item(0))
            self.accept()
    
    def create_new_client(self):
        """Create a new client"""
        from improved_customer_widget import QuickAddClientDialog
        
        dialog = QuickAddClientDialog(self.db, self)
        if dialog.exec():
            new_client_id = dialog.get_created_client_id()
            if new_client_id:
                self._selected_client_id = new_client_id
                # Reload and search
                self.load_clients()
                self.accept()
    
    def get_selected_client_id(self):
        """Return the selected client ID"""
        return self._selected_client_id
    
    def get_selected_client_name(self):
        """Return the selected client name"""
        return self._selected_client_name
    
    def get_selected_company_type(self):
        """Return the selected company type"""
        return self._selected_company_type
