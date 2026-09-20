"""
Client Finder Dialog
Search for existing clients or create new ones
"""

import logging
import re
from difflib import SequenceMatcher

import psycopg2

from db_error_handling import DatabaseContext
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


def _norm_text(value: str) -> str:
    """Normalize text for tolerant name matching."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _get_clients_columns(cur) -> object:
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'clients'
    """)
    return {row[0] for row in cur.fetchall()}


def _is_account_number_unique_violation(error: psycopg2.Error) -> bool:
    """Return True when DB error indicates account number unique conflict."""
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
    """Get next account number from shared sequence; fallback to MAX+1."""
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


class ClientFinderDialog(QDialog):
    """Find existing client or create new one"""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.selected_client_id = None
        self.selected_client_name = None
        self.clients_data = []

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(180)
        self._search_timer.timeout.connect(self.search_clients)

        self.setWindowTitle("Find or Create Client")
        self.setGeometry(150, 150, 900, 500)
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize UI"""
        layout = QVBoxLayout()

        # ===== SEARCH SECTION =====
        search_group = QGroupBox("Find Existing Client")
        search_layout = QHBoxLayout()

        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Client name, phone, email...")
        self.search_input.textChanged.connect(self._schedule_search)
        search_layout.addWidget(self.search_input)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # ===== RESULTS TABLE =====
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(
            ["Client ID", "Name", "Phone", "Email", "Address"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.results_table.itemDoubleClicked.connect(
            self.select_client_from_table
        )
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

    def _schedule_search(self) -> None:
        """Debounce search while typing to keep the dialog responsive."""
        self._search_timer.start()

    def load_all_clients(self) -> None:
        """Load all clients into table, grouping children under parents"""
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Load all clients with their parent info
                cur.execute("""
                    SELECT
                        c.client_id,
                        COALESCE(c.company_name,
                        c.client_name) as display_name,
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
            logger.error(f"Failed to load clients: {e}")
            QMessageBox.warning(
                self, "Load Error", f"Failed to load clients: {e}"
            )

    def display_clients(self, clients) -> None:
        """Display clients in table with children grouped under parents"""
        self.results_table.setRowCount(len(clients))
        for row_idx, client in enumerate(clients):
            (
                client_id,
                display_name,
                full_name,
                phone,
                email,
                address,
                parent_id,
            ) = client

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

    def search_clients(self) -> None:
        """Filter clients based on search text, including parent and child"
        "relationships"""

        search_text = self.search_input.text().lower().strip()

        if not search_text:
            self.display_clients(self.clients_data)
            return

        db_rows = self._query_clients(search_text)
        if db_rows:
            self.display_clients(self._rank_matches(db_rows, search_text))
            return

        # Find matching clients
        matching_ids = set()
        _parent_child_map = {}  # Track parent-child relationships

        for client in self.clients_data:
            (
                client_id,
                display_name,
                full_name,
                phone,
                email,
                address,
                parent_id,
            ) = client

            # Check if this client matches
            if any(
                [
                    search_text in (display_name or "").lower(),
                    search_text in (full_name or "").lower(),
                    search_text in (phone or "").lower(),
                    search_text in (email or "").lower(),
                ]
            ):
                matching_ids.add(client_id)
                # Also add parent if searching for a child
                if parent_id and parent_id > 0:
                    matching_ids.add(parent_id)

        # When parent matches, include all children
        for client in self.clients_data:
            (
                client_id,
                display_name,
                full_name,
                phone,
                email,
                address,
                parent_id,
            ) = client
            if parent_id and parent_id in matching_ids:
                matching_ids.add(client_id)

        # Display matching clients and their families
        filtered = [c for c in self.clients_data if c[0] in matching_ids]
        # Sort by parent_id then client_id
        filtered.sort(key=lambda x: (x[6] or 0, x[0]))

        self.display_clients(filtered)

    def _query_clients(self, search_text: str) -> list:
        """Search full clients table, not only the initial cached subset."""
        terms = [t for t in re.split(r"\s+", search_text) if t]
        if not terms:
            return []

        clauses = []
        params = []
        for term in terms:
            like_val = f"%{term}%"
            clauses.append(
                "(COALESCE(c.company_name, '') ILIKE %s "
                "OR COALESCE(c.client_name, '') ILIKE %s "
                "OR COALESCE(c.primary_phone, '') ILIKE %s "
                "OR COALESCE(c.email, '') ILIKE %s)"
            )
            params.extend([like_val, like_val, like_val, like_val])

        where_sql = " OR ".join(clauses)
        try:
            with DatabaseContext(self.db, auto_commit=False) as cur:
                cur.execute(
                    f"""
                    SELECT
                        c.client_id,
                        COALESCE(c.company_name, c.client_name) as display_name,
                        c.client_name,
                        c.primary_phone,
                        c.email,
                        c.address_line1,
                        c.parent_client_id
                    FROM clients c
                    WHERE {where_sql}
                    ORDER BY COALESCE(c.parent_client_id, c.client_id), c.client_id
                    LIMIT 800
                    """,
                    params,
                )
                return cur.fetchall() or []
        except Exception as e:
            logger.warning("Client finder DB search failed: %s", e)
            return []

    def _rank_matches(self, rows: list, search_text: str) -> list:
        """Rank fuzzy name matches so near-typos still surface."""
        search_norm = _norm_text(search_text)
        terms = [t for t in re.split(r"\s+", search_text.lower()) if t]

        scored = []
        for row in rows:
            display_name = str(row[1] or "")
            full_name = str(row[2] or "")
            phone = str(row[3] or "")
            email = str(row[4] or "")
            haystack = " ".join([display_name, full_name, phone, email]).lower()

            base_score = 0.0
            if all(term in haystack for term in terms):
                base_score = 1.0
            else:
                cand_norm = _norm_text(" ".join([display_name, full_name]))
                if cand_norm:
                    base_score = SequenceMatcher(
                        None, search_norm, cand_norm
                    ).ratio()

            if base_score >= 0.58:
                scored.append((base_score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored] or rows

    def select_client_from_table(self, *_args) -> None:
        """Select client from table and close dialog"""
        selected = self.results_table.selectedItems()
        if not selected:
            QMessageBox.warning(
                self, "No Selection", "Please select a client from the list."
            )
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

    def create_new_client(self) -> None:
        """Create new client"""
        dialog = ClientInputDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get the new client ID from the dialog
            if dialog.new_client_id:
                self.selected_client_id = dialog.new_client_id
                self.selected_client_name = dialog.new_client_name
                self.accept()


class ClientInputDialog(QDialog):
    """Quick client input dialog"""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.new_client_id = None
        self.new_client_name = None

        self.setWindowTitle("New Client")
        self.setGeometry(200, 200, 560, 420)
        self.init_ui()

    def init_ui(self) -> None:
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

        self.bill_to_input = QLineEdit()
        self.bill_to_input.setPlaceholderText("Billing contact/name")
        form_layout.addRow("Bill To:", self.bill_to_input)

        self.alt_phone_input = QLineEdit()
        self.alt_phone_input.setPlaceholderText("Alternate phone number")
        form_layout.addRow("Alternate Phone:", self.alt_phone_input)

        self.cc_info_input = QLineEdit()
        self.cc_info_input.setPlaceholderText("CC info (e.g., VISA ****1234)")
        form_layout.addRow("CC Information:", self.cc_info_input)

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

    def save_client(self) -> None:
        """Save new client to database"""
        client_name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        email = self.email_input.text().strip()
        address = self.address_input.text().strip()
        city = self.city_input.text().strip()
        bill_to = self.bill_to_input.text().strip()
        alt_phone = self.alt_phone_input.text().strip()
        cc_info = self.cc_info_input.text().strip()

        if not client_name:
            QMessageBox.warning(
                self, "Missing Name", "Please enter client name."
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
                    "city",
                    "company_name",
                    "is_company",
                ]
                values = [
                    client_name,
                    phone or None,
                    email or None,
                    address or None,
                    city or None,
                    client_name,
                    False,
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
                account_number = None
                result = None
                last_error = None
                for _attempt in range(2):
                    account_number = _next_client_account_number(cur)
                    attempt_values = [account_number, *values]
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
                        result = cur.fetchone()
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

                self.new_client_id = result[0]
                self.new_client_name = client_name

            QMessageBox.information(
                self,
                "Success",
                f"Client '{client_name}' created successfully!",
            )
            self.accept()
        except Exception as e:
            logger.error(f"Failed to create client: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to create client: {e}"
            )
