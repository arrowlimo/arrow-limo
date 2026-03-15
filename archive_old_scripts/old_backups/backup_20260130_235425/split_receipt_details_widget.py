"""
Split Receipt Details Widget - Side-by-side display for split receipts with cash portions
Handles detection, display, and management of split receipts in receipt details window
"""

from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import psycopg2
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QFormLayout, QMessageBox, QDialog, QTableWidget, QTableWidgetItem,
    QSpinBox, QComboBox, QDoubleSpinBox, QHeaderView, QScrollArea, QCheckBox
)


class SplitReceiptDetailsWidget(QWidget):
    """Display and manage side-by-side split receipt details with cash portions."""
    
    split_updated = pyqtSignal(int)  # receipt_id
    
    def __init__(self, conn: psycopg2.extensions.connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.current_receipt_id: Optional[int] = None
        self.split_parts: List[Dict] = []  # List of split receipt parts
        self.cash_portion: Optional[Dict] = None
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the UI with split detection panel and side-by-side details."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Split detection banner (hidden by default)
        self.split_banner = self._build_split_banner()
        layout.addWidget(self.split_banner)
        
        # Container for split details (side-by-side)
        self.split_container = QWidget()
        self.split_container_layout = QHBoxLayout(self.split_container)
        self.split_container_layout.setSpacing(5)
        self.split_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Will hold 2-3 detail panels side-by-side
        self.detail_panels: List[QGroupBox] = []
        
        layout.addWidget(self.split_container)
        layout.addStretch()
    
    def _build_split_banner(self) -> QGroupBox:
        """Build the split detection banner showing linked receipts."""
        group = QGroupBox("Split Receipt Detected")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #FF6B6B;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #fff5f5;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
                color: #FF6B6B;
            }
        """)
        group.setHidden(True)  # Hidden until split is detected
        
        layout = QVBoxLayout(group)
        
        # Linked receipts info
        self.linked_receipts_label = QLabel()
        layout.addWidget(self.linked_receipts_label)
        
        # Action buttons
        btn_row = QHBoxLayout()
        
        self.view_splits_btn = QPushButton("👁️ View Split Details")
        self.view_splits_btn.clicked.connect(self._show_split_details_dialog)
        btn_row.addWidget(self.view_splits_btn)
        
        self.collapse_btn = QPushButton("🔽 Collapse Split View")
        self.collapse_btn.clicked.connect(self._collapse_split_view)
        btn_row.addWidget(self.collapse_btn)
        
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        return group
    
    def load_receipt(self, receipt_id: int):
        """Load and display receipt, checking for splits via split_group_id column."""
        self.current_receipt_id = receipt_id
        
        try:
            cur = self.conn.cursor()
            
            # Get this receipt's split_group_id
            cur.execute("""
                SELECT split_group_id, receipt_date, vendor_name, gross_amount, COALESCE(description,'')
                FROM receipts WHERE receipt_id = %s
            """, (receipt_id,))
            row = cur.fetchone()
            
            split_group_id = row[0] if row else None
            base_date = row[1] if row else None
            base_vendor = row[2] if row else None
            base_amount = float(row[3]) if row and row[3] is not None else None
            base_desc = (row[4] or "") if row else ""
            
            # If this receipt has a split_group_id, load all receipts in that group
            if split_group_id:
                self._load_split_receipts(receipt_id, split_group_id)
                if len(self.split_parts) > 1:
                    # Multiple receipts in same group = split
                    self._display_split_layout()
                else:
                    self._hide_split_view()
            else:
                # Fallback heuristic: detect splits by same vendor/date and 'split' in description
                self._load_split_fallback(receipt_id, base_date, base_vendor, base_amount, base_desc)
            
            cur.close()
        
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading receipt splits: {e}")
            self._hide_split_view()
    
    def _load_split_receipts(self, receipt_id: int, split_group_id: int):
        """Load all receipts in the same split group."""
        try:
            cur = self.conn.cursor()
            
            # Find all receipts with same split_group_id
            cur.execute("""
                SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
                FROM receipts
                WHERE split_group_id = %s
                ORDER BY gross_amount DESC
            """, (split_group_id,))
            
            rows = cur.fetchall()
            cur.close()
            
            self.split_parts = []
            for receipt_id, rec_date, vendor, amount, desc in rows:
                self.split_parts.append({
                    'receipt_id': receipt_id,
                    'date': rec_date,
                    'vendor': vendor,
                    'amount': float(amount),
                    'description': desc or ''
                })
        
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading split receipts: {e}")
            import traceback
            traceback.print_exc()
            self.split_parts = []
            
            # No separate cash portions - just the linked receipts
            self.cash_portion = None
            cur.close()
            
            # Update banner
            total_amount = sum(p['amount'] for p in self.split_parts)
            
            msg = f"📦 Split into {len(self.split_parts)} linked receipt(s) | Total: ${total_amount:,.2f}"
            
            self.linked_receipts_label.setText(msg)
            self.split_banner.setHidden(False)
        
        except Exception as e:
            print(f"Error loading split receipts: {e}")
            self.split_parts = []
            self.cash_portion = None
            self._hide_split_view()
    
    def _display_split_layout(self):
        """Display receipts side-by-side."""
        # Clear previous panels
        for panel in self.detail_panels:
            panel.deleteLater()
        self.detail_panels.clear()
        
        # Create side-by-side panels for each split part
        for i, part in enumerate(self.split_parts):
            panel = self._create_receipt_detail_panel(part, i + 1, len(self.split_parts))
            self.detail_panels.append(panel)
            self.split_container_layout.addWidget(panel)
        
        self.split_container_layout.addStretch()

        # Update banner
        total_amount = sum(p['amount'] for p in self.split_parts)
        msg = f"📦 Split into {len(self.split_parts)} linked receipt(s) | Total: ${total_amount:,.2f}"
        self.linked_receipts_label.setText(msg)
        self.split_banner.setHidden(False)
    
    def _create_receipt_detail_panel(self, receipt_part: Dict, index: int, total: int) -> QGroupBox:
        """Create a detail panel for a split receipt part."""
        group = QGroupBox(f"Receipt Part {index} of {total}")
        group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #4CAF50;
                border-radius: 3px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
                color: #2E7D32;
                font-weight: bold;
            }
        """)
        
        form = QFormLayout(group)
        form.setSpacing(3)
        
        # Receipt ID (clickable to open)
        id_row = QHBoxLayout()
        id_label = QLabel(f"<b>Receipt #{receipt_part['receipt_id']}</b>")
        id_label.setOpenExternalLinks(False)
        id_row.addWidget(id_label)
        open_btn = QPushButton("🔗 Open")
        open_btn.setMaximumWidth(80)
        open_btn.clicked.connect(
            lambda: self._emit_open_receipt(receipt_part['receipt_id'])
        )
        id_row.addWidget(open_btn)
        id_row.addStretch()
        form.addRow("ID:", id_row)
        
        # Date
        form.addRow("Date:", QLabel(str(receipt_part['date'])))
        
        # Vendor
        form.addRow("Vendor:", QLabel(receipt_part['vendor']))
        
        # Amount (editable for split adjustment)
        amount_input = QDoubleSpinBox()
        amount_input.setRange(0, 999999.99)
        amount_input.setDecimals(2)
        amount_input.setValue(receipt_part['amount'])
        amount_input.setPrefix("$")
        amount_input.setMaximumWidth(150)
        amount_input.setSingleStep(0.01)
        form.addRow("Amount:", amount_input)
        
        # Description
        desc_label = QLabel(receipt_part.get('description', '') or "")
        desc_label.setWordWrap(True)
        form.addRow("Notes:", desc_label)
        
        # Split group indicator (based on split_group_id)
        if receipt_part.get('split_group_id'):
            status_label = QLabel(f"Split Group #{receipt_part['split_group_id']}")
            status_label.setStyleSheet("color: #2E7D32; font-weight: bold;")
            form.addRow("Split Info:", status_label)
        
        # Auto-adjustment checkbox
        adjust_chk = QCheckBox("Auto-adjust other parts to match total")
        adjust_chk.setChecked(False)
        form.addRow("", adjust_chk)
        
        return group
    
    def _show_split_details_dialog(self):
        """Show detailed split information dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Split Receipt Details - #{self.current_receipt_id}")
        dialog.setGeometry(100, 100, 700, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Summary
        total_amount = sum(p['amount'] for p in self.split_parts)
        
        summary_text = f"""
        <b>Split Summary</b><br>
        {len(self.split_parts)} linked receipt(s)<br>
        <b>Total: ${total_amount:,.2f}</b>
        """
        summary_label = QLabel(summary_text)
        summary_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        layout.addWidget(summary_label)
        
        # Split parts table
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Receipt ID", "Date", "Vendor", "Amount"])
        table.setRowCount(len(self.split_parts))
        
        for row, part in enumerate(self.split_parts):
            table.setItem(row, 0, QTableWidgetItem(str(part['receipt_id'])))
            table.setItem(row, 1, QTableWidgetItem(str(part['date'])))
            table.setItem(row, 2, QTableWidgetItem(part['vendor']))
            table.setItem(row, 3, QTableWidgetItem(f"${part['amount']:,.2f}"))
        
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def _collapse_split_view(self):
        """Collapse the split view back to single receipt."""
        self._hide_split_view()
    
    def _hide_split_view(self):
        """Hide split banner and panels."""
        self.split_banner.setHidden(True)
        for panel in self.detail_panels:
            panel.setHidden(True)
        self.detail_panels.clear()

    def _load_split_fallback(self, receipt_id: int, rec_date, vendor: str, amount: float | None, description: str):
        """Fallback split detection when no split_group_id is present.
        Heuristic: find receipts on the same day (±1), same vendor, with 'split' in description.
        """
        try:
            self.split_parts = []
            if not vendor or not rec_date:
                self._hide_split_view()
                return

            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT receipt_id, receipt_date, vendor_name, gross_amount, COALESCE(description,'')
                FROM receipts
                WHERE vendor_name = %s
                  AND receipt_date BETWEEN %s - INTERVAL '1 day' AND %s + INTERVAL '1 day'
                  AND LOWER(COALESCE(description,'')) LIKE '%%split%%'
                ORDER BY gross_amount DESC
                LIMIT 20
                """,
                (vendor, rec_date, rec_date),
            )
            rows = cur.fetchall()
            cur.close()

            for rid, rdate, vname, amt, desc in rows:
                self.split_parts.append({
                    'receipt_id': rid,
                    'date': rdate,
                    'vendor': vname,
                    'amount': float(amt) if amt is not None else 0.0,
                    'description': desc or ''
                })

            # Ensure current receipt is included
            present = any(p['receipt_id'] == receipt_id for p in self.split_parts)
            if not present:
                self.split_parts.append({
                    'receipt_id': receipt_id,
                    'date': rec_date,
                    'vendor': vendor,
                    'amount': amount or 0.0,
                    'description': description or ''
                })

            if len(self.split_parts) > 1:
                self._display_split_layout()
            else:
                self._hide_split_view()
        except Exception as e:
            print(f"Error in fallback split detection: {e}")
            self._hide_split_view()
    
    def _emit_open_receipt(self, receipt_id: int):
        """Emit signal to open a linked receipt."""
        # This would be connected in the main widget to load the receipt
        print(f"Opening linked receipt #{receipt_id}")
        self.split_updated.emit(receipt_id)
    
    def add_cash_portion_dialog(self, receipt_id: int, receipt_amount: float):
        """Show dialog to add a cash portion to a receipt."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Add Cash Portion - Receipt #{receipt_id}")
        dialog.setGeometry(200, 200, 500, 300)
        
        layout = QVBoxLayout(dialog)
        
        form = QFormLayout()
        
        # Receipt amount display
        form.addRow("Receipt Total:", QLabel(f"${receipt_amount:,.2f}"))
        
        # Cash amount input
        cash_amount = QDoubleSpinBox()
        cash_amount.setRange(0, receipt_amount)
        cash_amount.setDecimals(2)
        cash_amount.setValue(receipt_amount)
        cash_amount.setPrefix("$")
        cash_amount.setSingleStep(0.01)
        form.addRow("Cash Amount:", cash_amount)
        
        # Driver selection
        driver_combo = QComboBox()
        self._load_drivers_combo(driver_combo)
        form.addRow("Driver:", driver_combo)
        
        # Type selection
        type_combo = QComboBox()
        type_combo.addItems(["cash_received", "float_out", "reimbursed", "other"])
        form.addRow("Type:", type_combo)
        
        # Notes
        notes_input = QLineEdit()
        notes_input.setPlaceholderText("Optional notes...")
        form.addRow("Notes:", notes_input)
        
        layout.addLayout(form)
        
        # Buttons
        btn_row = QHBoxLayout()
        
        add_btn = QPushButton("✅ Add Cash Portion")
        add_btn.clicked.connect(lambda: self._save_cash_portion(
            dialog, receipt_id, cash_amount.value(), 
            driver_combo.currentData(), type_combo.currentText(), notes_input.text()
        ))
        btn_row.addWidget(add_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        btn_row.addWidget(cancel_btn)
        
        layout.addLayout(btn_row)
        
        dialog.exec()
    
    def _load_drivers_combo(self, combo: QComboBox):
        """Load drivers into combo box."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT employee_id, first_name, last_name 
                FROM employees 
                WHERE status = 'active'
                ORDER BY first_name, last_name
            """)
            
            combo.addItem("Select a driver...", None)
            for row in cur.fetchall():
                combo.addItem(f"{row[1]} {row[2]}", row[0])
            
            cur.close()
        
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading drivers: {e}")
    
    def _save_cash_portion(self, dialog: QDialog, receipt_id: int, amount: float, 
                          driver_id: Optional[int], type_str: str, notes: str):
        """Save cash portion to database."""
        if not driver_id:
            QMessageBox.warning(dialog, "Required", "Please select a driver")
            return
        
        try:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO receipt_cashbox_links 
                (receipt_id, cashbox_amount, float_reimbursement_type, driver_id, 
                 driver_notes, confirmed_by, confirmed_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (receipt_id) DO UPDATE SET
                    cashbox_amount = %s,
                    float_reimbursement_type = %s,
                    driver_id = %s,
                    driver_notes = %s,
                    confirmed_at = NOW()
            """, (receipt_id, amount, type_str, driver_id, notes, 'admin',
                  amount, type_str, driver_id, notes))
            
            self.conn.commit()
            cur.close()
            
            QMessageBox.information(dialog, "Success", f"Cash portion of ${amount:,.2f} added!")
            dialog.accept()
            self.split_updated.emit(receipt_id)
        
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            QMessageBox.critical(dialog, "Error", f"Could not save cash portion:\n{e}")
