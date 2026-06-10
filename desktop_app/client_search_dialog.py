"""
Client Search Dialog with Fuzzy Matching
Used for searching existing clients or creating new client before charter
creation
"""

import logging

from db_error_handling import DatabaseContext
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class ClientSearchDialog(QDialog):
    """Dialog to search and select existing client or create new one"""

    client_selected = pyqtSignal(int)  # Signal with client_id

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self._selected_client_id = None
        self.init_ui()

    def init_ui(self) -> None:
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
        self.search_input.setPlaceholderText(
            "Type client name, phone, or email (fuzzy search)..."
        )
        self.search_input.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(
            ["ID", "Client Name", "Phone", "Email", "Account #"]
        )
        self.results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.results_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
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
        self.status_label.setStyleSheet(
            "color: #666; font-style: italic; font-size: 10px;"
        )
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def on_search_changed(self, text) -> None:
        """Search for clients matching text (fuzzy match)"""
        self.results_table.setRowCount(0)

        if not text or len(text) < 2:
            self.status_label.setText(
                "Type at least 2 characters to search..."
            )
            return

        try:
            search_term = f"%{text}%"
            with DatabaseContext(self.db, auto_commit=False) as cur:
                # Fuzzy search across name, phone, email
                cur.execute(
                    """
                    SELECT client_id, client_name, phone, email, account_number
                    FROM clients
                    WHERE client_name ILIKE %s
                       OR phone ILIKE %s
                       OR email ILIKE %s
                    ORDER BY client_name ASC
                    LIMIT 50
                """,
                    (search_term, search_term, search_term),
                )

                rows = cur.fetchall()

            if rows:
                for row in rows:
                    client_id, name, phone, email, account_num = row
                    self.results_table.insertRow(self.results_table.rowCount())

                    # ID (hidden, but stored)
                    id_item = QTableWidgetItem(str(client_id))
                    id_item.setFlags(
                        id_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                    )
                    self.results_table.setItem(
                        self.results_table.rowCount() - 1, 0, id_item
                    )

                    # Name
                    name_item = QTableWidgetItem(name or "")
                    name_item.setFlags(
                        name_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                    )
                    self.results_table.setItem(
                        self.results_table.rowCount() - 1, 1, name_item
                    )

                    # Phone
                    phone_item = QTableWidgetItem(phone or "")
                    phone_item.setFlags(
                        phone_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                    )
                    self.results_table.setItem(
                        self.results_table.rowCount() - 1, 2, phone_item
                    )

                    # Email
                    email_item = QTableWidgetItem(email or "")
                    email_item.setFlags(
                        email_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                    )
                    self.results_table.setItem(
                        self.results_table.rowCount() - 1, 3, email_item
                    )

                    # Account #
                    acct_item = QTableWidgetItem(account_num or "")
                    acct_item.setFlags(
                        acct_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                    )
                    self.results_table.setItem(
                        self.results_table.rowCount() - 1, 4, acct_item
                    )

                self.status_label.setText(
                    f"Found {len(rows)} clients. Double-click to select, or"
                    f"click 'Select Client' button."
                )
            else:
                self.status_label.setText(
                    "No clients found matching your search."
                )

        except Exception as e:
            self.status_label.setText(f"❌ Search error: {str(e)[:50]}")
            print(f"Error searching clients: {e}")

    def on_client_double_clicked(self, index) -> None:
        """Handle double-click on client row"""
        self.select_client()

    def select_client(self) -> None:
        """Select the currently selected row"""
        row = self.results_table.currentRow()
        if row >= 0:
            client_id = int(self.results_table.item(row, 0).text())
            self._selected_client_id = client_id
            self.client_selected.emit(client_id)
            self.accept()
        else:
            QMessageBox.warning(
                self,
                "Warning",
                "Please select a client first or create a new one.",
            )

    def create_new_client(self) -> None:
        """Create a new client"""
        from client_drill_down import ClientDetailDialog

        dialog = ClientDetailDialog(self.db, client_id=None, parent=self)
        dialog.exec()

        new_client_id = dialog.client_id
        if new_client_id:
            self._selected_client_id = new_client_id
            self.client_selected.emit(new_client_id)
            self.accept()

    def get_selected_client_id(self) -> object:
        """Return the selected client ID"""
        return self._selected_client_id
