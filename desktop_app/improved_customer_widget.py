"""
Improved Customer Information Widget with professional UX:
- Compact reserve number field (8 chars, display-only after save)
- Client lookup with autocomplete and add/edit functionality
- Optimized field sizing (phone, address, etc. use standard widths)
- Conditional Save button (visible only on changes)
- Read-only display mode after save
"""

import re

from db_error_handling import DatabaseContext, logger
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_PLACEHOLDER = "\u2014 Please select or add client —"


def _get_clients_columns(cur) -> object:
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'clients'
    """)
    return {row[0] for row in cur.fetchall()}


_CLIENT_NAME_DATETIME_RE = re.compile(
    r"^[\"'\-\s]*\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\s*$",
    re.IGNORECASE,
)

_CLIENT_NAME_TIME_ONLY_RE = re.compile(
    r"^[\"'\-\s]*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\s*$",
    re.IGNORECASE,
)

_CLIENT_NAME_NUMERIC_RE = re.compile(r"^\d{4,}$")

_CLIENT_NAME_BEVERAGE_HINTS = (
    "pack of",
    "coors",
    "cuervo",
    "vodka",
    "wine",
    "beverage",
    "tea",
    "iced tea",
    "sparkling",
)

_CLIENT_NAME_NOTE_HINTS = (
    "does not want",
    "stick to",
)


def _is_noise_client_name(name: str) -> bool:
    """Return True for malformed values that should never appear in client pickers."""
    text = (name or "").strip()
    if not text:
        return True

    # Drop accidental datetime values saved into client_name, e.g.
    # "08/01/2025 10:27:57 AM".
    if _CLIENT_NAME_DATETIME_RE.match(text):
        return True

    unquoted = text.strip('"\'').strip()
    if _CLIENT_NAME_DATETIME_RE.match(unquoted):
        return True

    if _CLIENT_NAME_TIME_ONLY_RE.match(text) or _CLIENT_NAME_TIME_ONLY_RE.match(
        unquoted
    ):
        return True

    if _CLIENT_NAME_NUMERIC_RE.match(unquoted):
        return True

    # Drop malformed quoted/import artifacts like '"-Jose Cuervo Sparkling 20'.
    if text[:1] in ('"', "'") and unquoted.startswith("-"):
        return True

    lowered = unquoted.casefold()
    for token in _CLIENT_NAME_BEVERAGE_HINTS:
        if token in lowered:
            return True

    for token in _CLIENT_NAME_NOTE_HINTS:
        if token in lowered:
            return True

    # Entries that start with punctuation are often malformed imports/notes.
    if unquoted and not unquoted[0].isalnum():
        return True

    return False


class QuickAddClientDialog(QDialog):
    """Quick add client information dialog"""

    def __init__(self, db_connection, parent=None) -> None:
        super().__init__(parent)
        self.db = db_connection
        self.new_client_id = None
        self.setWindowTitle("Add New Client")
        self.setGeometry(200, 200, 560, 460)
        self.init_ui()

    def init_ui(self) -> None:
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

        # Bill To
        self.bill_to_input = QLineEdit()
        self.bill_to_input.setPlaceholderText("Billing contact/name")
        self.bill_to_input.setMaximumWidth(300)
        form_layout.addRow("Bill To:", self.bill_to_input)

        # Alternate phone
        self.alt_phone_input = QLineEdit()
        self.alt_phone_input.setPlaceholderText("Alternate phone number")
        self.alt_phone_input.setMaximumWidth(200)
        form_layout.addRow("Alternate Phone:", self.alt_phone_input)

        # CC information
        self.cc_info_input = QLineEdit()
        self.cc_info_input.setPlaceholderText("CC info (e.g., VISA ****1234)")
        form_layout.addRow("CC Information:", self.cc_info_input)

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

    def save_client(self) -> None:
        """Save new client to database"""
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        bill_to = self.bill_to_input.text().strip()
        alt_phone = self.alt_phone_input.text().strip()
        cc_info = self.cc_info_input.text().strip()

        if not name or not phone:
            QMessageBox.warning(
                self, "Validation", "Client Name and Phone are required"
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                clients_columns = _get_clients_columns(cur)

                # Generate account_number (max + 1)
                cur.execute(
                    "SELECT MAX(CAST(account_number AS INTEGER)) FROM clients "
                    "WHERE account_number ~ '^[0-9]+$'"
                )
                max_account = cur.fetchone()[0] or 7604
                new_account_number = str(int(max_account) + 1)

                insert_columns = [
                    "account_number",
                    "client_name",
                    "primary_phone",
                    "email",
                    "address_line1",
                ]
                values = [
                    new_account_number,
                    name,
                    phone or None,
                    email or None,
                    address or None,
                ]

                optional_values = {
                    "billing_no": bill_to or None,
                    "cell_phone": alt_phone or None,
                    "contact_info": cc_info or None,
                }
                for column_name, value in optional_values.items():
                    if column_name in clients_columns:
                        insert_columns.append(column_name)
                        values.append(value)

                placeholders = ", ".join(["%s"] * len(insert_columns))
                column_clause = ", ".join(insert_columns)

                cur.execute(
                    f"""
                    INSERT INTO clients ({column_clause})
                    VALUES ({placeholders})
                    RETURNING client_id
                """,
                    values,
                )
                self.new_client_id = cur.fetchone()[0]

            QMessageBox.information(
                self,
                "Success",
                f"Client '{name}' (Account #{new_account_number}) added"
                f"successfully",
            )
            self.accept()
        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save client: {e}")

    def get_created_client_id(self) -> object:
        """Return the newly created client ID"""
        return self.new_client_id


class EditClientDialog(QDialog):
    """Edit existing client information dialog"""

    def __init__(self, db_connection, client_id, parent=None) -> None:
        super().__init__(parent)
        self.db = db_connection
        self.client_id = client_id
        self.setWindowTitle("Edit Client")
        self.setGeometry(200, 200, 560, 460)
        self.init_ui()
        self.load_client()

    def init_ui(self) -> None:
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

        # Bill To
        self.bill_to_input = QLineEdit()
        self.bill_to_input.setPlaceholderText("Billing contact/name")
        self.bill_to_input.setMaximumWidth(300)
        form_layout.addRow("Bill To:", self.bill_to_input)

        # Alternate phone
        self.alt_phone_input = QLineEdit()
        self.alt_phone_input.setPlaceholderText("Alternate phone number")
        self.alt_phone_input.setMaximumWidth(200)
        form_layout.addRow("Alternate Phone:", self.alt_phone_input)

        # CC information
        self.cc_info_input = QLineEdit()
        self.cc_info_input.setPlaceholderText("CC info (e.g., VISA ****1234)")
        form_layout.addRow("CC Information:", self.cc_info_input)

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

    def load_client(self) -> None:
        """Load client data from database"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                clients_columns = _get_clients_columns(cur)
                bill_to_select = (
                    "billing_no"
                    if "billing_no" in clients_columns
                    else "NULL::text AS billing_no"
                )
                alt_phone_select = (
                    "cell_phone"
                    if "cell_phone" in clients_columns
                    else "NULL::text AS cell_phone"
                )
                cc_info_select = (
                    "contact_info"
                    if "contact_info" in clients_columns
                    else "NULL::text AS contact_info"
                )

                cur.execute(
                    f"""
                    SELECT client_name, primary_phone, email, address_line1,
                           {bill_to_select}, {alt_phone_select},
                           {cc_info_select}
                    FROM clients
                    WHERE client_id = %s
                """,
                    (self.client_id,),
                )

                row = cur.fetchone()

            if row:
                name, phone, email, address, bill_to, alt_phone, cc_info = row
                self.name_input.setText(name or "")
                self.phone_input.setText(phone or "")
                self.email_input.setText(email or "")
                self.address_input.setText(address or "")
                self.bill_to_input.setText(bill_to or "")
                self.alt_phone_input.setText(alt_phone or "")
                self.cc_info_input.setText(cc_info or "")
        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load client: {e}")

    def save_changes(self) -> None:
        """Save changes to client"""
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        bill_to = self.bill_to_input.text().strip()
        alt_phone = self.alt_phone_input.text().strip()
        cc_info = self.cc_info_input.text().strip()

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                clients_columns = _get_clients_columns(cur)

                set_clauses = [
                    "client_name = %s",
                    "primary_phone = %s",
                    "email = %s",
                    "address_line1 = %s",
                ]
                params = [name, phone, email, address]

                optional_updates = {
                    "billing_no": bill_to or None,
                    "cell_phone": alt_phone or None,
                    "contact_info": cc_info or None,
                }
                for column_name, value in optional_updates.items():
                    if column_name in clients_columns:
                        set_clauses.append(f"{column_name} = %s")
                        params.append(value)

                params.append(self.client_id)
                cur.execute(
                    f"UPDATE clients SET {', '.join(set_clauses)} "
                    f"WHERE client_id = %s",
                    params,
                )

            QMessageBox.information(
                self, "Success", "Client information updated"
            )
            self.accept()
        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save changes: {e}")


class ImprovedCustomerWidget(QWidget):
    """Improved customer information widget with professional UX"""

    # Signals
    changed = pyqtSignal()  # Emitted when any field changes
    saved = pyqtSignal(int)  # Emitted when data is saved (client_id)
    client_selected = pyqtSignal(int)  # Emitted when a client is chosen from dropdown

    def __init__(self, db_connection, parent=None) -> None:
        super().__init__(parent)
        self.db = db_connection
        self.is_saved = True  # Track if changes have been made
        self.is_edit_mode = False  # Track if we're in edit mode
        self.current_client_id = None
        self.client_ids_map = {}  # Map client names to IDs for quick lookup
        self.client_ids_map_ci = {}  # Case-insensitive lookup
        self._loading_client_fields = False
        self._suppress_autosave = False

        self.init_ui()
        self.load_client_list()

    def init_ui(self) -> None:
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
        phone_col.addWidget(
            QLabel(
                "Phone:",
            )
        )
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
        self.add_client_btn = QPushButton("➕ New Client")
        self.add_client_btn.setMaximumWidth(100)
        self.add_client_btn.clicked.connect(self.add_new_client)
        client_row.addWidget(self.add_client_btn)

        # Edit client button - MOVED TO LEFT
        self.edit_client_btn = QPushButton("✏️ Edit")
        self.edit_client_btn.setMaximumWidth(80)
        self.edit_client_btn.clicked.connect(self.edit_current_client)
        client_row.addWidget(self.edit_client_btn)

        client_row.addSpacing(15)

        client_row.addWidget(QLabel("Client: *"))

        self.client_combo = QComboBox()
        self.client_combo.setEditable(True)
        self.client_combo.setMaximumWidth(300)
        self.client_combo.currentTextChanged.connect(self.on_client_selected)
        self.client_combo.editTextChanged.connect(self.on_form_changed)
        if self.client_combo.lineEdit():
            self.client_combo.lineEdit().editingFinished.connect(
                self._autosave_on_focus_out
            )
        client_row.addWidget(self.client_combo)

        client_row.addStretch()
        form_layout.addRow(client_row)
        # Phone (standard phone width)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("(403) 555-1234")
        self.phone_input.setMaximumWidth(150)
        self.phone_input.textChanged.connect(self.on_form_changed)
        self.phone_input.editingFinished.connect(self._autosave_on_focus_out)
        form_layout.addRow("Phone: *", self.phone_input)

        # Email (wider for email addresses)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        self.email_input.setMaximumWidth(300)
        self.email_input.textChanged.connect(self.on_form_changed)
        self.email_input.editingFinished.connect(self._autosave_on_focus_out)
        form_layout.addRow("Email:", self.email_input)

        # Address (standard address width)
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Street address")
        self.address_input.setMaximumWidth(400)
        self.address_input.textChanged.connect(self.on_form_changed)
        self.address_input.editingFinished.connect(self._autosave_on_focus_out)
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

    def load_client_list(self) -> None:
        """Load all clients from database for autocomplete"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute("""
                    SELECT client_id, client_name
                    FROM clients
                    WHERE client_name IS NOT NULL
                    AND client_name NOT ILIKE '%party bus%'
                    AND client_name NOT ILIKE '%limo bus%'
                    AND client_name NOT ILIKE '%passenger%'
                    AND client_name NOT ILIKE '%ute%'
                    AND client_name NOT ILIKE '%vehicle%'
                    ORDER BY client_name
                """)

                self.client_ids_map = {}
                self.client_ids_map_ci = {}
                client_names = []

                for client_id, name in cur.fetchall():
                    if _is_noise_client_name(name):
                        continue
                    self.client_ids_map[name] = client_id
                    if name:
                        self.client_ids_map_ci[name.strip().casefold()] = (
                            client_id
                        )
                    client_names.append(name)

            # Clear existing items and set autocomplete model
            self.client_combo.blockSignals(True)
            self.client_combo.clear()
            self.client_combo.addItem(_PLACEHOLDER)  # index 0: no selection
            self.client_combo.addItems(client_names)
            self.client_combo.blockSignals(False)
            completer = QCompleter(client_names)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.client_combo.setCompleter(completer)

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load clients: {e}")

    def on_client_selected(self, client_name) -> None:
        """Load selected client details"""
        normalized_name = (client_name or "").strip()
        if not normalized_name or normalized_name == _PLACEHOLDER:
            self.current_client_id = None
            return
        if _is_noise_client_name(normalized_name):
            self.current_client_id = None
            return

        selected_client_id = self.client_ids_map.get(normalized_name)
        if not selected_client_id:
            selected_client_id = self.client_ids_map_ci.get(
                normalized_name.casefold()
            )
        if not selected_client_id:
            self.current_client_id = None
            return

        self.current_client_id = selected_client_id
        self.client_selected.emit(selected_client_id)

        try:
            self._loading_client_fields = True
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT primary_phone, email, address_line1
                    FROM clients
                    WHERE client_id = %s
                """,
                    (self.current_client_id,),
                )

                row = cur.fetchone()

            if row:
                phone, email, address = row
                self.phone_input.setText(phone or "")
                self.email_input.setText(email or "")
                self.address_input.setText(address or "")
        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to load client details: {e}"
            )
        finally:
            self._loading_client_fields = False

    def add_new_client(self) -> None:
        """Add new client"""
        dialog = QuickAddClientDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Reload client list and select the new one
            self.load_client_list()
            if dialog.new_client_id:
                # Find and select the new client
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    cur.execute(
                        "SELECT client_name FROM clients WHERE client_id = %s",
                        (dialog.new_client_id,),
                    )
                    row = cur.fetchone()
                if row:
                    client_name = row[0]
                    # Set the combo box to the new client (triggers
                    # on_client_selected)
                    index = self.client_combo.findText(client_name)
                    if index >= 0:
                        self.client_combo.setCurrentIndex(index)
                        # Also manually trigger the load in case signal doesn't
                        # fire
                        self.on_client_selected(client_name)
                # Auto-save: client is already in DB — immediately link it
                # to the charter without requiring an extra button click.
                if self.current_client_id:
                    self.is_saved = True
                    self.save_btn.setEnabled(False)
                    self.saved.emit(self.current_client_id)
                    self.show_display_mode()

    def edit_current_client(self) -> None:
        """Edit current client"""
        if not self.current_client_id:
            QMessageBox.warning(self, "Warning", "Select a client first")
            return

        dialog = EditClientDialog(self.db, self.current_client_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Reload client details
            client_name = self.client_combo.currentText()
            self.on_client_selected(client_name)

    def on_form_changed(self) -> None:
        """Called when any form field changes"""
        if self._loading_client_fields:
            return
        self.is_saved = False
        self.save_btn.setEnabled(True)
        self.changed.emit()

    def _autosave_on_focus_out(self) -> None:
        """Autosave only when a field loses focus for quieter DB writes."""
        if self._suppress_autosave or self._loading_client_fields:
            return
        if self.is_saved:
            return
        self._save_customer_impl(show_feedback=False)

    def save_customer(self) -> None:
        """Save customer information (manual save button)."""
        self._save_customer_impl(show_feedback=True)

    def _save_customer_impl(self, show_feedback: bool) -> object:
        """Save customer information, creating a client row when name is"
        "new."""

        client_name = self.client_combo.currentText().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()

        if not client_name or not phone:
            if show_feedback:
                QMessageBox.warning(
                    self, "Validation", "Client name and phone are required"
                )
            return False

        if _is_noise_client_name(client_name):
            if show_feedback:
                QMessageBox.warning(
                    self,
                    "Validation",
                    "This client name format is invalid. Please select a real client name.",
                )
            return False

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                selected_client_id = self.current_client_id

                if not selected_client_id:
                    cur.execute(
                        """
                        SELECT client_id
                        FROM clients
                        WHERE LOWER(client_name) = LOWER(%s)
                        ORDER BY client_id DESC
                        LIMIT 1
                        """,
                        (client_name,),
                    )
                    row = cur.fetchone()
                    if row:
                        selected_client_id = row[0]

                if selected_client_id:
                    cur.execute(
                        """
                        UPDATE clients
                        SET client_name = %s,
                            primary_phone = %s,
                            email = %s,
                            address_line1 = %s
                        WHERE client_id = %s
                        """,
                        (
                            client_name,
                            phone,
                            email or None,
                            address or None,
                            selected_client_id,
                        ),
                    )
                    self.current_client_id = selected_client_id
                else:
                    cur.execute(
                        "SELECT MAX(CAST(account_number AS INTEGER)) FROM "
                        "clients WHERE account_number ~ '^[0-9]+$'"
                    )
                    max_account = cur.fetchone()[0] or 7604
                    new_account_number = str(int(max_account) + 1)

                    cur.execute(
                        """
                        INSERT INTO clients (account_number, client_name,
                        primary_phone, email, address_line1)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING client_id
                        """,
                        (
                            new_account_number,
                            client_name,
                            phone,
                            email or None,
                            address or None,
                        ),
                    )
                    self.current_client_id = cur.fetchone()[0]

            self.client_ids_map[client_name] = self.current_client_id
            self.client_ids_map_ci[client_name.casefold()] = (
                self.current_client_id
            )

            self._suppress_autosave = True
            idx = self.client_combo.findText(client_name)
            if idx < 0:
                self.client_combo.addItem(client_name)
                idx = self.client_combo.findText(client_name)
            if idx >= 0:
                self.client_combo.setCurrentIndex(idx)
            self._suppress_autosave = False

            self.is_saved = True
            self.save_btn.setEnabled(False)
            self.saved.emit(self.current_client_id)

            if show_feedback:
                self.show_display_mode()
                QMessageBox.information(
                    self,
                    "Success",
                    f"Client '{client_name}' saved successfully",
                )

            return True
        except Exception as e:
            self._suppress_autosave = False
            logger.error(f"Failed: {e}")
            if show_feedback:
                QMessageBox.critical(
                    self, "Error", f"Failed to save customer: {e}"
                )
            return False

    def enter_edit_mode(self) -> None:
        """Enter edit mode"""
        self._suppress_autosave = False
        self.is_edit_mode = True
        self.display_frame.hide()
        self.edit_frame.show()

    def cancel_edit(self) -> None:
        """Cancel edit and return to display mode"""
        self.is_edit_mode = False
        self.is_saved = True
        self.save_btn.setEnabled(False)
        self.show_display_mode()

    def show_display_mode(self) -> None:
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
        if client_name and client_name != _PLACEHOLDER:
            self.client_display.setText(client_name)
        else:
            self.client_display.setText("⚠️ No client — please add one")
        self.phone_display.setText(phone or "")
        self.email_display.setText(email or "")
        self.address_display.setText(address or "")

    def set_charter_data(self, charter_id, reserve_number, client_id,
                          fallback_display_name: str = "") -> None:
        """Set charter data for display"""
        self.reserve_input.setText(reserve_number or "")
        self.reserve_display.setText(reserve_number or "-----")
        # Set the authoritative client_id from the DB record FIRST.
        # Must not be overwritten by on_client_selected signal below.
        self.current_client_id = client_id

        # Load client details if client_id is provided
        if client_id:
            try:
                with DatabaseContext(self.db, auto_commit=False) as cur:
                    cur.execute(
                        """
                        SELECT client_name, primary_phone, email, address_line1
                        FROM clients
                        WHERE client_id = %s
                    """,
                        (client_id,),
                    )

                    row = cur.fetchone()

                if row:
                    name, phone, email, address = row
                    # Block signals so on_client_selected cannot null out
                    # current_client_id when the name is not yet in the map.
                    self.client_combo.blockSignals(True)
                    try:
                        self.client_combo.setCurrentText(name)
                        # Ensure the name is resolvable for future edits.
                        if name:
                            self.client_ids_map[name] = client_id
                            self.client_ids_map_ci[
                                name.strip().casefold()] = client_id
                    finally:
                        self.client_combo.blockSignals(False)
                    self.phone_input.setText(phone or "")
                    self.email_input.setText(email or "")
                    self.address_input.setText(address or "")
                    self.show_display_mode()
            except Exception as e:
                logger.error(f"Failed: {e}")
                QMessageBox.critical(
                    self, "Error", f"Failed to load customer: {e}"
                )
        else:
            # No client linked — reset combo to placeholder
            self.client_combo.blockSignals(True)
            try:
                self.client_combo.setCurrentIndex(0)  # placeholder
            finally:
                self.client_combo.blockSignals(False)
            self.phone_input.clear()
            self.email_input.clear()
            self.address_input.clear()
            # If a display name was stored on the charter even without a
            # client_id FK, show it so the form doesn't look broken.
            if fallback_display_name:
                self.client_display.setText(fallback_display_name)
            self.show_display_mode()
            # Restore fallback name after show_display_mode may have cleared it
            if fallback_display_name:
                self.client_display.setText(fallback_display_name)

    def get_customer_data(self) -> object:
        """Get current customer data"""
        return {
            "reserve_number": self.reserve_input.text(),
            "client_id": self.current_client_id,
            "client_name": self.client_combo.currentText(),
            "phone": self.phone_input.text(),
            "email": self.email_input.text(),
            "address": self.address_input.text(),
        }
