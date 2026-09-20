"""
Payment Linker Widget - Manual assignment of orphaned 2025-2026 payments to charters.

Targets 251 orphaned credit card payments from Square that have no charter or client link.
Allows dispatch to manually select a charter, which auto-populates the client_id.
"""

import logging
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class PaymentLinkerWidget(QWidget):
    """Manual orphaned payment linker with charter assignment."""

    def __init__(self, db=None):
        super().__init__()
        self.db = db
        self.setWindowTitle("💳 Payment Linker - Assign Orphaned Payments")
        
        layout = QVBoxLayout()
        
        # Header
        header = QLabel(
            "<h3>💳 Orphaned Payment Linker</h3>"
            "<p>Manually assign 2025-2026 credit card payments (no charter/client) to charters.</p>"
            "<p style='color: #666; font-size: 10pt;'>"
            "These payments came from Square but don't have charter or dispatch info. "
            "Select a charter from the dropdown to link each payment.</p>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)
        
        # Table: Orphaned payments
        self.orphaned_table = QTableWidget()
        self.orphaned_table.setColumnCount(8)
        self.orphaned_table.setHorizontalHeaderLabels([
            "Payment ID",
            "Date",
            "Amount",
            "Method",
            "Square ID",
            "Link To Charter",
            "Client Name (auto)",
            "Action",
        ])
        self.orphaned_table.horizontalHeader().setStretchLastSection(False)
        for col in [0, 1, 4]:
            self.orphaned_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        for col in [2, 5, 6]:
            self.orphaned_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.Stretch
            )
        self.orphaned_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.orphaned_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.orphaned_table)
        
        # Status
        self.status_label = QLabel("Loading orphaned payments...")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QVBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_orphaned_payments)
        button_layout.addWidget(refresh_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Load initial data after construction so the widget does not
        # block startup while fetching orphaned payments.
        QTimer.singleShot(0, self.load_orphaned_payments)
    
    def load_orphaned_payments(self) -> None:
        """Load all orphaned 2025-2026 payments from database."""
        try:
            if not self.db or not self.db.conn:
                self.status_label.setText("❌ Database connection unavailable")
                return
            
            cur = self.db.conn.cursor()
            
            # Cache recent charters for on-demand picker dialog.
            # Building a full dropdown in each table row can freeze the UI.
            cur.execute("""
                SELECT charter_id, reserve_number, client_id
                FROM charters
                ORDER BY charter_id DESC
                LIMIT 800
            """)
            self.charters = {
                charter_id: (reserve_number, client_id)
                for charter_id, reserve_number, client_id in cur.fetchall()
            }
            
            # Build dropdown text for charters
            self.charter_display = {}
            for cid, (res_num, client_id) in self.charters.items():
                # Show: "020123 (cid: 19257)"
                self.charter_display[cid] = f"{res_num or '?'} (ID: {cid})"
            
            # Get all clients for display
            cur.execute("SELECT client_id, COALESCE(company_name, client_name) FROM clients")
            self.clients = {client_id: name for client_id, name in cur.fetchall()}
            
            # Fetch orphaned payments: 2025-2026, credit_card, no charter/client
            cur.execute("""
                SELECT payment_id, payment_date, COALESCE(amount, payment_amount, 0),
                       payment_method, square_payment_id
                FROM payments
                WHERE COALESCE(amount, payment_amount, 0) <> 0
                  AND client_id IS NULL
                  AND charter_id IS NULL
                  AND (reserve_number IS NULL OR TRIM(reserve_number) = '')
                  AND payment_date >= '2025-01-01'
                ORDER BY payment_date DESC, payment_id DESC
            """)
            orphaned = cur.fetchall()
            cur.close()
            
            # Prepare charter options once; reused by picker dialog.
            self.charter_options = [
                (cid, self.charter_display[cid])
                for cid in sorted(self.charters.keys(), reverse=True)
            ]

            # Populate table
            self.orphaned_table.setRowCount(len(orphaned))
            
            for row_idx, (pid, pdate, amount, method, square_id) in enumerate(orphaned):
                # Payment ID
                item = QTableWidgetItem(str(pid))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setData(Qt.ItemDataRole.UserRole, pid)
                self.orphaned_table.setItem(row_idx, 0, item)
                
                # Date
                date_str = pdate.strftime("%Y-%m-%d") if pdate else "N/A"
                item = QTableWidgetItem(date_str)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.orphaned_table.setItem(row_idx, 1, item)
                
                # Amount
                amt_str = f"${amount:,.2f}"
                item = QTableWidgetItem(amt_str)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.orphaned_table.setItem(row_idx, 2, item)
                
                # Method
                item = QTableWidgetItem(method or "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.orphaned_table.setItem(row_idx, 3, item)
                
                # Square ID (truncated)
                sq_display = (square_id[-12:] if square_id else "N/A")
                item = QTableWidgetItem(sq_display)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.orphaned_table.setItem(row_idx, 4, item)
                
                # Charter display (selected via on-demand dialog)
                charter_item = QTableWidgetItem("-- Select Charter --")
                charter_item.setFlags(charter_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.orphaned_table.setItem(row_idx, 5, charter_item)
                
                # Client name (auto-populated when charter selected)
                client_item = QTableWidgetItem("")
                client_item.setFlags(client_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.orphaned_table.setItem(row_idx, 6, client_item)
                
                # Select + save button
                link_btn = QPushButton("Select & Save")
                link_btn.clicked.connect(
                    lambda _checked=False, r=row_idx: self._choose_charter_and_save(r)
                )
                self.orphaned_table.setCellWidget(row_idx, 7, link_btn)
            
            self.status_label.setText(f"✓ Loaded {len(orphaned)} orphaned payments")
            
        except Exception as e:
            logger.exception("Error loading orphaned payments: %s", e)
            self.status_label.setText(f"❌ Error: {e}")
    
    def _choose_charter_and_save(self, row_idx: int) -> None:
        """Open charter picker dialog for one row and save the link."""
        try:
            if row_idx < 0 or row_idx >= self.orphaned_table.rowCount():
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Select Charter")
            dialog_layout = QVBoxLayout(dialog)

            helper = QLabel("Choose a charter to link this payment. Type in search to filter.")
            helper.setWordWrap(True)
            dialog_layout.addWidget(helper)

            search_input = QLineEdit()
            search_input.setPlaceholderText("Filter by reserve number or charter ID")
            dialog_layout.addWidget(search_input)

            combo = QComboBox()
            combo.setEditable(True)
            combo.addItem("-- Select Charter --", None)
            for cid, label in self.charter_options:
                combo.addItem(label, cid)
            dialog_layout.addWidget(combo)

            def apply_filter(text: str) -> None:
                selected_id = combo.currentData()
                combo.blockSignals(True)
                combo.clear()
                combo.addItem("-- Select Charter --", None)
                needle = (text or "").strip().lower()
                for cid, label in self.charter_options:
                    if not needle or needle in label.lower() or needle in str(cid):
                        combo.addItem(label, cid)
                if selected_id is not None:
                    idx = combo.findData(selected_id)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                combo.blockSignals(False)

            search_input.textChanged.connect(apply_filter)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            dialog_layout.addWidget(buttons)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            charter_id = combo.currentData()
            if charter_id is None:
                QMessageBox.warning(self, "Missing Charter", "Please select a charter.")
                return

            self._save_link_for_row(row_idx, int(charter_id))
        except Exception as e:
            logger.exception("Error selecting charter for row %s: %s", row_idx, e)
    
    def _save_link_for_row(self, row_idx: int, charter_id: int) -> None:
        """Save payment-to-charter link to database for one row."""
        try:
            pid_item = self.orphaned_table.item(row_idx, 0)
            pid = int(pid_item.data(Qt.ItemDataRole.UserRole)) if pid_item else None
            if not pid:
                QMessageBox.warning(self, "Error", "Cannot identify payment ID")
                return

            # Get client_id from charter
            reserve_num, client_id = self.charters[charter_id]
            if client_id is None:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Selected charter has no client link. Charter: {reserve_num}"
                )
                return

            # Update UI preview before save
            charter_item = self.orphaned_table.item(row_idx, 5)
            if charter_item:
                charter_item.setText(self.charter_display.get(charter_id, f"ID {charter_id}"))
            client_item = self.orphaned_table.item(row_idx, 6)
            if client_item:
                client_item.setText(self.clients.get(client_id, "-- No client --"))

            # Update database
            cur = self.db.conn.cursor()
            cur.execute("""
                UPDATE payments
                SET charter_id = %s, client_id = %s
                WHERE payment_id = %s
                  AND (charter_id IS DISTINCT FROM %s OR client_id IS DISTINCT FROM %s)
            """, (charter_id, client_id, pid, charter_id, client_id))
            rows_updated = cur.rowcount if hasattr(cur, 'rowcount') else 1
            self.db.conn.commit()
            cur.close()

            if rows_updated > 0:
                # Remove row from table
                self.orphaned_table.removeRow(row_idx)
                remaining = self.orphaned_table.rowCount()
                self.status_label.setText(
                    f"✓ Payment {pid} linked to charter {self.charter_display[charter_id]} | "
                    f"{remaining} remaining"
                )
            else:
                QMessageBox.information(
                    self,
                    "Already Linked",
                    f"Payment {pid} is already linked to this charter."
                )
        
        except Exception as e:
            logger.exception("Error saving link: %s", e)
            QMessageBox.critical(self, "Save Error", str(e))
            self.db.conn.rollback() if self.db and self.db.conn else None
