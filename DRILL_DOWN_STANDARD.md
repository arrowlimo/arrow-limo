# Standardized Drill-Down Dialog Specification

## Overview
This document defines the standardized pattern for all drill-down dialogs in the Arrow Limousine Management System desktop app. All detail views (Client, Employee, Vehicle, Charter, Quote, Receipt) follow this specification for consistent UX.

## Button Layout (TOP OF DIALOG)

```
┌─────────────────────────────────────────────────────────────────┐
│ [🚫 Suspend] [✅ Activate]         [➕ Add] [📋 Dup] [🗑️ Del] [💾 Save] [Close] │
│  ^-- Action-Specific              ^-- Standard Drill-Down Buttons                   │
│      (varies by module)            (same in all modules)         │
└─────────────────────────────────────────────────────────────────┘
```

### Button Organization
- **Left Side**: Action-specific buttons (module-dependent)
  - Client: Suspend, Activate
  - Employee: Terminate, Suspend
  - Vehicle: Retire, Sell
  - Charter: Lock, Unlock, Cancel
  - Quote: (none yet)
  - Receipt: (none yet)

- **Center**: Stretch (empty space)

- **Right Side**: Standard drill-down buttons (SAME across all modules)
  1. ➕ **Add New** - Create new record (opens new dialog with no ID)
  2. 📋 **Duplicate** - Copy current record with identifier change
  3. 🗑️ **Delete** - Delete current record (with confirmation)
  4. 💾 **Save Changes** - Save modifications to current record
  5. **Close** - Exit dialog without saving

## Button Behavior

### Add New Record
```
User clicks [➕ Add New]
  ↓
Confirmation dialog: "Create a new [type] record?"
  ↓
Opens new instance of same dialog class with record_id=None
  ↓
User fills in fields
  ↓
Clicks [Save]
  ↓
New record inserted into database
  ↓
Dialog emits saved() signal
  ↓
Parent list refreshes
```

### Duplicate Record
```
User clicks [📋 Duplicate]
  ↓
DuplicateRecordDialog opens: "Enter a new [identifier] for the duplicate"
  ↓
User modifies identifier (name, license plate, reserve number, etc.)
  ↓
Clicks "Duplicate" button
  ↓
New record created with:
  - All fields copied from current record
  - Primary key removed
  - Identifier field updated per user input
  ↓
Dialog emits saved() signal
  ↓
Parent list refreshes
```

### Delete Record
```
User clicks [🗑️ Delete]
  ↓
Confirmation dialog: "Delete this [type] record? Cannot be undone."
  ↓
User confirms [Yes]
  ↓
Record deleted from database
  ↓
Dialog emits saved({"action": "delete", "id": record_id}) signal
  ↓
Dialog closes
  ↓
Parent list refreshes
```

### Save Changes
```
User modifies fields
  ↓
Clicks [💾 Save Changes]
  ↓
All modified fields collected
  ↓
UPDATE query executes on database
  ↓
Success message shown
  ↓
Dialog emits saved() signal with record data
  ↓
Dialog stays open (user can continue editing)
  ↓
Parent list refreshes in background
```

## Navigation Flow

### Double-Click from List → Detail View
```
User sees list of records (enhanced_*_widget.py)
  ↓
Double-clicks row
  ↓
List emits doubleClicked signal
  ↓
open_detail() method called with record_id
  ↓
*DetailDialog(db, record_id=selected_id) opens
  ↓
load_record_data() populates fields
  ↓
Dialog displays as modal (blocks parent)
```

### Detail View Close → Back to List
```
User clicks [Close] button
  ↓
Dialog closes
  ↓
Modal dismissed
  ↓
Control returns to parent list widget
  ↓
Parent list checks for saved() signals and refreshes if needed
```

### List Refresh After Save
```
Child dialog emits saved() signal
  ↓
Parent list receives signal via saved.connect()
  ↓
Parent list reloads data from database
  ↓
List table repopulates with fresh records
  ↓
(New/duplicate records now visible, deleted records removed)
```

## Code Pattern: Base Class

All drill-down dialogs inherit from `StandardDrillDownDialog` or follow this pattern:

```python
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QTabWidget
from PyQt6.QtCore import pyqtSignal, Qt

class SampleDetailDialog(QDialog):
    """Master-detail view for Sample records"""
    
    saved = pyqtSignal(dict)  # Signal emitted when record saved/deleted
    
    def __init__(self, db, sample_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.sample_id = sample_id
        self.sample_data = {}
        
        self.setWindowTitle(f"Sample Detail - {sample_id or 'New'}")
        self.setGeometry(50, 50, 1400, 900)
        
        layout = QVBoxLayout()
        
        # ===== TOP BUTTONS (STANDARD LAYOUT) =====
        button_layout = QHBoxLayout()
        
        # Left: Action-specific buttons
        self.custom_btn = QPushButton("🔧 Custom Action")
        self.custom_btn.clicked.connect(self.custom_action)
        button_layout.addWidget(self.custom_btn)
        
        button_layout.addStretch()
        
        # Right: Standard buttons
        self.add_new_btn = QPushButton("➕ Add New")
        self.add_new_btn.clicked.connect(self.add_new_sample)
        button_layout.addWidget(self.add_new_btn)
        
        self.duplicate_btn = QPushButton("📋 Duplicate")
        self.duplicate_btn.clicked.connect(self.duplicate_sample)
        button_layout.addWidget(self.duplicate_btn)
        
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self.delete_sample)
        button_layout.addWidget(self.delete_btn)
        
        self.save_btn = QPushButton("💾 Save Changes")
        self.save_btn.clicked.connect(self.save_sample)
        button_layout.addWidget(self.save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # ===== CONTENT (Tabs, Forms, etc.) =====
        tabs = QTabWidget()
        tabs.addTab(self.create_tab1(), "📋 Tab 1")
        # ... add more tabs ...
        layout.addWidget(tabs)
        
        self.setLayout(layout)
        
        # Load data if sample_id provided
        if sample_id:
            self.load_sample_data()
    
    def load_sample_data(self):
        """Load record from database and populate UI"""
        try:
            cur = self.db.get_cursor()
            cur.execute("SELECT * FROM samples WHERE sample_id = %s", (self.sample_id,))
            row = cur.fetchone()
            if row:
                self.sample_data = {... populate from row ...}
                # Populate form fields
                self.field1.setText(...)
            cur.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load: {e}")
    
    def save_sample(self):
        """Save record changes to database"""
        try:
            cur = self.db.get_cursor()
            cur.execute("""
                UPDATE samples SET
                    field1 = %s,
                    field2 = %s
                WHERE sample_id = %s
            """, (self.field1.text(), self.field2.text(), self.sample_id))
            self.db.conn.commit()
            QMessageBox.information(self, "Success", "Record saved")
            self.saved.emit({"action": "save", "sample_id": self.sample_id})
            cur.close()
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
    
    def add_new_sample(self):
        """Create new record"""
        reply = QMessageBox.question(self, "Add New", "Create new record?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            new_dialog = SampleDetailDialog(self.db, sample_id=None, parent=self.parent())
            new_dialog.saved.connect(self.on_sample_saved)
            new_dialog.exec()
    
    def duplicate_sample(self):
        """Duplicate record with modified identifier"""
        if not self.sample_id:
            QMessageBox.warning(self, "Warning", "No record loaded to duplicate.")
            return
        
        # Show dialog to get new identifier
        dialog = QDialog(self)
        # ... build dialog to prompt for new identifier ...
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_identifier = dialog.identifier_input.text()
            
            # Insert duplicate
            cur = self.db.get_cursor()
            cur.execute("""
                INSERT INTO samples (field1, field2, ...)
                VALUES (%s, %s, ...)
            """, (...))
            self.db.conn.commit()
            QMessageBox.information(self, "Success", "Record duplicated")
            cur.close()
            self.load_sample_data()
    
    def delete_sample(self):
        """Delete record"""
        if not self.sample_id:
            QMessageBox.warning(self, "Warning", "No record to delete.")
            return
        
        reply = QMessageBox.question(self, "Confirm", f"Delete this record? Cannot undo.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cur = self.db.get_cursor()
                cur.execute("DELETE FROM samples WHERE sample_id = %s", (self.sample_id,))
                self.db.conn.commit()
                QMessageBox.information(self, "Success", "Record deleted")
                self.saved.emit({"action": "delete", "sample_id": self.sample_id})
                cur.close()
                self.close()
            except Exception as e:
                self.db.conn.rollback()
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
    
    def on_sample_saved(self, data):
        """Handle child dialog save - refresh current view"""
        if self.sample_id:
            self.load_sample_data()
    
    def create_tab1(self):
        """Create first tab content"""
        widget = QWidget()
        layout = QVBoxLayout()
        # ... build tab content ...
        widget.setLayout(layout)
        return widget
```

## List Widget Pattern

Parent list widgets should:

1. Create detail dialog on double-click:
```python
def on_double_clicked(self, index):
    if index.isValid():
        record_id = self.table.item(index.row(), 0).text()  # Get ID from first column
        dialog = DetailDialog(self.db, record_id=record_id, parent=self)
        dialog.saved.connect(self.refresh_data)  # Refresh on save
        dialog.exec()
```

2. Refresh list after dialog closes:
```python
def refresh_data(self, data=None):
    """Reload list from database"""
    try:
        cur = self.db.get_cursor()
        cur.execute("SELECT * FROM [table] ORDER BY [id]")
        rows = cur.fetchall()
        self.table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            # Populate table cells ...
        cur.close()
    except Exception as e:
        QMessageBox.critical(self, "Error", f"Failed to refresh: {e}")
```

## Implemented Modules

### ✅ Completed
- **ClientDetailDialog** (`client_drill_down.py`) - All buttons, all methods
- **EmployeeDetailDialog** (`employee_drill_down.py`) - All buttons, all methods
- **VehicleDetailDialog** (`vehicle_drill_down.py`) - All buttons, all methods
- **CharterDetailDialog** (`drill_down_widgets.py`) - All buttons, all methods

### ⏳ To Be Implemented
- **QuoteDetailDialog** (`drill_down_widgets.py` or `quotes_drill_down.py`)
- **ReceiptDetailDialog** (`drill_down_widgets.py` or `receipt_drill_down.py`)

## Testing Checklist

### Per Module (Client, Employee, Vehicle, Charter):

- [ ] **Double-Click Navigation**
  - [ ] List shows records
  - [ ] Double-click row opens detail dialog
  - [ ] Dialog displays correct record data
  - [ ] Modal blocks parent until closed

- [ ] **Add New Record**
  - [ ] Click [➕ Add New] → confirmation dialog
  - [ ] Click "Yes" → new empty dialog opens
  - [ ] Fill fields → click [Save]
  - [ ] New record appears in parent list
  - [ ] Database contains new record

- [ ] **Duplicate Record**
  - [ ] Click [📋 Duplicate] → identifier dialog
  - [ ] Modify identifier → click "Duplicate"
  - [ ] New record appears in parent list with new identifier
  - [ ] All other fields copied from original
  - [ ] Original record unchanged

- [ ] **Delete Record**
  - [ ] Click [🗑️ Delete] → confirmation
  - [ ] Click "Yes" → record deleted from database
  - [ ] Dialog closes
  - [ ] Record removed from parent list

- [ ] **Save Changes**
  - [ ] Modify field → click [Save]
  - [ ] Success message shown
  - [ ] Dialog remains open (can edit more)
  - [ ] Parent list refreshes with changes

- [ ] **Close Button**
  - [ ] Click [Close] → dialog closes
  - [ ] Returns to parent list
  - [ ] Unsaved changes discarded (warning shown first)

- [ ] **Action-Specific Buttons**
  - [ ] (Client) Suspend/Activate work
  - [ ] (Employee) Terminate/Suspend work
  - [ ] (Vehicle) Retire/Sell work
  - [ ] (Charter) Lock/Unlock/Cancel work

## UI Consistency

- All dialogs have **consistent button layout**
- All dialogs have **consistent dialog size** (1400x900)
- All dialogs have **consistent styling** (same fonts, colors)
- All dialogs use **same signal pattern** (saved signal with dict)
- All **action buttons on left**, **standard buttons on right**
- **Modal behavior** - dialog blocks parent until closed
- **Smooth workflow** - add/duplicate/delete with confirmations

## Notes

- Use `pyqtSignal(dict)` to emit saved state with record data
- Always use `.connect()` to link saved signal to parent refresh
- Always show confirmation dialogs for delete/add operations
- Always call `self.db.conn.commit()` after modifications
- Always call `cur.close()` after database operations
- Always wrap DB operations in try/except blocks
- Use UTF-8 encoding when running Python with `-X utf8` flag
