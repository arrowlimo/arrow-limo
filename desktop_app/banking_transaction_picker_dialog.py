"""
Banking Transaction Picker Dialog - Select and link banking transactions to
receipts
"""

import logging

import psycopg2
from db_error_handling import DatabaseContext
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class BankingTransactionPickerDialog(QDialog):
    """Dialog to select and link a banking transaction to a receipt."""

    def __init__(
        self,
        conn: psycopg2.extensions.connection,
        receipt_id: int,
        receipt_amount: float,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.receipt_id = receipt_id
        self.receipt_amount = receipt_amount
        self.selected_transaction = None  # (transaction_id, linked_amount)

        self.setWindowTitle(
            f"Link Banking Transaction - Receipt #{receipt_id}"
            f"(${receipt_amount:.2f})"
        )
        self.setGeometry(150, 150, 1200, 600)
        self.setModal(True)

        self._build_ui()
        self._load_unmatched_transactions()

    def _build_ui(self) -> None:
        """Build the picker dialog UI."""
        layout = QVBoxLayout(self)

        # Info
        info = QLabel(
            f"Select a banking transaction to link to Receipt"
            f"#{self.receipt_id} (${self.receipt_amount:.2f})"
        )
        info.setStyleSheet("font-weight: bold; color: #333;")
        layout.addWidget(info)

        # Search filters
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Date From:"))
        self.date_from = QDateEdit()
        self.date_from.setDate(
            QDate.currentDate().addMonths(-3)
        )  # Last 3 months
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        filter_layout.addWidget(self.date_to)

        filter_layout.addWidget(QLabel("Amount (approx):"))
        self.amount_filter = QDoubleSpinBox()
        self.amount_filter.setRange(0, 999999.99)
        self.amount_filter.setValue(self.receipt_amount)
        self.amount_filter.setDecimals(2)
        filter_layout.addWidget(self.amount_filter)

        filter_layout.addWidget(QLabel("Account:"))
        self.account_filter = QComboBox()
        self.account_filter.addItem("All Accounts", None)
        self._load_account_list()
        filter_layout.addWidget(self.account_filter)

        search_btn = QPushButton("🔍 Search")
        search_btn.clicked.connect(self._load_unmatched_transactions)
        filter_layout.addWidget(search_btn)

        layout.addLayout(filter_layout)

        # Transactions table
        self.transactions_table = QTableWidget()
        self.transactions_table.setColumnCount(7)
        self.transactions_table.setHorizontalHeaderLabels(
            [
                "Transaction Date",
                "Description",
                "Debit",
                "Credit",
                "Balance",
                "Account",
                "Link Amount",
            ]
        )
        self.transactions_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.transactions_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.transactions_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.transactions_table.itemSelectionChanged.connect(
            self._on_transaction_selected
        )
        layout.addWidget(self.transactions_table)

        # Link amount editor
        link_layout = QHBoxLayout()
        link_layout.addWidget(QLabel("Link Amount:"))
        self.link_amount_edit = QDoubleSpinBox()
        self.link_amount_edit.setRange(0, 999999.99)
        self.link_amount_edit.setValue(self.receipt_amount)
        self.link_amount_edit.setDecimals(2)
        self.link_amount_edit.setMinimumWidth(100)
        link_layout.addWidget(self.link_amount_edit)
        link_layout.addWidget(QLabel(f"(Receipt: ${self.receipt_amount:.2f})"))
        link_layout.addStretch()
        layout.addLayout(link_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        link_btn = QPushButton("✅ Link Transaction")
        link_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        link_btn.clicked.connect(self._link_selected_transaction)
        btn_layout.addWidget(link_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _load_account_list(self) -> None:
        """Load unique bank accounts for the filter."""
        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute("""
                    SELECT DISTINCT account_number
                    FROM banking_transactions
                    WHERE account_number IS NOT NULL
                    ORDER BY account_number
                """)
                for (account,) in cur.fetchall():
                    self.account_filter.addItem(account, account)
        except Exception as _e:
            logger.debug('Suppressed: %s', _e)  # Fail silently if accounts can't be loaded

    def _load_unmatched_transactions(self) -> None:
        """Load unmatched banking transactions within date range and amount"
        "tolerance."""

        try:
            date_from = self.date_from.date().toPyDate()
            date_to = self.date_to.date().toPyDate()
            amount = float(self.amount_filter.value())
            # 10% or $50, whichever is larger
            tolerance = max(amount * 0.1, 50)

            # Build query with account filter
            query = """
                SELECT transaction_id, transaction_date, description,
                       debit_amount, credit_amount, balance, account_number
                FROM banking_transactions
                WHERE transaction_date BETWEEN %s AND %s
                AND (
                    reconciliation_status IS NULL
                    OR reconciliation_status = 'unmatched'
                )
                AND (debit_amount
                BETWEEN %s AND %s OR credit_amount BETWEEN %s AND %s)
                AND receipt_id IS NULL
            """
            params = [
                date_from,
                date_to,
                amount - tolerance,
                amount + tolerance,
                amount - tolerance,
                amount + tolerance,
            ]

            # Add account filter if selected
            selected_account = self.account_filter.currentData()
            if selected_account:
                query += " AND account_number = %s"
                params.append(selected_account)

            query += (
                " ORDER BY transaction_date DESC, "
                "transaction_id DESC LIMIT 1000"
            )

            # Find unmatched transactions
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

            self.transactions_table.setRowCount(len(rows))
            exact_match_count = 0

            for r, (
                txn_id,
                txn_date,
                desc,
                debit,
                credit,
                balance,
                account,
            ) in enumerate(rows):

                # Check if this is an exact match (within $0.01)
                amt = debit or credit or 0
                is_exact_match = abs(amt - self.receipt_amount) < 0.01

                if is_exact_match:
                    exact_match_count += 1

                date_item = QTableWidgetItem(str(txn_date))
                if is_exact_match:
                    date_item.setBackground(
                        QColor(212, 237, 218)
                    )  # Light green
                self.transactions_table.setItem(r, 0, date_item)

                desc_item = QTableWidgetItem(desc or "")
                if is_exact_match:
                    desc_item.setBackground(
                        QColor(212, 237, 218)
                    )  # Light green
                self.transactions_table.setItem(r, 1, desc_item)

                debit_item = QTableWidgetItem(f"${debit:.2f}" if debit else "")
                debit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                if is_exact_match:
                    debit_item.setBackground(
                        QColor(212, 237, 218)
                    )  # Light green
                self.transactions_table.setItem(r, 2, debit_item)

                credit_item = QTableWidgetItem(
                    f"${credit:.2f}" if credit else ""
                )
                credit_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                if is_exact_match:
                    credit_item.setBackground(
                        QColor(212, 237, 218)
                    )  # Light green
                self.transactions_table.setItem(r, 3, credit_item)

                balance_item = QTableWidgetItem(
                    f"${balance:.2f}" if balance else ""
                )
                balance_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                if is_exact_match:
                    balance_item.setBackground(
                        QColor(212, 237, 218)
                    )  # Light green
                self.transactions_table.setItem(r, 4, balance_item)

                account_item = QTableWidgetItem(account or "")
                if is_exact_match:
                    account_item.setBackground(
                        QColor(212, 237, 218)
                    )  # Light green
                self.transactions_table.setItem(r, 5, account_item)

                # Store transaction_id in last column (hidden from view)
                amt_item = QTableWidgetItem(f"${amt:.2f}")
                amt_item.setData(Qt.ItemDataRole.UserRole, txn_id)
                amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
                if is_exact_match:
                    amt_item.setBackground(
                        QColor(212, 237, 218)
                    )  # Light green
                self.transactions_table.setItem(r, 6, amt_item)

            # Update window title with results count
            self.setWindowTitle(
                f"Link Banking Transaction - Receipt #{self.receipt_id}"
                f"(${self.receipt_amount:.2f}) - "
                f"{len(rows)} transaction(s) found ({exact_match_count} exact"
                f"match{'es' if exact_match_count != 1 else ''})"
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Could not load banking transactions: {e}"
            )

    def _on_transaction_selected(self) -> None:
        """Update link amount when transaction is selected."""
        selected = self.transactions_table.selectedItems()
        if selected:
            # Get the amount from row (debit or credit)
            row = selected[0].row()
            debit_item = self.transactions_table.item(row, 2)
            credit_item = self.transactions_table.item(row, 3)

            debit_text = debit_item.text().replace("$", "").strip()
            credit_text = credit_item.text().replace("$", "").strip()

            try:
                amt = (
                    float(debit_text)
                    if debit_text
                    else (float(credit_text) if credit_text else 0)
                )
                self.link_amount_edit.setValue(amt)
            except Exception as _e:
                logger.debug('Suppressed: %s', _e)
    def _link_selected_transaction(self) -> None:
        """Link the selected transaction to the receipt."""
        selected = self.transactions_table.selectedItems()
        if not selected:
            QMessageBox.warning(
                self, "No Selection", "Select a transaction to link"
            )
            return

        row = selected[0].row()
        txn_id_item = self.transactions_table.item(row, 6)
        txn_id = txn_id_item.data(Qt.ItemDataRole.UserRole)
        link_amount = float(self.link_amount_edit.value())

        if link_amount <= 0:
            QMessageBox.warning(
                self, "Invalid Amount", "Link amount must be greater than 0"
            )
            return

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                # Insert receipt_banking_link
                cur.execute(
                    """
                    INSERT INTO receipt_banking_links
                    (receipt_id, transaction_id, linked_amount, link_status,
                    linked_at)
                    VALUES (%s, %s, %s, 'matched', NOW())
                    ON CONFLICT (receipt_id, transaction_id) DO UPDATE
                    SET linked_amount = %s, link_status = 'matched'
                """,
                    (self.receipt_id, txn_id, link_amount, link_amount),
                )

                # Update banking_transaction to link back
                cur.execute(
                    """
                    UPDATE banking_transactions
                    SET receipt_id = %s, reconciliation_status = 'matched'
                    WHERE transaction_id = %s
                """,
                    (self.receipt_id, txn_id),
                )

            self.selected_transaction = (txn_id, link_amount)
            QMessageBox.information(
                self,
                "Success",
                f"✅ Linked ${link_amount:.2f} from banking transaction",
            )
            self.accept()

        except Exception as e:
            logger.error(f"Failed to link transaction: {e}")
            QMessageBox.critical(
                self, "Error", f"Could not link transaction: {e}"
            )

    def get_result(self) -> tuple[int, float] | None:
        """Return (transaction_id, linked_amount) or None."""
        return self.selected_transaction
