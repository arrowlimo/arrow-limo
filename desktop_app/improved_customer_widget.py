"""
Improved Customer Information Widget with professional UX:
- Compact reserve number field (8 chars, display-only after save)
- Client lookup with autocomplete and add/edit functionality
- Optimized field sizing (phone, address, etc. use standard widths)
- Conditional Save button (visible only on changes)
- Read-only display mode after save
"""

import re

import psycopg2

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
    QInputDialog,
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


def _is_account_number_unique_violation(error: psycopg2.Error) -> bool:
    """Return True when a DB error is a unique conflict on account_number."""
    constraint_name = (
        getattr(getattr(error, "diag", None), "constraint_name", "") or ""
    ).lower()
    message = str(error).lower()
    return (
        "account_number" in constraint_name
        or (
            "unique" in message
            and "account_number" in message
            and "clients" in message
        )
    )


def _next_client_account_number(cur) -> str:
    """Get next client account number from shared sequence, fallback to MAX+1."""
    try:
        cur.execute("SAVEPOINT acct_seq")
        cur.execute("SELECT nextval('account_number_seq')")
        account_number = str(int(cur.fetchone()[0]))
        cur.execute("RELEASE SAVEPOINT acct_seq")
        return account_number
    except Exception:
        cur.execute("ROLLBACK TO SAVEPOINT acct_seq")
        cur.execute(
            "SELECT MAX(CAST(account_number AS INTEGER)) FROM clients "
            "WHERE account_number ~ '^[0-9]+$'"
        )
        max_account = cur.fetchone()[0] or 7604
        return str(int(max_account) + 1)


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


def _normalize_client_lookup(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").casefold())


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

        address_row = QHBoxLayout()
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("City")
        address_row.addWidget(self.city_input)
        self.province_input = QLineEdit()
        self.province_input.setPlaceholderText("Province")
        self.province_input.setMaximumWidth(120)
        address_row.addWidget(self.province_input)
        self.postal_input = QLineEdit()
        self.postal_input.setPlaceholderText("Postal code")
        self.postal_input.setMaximumWidth(120)
        address_row.addWidget(self.postal_input)
        form_layout.addRow("City / Province / Postal:", address_row)

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
        phone = self.phone_input.text().strip() or None
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        city = self.city_input.text().strip()
        province = self.province_input.text().strip()
        postal = self.postal_input.text().strip()
        bill_to = self.bill_to_input.text().strip()
        alt_phone = self.alt_phone_input.text().strip() or None
        cc_info = self.cc_info_input.text().strip()

        if not name:
            QMessageBox.warning(
                self, "Validation", "Client Name is required"
            )
            return

        try:
            with DatabaseContext(self.db, auto_commit=True) as cur:
                clients_columns = _get_clients_columns(cur)

                insert_columns = [
                    "account_number",
                    "client_name",
                    "primary_phone",
                    "email",
                    "address_line1",
                ]
                values = [
                    name,
                    phone or None,
                    email or None,
                    address or None,
                ]

                address_optional_values = {
                    "city": city or None,
                    "province": province or None,
                    "postal_code": postal or None,
                }
                for column_name, value in address_optional_values.items():
                    if column_name in clients_columns:
                        insert_columns.append(column_name)
                        values.append(value)

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
                new_account_number = None
                last_error = None
                for _attempt in range(2):
                    new_account_number = _next_client_account_number(cur)
                    attempt_values = [new_account_number, *values]
                    cur.execute("SAVEPOINT client_insert")
                    try:
                        cur.execute(
                            f"""
                            INSERT INTO clients ({column_clause})
                            VALUES ({placeholders})
                            RETURNING client_id
                        """,
                            attempt_values,
                        )
                        self.new_client_id = cur.fetchone()[0]
                        cur.execute("RELEASE SAVEPOINT client_insert")
                        last_error = None
                        break
                    except psycopg2.Error as insert_error:
                        cur.execute("ROLLBACK TO SAVEPOINT client_insert")
                        last_error = insert_error
                        if (
                            _attempt == 0
                            and _is_account_number_unique_violation(insert_error)
                        ):
                            continue
                        raise

                if last_error is not None:
                    raise last_error

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

        address_row = QHBoxLayout()
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("City")
        address_row.addWidget(self.city_input)
        self.province_input = QLineEdit()
        self.province_input.setPlaceholderText("Province")
        self.province_input.setMaximumWidth(120)
        address_row.addWidget(self.province_input)
        self.postal_input = QLineEdit()
        self.postal_input.setPlaceholderText("Postal code")
        self.postal_input.setMaximumWidth(120)
        address_row.addWidget(self.postal_input)
        form_layout.addRow("City / Province / Postal:", address_row)

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
                city_select = "city" if "city" in clients_columns else "NULL::text AS city"
                province_select = (
                    "province" if "province" in clients_columns else "NULL::text AS province"
                )
                postal_select = (
                    "postal_code"
                    if "postal_code" in clients_columns
                    else "NULL::text AS postal_code"
                )

                cur.execute(
                    f"""
                    SELECT client_name, primary_phone, email, address_line1,
                           {city_select}, {province_select}, {postal_select},
                           {bill_to_select}, {alt_phone_select},
                           {cc_info_select}
                    FROM clients
                    WHERE client_id = %s
                """,
                    (self.client_id,),
                )

                row = cur.fetchone()

            if row:
                (
                    name,
                    phone,
                    email,
                    address,
                    city,
                    province,
                    postal,
                    bill_to,
                    alt_phone,
                    cc_info,
                ) = row
                self.name_input.setText(name or "")
                self.phone_input.setText(phone or "")
                self.email_input.setText(email or "")
                self.address_input.setText(address or "")
                self.city_input.setText(city or "")
                self.province_input.setText(province or "")
                self.postal_input.setText(postal or "")
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
        city = self.city_input.text().strip()
        province = self.province_input.text().strip()
        postal = self.postal_input.text().strip()
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

                address_optional_updates = {
                    "city": city or None,
                    "province": province or None,
                    "postal_code": postal or None,
                }
                for column_name, value in address_optional_updates.items():
                    if column_name in clients_columns:
                        set_clauses.append(f"{column_name} = %s")
                        params.append(value)

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
        self.client_lookup_rows = []  # [(client_id, client_name)] for fuzzy match
        self._loading_client_fields = False
        self._suppress_autosave = False
        self._suppress_client_autoselect = False

        self.init_ui()
        self.load_client_list()

    def init_ui(self) -> None:
        """Initialize UI"""
        layout = QVBoxLayout()

        # ===== DISPLAY MODE (READ-ONLY) =====
        self.display_frame = QFrame()
        self.display_frame.setStyleSheet("QFrame { border: 0; }")
        display_layout = QVBoxLayout()
        display_layout.setContentsMargins(4, 4, 4, 4)
        display_layout.setSpacing(4)

        # Reserve number and client name header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        reserve_label = QLabel("Reserve #:")
        reserve_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(reserve_label)

        self.reserve_display = QLabel("")
        self.reserve_display.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.reserve_display.setStyleSheet("color: #0b3a63;")
        self.reserve_display.setMinimumWidth(100)

        client_label = QLabel("Client:")
        client_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(self.reserve_display)
        header_layout.addWidget(client_label)

        self.client_display = QLabel("")
        self.client_display.setFont(QFont("Arial", 10))
        self.client_display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_layout.addWidget(self.client_display)
        header_layout.addStretch()

        self.add_btn_display = QPushButton("➕ New Client")
        self.add_btn_display.setFixedWidth(100)
        self.add_btn_display.setFixedHeight(24)
        self.add_btn_display.clicked.connect(self.add_new_client)
        header_layout.addWidget(self.add_btn_display)

        self.edit_btn_display = QPushButton("✏️ Edit")
        self.edit_btn_display.setFixedWidth(70)
        self.edit_btn_display.setFixedHeight(24)
        self.edit_btn_display.clicked.connect(self.enter_edit_mode)
        header_layout.addWidget(self.edit_btn_display)

        display_layout.addLayout(header_layout)

        # Customer details display
        details_container = QWidget()
        details_layout = QHBoxLayout(details_container)
        details_layout.setSpacing(10)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_container.setMaximumHeight(48)

        phone_col = QVBoxLayout()
        phone_col.setSpacing(1)
        phone_col.addWidget(QLabel("Phone:"))
        self.phone_display = QLabel("")
        self.phone_display.setWordWrap(False)
        self.phone_display.setMaximumHeight(18)
        phone_col.addWidget(self.phone_display)
        details_layout.addLayout(phone_col)

        email_col = QVBoxLayout()
        email_col.setSpacing(1)
        email_col.addWidget(QLabel("Email:"))
        self.email_display = QLabel("")
        self.email_display.setWordWrap(False)
        self.email_display.setMaximumHeight(18)
        email_col.addWidget(self.email_display)
        details_layout.addLayout(email_col)

        address_col = QVBoxLayout()
        address_col.setSpacing(1)
        address_col.addWidget(QLabel("Address:"))
        self.address_display = QLabel("")
        self.address_display.setWordWrap(False)
        self.address_display.setMaximumHeight(18)
        address_col.addWidget(self.address_display)
        details_layout.addLayout(address_col)

        display_layout.addWidget(details_container)
        self.display_frame.setLayout(display_layout)
        layout.addWidget(self.display_frame)

        # ===== EDIT MODE (EDITABLE) =====
        self.edit_frame = QFrame()
        self.edit_frame.setStyleSheet("QFrame { border: 0; }")
        edit_layout = QVBoxLayout()
        edit_layout.setContentsMargins(4, 0, 4, 4)
        edit_layout.setSpacing(4)

        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(6)

        # Reserve number (display-only styling, not a box)
        reserve_row = QHBoxLayout()
        reserve_row.addWidget(QLabel("Reserve #:"))
        self.reserve_input = QLineEdit()
        self.reserve_input.setReadOnly(True)
        self.reserve_input.setFrame(False)
        self.reserve_input.setMaximumWidth(90)
        self.reserve_input.setPlaceholderText("Auto-gen")
        self.reserve_input.setStyleSheet(
            "QLineEdit { border: none; background: transparent; padding: 0; "
            "font-weight: bold; color: #0b3a63; }"
        )
        reserve_row.addWidget(self.reserve_input)
        reserve_row.addStretch()
        form_layout.addRow(reserve_row)

        # Client lookup with autocomplete - keep the selector primary and put the add/edit actions beside it.
        client_row = QHBoxLayout()
        client_row.setSpacing(8)

        client_row.addWidget(QLabel("Client: *"))

        self.client_combo = QComboBox()
        self.client_combo.setEditable(True)
        self.client_combo.setMinimumWidth(180)
        self.client_combo.setMaximumWidth(360)
        self.client_combo.currentTextChanged.connect(self._on_client_combo_text_changed)
        self.client_combo.activated.connect(self._confirm_client_selection)
        self.client_combo.editTextChanged.connect(self.on_form_changed)
        if self.client_combo.lineEdit():
            self.client_combo.lineEdit().setPlaceholderText("Type client name")
            self.client_combo.lineEdit().returnPressed.connect(self._confirm_client_selection)
            self.client_combo.lineEdit().editingFinished.connect(
                self._autosave_on_focus_out
            )
        client_row.addWidget(self.client_combo)

        self.add_client_btn = QPushButton("➕ New Client")
        self.add_client_btn.setFixedWidth(96)
        self.add_client_btn.setFixedHeight(24)
        self.add_client_btn.clicked.connect(self.add_new_client)
        client_row.addWidget(self.add_client_btn)

        self.edit_client_btn = QPushButton("✏️ Edit")
        self.edit_client_btn.setFixedWidth(68)
        self.edit_client_btn.setFixedHeight(24)
        self.edit_client_btn.clicked.connect(self.edit_current_client)
        client_row.addWidget(self.edit_client_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_edit)
        self.cancel_btn.setFixedHeight(24)
        self.cancel_btn.hide()
        client_row.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("💾 Save Client")
        self.save_btn.clicked.connect(self.save_customer)
        self.save_btn.setEnabled(False)
        self.save_btn.setFixedHeight(24)
        self.save_btn.hide()
        client_row.addWidget(self.save_btn)

        client_row.addStretch()
        form_layout.addRow(client_row)
        # Phone (standard phone width)
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("(403) 555-1234")
        self.phone_input.setMaximumWidth(150)
        self.phone_input.textChanged.connect(self.on_form_changed)
        self.phone_input.editingFinished.connect(self._autosave_on_focus_out)
        form_layout.addRow("Phone:", self.phone_input)

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

        address_row = QHBoxLayout()
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("City")
        self.city_input.setMaximumWidth(180)
        self.city_input.textChanged.connect(self.on_form_changed)
        self.city_input.editingFinished.connect(self._autosave_on_focus_out)
        address_row.addWidget(self.city_input)

        self.province_input = QLineEdit()
        self.province_input.setPlaceholderText("Province")
        self.province_input.setMaximumWidth(120)
        self.province_input.textChanged.connect(self.on_form_changed)
        self.province_input.editingFinished.connect(self._autosave_on_focus_out)
        address_row.addWidget(self.province_input)

        self.postal_input = QLineEdit()
        self.postal_input.setPlaceholderText("Postal code")
        self.postal_input.setMaximumWidth(120)
        self.postal_input.textChanged.connect(self.on_form_changed)
        self.postal_input.editingFinished.connect(self._autosave_on_focus_out)
        address_row.addWidget(self.postal_input)
        form_layout.addRow("City / Province / Postal:", address_row)

        edit_layout.addLayout(form_layout)

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
                self.client_lookup_rows = []
                client_names = []

                for client_id, name in cur.fetchall():
                    if _is_noise_client_name(name):
                        continue
                    self.client_ids_map[name] = client_id
                    if name:
                        self.client_ids_map_ci[name.strip().casefold()] = (
                            client_id
                        )
                        self.client_lookup_rows.append((int(client_id), str(name)))
                    client_names.append(name)

            # Clear existing items and set autocomplete model without forcing a
            # preselected default string that must be deleted before typing.
            self.client_combo.blockSignals(True)
            self.client_combo.clear()
            self.client_combo.addItems(client_names)
            self.client_combo.setCurrentIndex(-1)
            if self.client_combo.lineEdit():
                self.client_combo.lineEdit().clear()
            self.client_combo.blockSignals(False)
            completer = QCompleter(client_names)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            try:
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
            except Exception:
                pass
            self.client_combo.setCompleter(completer)

        except Exception as e:
            logger.error(f"Failed: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load clients: {e}")

    def _resolve_existing_client(self, typed_name: str) -> tuple:
        """Resolve a typed client name to an existing client, with ambiguity guard."""
        query = (typed_name or "").strip()
        if not query or query == _PLACEHOLDER:
            return None, "none", []

        direct_id = self.client_ids_map.get(query)
        if direct_id:
            return int(direct_id), "exact", []

        direct_id = self.client_ids_map_ci.get(query.casefold())
        if direct_id:
            return int(direct_id), "exact_ci", []

        query_key = _normalize_client_lookup(query)
        if not query_key:
            return None, "none", []

        scored = []
        query_lower = query.casefold()
        for client_id, client_name in self.client_lookup_rows:
            name = (client_name or "").strip()
            if not name:
                continue
            name_lower = name.casefold()
            name_key = _normalize_client_lookup(name)

            score = -1
            if name_key == query_key:
                score = 100
            elif name_lower == query_lower:
                score = 95
            elif name_lower.startswith(query_lower):
                score = 90
            elif query_lower in name_lower:
                score = 80
            else:
                tokens = [t for t in re.split(r"[^a-z0-9]+", name_lower) if t]
                if any(tok == query_lower for tok in tokens):
                    score = 75
                elif any(tok.startswith(query_lower) for tok in tokens):
                    score = 70

            if score >= 0:
                scored.append((score, int(client_id), name))

        if not scored:
            return None, "none", []

        scored.sort(key=lambda row: (row[0], -len(row[2]), -row[1]), reverse=True)
        best_score = scored[0][0]
        best_matches = [row for row in scored if row[0] == best_score]

        if best_score >= 90 and len(best_matches) == 1:
            return best_matches[0][1], "fuzzy_unique", []

        # For shorter inputs like "clarke", allow a single strong match;
        # for ambiguous terms like "harrison", force explicit user choice.
        if best_score >= 80 and len(best_matches) == 1 and len(query_key) >= 4:
            return best_matches[0][1], "contains_unique", []

        candidates = [row for row in scored if row[0] >= 70][:8]
        return None, "ambiguous", candidates

    def _prompt_for_ambiguous_client_choice(self, typed_name: str, candidates: list) -> object:
        """Let user choose the exact client when fuzzy lookup has multiple matches."""
        if not candidates:
            return None
        options = []
        option_to_id = {}
        for _score, client_id, client_name in candidates:
            label = f"{client_name} (ID {client_id})"
            options.append(label)
            option_to_id[label] = int(client_id)

        selected, ok = QInputDialog.getItem(
            self,
            "Choose Client",
            f"Multiple matches for '{typed_name}'. Select the exact client:",
            options,
            0,
            False,
        )
        if not ok or not selected:
            return None
        return option_to_id.get(selected)

    def _on_client_combo_text_changed(self, client_name) -> None:
        """Ignore partial typing until the dispatcher explicitly chooses a client."""
        if self._suppress_client_autoselect:
            return
        if self._loading_client_fields:
            return

        normalized_name = (client_name or "").strip()
        if not normalized_name or normalized_name == _PLACEHOLDER:
            self.current_client_id = None
            return
        if _is_noise_client_name(normalized_name):
            self.current_client_id = None
            return

        # Keep the field active while the user is still typing; only explicit
        # activation or save should resolve and load the customer details.
        self.current_client_id = None

    def _confirm_client_selection(self) -> None:
        """Resolve the current combo text only after the user confirms it."""
        client_name = self.client_combo.currentText()
        self._suppress_client_autoselect = True
        try:
            self.on_client_selected(client_name)
        finally:
            self._suppress_client_autoselect = False

    def on_client_selected(self, client_name) -> None:
        """Load selected client details after an explicit selection/confirmation."""
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
                clients_columns = _get_clients_columns(cur)
                city_expr = "city" if "city" in clients_columns else "NULL::text AS city"
                province_expr = (
                    "province" if "province" in clients_columns else "NULL::text AS province"
                )
                postal_expr = (
                    "postal_code"
                    if "postal_code" in clients_columns
                    else "NULL::text AS postal_code"
                )
                cur.execute(
                    f"""
                    SELECT primary_phone, email, address_line1,
                           {city_expr}, {province_expr}, {postal_expr}
                    FROM clients
                    WHERE client_id = %s
                """,
                    (self.current_client_id,),
                )

                row = cur.fetchone()

            if row:
                phone, email, address, city, province, postal = row
                self.phone_input.setText(phone or "")
                self.email_input.setText(email or "")
                self.address_input.setText(address or "")
                self.city_input.setText(city or "")
                self.province_input.setText(province or "")
                self.postal_input.setText(postal or "")
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
        phone = self.phone_input.text().strip() or None
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        city = self.city_input.text().strip()
        province = self.province_input.text().strip()
        postal = self.postal_input.text().strip()

        if not client_name or client_name == _PLACEHOLDER:
            # Explicit unlink flow: allow clearing the charter's client link.
            self.current_client_id = None
            self.phone_input.clear()
            self.email_input.clear()
            self.address_input.clear()
            self.city_input.clear()
            self.province_input.clear()
            self.postal_input.clear()
            self.is_saved = True
            self.save_btn.setEnabled(False)
            self.saved.emit(0)
            if show_feedback:
                self.show_display_mode()
                QMessageBox.information(
                    self,
                    "Success",
                    "Client link cleared for this charter",
                )
            return True

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
                match_mode = "selected"

                if not selected_client_id:
                    selected_client_id, match_mode, candidates = self._resolve_existing_client(client_name)
                    if match_mode == "ambiguous":
                        if not show_feedback:
                            return False
                        chosen_client_id = self._prompt_for_ambiguous_client_choice(
                            client_name,
                            candidates,
                        )
                        if not chosen_client_id:
                            return False
                        selected_client_id = int(chosen_client_id)
                        match_mode = "ambiguous_choice"

                if selected_client_id:
                    persisted_client_name = client_name
                    if match_mode in (
                        "fuzzy_unique",
                        "contains_unique",
                        "ambiguous_choice",
                    ):
                        cur.execute(
                            "SELECT client_name FROM clients WHERE client_id = %s",
                            (selected_client_id,),
                        )
                        name_row = cur.fetchone()
                        if name_row and name_row[0]:
                            persisted_client_name = str(name_row[0]).strip()

                    set_clauses = [
                        "client_name = %s",
                        "primary_phone = %s",
                        "email = %s",
                        "address_line1 = %s",
                    ]
                    params_update = [
                        persisted_client_name,
                        phone,
                        email or None,
                        address or None,
                    ]
                    for column_name, value in (
                        ("city", city or None),
                        ("province", province or None),
                        ("postal_code", postal or None),
                    ):
                        if column_name in clients_columns:
                            set_clauses.append(f"{column_name} = %s")
                            params_update.append(value)
                    for column_name, value in {
                        "billing_no": bill_to or None,
                        "cell_phone": alt_phone or None,
                        "contact_info": cc_info or None,
                    }.items():
                        if column_name in clients_columns:
                            set_clauses.append(f"{column_name} = %s")
                            params_update.append(value)
                    params_update.append(selected_client_id)
                    cur.execute(
                        f"UPDATE clients SET {', '.join(set_clauses)} WHERE client_id = %s",
                        params_update,
                    )
                    self.current_client_id = selected_client_id
                    client_name = persisted_client_name
                else:
                    new_account_number = None
                    last_error = None
                    for _attempt in range(2):
                        new_account_number = _next_client_account_number(cur)
                        cur.execute("SAVEPOINT client_insert")
                        try:
                            insert_columns = ["account_number", "client_name", "primary_phone", "email", "address_line1"]
                            insert_values = [new_account_number, client_name, phone, email or None, address or None]
                            for column_name, value in (
                                ("city", city or None),
                                ("province", province or None),
                                ("postal_code", postal or None),
                                ("billing_no", bill_to or None),
                                ("cell_phone", alt_phone or None),
                                ("contact_info", cc_info or None),
                            ):
                                if column_name in clients_columns:
                                    insert_columns.append(column_name)
                                    insert_values.append(value)
                            cur.execute(
                                f"""
                                INSERT INTO clients ({", ".join(insert_columns)})
                                VALUES ({", ".join(["%s"] * len(insert_columns))})
                                RETURNING client_id
                                """,
                                insert_values,
                            )
                            self.current_client_id = cur.fetchone()[0]
                            cur.execute("RELEASE SAVEPOINT client_insert")
                            last_error = None
                            break
                        except psycopg2.Error as insert_error:
                            cur.execute("ROLLBACK TO SAVEPOINT client_insert")
                            last_error = insert_error
                            if (
                                _attempt == 0
                                and _is_account_number_unique_violation(insert_error)
                            ):
                                continue
                            raise

                    if last_error is not None:
                        raise last_error

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
        """Show the standard compact client form.

        Saved/load paths used to switch to a separate read-only label view,
        while new charters used the editable form. Keeping one layout avoids
        the same Run Charter page looking different depending on how it was
        opened.
        """
        self.is_edit_mode = False
        self.display_frame.hide()
        self.edit_frame.show()
        self.cancel_btn.hide()
        self.save_btn.hide()
        self.save_btn.setEnabled(False)

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
        city = self.city_input.text().strip() if hasattr(self, "city_input") else ""
        province = self.province_input.text().strip() if hasattr(self, "province_input") else ""
        postal = self.postal_input.text().strip() if hasattr(self, "postal_input") else ""
        address_parts = [part for part in [address, city, province, postal] if part]
        self.address_display.setText("\n".join(address_parts))

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
                    clients_columns = _get_clients_columns(cur)
                    city_expr = "city" if "city" in clients_columns else "NULL::text AS city"
                    province_expr = (
                        "province" if "province" in clients_columns else "NULL::text AS province"
                    )
                    postal_expr = (
                        "postal_code"
                        if "postal_code" in clients_columns
                        else "NULL::text AS postal_code"
                    )
                    cur.execute(
                        f"""
                        SELECT client_name, primary_phone, email, address_line1,
                               {city_expr}, {province_expr}, {postal_expr}
                        FROM clients
                        WHERE client_id = %s
                    """,
                        (client_id,),
                    )

                    row = cur.fetchone()

                if row:
                    name, phone, email, address, city, province, postal = row
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
                    self.city_input.setText(city or "")
                    self.province_input.setText(province or "")
                    self.postal_input.setText(postal or "")
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
            self.city_input.clear()
            self.province_input.clear()
            self.postal_input.clear()
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
        client_name = (self.client_combo.currentText() or "").strip()
        if client_name == _PLACEHOLDER:
            client_name = ""
        return {
            "reserve_number": self.reserve_input.text(),
            "client_id": self.current_client_id,
            "client_name": client_name,
            "phone": self.phone_input.text(),
            "email": self.email_input.text(),
            "address": self.address_input.text(),
            "city": self.city_input.text(),
            "province": self.province_input.text(),
            "postal_code": self.postal_input.text(),
        }
