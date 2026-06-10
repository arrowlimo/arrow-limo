"""
Vendor Management Widget
- Browse all vendor accounts with receipt counts
- Click a vendor to see all its linked receipts
- Rename a vendor (updates vendor_accounts + all receipts)
- Delete a vendor account when it has zero receipts
"""

import logging

import psycopg2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# ─── Rename Dialog
# ────────────────────────────────────────────────────────────


class RenameVendorDialog(QDialog):
    """Simple dialog to enter a new vendor name."""

    def __init__(self, current_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rename Vendor")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QFormLayout(self)

        self.current_label = QLabel(f"<b>{current_name}</b>")
        layout.addRow("Current name:", self.current_label)

        self.new_name_edit = QLineEdit()
        self.new_name_edit.setText(current_name)
        self.new_name_edit.selectAll()
        self.new_name_edit.setPlaceholderText("Enter new vendor name...")
        layout.addRow("New name:", self.new_name_edit)

        self.info_label = QLabel(
            "This will update the vendor account AND every receipt linked to"
            "it."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addRow("", self.info_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.new_name_edit.setFocus()

    def get_new_name(self) -> str:
        return self.new_name_edit.text().strip().upper()


# ─── Main Widget
# ──────────────────────────────────────────────────────────────


class VendorManagementWidget(QWidget):
    """
    Vendor management: browse, rename, and delete vendor accounts.

    Left panel   — searchable list of vendor accounts with receipt counts.
    Right panel  — receipts belonging to the selected vendor.
    Action bar   — Rename and Delete buttons.
    """

    def __init__(self, conn: psycopg2.extensions.connection, parent=None) -> None:
        super().__init__(parent)
        self.conn = conn
        self._selected_account_id: int | None = None
        self._selected_vendor_name: str = ""
        self._build_ui()
        self._load_vendors()

    # ── UI
    # ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Search:"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter vendors...")
        self.search_edit.textChanged.connect(self._filter_vendors)
        top_row.addWidget(self.search_edit, 1)

        self.vendor_count_label = QLabel("Vendors: 0")
        self.vendor_count_label.setStyleSheet("color: #888; font-size: 11px;")
        top_row.addWidget(self.vendor_count_label)

        refresh_btn = QPushButton("↺")
        refresh_btn.setFixedWidth(30)
        refresh_btn.setToolTip("Reload vendor list")
        refresh_btn.clicked.connect(self._load_vendors)
        top_row.addWidget(refresh_btn)

        root.addLayout(top_row)

        # Splitter: vendor list  |  receipts
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # ── Left: vendor list ──────────────────────────────────────────────
        left = QFrame()
        left.setFrameShape(QFrame.Shape.StyledPanel)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)

        self.vendor_table = QTableWidget()
        self.vendor_table.setColumnCount(3)
        self.vendor_table.setHorizontalHeaderLabels(
            ["Vendor Name", "Receipts", "Total ($)"]
        )
        self.vendor_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.vendor_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.vendor_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.vendor_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.vendor_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.vendor_table.setAlternatingRowColors(True)
        self.vendor_table.verticalHeader().setVisible(False)
        self.vendor_table.itemSelectionChanged.connect(
            self._on_vendor_selected
        )
        left_layout.addWidget(self.vendor_table, 1)

        # Action buttons under vendor list
        btn_row = QHBoxLayout()
        self.rename_btn = QPushButton("✏️ Rename")
        self.rename_btn.setEnabled(False)
        self.rename_btn.setToolTip(
            "Rename this vendor and update all linked receipts"
        )
        self.rename_btn.clicked.connect(self._rename_vendor)
        btn_row.addWidget(self.rename_btn)

        self.delete_btn = QPushButton("🗑️ Delete Account")
        self.delete_btn.setEnabled(False)
        self.delete_btn.setToolTip(
            "Delete vendor account (only available when no receipts are"
            "linked)"
        )
        self.delete_btn.setStyleSheet("color: #c0392b;")
        self.delete_btn.clicked.connect(self._delete_vendor)
        btn_row.addWidget(self.delete_btn)

        left_layout.addLayout(btn_row)
        splitter.addWidget(left)

        # ── Right: receipts for selected vendor ──────────────────────────
        right = QFrame()
        right.setFrameShape(QFrame.Shape.StyledPanel)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)

        self.receipts_header = QLabel("Select a vendor to view receipts")
        self.receipts_header.setStyleSheet(
            "font-weight: bold; padding-bottom: 2px;"
        )
        right_layout.addWidget(self.receipts_header)

        self.receipts_table = QTableWidget()
        self.receipts_table.setColumnCount(6)
        self.receipts_table.setHorizontalHeaderLabels(
            [
                "Receipt ID",
                "Date",
                "Payment",
                "Running Balance",
                "Description",
                "GL Code",
            ]
        )
        self.receipts_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.receipts_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.receipts_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.receipts_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.receipts_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self.receipts_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self.receipts_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.receipts_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.receipts_table.setAlternatingRowColors(True)
        self.receipts_table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.receipts_table, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([420, 900])

        root.addWidget(splitter, 1)

    # ── Data loading
    # ──────────────────────────────────────────────────────────

    def _load_vendors(self) -> None:
        """Load all vendor accounts with receipt counts from the DB."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT
                    va.account_id,
                    va.canonical_vendor,
                    va.display_name,
                    COUNT(r.receipt_id)         AS receipt_count,
                    COALESCE(SUM(r.gross_amount), 0) AS total_amount
                FROM vendor_accounts va
                LEFT JOIN receipts r ON r.vendor_account_id = va.account_id
                GROUP BY va.account_id, va.canonical_vendor, va.display_name
                ORDER BY va.canonical_vendor
                """)
            rows = cur.fetchall()
            cur.close()
        except Exception as exc:
            logger.exception("Failed to load vendors: %s", exc)
            self.conn.rollback()
            QMessageBox.warning(
                self, "DB Error", f"Could not load vendors:\n{exc}"
            )
            return

        self._all_vendor_rows = rows
        self._populate_vendor_table(rows)

    def _populate_vendor_table(self, rows) -> None:
        self.vendor_table.setRowCount(0)
        bold = QFont()
        bold.setBold(True)
        zero_color = QColor("#888888")

        for (
            account_id,
            canonical,
            display_name,
            receipt_count,
            total_amount,
        ) in rows:
            row = self.vendor_table.rowCount()
            self.vendor_table.insertRow(row)

            name_item = QTableWidgetItem(display_name or canonical)
            name_item.setData(Qt.ItemDataRole.UserRole, account_id)
            name_item.setData(Qt.ItemDataRole.UserRole + 1, canonical)
            if receipt_count > 0:
                name_item.setFont(bold)
            self.vendor_table.setItem(row, 0, name_item)

            count_item = QTableWidgetItem(str(receipt_count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if receipt_count == 0:
                count_item.setForeground(zero_color)
            self.vendor_table.setItem(row, 1, count_item)

            total_item = QTableWidgetItem(f"{float(total_amount):,.2f}")
            total_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            if receipt_count == 0:
                total_item.setForeground(zero_color)
            self.vendor_table.setItem(row, 2, total_item)

        self.vendor_count_label.setText(f"Vendors: {len(rows)}")
        self._clear_receipts()

    def _filter_vendors(self, text: str) -> None:
        """Filter vendor list by search text."""
        if not hasattr(self, "_all_vendor_rows"):
            return
        text_lower = text.lower()
        filtered = [
            r
            for r in self._all_vendor_rows
            if text_lower in (r[1] or "").lower()
            or text_lower in (r[2] or "").lower()
        ]
        self._populate_vendor_table(filtered)

    def _on_vendor_selected(self) -> None:
        """Handle vendor table row selection."""
        rows = self.vendor_table.selectedItems()
        if not rows:
            self._selected_account_id = None
            self._selected_vendor_name = ""
            self.rename_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            self._clear_receipts()
            return

        name_item = self.vendor_table.item(self.vendor_table.currentRow(), 0)
        if name_item is None:
            return

        self._selected_account_id = name_item.data(Qt.ItemDataRole.UserRole)
        self._selected_vendor_name = name_item.data(
            Qt.ItemDataRole.UserRole + 1
        )

        count_item = self.vendor_table.item(self.vendor_table.currentRow(), 1)
        receipt_count = int(count_item.text()) if count_item else 0

        self.rename_btn.setEnabled(True)
        self.delete_btn.setEnabled(receipt_count == 0)

        self._load_receipts_for_vendor(
            self._selected_account_id, self._selected_vendor_name
        )

    def _load_receipts_for_vendor(self, account_id: int, vendor_name: str) -> None:
        """Load all receipts linked to the given vendor account."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT
                    receipt_id,
                    receipt_date,
                    gross_amount,
                    description,
                    gl_code
                FROM receipts
                WHERE vendor_account_id = %s
                ORDER BY receipt_date ASC, receipt_id ASC
                """,
                (account_id,),
            )
            rows = cur.fetchall()
            cur.close()
        except Exception as exc:
            logger.exception("Failed to load receipts: %s", exc)
            self.conn.rollback()
            QMessageBox.warning(
                self, "DB Error", f"Could not load receipts:\n{exc}"
            )
            return

        self.receipts_header.setText(
            f"Receipts for: <b>{vendor_name}</b>  ({len(rows)} records)"
        )
        self.receipts_table.setRowCount(0)

        running_balance = 0.0

        for receipt_id, date, amount, description, gl_code in rows:
            row = self.receipts_table.rowCount()
            self.receipts_table.insertRow(row)

            payment_amount = float(amount) if amount else 0.0
            running_balance += payment_amount

            self.receipts_table.setItem(
                row, 0, QTableWidgetItem(str(receipt_id))
            )
            self.receipts_table.setItem(
                row,
                1,
                QTableWidgetItem(date.strftime("%Y-%m-%d") if date else ""),
            )
            payment_item = QTableWidgetItem(f"{payment_amount:,.2f}")
            payment_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.receipts_table.setItem(row, 2, payment_item)

            running_item = QTableWidgetItem(f"{running_balance:,.2f}")
            running_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.receipts_table.setItem(row, 3, running_item)

            self.receipts_table.setItem(
                row, 4, QTableWidgetItem(description or "")
            )
            self.receipts_table.setItem(
                row, 5, QTableWidgetItem(gl_code or "")
            )

    def _clear_receipts(self) -> None:
        self.receipts_table.setRowCount(0)
        self.receipts_header.setText("Select a vendor to view receipts")

    # ── Actions
    # ───────────────────────────────────────────────────────────────

    def _rename_vendor(self) -> None:
        """Rename vendor account and update all linked receipts."""
        if self._selected_account_id is None:
            return

        dlg = RenameVendorDialog(self._selected_vendor_name, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_name = dlg.get_new_name()
        if not new_name:
            QMessageBox.warning(
                self, "Validation", "Vendor name cannot be empty."
            )
            return
        if new_name == self._selected_vendor_name:
            return

        # Confirm
        confirm = QMessageBox.question(
            self,
            "Confirm Rename",
            f"Rename <b>{self._selected_vendor_name}</b> →"
            f"<b>{new_name}</b>?<br><br>"
            "This will update the vendor account and every linked receipt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            cur = self.conn.cursor()

            # Check target name doesn't already exist as a different account
            cur.execute(
                """
                SELECT account_id FROM vendor_accounts
                WHERE UPPER(canonical_vendor) = %s AND account_id <> %s
                """,
                (new_name, self._selected_account_id),
            )
            conflict = cur.fetchone()
            if conflict:
                cur.close()
                QMessageBox.warning(
                    self,
                    "Name Conflict",
                    f"A vendor account named '{new_name}' already exists (ID"
                    f"{conflict[0]}).\n"
                    "Use the Merge function in Vendor"
                    " Standardization instead.",
                )
                return

            # Update vendor_accounts
            cur.execute(
                """
                UPDATE vendor_accounts
                SET canonical_vendor = %s,
                    display_name = %s
                WHERE account_id = %s
                """,
                (new_name, new_name, self._selected_account_id),
            )

            # Update receipts.vendor_name + canonical_vendor
            cur.execute(
                """
                UPDATE receipts
                SET vendor_name = %s,
                    canonical_vendor = %s
                WHERE vendor_account_id = %s
                """,
                (new_name, new_name, self._selected_account_id),
            )
            affected_receipts = cur.rowcount

            self.conn.commit()
            cur.close()

            logger.info(
                "Renamed vendor %d: '%s' → '%s' (%d receipts updated)",
                self._selected_account_id,
                self._selected_vendor_name,
                new_name,
                affected_receipts,
            )

            QMessageBox.information(
                self,
                "Renamed",
                f"Vendor renamed to <b>{new_name}</b>.<br>"
                f"{affected_receipts} receipt(s) updated.",
            )

            self._load_vendors()

        except Exception as exc:
            self.conn.rollback()
            logger.exception("Rename failed: %s", exc)
            QMessageBox.critical(self, "Error", f"Rename failed:\n{exc}")

    def _delete_vendor(self) -> None:
        """Delete a vendor account that has zero linked receipts."""
        if self._selected_account_id is None:
            return

        # Double-check receipt count before deleting
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM receipts WHERE vendor_account_id = %s",
                (self._selected_account_id,),
            )
            count = cur.fetchone()[0]
            cur.close()
        except Exception as exc:
            self.conn.rollback()
            QMessageBox.warning(
                self, "DB Error", f"Could not verify receipt count:\n{exc}"
            )
            return

        if count > 0:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                f"This vendor still has {count} linked receipt(s).\n"
                "Rename or re-assign the receipts first.",
            )
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Permanently delete vendor account"
            f"<b>{self._selected_vendor_name}</b>?<br><br>"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            cur = self.conn.cursor()
            cur.execute(
                "DELETE FROM vendor_accounts WHERE account_id = %s",
                (self._selected_account_id,),
            )
            self.conn.commit()
            cur.close()

            logger.info(
                "Deleted vendor account %d (%s)",
                self._selected_account_id,
                self._selected_vendor_name,
            )

            QMessageBox.information(
                self,
                "Deleted",
                f"Vendor <b>{self._selected_vendor_name}</b>"
                " has been deleted.",
            )

            self._selected_account_id = None
            self._selected_vendor_name = ""
            self._load_vendors()

        except Exception as exc:
            self.conn.rollback()
            logger.exception("Delete failed: %s", exc)
            QMessageBox.critical(self, "Error", f"Delete failed:\n{exc}")
