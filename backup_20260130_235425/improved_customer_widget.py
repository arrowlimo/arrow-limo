"""
Improved Customer Information Widget with professional UX:
- Compact reserve number field (8 chars, display-only after save)
- Client lookup with autocomplete and add/edit functionality
- Optimized field sizing (phone, address, etc. use standard widths)
- Conditional Save button (visible only on changes)
- Read-only display mode after save
"""
from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QComboBox, QDialog, QMessageBox, QWidget, QCompleter, QFrame
)
from PyQt6.QtCore import Qt, QStringListModel, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import psycopg2


class QuickAddClientDialog(QDialog):
    """Quick add client information dialog"""
    
    def __init__(self, db_connection, parent=None):
        super().__init__(parent)
        self.db = db_connection
        self.new_client_id = None
        self.setWindowTitle("Add New Client")
        self.setGeometry(200, 200, 500, 400)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        # Client name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Full name or business name")
        form_layout.addRow("Client Name: *", self.name_input)
        
        # Phone
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("(403) 555-1234")
        self.phone_input.setMaximumWidth(200)
        form_layout.addRow("Phone: *", self.phone_input)
        
        # Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        self.email_input.setMaximumWidth(300)
        form_layout.addRow("Email:", self.email_input)
        
        # Address
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Street address")
        form_layout.addRow("Address:", self.address_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("💾 Save Client")
        save_btn.clicked.connect(self.save_client)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def save_client(self):
        """Save new client to database"""
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        
        if not name or not phone:
            QMessageBox.warning(self, "Validation", "Client Name and Phone are required")
            return
        
        try:
            cur = self.db.get_cursor()
            
            # Generate account_number (max + 1)
            cur.execute("SELECT MAX(CAST(account_number AS INTEGER)) FROM clients WHERE account_number ~ '^[0-9]+$'")
            max_account = cur.fetchone()[0] or 7604
            new_account_number = str(int(max_account) + 1)
            
            cur.execute("""
                INSERT INTO clients (account_number, client_name, primary_phone, email, address_line1)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING client_id
            """, (new_account_number, name, phone, email, address))
            self.new_client_id = cur.fetchone()[0]
            self.db.commit()
            cur.close()
            
            QMessageBox.information(self, "Success", f"Client '{name}' (Account #{new_account_number}) added successfully")
            self.accept()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save client: {e}")
    
    def get_created_client_id(self):
        """Return the newly created client ID"""
        return self.new_client_id


class EditClientDialog(QDialog):
    """Edit existing client information dialog"""
    
    def __init__(self, db_connection, client_id, parent=None):
        super().__init__(parent)
        self.db = db_connection
        self.client_id = client_id
        self.setWindowTitle("Edit Client")
        self.setGeometry(200, 200, 500, 400)
        self.init_ui()
        self.load_client()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        # Client name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Full name or business name")
        form_layout.addRow("Client Name:", self.name_input)
        
        # Phone
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("(403) 555-1234")
        self.phone_input.setMaximumWidth(200)
        form_layout.addRow("Phone:", self.phone_input)
        
        # Email
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        self.email_input.setMaximumWidth(300)
        form_layout.addRow("Email:", self.email_input)
        
        # Address
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Street address")
        form_layout.addRow("Address:", self.address_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("💾 Save Changes")
        save_btn.clicked.connect(self.save_changes)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_client(self):
        """Load client data from database"""
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT client_name, primary_phone, email, address_line1
                FROM clients
                WHERE client_id = %s
            """, (self.client_id,))
            
            row = cur.fetchone()
            cur.close()
            
            if row:
                name, phone, email, address = row
                self.name_input.setText(name or "")
                self.phone_input.setText(phone or "")
                self.email_input.setText(email or "")
                self.address_input.setText(address or "")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load client: {e}")
    
    def save_changes(self):
        """Save changes to client"""
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                UPDATE clients
                SET client_name = %s, primary_phone = %s, email = %s, address_line1 = %s
                WHERE client_id = %s
            """, (name, phone, email, address, self.client_id))
            self.db.commit()
            cur.close()
            
            QMessageBox.information(self, "Success", "Client information updated")
            self.accept()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save changes: {e}")


class ImprovedCustomerWidget(QWidget):
    """Improved customer information widget with professional UX"""
    
    # Signals
    changed = pyqtSignal()  # Emitted when any field changes
    saved = pyqtSignal(int)  # Emitted when data is saved (client_id)
    
    def __init__(self, db_connection, parent=None):
        super().__init__(parent)
        self.db = db_connection
        self.is_saved = True  # Track if changes have been made
        self.is_edit_mode = False  # Track if we're in edit mode
        self.current_client_id = None
        self.client_ids_map = {}  # Map client names to IDs for quick lookup
        
        self.init_ui()
        self.load_client_list()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout()
        
        # ===== DISPLAY MODE (READ-ONLY) =====
        self.display_frame = QFrame()
        display_layout = QVBoxLayout()
        
        # Reserve number and client name header
        header_layout = QHBoxLayout()
        
        reserve_label = QLabel("Reserve #:")
        reserve_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(reserve_label)
        
        self.reserve_display = QLabel("")
        self.reserve_display.setFont(QFont("Courier", 11, QFont.Weight.Bold))
        self.reserve_display.setMinimumWidth(100)
        
        # Add New Client button (visible when in display mode) - MOVED TO LEFT
        self.add_btn_display = QPushButton("➕ New Client")
        self.add_btn_display.setMaximumWidth(120)
        self.add_btn_display.clicked.connect(self.add_new_client)
        header_layout.addWidget(self.add_btn_display)
        
        # Edit button (visible when in display mode) - MOVED TO LEFT
        self.edit_btn_display = QPushButton("✏️ Edit")
        self.edit_btn_display.setMaximumWidth(100)
        self.edit_btn_display.clicked.connect(self.enter_edit_mode)
        header_layout.addWidget(self.edit_btn_display)
        
        header_layout.addSpacing(15)
        
        header_layout.addWidget(self.reserve_display)
        
        header_layout.addSpacing(30)
        
        client_label = QLabel("Client:")
        client_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(client_label)
        
        self.client_display = QLabel("")
        self.client_display.setFont(QFont("Arial", 10))
        header_layout.addWidget(self.client_display)
        
        header_layout.addStretch()
        display_layout.addLayout(header_layout)
        
        # Customer details display
        details_layout = QHBoxLayout()
        
        phone_col = QVBoxLayout()
        phone_col.addWidget(QLabel("Phone:", ))
        self.phone_display = QLabel("")
        phone_col.addWidget(self.phone_display)
        details_layout.addLayout(phone_col)
        
        email_col = QVBoxLayout()
        email_col.addWidget(QLabel("Email:"))
        self.email_display = QLabel("")
        self.email_display.setWordWrap(True)
        email_col.addWidget(self.email_display)
        details_layout.addLayout(email_col)
        
        address_col = QVBoxLayout()
        address_col.addWidget(QLabel("Address:"))
        self.address_display = QLabel("")
        self.address_display.setWordWrap(True)
        address_col.addWidget(self.address_display)
        details_layout.addLayout(address_col)
        
        display_layout.addLayout(details_layout)
        self.display_frame.setLayout(display_layout)
        layout.addWidget(self.display_frame)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)
        
        # ===== EDIT MODE (EDITABLE) =====
        self.edit_frame = QFrame()
        edit_layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        # Reserve number (8 chars, display-only in edit mode)
        reserve_row = QHBoxLayout()
        reserve_row.addWidget(QLabel("Reserve #:"))
        self.reserve_input = QLineEdit()
        self.reserve_input.setReadOnly(True)
        self.reserve_input.setMaximumWidth(80)
        self.reserve_input.setPlaceholderText("Auto-gen")
        reserve_row.addWidget(self.reserve_input)
        reserve_row.addStretch()
        form_layout.addRow(reserve_row)
        
        
        # Client lookup with autocomplete - BUTTONS MOVED LEFT
        client_row = QHBoxLayout()
        
        # Add new client button - MOVED TO LEFT
        add_client_btn = QPushButton("➕ New Client")
        add_client_btn.setMaximumWidth(100)
        add_client_btn.clicked.connect(self.add_new_client)
        client_row.addWidget(add_client_btn)
        
        # Edit client button - MOVED TO LEFT
        edit_client_btn = QPushButton("✏️ Edit")
        edit_client_btn.setMaximumWidth(80)
        edit_client_btn.clicked.connect(self.edit_current_client)
        client_row.addWidget(edit_client_btn)
        
        client_row.addSpacing(15)
        
        client_row.addWidget(QLabel("Client: *"))
        
        self.client_combo = QComboBox()
        self.client_combo.setEditable(True)
        self.client_combo.setMaximumWidth(300)
        self.client_combo.currentTextChanged.connect(self.on_client_selected)
        self.client_combo.editTextChanged.connect(self.on_form_changed)
        client_row.addWidget(self.client_combo)
        
        client_row.addStretch()
        form_layout.addRow(client_row)
        # Phone (standard phone width)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("(403) 555-1234")
        self.phone_input.setMaximumWidth(150)
        self.phone_input.textChanged.connect(self.on_form_changed)
        form_layout.addRow("Phone: *", self.phone_input)
        
        # Email (wider for email addresses)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        self.email_input.setMaximumWidth(300)
        self.email_input.textChanged.connect(self.on_form_changed)
        form_layout.addRow("Email:", self.email_input)
        
        # Address (standard address width)
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Street address")
        self.address_input.setMaximumWidth(400)
        self.address_input.textChanged.connect(self.on_form_changed)
        form_layout.addRow("Address:", self.address_input)
        
        edit_layout.addLayout(form_layout)
        
        # Save/Cancel buttons (bottom right)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_edit)
        button_layout.addWidget(self.cancel_btn)
        
        self.save_btn = QPushButton("💾 Save Client")
        self.save_btn.clicked.connect(self.save_customer)
        self.save_btn.setEnabled(False)  # Disabled until changes made
        button_layout.addWidget(self.save_btn)
        
        edit_layout.addLayout(button_layout)
        self.edit_frame.setLayout(edit_layout)
        layout.addWidget(self.edit_frame)
        
        self.setLayout(layout)
        
        # Start in display mode
        self.show_display_mode()
    
    def load_client_list(self):
        """Load all clients from database for autocomplete"""
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT client_id, client_name
                FROM clients
                WHERE client_name IS NOT NULL
                ORDER BY client_name
            """)
            
            self.client_ids_map = {}
            client_names = []
            
            for client_id, name in cur.fetchall():
                self.client_ids_map[name] = client_id
                client_names.append(name)
            
            cur.close()
            
            # Clear existing items and set autocomplete model
            self.client_combo.clear()
            self.client_combo.addItems(client_names)
            completer = QCompleter(client_names)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.client_combo.setCompleter(completer)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load clients: {e}")
    
    def on_client_selected(self, client_name):
        """Load selected client details"""
        if not client_name or client_name not in self.client_ids_map:
            return
        
        self.current_client_id = self.client_ids_map[client_name]
        
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                SELECT primary_phone, email, address_line1
                FROM clients
                WHERE client_id = %s
            """, (self.current_client_id,))
            
            row = cur.fetchone()
            cur.close()
            
            if row:
                phone, email, address = row
                self.phone_input.setText(phone or "")
                self.email_input.setText(email or "")
                self.address_input.setText(address or "")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load client details: {e}")
    
    def add_new_client(self):
        """Add new client"""
        dialog = QuickAddClientDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Reload client list and select the new one
            self.load_client_list()
            if dialog.new_client_id:
                # Find and select the new client
                cur = self.db.get_cursor()
                cur.execute("SELECT client_name FROM clients WHERE client_id = %s", (dialog.new_client_id,))
                row = cur.fetchone()
                cur.close()
                if row:
                    client_name = row[0]
                    # Set the combo box to the new client (triggers on_client_selected)
                    index = self.client_combo.findText(client_name)
                    if index >= 0:
                        self.client_combo.setCurrentIndex(index)
                        # Also manually trigger the load in case signal doesn't fire
                        self.on_client_selected(client_name)
    
    def edit_current_client(self):
        """Edit current client"""
        if not self.current_client_id:
            QMessageBox.warning(self, "Warning", "Select a client first")
            return
        
        dialog = EditClientDialog(self.db, self.current_client_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Reload client details
            client_name = self.client_combo.currentText()
            self.on_client_selected(client_name)
    
    def on_form_changed(self):
        """Called when any form field changes"""
        self.is_saved = False
        self.save_btn.setEnabled(True)
        self.changed.emit()
    
    def save_customer(self):
        """Save customer information"""
        client_name = self.client_combo.currentText().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        
        if not client_name or not phone:
            QMessageBox.warning(self, "Validation", "Client name and phone are required")
            return
        
        try:
            # Save client info to database
            if self.current_client_id:
                cur = self.db.get_cursor()
                cur.execute("""
                    UPDATE clients
                    SET primary_phone = %s, email = %s, address_line1 = %s
                    WHERE client_id = %s
                """, (phone, email, address, self.current_client_id))
                self.db.commit()
                cur.close()
            
            self.is_saved = True
            self.save_btn.setEnabled(False)
            self.show_display_mode()
            self.saved.emit(self.current_client_id)
            
            QMessageBox.information(self, "Success", f"Client '{client_name}' saved successfully")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save customer: {e}")
    
    def enter_edit_mode(self):
        """Enter edit mode"""
        self.is_edit_mode = True
        self.display_frame.hide()
        self.edit_frame.show()
    
    def cancel_edit(self):
        """Cancel edit and return to display mode"""
        self.is_edit_mode = False
        self.is_saved = True
        self.save_btn.setEnabled(False)
        self.show_display_mode()
    
    def show_display_mode(self):
        """Show read-only display mode"""
        self.is_edit_mode = False
        self.display_frame.show()
        self.edit_frame.hide()
        
        # Update display from inputs
        client_name = self.client_combo.currentText()
        phone = self.phone_input.text()
        email = self.email_input.text()
        address = self.address_input.text()
        reserve = self.reserve_input.text()
        
        self.reserve_display.setText(reserve or "-----")
        self.client_display.setText(client_name or "")
        self.phone_display.setText(phone or "")
        self.email_display.setText(email or "")
        self.address_display.setText(address or "")
    
    def set_charter_data(self, charter_id, reserve_number, client_id):
        """Set charter data for display"""
        self.reserve_input.setText(reserve_number or "")
        self.reserve_display.setText(reserve_number or "-----")
        self.current_client_id = client_id
        
        # Load client details if client_id is provided
        if client_id:
            try:
                cur = self.db.get_cursor()
                cur.execute("""
                    SELECT client_name, primary_phone, email, address_line1
                    FROM clients
                    WHERE client_id = %s
                """, (client_id,))
                
                row = cur.fetchone()
                cur.close()
                
                if row:
                    name, phone, email, address = row
                    self.client_combo.setCurrentText(name)
                    self.phone_input.setText(phone or "")
                    self.email_input.setText(email or "")
                    self.address_input.setText(address or "")
                    self.show_display_mode()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load customer: {e}")
    
    def get_customer_data(self):
        """Get current customer data"""
        return {
            'reserve_number': self.reserve_input.text(),
            'client_id': self.current_client_id,
            'client_name': self.client_combo.currentText(),
            'phone': self.phone_input.text(),
            'email': self.email_input.text(),
            'address': self.address_input.text(),
        }
