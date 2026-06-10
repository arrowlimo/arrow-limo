"""Cheque register management widget for the desktop accounting area."""

import logging

import psycopg2
from common_widgets import StandardDateEdit
from db_error_handling import DatabaseContext
from print_export_helper import PrintExportHelper
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from simple_receipt_editor import SimpleReceiptEditor

logger = logging.getLogger(__name__)


class NumericTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically instead of lexicographically."""

    def __lt__(self, other) -> object:
        try:
            return float(self.text().replace(",", "")) < float(
                other.text().replace(",", "")
            )
        except (ValueError, AttributeError):
            return super().__lt__(other)


def _normalize_status(status: str | None) -> str:
    value = (status or "PENDING").strip().upper()
    if value == "":
        return "PENDING"
    return value


def _bank_label(account_number: str | None) -> str:
    value = (account_number or "").strip()
    if value == "903990106011":
        return "Scotia 903990106011"
    if value == "0228362":
        return "CIBC 0228362"
    if value == "1615":
        return "CIBC 1615"
    if not value:
        return ""
    return value


class ChequeEditDialog(QDialog):
    """Add or edit a cheque register row."""

    def __init__(
        self,
        conn: psycopg2.extensions.connection,
        bank_accounts: list[str],
        cheque_id: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.bank_accounts = bank_accounts
        self.cheque_id = cheque_id
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setWindowTitle(
            "Edit Check Details"
            if cheque_id is not None
            else "Add Check Written"
        )
        self._build_ui()
        if cheque_id is not None:
            self._load_cheque()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.cheque_number = QLineEdit()
        form.addRow("Check Number:", self.cheque_number)

        self.cheque_date = StandardDateEdit(allow_blank=True)
        form.addRow("Check Date:", self.cheque_date)

        self.cleared_date = StandardDateEdit(allow_blank=True)
        form.addRow("Cleared Date:", self.cleared_date)

        self.payee = QLineEdit()
        form.addRow("Vendor / Payee:", self.payee)

        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 9_999_999.99)
        self.amount.setDecimals(2)
        self.amount.setPrefix("$")
        self.amount.setMaximumWidth(140)
        form.addRow("Amount:", self.amount)

        self.account_number = QComboBox()
        self.account_number.setEditable(True)
        self.account_number.addItem("", "")
        for account_number in self.bank_accounts:
            self.account_number.addItem(
                _bank_label(account_number), account_number
            )
        form.addRow("Bank Account:", self.account_number)

        self.status = QComboBox()
        self.status.addItems(["PENDING", "CLEARED", "VOID", "NSF"])
        form.addRow("Status:", self.status)

        self.banking_transaction_id = QLineEdit()
        self.banking_transaction_id.setPlaceholderText(
            "Optional banking transaction ID"
        )
        form.addRow("Banking Txn ID:", self.banking_transaction_id)

        self.memo = QTextEdit()
        self.memo.setMaximumHeight(120)
        form.addRow("Memo / Notes:", self.memo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_cheque(self) -> None:
        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute(
                    """
                    SELECT cheque_number,
                           cheque_date,
                           cleared_date,
                           payee,
                           amount,
                           memo,
                           banking_transaction_id,
                           status,
                           account_number
                    FROM cheque_register
                    WHERE id = %s
                    """,
                    (self.cheque_id,),
                )
                row = cur.fetchone()

            if not row:
                QMessageBox.warning(
                    self, "Not Found", "Selected cheque could not be loaded."
                )
                self.reject()
                return

            (
                cheque_number,
                cheque_date,
                cleared_date,
                payee,
                amount,
                memo,
                banking_id,
                status,
                account_number,
            ) = row
            self.cheque_number.setText(cheque_number or "")
            if cheque_date:
                self.cheque_date.setDate(cheque_date)
            if cleared_date:
                self.cleared_date.setDate(cleared_date)
            self.payee.setText(payee or "")
            self.amount.setValue(float(amount or 0))
            self.memo.setPlainText(memo or "")
            self.banking_transaction_id.setText(
                str(banking_id) if banking_id else ""
            )
            self.status.setCurrentText(_normalize_status(status))

            match_index = self.account_number.findData(account_number or "")
            if match_index >= 0:
                self.account_number.setCurrentIndex(match_index)
            else:
                self.account_number.setEditText(account_number or "")
        except Exception as exc:
            QMessageBox.critical(
                self, "Error", f"Failed to load cheque details:\n{exc}"
            )
            self.reject()

    def _save(self) -> None:
        cheque_number = self.cheque_number.text().strip()
        payee = self.payee.text().strip()
        amount = round(self.amount.value(), 2)
        status = _normalize_status(self.status.currentText())

        if not cheque_number:
            QMessageBox.warning(
                self, "Validation", "Check number is required."
            )
            return

        if amount <= 0 and status != "VOID":
            QMessageBox.warning(
                self,
                "Validation",
                "Amount must be greater than zero unless the check is void.",
            )
            return

        if not payee and status != "VOID":
            QMessageBox.warning(
                self,
                "Validation",
                "Vendor / payee is required unless the check is void.",
            )
            return

        banking_id = None
        banking_text = self.banking_transaction_id.text().strip()
        if banking_text:
            try:
                banking_id = int(banking_text)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Validation",
                    "Banking transaction ID must be numeric.",
                )
                return

        account_number = self.account_number.currentData()
        if account_number is None:
            account_number = self.account_number.currentText().strip()
        else:
            account_number = str(account_number).strip()

        _qd = self.cheque_date.getDate()
        cheque_date = _qd.toPyDate() if _qd else None
        _qd = self.cleared_date.getDate()
        cleared_date = _qd.toPyDate() if _qd else None
        memo = self.memo.toPlainText().strip() or None

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                if self.cheque_id is None:
                    cur.execute(
                        """
                        INSERT INTO cheque_register (
                            cheque_number,
                            cheque_date,
                            cleared_date,
                            payee,
                            amount,
                            memo,
                            banking_transaction_id,
                            status,
                            account_number
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            cheque_number,
                            cheque_date,
                            cleared_date,
                            payee or None,
                            amount,
                            memo,
                            banking_id,
                            status,
                            account_number or None,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE cheque_register
                        SET cheque_number = %s,
                            cheque_date = %s,
                            cleared_date = %s,
                            payee = %s,
                            amount = %s,
                            memo = %s,
                            banking_transaction_id = %s,
                            status = %s,
                            account_number = %s
                        WHERE id = %s
                        """,
                        (
                            cheque_number,
                            cheque_date,
                            cleared_date,
                            payee or None,
                            amount,
                            memo,
                            banking_id,
                            status,
                            account_number or None,
                            self.cheque_id,
                        ),
                    )

            self.accept()
        except Exception as exc:
            QMessageBox.critical(
                self, "Save Error", f"Failed to save cheque details:\n{exc}"
            )


class CheckBookManagementWidget(QWidget):
    """Manage cheque register rows from the desktop accounting UI."""

    def __init__(self, conn: psycopg2.extensions.connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self._has_vendor_invoice_payments = False
        self._build_ui()
        self._load_schema_flags()
        self._load_bank_accounts()
        self._load_cheques()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Bank:"))
        self.bank_filter = QComboBox()
        self.bank_filter.setMaximumWidth(170)
        filter_layout.addWidget(self.bank_filter)

        filter_layout.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(
            ["All", "PENDING", "CLEARED", "VOID", "NSF"]
        )
        self.status_filter.setMaximumWidth(130)
        filter_layout.addWidget(self.status_filter)

        filter_layout.addWidget(QLabel("Match:"))
        self.match_filter = QComboBox()
        self.match_filter.addItems(["All", "Matched", "Unmatched"])
        self.match_filter.setMaximumWidth(120)
        filter_layout.addWidget(self.match_filter)

        filter_layout.addWidget(QLabel("Check #:"))
        self.cheque_filter = QLineEdit()
        self.cheque_filter.setPlaceholderText("Number...")
        self.cheque_filter.setMaximumWidth(110)
        filter_layout.addWidget(self.cheque_filter)

        filter_layout.addWidget(QLabel("Vendor:"))
        self.payee_filter = QLineEdit()
        self.payee_filter.setPlaceholderText("Payee / vendor...")
        self.payee_filter.setMaximumWidth(180)
        filter_layout.addWidget(self.payee_filter)

        filter_layout.addWidget(QLabel("Date:"))
        self.date_from = StandardDateEdit(allow_blank=True)
        self.date_from.setMaximumWidth(110)
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("to"))
        self.date_to = StandardDateEdit(allow_blank=True)
        self.date_to.setMaximumWidth(110)
        filter_layout.addWidget(self.date_to)

        filter_layout.addStretch()

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._load_cheques)
        filter_layout.addWidget(search_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_btn)

        layout.addLayout(filter_layout)

        action_layout = QHBoxLayout()
        self.results_label = QLabel("Checks: 0")
        action_layout.addWidget(self.results_label)
        action_layout.addStretch()

        add_btn = QPushButton("Add Check Written")
        add_btn.clicked.connect(self._add_cheque)
        action_layout.addWidget(add_btn)

        edit_btn = QPushButton("Edit Check Details")
        edit_btn.clicked.connect(self._edit_selected_cheque)
        action_layout.addWidget(edit_btn)

        matches_btn = QPushButton("View Matches")
        matches_btn.clicked.connect(self._view_matches)
        action_layout.addWidget(matches_btn)

        receipt_btn = QPushButton("Edit Linked Receipt")
        receipt_btn.clicked.connect(self._edit_linked_receipt)
        action_layout.addWidget(receipt_btn)

        print_btn = QPushButton("Print Preview")
        print_btn.clicked.connect(
            lambda: PrintExportHelper.print_preview(
                self.table, "Check Book Management", self
            )
        )
        action_layout.addWidget(print_btn)

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(
            lambda: PrintExportHelper.export_csv(
                self.table, "Check Book Management", parent=self
            )
        )
        action_layout.addWidget(export_btn)

        delete_btn = QPushButton("Delete Check")
        delete_btn.setStyleSheet("color: #cc0000; font-weight: bold;")
        delete_btn.clicked.connect(self._delete_selected_cheque)
        action_layout.addWidget(delete_btn)

        layout.addLayout(action_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Check #",
                "Date",
                "Cleared",
                "Vendor",
                "Amount",
                "Status",
                "Bank",
                "Banking Txn",
                "Receipts",
                "Invoices",
                "Memo",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(11, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sectionClicked.connect(
            self._on_header_clicked
        )
        self.table.cellDoubleClicked.connect(
            lambda *_: self._edit_selected_cheque()
        )
        self._sort_column: int = 2  # default: Date
        self._sort_order = Qt.SortOrder.DescendingOrder
        layout.addWidget(self.table)

    def _load_schema_flags(self) -> None:
        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_name = 'vendor_invoice_payments'
                    )
                    """)
                self._has_vendor_invoice_payments = bool(cur.fetchone()[0])
        except Exception as exc:
            logger.warning(
                "Failed to inspect vendor_invoice_payments presence: %s", exc
            )
            self._has_vendor_invoice_payments = False

    def _load_bank_accounts(self) -> None:
        self.bank_filter.clear()
        self.bank_filter.addItem("All Banks", "")

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute("""
                    SELECT DISTINCT account_number
                    FROM cheque_register
                    WHERE account_number IS NOT NULL
                      AND account_number <> ''
                    ORDER BY account_number
                    """)
                accounts = [row[0] for row in cur.fetchall()]

            for account_number in accounts:
                self.bank_filter.addItem(
                    _bank_label(account_number), account_number
                )
        except Exception as exc:
            logger.error("Failed to load cheque bank accounts: %s", exc)

    def _load_cheques(self) -> None:
        receipt_join = """
            LEFT JOIN (
                SELECT banking_transaction_id,
                       COUNT(*) AS receipt_count,
                       STRING_AGG(
                           receipt_id::text, ', ' ORDER BY receipt_id
                       ) AS receipt_ids
                FROM receipts
                WHERE banking_transaction_id IS NOT NULL
                GROUP BY banking_transaction_id
            ) rc ON rc.banking_transaction_id = cr.banking_transaction_id
        """
        if self._has_vendor_invoice_payments:
            invoice_join = """
                LEFT JOIN (
                    SELECT banking_transaction_id,
                           COUNT(*) AS invoice_count,
                           STRING_AGG(
                               COALESCE(reference, receipt_id::text),
                               ', '
                               ORDER BY payment_date, payment_id
                           ) AS invoice_refs
                    FROM vendor_invoice_payments
                    WHERE banking_transaction_id IS NOT NULL
                    GROUP BY banking_transaction_id
                ) vip ON vip.banking_transaction_id = cr.banking_transaction_id
            """
            invoice_count_sql = (
                "COALESCE(vip.invoice_count, 0) AS invoice_count"
            )
            invoice_refs_sql = "COALESCE(vip.invoice_refs, '') AS invoice_refs"
        else:
            invoice_join = ""
            invoice_count_sql = "0 AS invoice_count"
            invoice_refs_sql = "'' AS invoice_refs"

        sql = [
            "SELECT cr.id,",
            "       cr.cheque_number,",
            "       cr.cheque_date,",
            "       cr.cleared_date,",
            "       cr.payee,",
            "       cr.amount,",
            "       cr.status,",
            "       cr.account_number,",
            "       cr.banking_transaction_id,",
            "       COALESCE(cr.memo, '') AS memo,",
            "       COALESCE(rc.receipt_count, 0) AS receipt_count,",
            f"       {invoice_count_sql},",
            "       COALESCE(rc.receipt_ids, '') AS receipt_ids,",
            f"       {invoice_refs_sql}",
            "FROM cheque_register cr",
            receipt_join,
            invoice_join,
            "WHERE 1=1",
        ]
        params: list[object] = []

        bank_account = self.bank_filter.currentData()
        if bank_account:
            sql.append("AND cr.account_number = %s")
            params.append(bank_account)

        status = self.status_filter.currentText()
        if status != "All":
            sql.append("AND UPPER(COALESCE(cr.status, 'PENDING')) = %s")
            params.append(status)

        cheque_number = self.cheque_filter.text().strip()
        if cheque_number:
            sql.append("AND cr.cheque_number ILIKE %s")
            params.append(f"%{cheque_number}%")

        payee = self.payee_filter.text().strip()
        if payee:
            sql.append("AND COALESCE(cr.payee, '') ILIKE %s")
            params.append(f"%{payee}%")

        _qd = self.date_from.getDate()
        date_from = _qd.toPyDate() if _qd else None
        if date_from:
            sql.append(
                "AND COALESCE(cr.cheque_date, cr.created_at::date) >= %s"
            )
            params.append(date_from)

        _qd = self.date_to.getDate()
        date_to = _qd.toPyDate() if _qd else None
        if date_to:
            sql.append(
                "AND COALESCE(cr.cheque_date, cr.created_at::date) <= %s"
            )
            params.append(date_to)

        match_filter = self.match_filter.currentText()
        if match_filter == "Matched":
            sql.append(
                "AND (COALESCE(rc.receipt_count, 0) > 0 OR "
                + (
                    "COALESCE(vip.invoice_count, 0) > 0)"
                    if self._has_vendor_invoice_payments
                    else "FALSE)"
                )
            )
        elif match_filter == "Unmatched":
            sql.append(
                "AND COALESCE(rc.receipt_count, 0) = 0 AND "
                + (
                    "COALESCE(vip.invoice_count, 0) = 0"
                    if self._has_vendor_invoice_payments
                    else "TRUE"
                )
            )

        sql.append(
            "ORDER BY COALESCE(cr.cheque_date, cr.created_at::date) DESC, "
            "CASE WHEN cr.cheque_number ~ '^[0-9]+$' THEN "
            "cr.cheque_number::integer END DESC NULLS LAST, "
            "cr.cheque_number DESC"
        )
        sql.append("LIMIT 1000")

        try:
            with DatabaseContext(self.conn, auto_commit=False) as cur:
                cur.execute("\n".join(sql), params)
                rows = cur.fetchall()
            self._populate_table(rows)
        except Exception as exc:
            logger.error("Failed to load cheque register rows: %s", exc)
            QMessageBox.critical(
                self, "Error", f"Failed to load cheque register rows:\n{exc}"
            )

    def _on_header_clicked(self, logical_index: int) -> None:
        if self._sort_column == logical_index:
            self._sort_order = (
                Qt.SortOrder.AscendingOrder
                if self._sort_order == Qt.SortOrder.DescendingOrder
                else Qt.SortOrder.DescendingOrder
            )
        else:
            self._sort_column = logical_index
            self._sort_order = Qt.SortOrder.AscendingOrder
        self.table.sortItems(self._sort_column, self._sort_order)

    def _populate_table(self, rows) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        total_amount = 0.0
        matched_count = 0
        status_colors = {
            "CLEARED": QColor(220, 255, 220),
            "NSF": QColor(255, 220, 220),
            "VOID": QColor(235, 235, 235),
            "PENDING": QColor(255, 248, 210),
        }

        for row_index, row in enumerate(rows):
            (
                cheque_id,
                cheque_number,
                cheque_date,
                cleared_date,
                payee,
                amount,
                status,
                account_number,
                banking_transaction_id,
                memo,
                receipt_count,
                invoice_count,
                receipt_ids,
                invoice_refs,
            ) = row

            total_amount += float(amount or 0)
            if receipt_count or invoice_count:
                matched_count += 1

            # Numeric columns use NumericTableWidgetItem for correct sort order
            _numeric_cols = {0, 1, 5, 8, 9, 10}

            values = [
                str(cheque_id),
                cheque_number or "",
                str(cheque_date) if cheque_date else "",
                str(cleared_date) if cleared_date else "",
                payee or "",
                f"{float(amount or 0):.2f}",
                _normalize_status(status),
                _bank_label(account_number),
                str(banking_transaction_id) if banking_transaction_id else "",
                str(receipt_count or 0),
                str(invoice_count or 0),
                memo or "",
            ]

            for col_index, value in enumerate(values):
                item = (
                    NumericTableWidgetItem(value)
                    if col_index in _numeric_cols
                    else QTableWidgetItem(value)
                )
                if col_index == 5:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                if col_index == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        {
                            "id": cheque_id,
                            "banking_transaction_id": banking_transaction_id,
                            "receipt_ids": receipt_ids or "",
                            "invoice_refs": invoice_refs or "",
                            "receipt_count": int(receipt_count or 0),
                            "invoice_count": int(invoice_count or 0),
                        },
                    )

                color = status_colors.get(_normalize_status(status))
                if color is not None:
                    item.setBackground(color)

                self.table.setItem(row_index, col_index, item)

        self.results_label.setText(
            f"Checks: {len(rows)} | Matched: {matched_count} | Total:"
            f"${total_amount:,.2f}"
        )
        self.table.setSortingEnabled(True)
        self.table.sortItems(self._sort_column, self._sort_order)

    def _clear_filters(self) -> None:
        self.bank_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.match_filter.setCurrentIndex(0)
        self.cheque_filter.clear()
        self.payee_filter.clear()
        if hasattr(self.date_from, "clearDate"):
            self.date_from.clearDate()
        if hasattr(self.date_to, "clearDate"):
            self.date_to.clearDate()
        self._load_cheques()

    def _selected_metadata(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(
                self, "Select Check", "Select a check row first."
            )
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _bank_accounts_for_editor(self) -> list[str]:
        accounts: list[str] = []
        for idx in range(1, self.bank_filter.count()):
            account_number = self.bank_filter.itemData(idx)
            if account_number:
                accounts.append(str(account_number))
        return accounts

    def _add_cheque(self) -> None:
        dialog = ChequeEditDialog(
            self.conn, self._bank_accounts_for_editor(), parent=self
        )
        if dialog.exec():
            self._load_bank_accounts()
            self._load_cheques()

    def _edit_selected_cheque(self) -> None:
        metadata = self._selected_metadata()
        if not metadata:
            return
        dialog = ChequeEditDialog(
            self.conn,
            self._bank_accounts_for_editor(),
            cheque_id=metadata["id"],
            parent=self,
        )
        if dialog.exec():
            self._load_cheques()

    def _view_matches(self) -> None:
        metadata = self._selected_metadata()
        if not metadata:
            return

        receipt_text = metadata["receipt_ids"] or "None"
        invoice_text = metadata["invoice_refs"] or "None"
        banking_text = metadata["banking_transaction_id"] or "Not linked"

        QMessageBox.information(
            self,
            "Check Matches",
            (
                f"Banking transaction: {banking_text}\n\n"
                f"Receipt matches ({metadata['receipt_count']}):"
                f"{receipt_text}\n\n"
                f"Invoice matches ({metadata['invoice_count']}):"
                f"{invoice_text}"
            ),
        )

    def _delete_selected_cheque(self) -> None:
        metadata = self._selected_metadata()
        if not metadata:
            return

        cheque_id = metadata["id"]
        # Find display info from the selected row
        rows = self.table.selectionModel().selectedRows()
        row_idx = rows[0].row()
        cheque_num = (
            self.table.item(row_idx, 1) or QTableWidgetItem("")
        ).text()
        payee_val = (
            self.table.item(row_idx, 4) or QTableWidgetItem("")
        ).text()
        amount_val = (
            self.table.item(row_idx, 5) or QTableWidgetItem("")
        ).text()

        confirm = QMessageBox.question(
            self,
            "Delete Check",
            (
                f"Permanently delete Check #{cheque_num}\n"
                f"Payee: {payee_val}  Amount: ${amount_val}\n\n"
                "This cannot be undone. Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            with DatabaseContext(self.conn, auto_commit=True) as cur:
                cur.execute(
                    "DELETE FROM cheque_register WHERE id = %s", (cheque_id,)
                )
            self._load_cheques()
        except Exception as exc:
            QMessageBox.critical(
                self, "Delete Error", f"Failed to delete check:\n{exc}"
            )

    def _edit_linked_receipt(self) -> None:
        metadata = self._selected_metadata()
        if not metadata:
            return

        receipt_ids_text = metadata["receipt_ids"] or ""
        if not receipt_ids_text:
            QMessageBox.information(
                self,
                "No Linked Receipt",
                "This check is not currently matched to any receipt.",
            )
            return

        receipt_ids = [
            value.strip()
            for value in receipt_ids_text.split(",")
            if value.strip()
        ]
        if len(receipt_ids) != 1:
            QMessageBox.information(
                self,
                "Multiple Linked Receipts",
                f"This check is linked to multiple receipts:"
                f"{receipt_ids_text}\n\nUse View Matches to inspect them.",
            )
            return

        try:
            receipt_id = int(receipt_ids[0])
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Receipt",
                f"Could not parse receipt ID: {receipt_ids_text}",
            )
            return

        dialog = SimpleReceiptEditor(self.conn, receipt_id, parent=self)
        if dialog.exec():
            self._load_cheques()
