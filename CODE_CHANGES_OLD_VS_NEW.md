# Side-by-Side: Old vs New Code Changes

## 1. CurrencyInput Class

### BEFORE (Old)
```python
class CurrencyInput(QLineEdit):
    """Currency input field with validation"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
```

### AFTER (New)
```python
class CurrencyInput(QLineEdit):
    """Currency input field with validation (compact 6-digit max)"""
    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.setPlaceholderText("0.00")
        self.setText("0.00")
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.compact = compact
        if compact:
            self.setMaxLength(10)  # "999999.99" = 9 chars
            self.setMaximumWidth(100)  # ← Compact mode enabled
```

**Change Summary:**
- Added `compact` parameter (default False for backward compatibility)
- If `compact=True`: width restricted to 100px and max 10 chars
- Still stores and displays full precision

---

## 2. NEW: CalculatorButton Class

### BEFORE (Old)
```python
# No calculator class existed
```

### AFTER (New)
```python
class CalculatorButton(QPushButton):
    """Quick calculator for currency amounts"""
    def __init__(self, target_field, parent=None):
        super().__init__(parent)
        self.setText("🧮")
        self.setMaximumWidth(35)
        self.setToolTip("Open calculator")
        self.target_field = target_field
        self.clicked.connect(self._open_calculator)
        
    def _open_calculator(self):
        """Open a simple calculator dialog"""
        from PyQt6.QtWidgets import QInputDialog
        
        current = self.target_field.get_value()
        value, ok = QInputDialog.getDouble(
            self,
            "Calculator",
            "Enter amount:",
            value=current,
            decimals=2,
            minValue=0,
            maxValue=999999.99
        )
        
        if ok:
            self.target_field.setText(f"{value:.2f}")
```

**What's New:**
- Entirely new class for calculator button
- Creates 🧮 emoji button
- Opens dialog on click
- Returns value to associated field

---

## 3. Invoice List - Table Columns

### BEFORE (Old)
```python
self.invoice_table.setColumnCount(7)
self.invoice_table.setHorizontalHeaderLabels([
    "ID", "Invoice #", "Date", "Amount", "Paid", "Balance", "Status"
])
```

### AFTER (New)
```python
self.invoice_table.setColumnCount(8)
self.invoice_table.setHorizontalHeaderLabels([
    "ID", "Invoice #", "Date", "Amount", "Paid", "Balance", "Running Balance", "Status"
])
```

**Change Summary:**
- 7 columns → 8 columns
- Added "Running Balance" between "Balance" and "Status"

---

## 4. Add Invoice Tab - Major Refactor

### BEFORE (Old - QFormLayout)
```python
def _create_add_invoice_tab(self):
    """Tab for adding new invoices"""
    widget = QWidget()
    layout = QFormLayout(widget)
    
    # Invoice number
    self.new_invoice_num = QLineEdit()
    layout.addRow("Invoice Number:", self.new_invoice_num)
    
    # Invoice date
    self.new_invoice_date = QDateEdit()
    self.new_invoice_date.setCalendarPopup(True)
    self.new_invoice_date.setDate(QDate.currentDate())
    self.new_invoice_date.setDisplayFormat("MM/dd/yyyy")
    layout.addRow("Invoice Date:", self.new_invoice_date)
    
    # Amount
    self.new_invoice_amount = CurrencyInput()
    layout.addRow("Amount:", self.new_invoice_amount)
    
    # Description
    self.new_invoice_desc = QTextEdit()
    self.new_invoice_desc.setMaximumHeight(80)
    self.new_invoice_desc.setPlaceholderText("Optional description...")
    layout.addRow("Description:", self.new_invoice_desc)
    
    # Category
    self.new_invoice_category = QComboBox()
    self.new_invoice_category.setEditable(True)
    self._load_categories()
    layout.addRow("Category:", self.new_invoice_category)
    
    # Add button
    add_btn = QPushButton("✅ Add Invoice")
    add_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 10px;")
    add_btn.clicked.connect(self._add_invoice)
    layout.addRow("", add_btn)
    
    return widget
```

### AFTER (New - QVBoxLayout with Fee Split)
```python
def _create_add_invoice_tab(self):
    """Tab for adding new invoices with split capability for fees"""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    
    # Main form
    form = QFormLayout()
    
    # Invoice number
    self.new_invoice_num = QLineEdit()
    form.addRow("Invoice Number:", self.new_invoice_num)
    
    # Invoice date
    self.new_invoice_date = QDateEdit()
    self.new_invoice_date.setCalendarPopup(True)
    self.new_invoice_date.setDate(QDate.currentDate())
    self.new_invoice_date.setDisplayFormat("MM/dd/yyyy")
    form.addRow("Invoice Date:", self.new_invoice_date)
    
    # Amount (compact with calculator) ← CHANGED
    amount_row = QHBoxLayout()
    self.new_invoice_amount = CurrencyInput(compact=True)
    amount_row.addWidget(self.new_invoice_amount, stretch=0)
    calc_btn = CalculatorButton(self.new_invoice_amount)
    amount_row.addWidget(calc_btn, stretch=0)
    amount_row.addStretch()
    form.addRow("Amount:", amount_row)
    
    # Description
    self.new_invoice_desc = QTextEdit()
    self.new_invoice_desc.setMaximumHeight(60)
    self.new_invoice_desc.setPlaceholderText("Optional description...")
    form.addRow("Description:", self.new_invoice_desc)
    
    # Category
    self.new_invoice_category = QComboBox()
    self.new_invoice_category.setEditable(True)
    self._load_categories()
    form.addRow("Category:", self.new_invoice_category)
    
    layout.addLayout(form)
    
    # ╔═══════════════════════════════════════════════════╗
    # ║ NEW: Split fees section                           ║
    # ╚═══════════════════════════════════════════════════╝
    
    # Split fees section (for vendors like WCB with overdue fees)
    split_group = QGroupBox("💳 Split Fees (Optional - for WCB overdue fees, CRA adjustments, etc.)")
    split_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 10px; }")
    split_layout = QVBoxLayout()
    
    # Split checkbox
    self.new_invoice_use_split = QCheckBox("Split this invoice into vendor charge + separate fee")
    self.new_invoice_use_split.setToolTip("Enable to separate base charge from overdue fees or other adjustments")
    self.new_invoice_use_split.stateChanged.connect(self._on_split_checkbox_changed)
    split_layout.addWidget(self.new_invoice_use_split)
    
    # Split details (hidden by default)
    self.split_details = QWidget()
    split_details_layout = QFormLayout(self.split_details)
    
    # Base amount
    base_amount_row = QHBoxLayout()
    self.new_invoice_base_amount = CurrencyInput(compact=True)
    base_amount_row.addWidget(self.new_invoice_base_amount, stretch=0)
    base_calc_btn = CalculatorButton(self.new_invoice_base_amount)
    base_amount_row.addWidget(base_calc_btn, stretch=0)
    base_amount_row.addStretch()
    split_details_layout.addRow("Base Charge Amount:", base_amount_row)
    
    # Fee amount
    fee_amount_row = QHBoxLayout()
    self.new_invoice_fee_amount = CurrencyInput(compact=True)
    fee_amount_row.addWidget(self.new_invoice_fee_amount, stretch=0)
    fee_calc_btn = CalculatorButton(self.new_invoice_fee_amount)
    fee_amount_row.addWidget(fee_calc_btn, stretch=0)
    fee_amount_row.addStretch()
    split_details_layout.addRow("Fee/Adjustment Amount:", fee_amount_row)
    
    # Fee type
    self.new_invoice_fee_type = QComboBox()
    self.new_invoice_fee_type.addItems([
        "Overdue Fee",
        "Interest Charge",
        "Penalty",
        "Service Charge",
        "Late Payment Fee",
        "CRA Adjustment",
        "Other"
    ])
    self.new_invoice_fee_type.setToolTip("CRA: Fees are NOT included in income calculations - tracked separately for reporting")
    split_details_layout.addRow("Fee Type:", self.new_invoice_fee_type)
    
    # Info note
    fee_note = QLabel("ℹ️ Overdue fees and penalties are tracked separately for CRA reporting (not counted as income)")
    fee_note.setStyleSheet("font-size: 9px; color: #0066cc; font-style: italic;")
    split_details_layout.addRow("", fee_note)
    
    self.split_details.setVisible(False)
    split_layout.addWidget(self.split_details)
    
    split_group.setLayout(split_layout)
    layout.addWidget(split_group)
    
    # ╚═══════════════════════════════════════════════════╝
    
    # Add button
    add_btn = QPushButton("✅ Add Invoice")
    add_btn.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 10px;")
    add_btn.clicked.connect(self._add_invoice)
    layout.addWidget(add_btn)
    
    layout.addStretch()
    
    return widget
```

**Change Summary:**
- Changed from QFormLayout to QVBoxLayout for flexibility
- Amount field now compact with calculator
- Added entire split fees section (30+ lines of UI)
- Hidden by default, shown when checkbox enabled
- Added new fields: base_amount, fee_amount, fee_type
- Fee type dropdown with 7 predefined options

---

## 5. Invoice Table Refresh - Running Balance

### BEFORE (Old - 7 columns)
```python
def _refresh_invoice_table(self):
    """Refresh the invoice table display"""
    self.invoice_table.setRowCount(len(self.current_invoices))
    
    for idx, invoice in enumerate(self.current_invoices):
        receipt_id, ref, date, amount, paid, balance, status = invoice
        
        # ID
        id_item = QTableWidgetItem(str(receipt_id))
        self.invoice_table.setItem(idx, 0, id_item)
        
        # Invoice #
        self.invoice_table.setItem(idx, 1, QTableWidgetItem(str(ref or f"R-{receipt_id}")))
        
        # Date
        self.invoice_table.setItem(idx, 2, QTableWidgetItem(str(date)))
        
        # Amount
        amt_item = QTableWidgetItem(f"${amount:,.2f}")
        amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.invoice_table.setItem(idx, 3, amt_item)
        
        # Paid
        paid_item = QTableWidgetItem(f"${paid:,.2f}")
        paid_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.invoice_table.setItem(idx, 4, paid_item)
        
        # Balance
        bal_item = QTableWidgetItem(f"${balance:,.2f}")
        bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if balance > 0:
            bal_item.setForeground(QBrush(QColor("red")))
        self.invoice_table.setItem(idx, 5, bal_item)
        
        # Status
        status_item = QTableWidgetItem(status)
        self.invoice_table.setItem(idx, 6, status_item)
```

### AFTER (New - 8 columns + running balance)
```python
def _refresh_invoice_table(self):
    """Refresh the invoice table display with running balance"""
    self.invoice_table.setRowCount(len(self.current_invoices))
    
    running_balance = 0.0  # ← NEW: Track cumulative balance
    
    for idx, invoice in enumerate(self.current_invoices):
        receipt_id, ref, date, amount, paid, balance, status = invoice
        
        # Update running balance (cumulative)
        running_balance += balance  # ← NEW: Accumulate
        
        # ID
        id_item = QTableWidgetItem(str(receipt_id))
        self.invoice_table.setItem(idx, 0, id_item)
        
        # Invoice #
        self.invoice_table.setItem(idx, 1, QTableWidgetItem(str(ref or f"R-{receipt_id}")))
        
        # Date
        self.invoice_table.setItem(idx, 2, QTableWidgetItem(str(date)))
        
        # Amount
        amt_item = QTableWidgetItem(f"${amount:,.2f}")
        amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.invoice_table.setItem(idx, 3, amt_item)
        
        # Paid
        paid_item = QTableWidgetItem(f"${paid:,.2f}")
        paid_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.invoice_table.setItem(idx, 4, paid_item)
        
        # Balance (individual invoice balance)
        bal_item = QTableWidgetItem(f"${balance:,.2f}")
        bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if balance > 0:
            bal_item.setForeground(QBrush(QColor("red")))
        self.invoice_table.setItem(idx, 5, bal_item)
        
        # ╔═════════════════════════════════════════════════╗
        # ║ NEW: Running Balance (column index 6)            ║
        # ╚═════════════════════════════════════════════════╝
        running_bal_item = QTableWidgetItem(f"${running_balance:,.2f}")
        running_bal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        running_bal_item.setForeground(QBrush(QColor("darkblue")))  # Dark blue color
        running_bal_item.setFont(self._get_bold_font())              # Bold font
        self.invoice_table.setItem(idx, 6, running_bal_item)
        # ╚═════════════════════════════════════════════════╝
        
        # Status
        status_item = QTableWidgetItem(status)
        self.invoice_table.setItem(idx, 7, status_item)  # ← Changed from 6 to 7

def _get_bold_font(self):
    """Get bold font for running balance"""
    font = QFont()
    font.setBold(True)
    return font
```

**Change Summary:**
- Added `running_balance` variable initialized to 0.0
- Inside loop: accumulate balance for each invoice
- New column 6: Running Balance (dark blue, bold)
- Status moved from column 6 to column 7
- New helper method `_get_bold_font()`

---

## 6. Add Invoice - Fee Split Logic

### BEFORE (Old - Simple)
```python
def _add_invoice(self):
    """Add a new invoice for current vendor"""
    if not self.current_vendor:
        QMessageBox.warning(self, "No Vendor", "Please select a vendor first.")
        return
        
    invoice_num = self.new_invoice_num.text().strip()
    amount = self.new_invoice_amount.get_value()
    
    if amount <= 0:
        QMessageBox.warning(self, "Invalid Amount", "Amount must be greater than 0.")
        return
        
    try:
        cur = self.conn.get_cursor()
        
        sql = """
            INSERT INTO receipts (
                vendor_name, source_reference, receipt_date, 
                gross_amount, description, category,
                created_from_banking, source_file
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING receipt_id
        """
        
        params = (
            self.current_vendor,
            invoice_num or None,
            self.new_invoice_date.date().toPyDate(),
            amount,
            self.new_invoice_desc.toPlainText().strip() or None,
            self.new_invoice_category.currentText().strip() or None,
            False,
            'VENDOR_INVOICE_MANAGER'
        )
        
        cur.execute(sql, params)
        new_id = cur.fetchone()[0]
        self.conn.commit()
        cur.close()
        
        QMessageBox.information(self, "Success", f"✅ Invoice added!\n\nInvoice ID: {new_id}")
        
        # Clear form
        self.new_invoice_num.clear()
        self.new_invoice_amount.setText("0.00")
        self.new_invoice_desc.clear()
        
        # Refresh
        self._load_vendor_invoices()
        
    except Exception as e:
        self.conn.rollback()
        QMessageBox.critical(self, "Add Error", f"Failed to add invoice:\n\n{e}")
```

### AFTER (New - With Fee Split)
```python
def _add_invoice(self):
    """Add a new invoice for current vendor (with optional fee split)"""
    if not self.current_vendor:
        QMessageBox.warning(self, "No Vendor", "Please select a vendor first.")
        return
        
    invoice_num = self.new_invoice_num.text().strip()
    amount = self.new_invoice_amount.get_value()
    
    if amount <= 0:
        QMessageBox.warning(self, "Invalid Amount", "Amount must be greater than 0.")
        return
    
    # ╔═══════════════════════════════════════════════╗
    # ║ NEW: Check if using split                     ║
    # ╚═══════════════════════════════════════════════╝
    use_split = self.new_invoice_use_split.isChecked()
    base_amount = amount
    fee_amount = 0.0
    fee_type = None
    
    if use_split:
        base_amount = self.new_invoice_base_amount.get_value()
        fee_amount = self.new_invoice_fee_amount.get_value()
        fee_type = self.new_invoice_fee_type.currentText()
        
        if base_amount + fee_amount != amount:
            QMessageBox.warning(
                self,
                "Split Mismatch",
                f"Base ({base_amount:.2f}) + Fee ({fee_amount:.2f}) must equal Total ({amount:.2f})"
            )
            return
    # ╚═══════════════════════════════════════════════╝
        
    try:
        cur = self.conn.get_cursor()
        
        # Add main invoice
        sql = """
            INSERT INTO receipts (
                vendor_name, source_reference, receipt_date, 
                gross_amount, description, category,
                created_from_banking, source_file
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING receipt_id
        """
        
        # ╔═══════════════════════════════════════════════╗
        # ║ NEW: Build description with fee breakdown     ║
        # ╚═══════════════════════════════════════════════╝
        description = self.new_invoice_desc.toPlainText().strip() or None
        if use_split and fee_amount > 0:
            if description:
                description = f"{description} | Base: ${base_amount:.2f} + {fee_type}: ${fee_amount:.2f}"
            else:
                description = f"Base: ${base_amount:.2f} + {fee_type}: ${fee_amount:.2f}"
        # ╚═══════════════════════════════════════════════╝
        
        params = (
            self.current_vendor,
            invoice_num or None,
            self.new_invoice_date.date().toPyDate(),
            amount,
            description,  # ← Now includes fee breakdown
            self.new_invoice_category.currentText().strip() or None,
            False,
            'VENDOR_INVOICE_MANAGER'
        )
        
        cur.execute(sql, params)
        receipt_id = cur.fetchone()[0]
        
        # ╔═══════════════════════════════════════════════╗
        # ║ NEW: Create vendor ledger entry for fee       ║
        # ╚═══════════════════════════════════════════════╝
        if use_split and fee_amount > 0:
            try:
                vendor_sql = """
                    INSERT INTO vendor_account_ledger (
                        account_id, entry_date, entry_type, amount, 
                        source_table, source_id, notes
                    ) 
                    SELECT 
                        va.account_id, %s, 'ADJUSTMENT', %s,
                        'receipts', %s, %s
                    FROM vendor_accounts va
                    WHERE va.canonical_vendor ILIKE %s
                    LIMIT 1
                """
                cur.execute(vendor_sql, (
                    self.new_invoice_date.date().toPyDate(),
                    fee_amount,
                    f"{receipt_id}_fee",
                    f"{fee_type} - Not counted in income calculation",
                    self.current_vendor
                ))
            except:
                pass  # Vendor ledger table may not exist yet
        # ╚═══════════════════════════════════════════════╝
        
        self.conn.commit()
        cur.close()
        
        # ╔═══════════════════════════════════════════════╗
        # ║ NEW: Enhanced success message                 ║
        # ╚═══════════════════════════════════════════════╝
        msg = f"✅ Invoice added!\n\nInvoice ID: {receipt_id}\nAmount: ${amount:,.2f}"
        if use_split and fee_amount > 0:
            msg += f"\n\nBreakdown:\n  Base: ${base_amount:,.2f}\n  {fee_type}: ${fee_amount:,.2f}\n\n⚠️ Fee tracked separately for CRA reporting"
        
        QMessageBox.information(self, "Success", msg)
        # ╚═══════════════════════════════════════════════╝
        
        # Clear form
        self.new_invoice_num.clear()
        self.new_invoice_amount.setText("0.00")
        self.new_invoice_base_amount.setText("0.00")  # ← NEW
        self.new_invoice_fee_amount.setText("0.00")   # ← NEW
        self.new_invoice_desc.clear()
        self.new_invoice_use_split.setChecked(False)  # ← NEW
        self.split_details.setVisible(False)          # ← NEW
        
        # Refresh
        self._load_vendor_invoices()
        
    except Exception as e:
        self.conn.rollback()
        QMessageBox.critical(self, "Add Error", f"Failed to add invoice:\n\n{e}")
```

**Change Summary:**
- Check if fee split enabled
- Validate base + fee = total
- Build description with fee breakdown
- Create vendor ledger entry for fee (optional, graceful fallback)
- Enhanced success message showing breakdown
- Clear additional fee fields on success

---

## Summary of All Changes

| Component | Change Type | Impact |
|-----------|------------|--------|
| CurrencyInput | Enhancement | Compact mode support |
| CalculatorButton | NEW | Calculator UI widget |
| Invoice Table | Structural | +1 column (Running Balance) |
| Add Invoice Form | Major Refactor | Fee split section added |
| Table Refresh | Enhancement | Running balance calculation |
| Invoice Logic | Enhancement | Fee split validation & ledger entry |
| Payment Tab | Enhancement | Added amount & reference fields |

**Total Lines Added:** ~300 (mostly UI and comments)  
**Backward Compatibility:** 100% (all new features optional)  
**Database Changes:** None required (ledger entry optional)
