"""
Split Receipt Creation Dialog - 2-3 panel side-by-side layout for splitting receipts
Allows user to split a receipt into multiple parts with automatic amount calculation
"""

from decimal import Decimal
from typing import Optional, List, Dict
import psycopg2
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QFormLayout, QMessageBox, QDoubleSpinBox, QSpinBox,
    QComboBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QWidget
)


class SplitReceiptCreationDialog(QDialog):
    """Dialog for splitting a receipt into 2-3 parts with auto-calculation."""
    
    def __init__(self, conn: psycopg2.extensions.connection, receipt_id: int, 
                 receipt_data: Dict, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.receipt_id = receipt_id
        self.receipt_data = receipt_data
        self.num_parts = 2  # Default to 2-part split
        self.split_parts: List[Dict] = []
        
        self.setWindowTitle(f"Split Receipt #{receipt_id}")
        self.setGeometry(50, 50, 1400, 700)
        self.setModal(True)
        
        self._build_ui()
        self._initialize_split_parts(2)
    
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Header: Receipt info
        header = self._build_header()
        layout.addWidget(header)
        
        # Split configuration
        config = self._build_config_panel()
        layout.addWidget(config)
        
        # Side-by-side panels container
        self.panels_container = QWidget()
        self.panels_layout = QHBoxLayout(self.panels_container)
        self.panels_layout.setSpacing(10)
        self.panels_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidget(self.panels_container)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        # Cash portion checkbox + button
        self.cash_group = self._build_cash_portion_group()
        layout.addWidget(self.cash_group)
        
        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        save_btn = QPushButton("✅ Save Split")
        save_btn.clicked.connect(self._save_split)
        btn_row.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        
        layout.addLayout(btn_row)
    
    def _build_header(self) -> QGroupBox:
        """Build receipt header with info."""
        group = QGroupBox("Original Receipt")
        form = QFormLayout(group)
        
        form.addRow("Receipt ID:", QLabel(str(self.receipt_id)))
        form.addRow("Date:", QLabel(str(self.receipt_data.get('receipt_date', ''))))
        form.addRow("Vendor:", QLabel(self.receipt_data.get('vendor_name', '')))
        
        total_label = QLabel(f"${float(self.receipt_data.get('gross_amount', 0)):,.2f}")
        total_label.setStyleSheet("font-weight: bold; color: #2E7D32; font-size: 14px;")
        form.addRow("Total Amount:", total_label)
        
        return group
    
    def _build_config_panel(self) -> QGroupBox:
        """Build the split configuration panel."""
        group = QGroupBox("Split Configuration")
        layout = QHBoxLayout(group)
        
        layout.addWidget(QLabel("Split into:"))
        
        self.num_parts_spin = QSpinBox()
        self.num_parts_spin.setRange(2, 3)
        self.num_parts_spin.setValue(2)
        self.num_parts_spin.setMaximumWidth(80)
        self.num_parts_spin.valueChanged.connect(self._on_num_parts_changed)
        layout.addWidget(self.num_parts_spin)
        
        layout.addWidget(QLabel("parts"))
        layout.addStretch()
        
        info_label = QLabel("💡 Enter first part amount; second (and third if applicable) auto-fill with remainder")
        info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info_label)
        
        return group
    
    def _build_cash_portion_group(self) -> QGroupBox:
        """Build cash portion management group."""
        group = QGroupBox("Cash Portion")
        layout = QHBoxLayout(group)
        
        self.cash_enabled_chk = QCheckBox("Add cash portion to first receipt")
        self.cash_enabled_chk.stateChanged.connect(self._on_cash_enabled_changed)
        layout.addWidget(self.cash_enabled_chk)
        
        layout.addWidget(QLabel("Amount:"))
        self.cash_amount_spin = QDoubleSpinBox()
        self.cash_amount_spin.setRange(0, 999999.99)
        self.cash_amount_spin.setDecimals(2)
        self.cash_amount_spin.setPrefix("$")
        self.cash_amount_spin.setSingleStep(0.01)
        self.cash_amount_spin.setMaximumWidth(150)
        self.cash_amount_spin.setEnabled(False)
        layout.addWidget(self.cash_amount_spin)
        
        layout.addWidget(QLabel("Driver:"))
        self.cash_driver_combo = QComboBox()
        self.cash_driver_combo.setEnabled(False)
        self._load_drivers_combo(self.cash_driver_combo)
        layout.addWidget(self.cash_driver_combo)
        
        layout.addWidget(QLabel("Type:"))
        self.cash_type_combo = QComboBox()
        self.cash_type_combo.addItems(["cash_received", "float_out", "reimbursed", "other"])
        self.cash_type_combo.setEnabled(False)
        self.cash_type_combo.setMaximumWidth(150)
        layout.addWidget(self.cash_type_combo)
        
        layout.addStretch()
        
        return group
    
    def _load_drivers_combo(self, combo: QComboBox):
        """Load active drivers into combo."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                SELECT employee_id, first_name, last_name 
                FROM employees 
                WHERE status = 'active'
                ORDER BY first_name, last_name
            """)
            
            combo.addItem("Select driver...", None)
            for row in cur.fetchall():
                combo.addItem(f"{row[1]} {row[2]}", row[0])
            
            cur.close()
        
        except Exception as e:
            try:
                self.db.rollback()
            except:
                pass
            print(f"Error loading drivers: {e}")
    
    def _initialize_split_parts(self, num_parts: int):
        """Initialize split part data structures."""
        self.num_parts = num_parts
        self.split_parts = []
        
        for i in range(num_parts):
            self.split_parts.append({
                'index': i + 1,
                'amount': 0,
                'payment_method': self.receipt_data.get('payment_method', ''),
                'gl_code': self.receipt_data.get('gl_account_code', ''),
                'description': f"Part {i+1} of {num_parts}"
            })
        
        self._refresh_panels()
    
    def _on_num_parts_changed(self, value: int):
        """Handle change in number of split parts."""
        self._initialize_split_parts(value)
    
    def _on_cash_enabled_changed(self, state):
        """Handle cash portion checkbox change."""
        enabled = state != 0
        self.cash_amount_spin.setEnabled(enabled)
        self.cash_driver_combo.setEnabled(enabled)
        self.cash_type_combo.setEnabled(enabled)
    
    def _refresh_panels(self):
        """Refresh the side-by-side panels."""
        # Clear existing panels
        while self.panels_layout.count():
            item = self.panels_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Create new panels
        self.part_inputs: List[Dict] = []
        
        for part in self.split_parts:
            panel = self._create_part_panel(part)
            self.panels_layout.addWidget(panel)
        
        self.panels_layout.addStretch()
    
    def _create_part_panel(self, part: Dict) -> QGroupBox:
        """Create a panel for a single receipt part."""
        group = QGroupBox(f"Part {part['index']} of {self.num_parts}")
        group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #4CAF50;
                border-radius: 5px;
                margin-top: 15px;
                padding-top: 15px;
                min-width: 300px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2E7D32;
                font-weight: bold;
            }
        """)
        
        form = QFormLayout(group)
        form.setSpacing(5)
        
        # Original receipt reference
        form.addRow("Original ID:", QLabel(f"#{self.receipt_id}"))
        
        # Amount input
        amount_spin = QDoubleSpinBox()
        amount_spin.setRange(0, float(self.receipt_data.get('gross_amount', 0)))
        amount_spin.setDecimals(2)
        amount_spin.setPrefix("$")
        amount_spin.setSingleStep(0.01)
        amount_spin.setMaximumWidth(150)
        amount_spin.setValue(part['amount'])
        
        # Auto-fill logic
        amount_spin.valueChanged.connect(
            lambda val: self._on_part_amount_changed(part['index'] - 1, val)
        )
        
        form.addRow("Amount:", amount_spin)
        
        # Payment method (editable)
        payment_combo = QComboBox()
        payment_combo.addItems(["cash", "check", "credit_card", "debit_card", 
                               "bank_transfer", "trade_of_services", "unknown"])
        payment_combo.setCurrentText(part['payment_method'] or "unknown")
        form.addRow("Payment Method:", payment_combo)
        
        # GL Code (editable)
        gl_code_input = QLineEdit()
        gl_code_input.setText(part['gl_code'] or "")
        gl_code_input.setPlaceholderText("e.g., 4100")
        form.addRow("GL Code:", gl_code_input)
        
        # Description (editable)
        desc_input = QLineEdit()
        desc_input.setText(part['description'] or "")
        form.addRow("Description:", desc_input)
        
        # Store references for later retrieval
        part_input = {
            'index': part['index'],
            'amount_spin': amount_spin,
            'payment_combo': payment_combo,
            'gl_input': gl_code_input,
            'desc_input': desc_input,
            'group': group
        }
        
        self.part_inputs.append(part_input)
        
        return group
    
    def _on_part_amount_changed(self, part_index: int, amount: float):
        """Handle amount change with auto-fill logic."""
        total_receipt = float(self.receipt_data.get('gross_amount', 0))
        
        # Update the part amount
        self.split_parts[part_index]['amount'] = amount
        
        # Auto-fill remaining parts
        remaining = total_receipt - amount
        
        if part_index == 0 and len(self.split_parts) > 1:
            # First part changed, auto-fill second part
            remaining_per_part = remaining / (len(self.split_parts) - 1)
            
            for i in range(1, len(self.split_parts)):
                self.part_inputs[i]['amount_spin'].blockSignals(True)
                self.part_inputs[i]['amount_spin'].setValue(remaining_per_part)
                self.split_parts[i]['amount'] = remaining_per_part
                self.part_inputs[i]['amount_spin'].blockSignals(False)
        
        # Update validation
        self._update_split_validation()
    
    def _update_split_validation(self):
        """Validate that split parts sum to original amount."""
        total_receipt = float(self.receipt_data.get('gross_amount', 0))
        split_sum = sum(part['amount'] for part in self.split_parts)
        
        difference = abs(split_sum - total_receipt)
        
        # Update color based on validation
        if difference < 0.01:  # Essentially equal
            color = "#C8E6C9"  # Green
            status = "✅ Amounts match"
        else:
            color = "#FFCDD2"  # Red
            status = f"⚠️ Difference: ${difference:,.2f}"
        
        # Apply to all panels
        stylesheet = f"""
            QGroupBox {{
                border: 2px solid {'#4CAF50' if difference < 0.01 else '#FF5252'};
                background-color: {color};
            }}
        """
        
        for part_input in self.part_inputs:
            part_input['group'].setStyleSheet(f"""
                QGroupBox {{
                    border: 2px solid {'#4CAF50' if difference < 0.01 else '#FF5252'};
                    border-radius: 5px;
                    margin-top: 15px;
                    padding-top: 15px;
                    min-width: 300px;
                    background-color: {color};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                    color: #2E7D32;
                    font-weight: bold;
                }}
            """)
    
    def _save_split(self):
        """Save the split receipt to database."""
        total_receipt = float(self.receipt_data.get('gross_amount', 0))
        split_sum = sum(part['amount'] for part in self.split_parts)
        
        if abs(split_sum - total_receipt) >= 0.01:
            QMessageBox.warning(
                self,
                "Validation Error",
                f"Split parts (${split_sum:,.2f}) must equal receipt total (${total_receipt:,.2f})"
            )
            return
        
        try:
            cur = self.conn.cursor()
            
            # Collect part data from UI
            parts_to_save = []
            for i, part_input in enumerate(self.part_inputs):
                parts_to_save.append({
                    'amount': part_input['amount_spin'].value(),
                    'payment_method': part_input['payment_combo'].currentText(),
                    'gl_code': part_input['gl_input'].text().strip() or None,
                    'description': part_input['desc_input'].text().strip() or f"Part {i+1} of {self.num_parts}",
                })
            
            # Insert receipt_splits for first part (or create linked receipt)
            for i, part in enumerate(parts_to_save):
                cur.execute("""
                    INSERT INTO receipt_splits 
                    (receipt_id, split_order, gl_code, amount, payment_method, notes, created_by, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'admin', NOW())
                """, (
                    self.receipt_id,
                    i + 1,
                    part['gl_code'],
                    part['amount'],
                    part['payment_method'],
                    part['description']
                ))
            
            # Add cash portion if enabled
            if self.cash_enabled_chk.isChecked():
                driver_id = self.cash_driver_combo.currentData()
                if not driver_id:
                    QMessageBox.warning(self, "Required", "Select a driver for cash portion")
                    cur.close()
                    return
                
                cur.execute("""
                    INSERT INTO receipt_cashbox_links 
                    (receipt_id, cashbox_amount, float_reimbursement_type, driver_id, confirmed_by, confirmed_at)
                    VALUES (%s, %s, %s, %s, 'admin', NOW())
                """, (
                    self.receipt_id,
                    self.cash_amount_spin.value(),
                    self.cash_type_combo.currentText(),
                    driver_id
                ))
            
            # Update receipt split status
            cur.execute("""
                UPDATE receipts SET split_status = 'split_reconciled' WHERE receipt_id = %s
            """, (self.receipt_id,))
            
            self.conn.commit()
            cur.close()
            
            QMessageBox.information(
                self,
                "Success",
                f"Receipt split into {self.num_parts} parts successfully!"
            )
            
            self.accept()
        
        except Exception as e:
            self.conn.rollback()
            QMessageBox.critical(self, "Error", f"Could not save split:\n{e}")
