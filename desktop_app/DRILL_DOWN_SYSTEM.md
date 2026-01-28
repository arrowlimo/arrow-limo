# Drill-Down Dashboard System

## Overview

The drill-down system enables users to view list data and **double-click to open detailed master-detail views** with edit, lock, cancel, and sub-item drilling capabilities.

## Features

### 1. **Master-Detail Views**
Each charter opens in a dialog showing 4 tabs:
- **Tab 1: Charter Details** - Main charter info, editable fields
- **Tab 2: Orders & Beverages** - Related beverage orders with add/edit/delete
- **Tab 3: Routing & Charges** - Stop-by-stop routing with charge breakdown
- **Tab 4: Payments** - Complete payment history and reconciliation

### 2. **List View with Filtering**
```
Charter Management Dashboard shows:
- Reserve # | Client | Date | Driver | Vehicle | Status | Total Due | Balance Due

With inline filters:
- Reserve # filter (text search)
- Min Balance Due filter (numeric)
- Status filter (dropdown)
```

### 3. **Actions Available**
- **Lock Charter** - Prevents further edits
- **Unlock Charter** - Re-enables edits
- **Cancel Charter** - Marks as cancelled (with confirmation)
- **Save Changes** - Commits edits to database
- **Add/Edit/Delete Orders** - Manage beverage orders
- **Record Payments** - Record already-received payments (manual ledger)

## Implementation

### Files Created

1. **drill_down_widgets.py**
   - `CharterDetailDialog` - Main detail view dialog
   - Handles all master and detail data loading
   - Supports edit, lock, unlock, cancel operations

2. **table_mixins.py**
   - `DrillDownTableMixin` - Add drill-down to any table
   - `FilterableTableMixin` - Add filtering capability

3. **enhanced_charter_widget.py**
   - `EnhancedCharterListWidget` - Complete charter list with drill-down
   - Example of applying mixins to real widgets
   - Full filtering and action buttons

### How to Add Drill-Down to Existing Dashboards

**Step 1:** Import the mixin
```python
from table_mixins import DrillDownTableMixin

class MyDashboard(QWidget, DrillDownTableMixin):
    def __init__(self, db):
        super().__init__()
        self.db = db
        # ... rest of init
```

**Step 2:** Enable drill-down on your table
```python
def load_data(self):
    # Load your data...
    self.table.setRowCount(len(rows))
    
    # Enable double-click detail view
    self.enable_drill_down(self.table, key_column=0)
    # key_column=0 means the first column contains the business key
```

**Step 3:** User double-clicks a row → CharterDetailDialog opens automatically

## Data Structure Expected

### Charter Table
```sql
charters (
    charter_id, reserve_number (KEY), charter_date,
    client_id, pickup_location, destination, pickup_time,
    passenger_count, employee_id, vehicle_id,
    charter_status, total_amount_due, is_locked, notes, ...
)
```

### Related Tables
```sql
payments (reserve_number, amount, payment_date, payment_method, ...)
charter_orders (reserve_number, item_name, quantity, unit_price, ...)
clients (client_id, company_name, client_name, ...)
employees (employee_id, full_name, is_chauffeur, ...)
vehicles (vehicle_id, vehicle_number, license_plate, ...)
```

## User Workflow Example

### Scenario: "Show all charters with over $100 balance, then select one to edit"

1. **Open Enhanced Charter Widget** → Shows full charter list
2. **Set Balance Filter** to $100 minimum → Only charters with >$100 balance shown
3. **Double-click a charter** → Opens CharterDetailDialog with 4 tabs
4. **In Detail View:**
   - View/edit pickup location, destination, notes
   - View all beverage orders placed
   - See stop-by-stop routing with charges
   - Review complete payment history
5. **Actions:**
   - Edit any field → Click "Save Changes"
   - Lock to prevent changes → Click "Lock Charter"
    - Record payment → Click "Record Payment" (Tab 4)
   - Cancel entire charter → Click "Cancel Charter"
   - Unlock for edits → Click "Unlock Charter"

## Custom Detail Views

For non-charter dashboards, pass a custom callback:

```python
def enable_custom_drill_down(self):
    self.enable_drill_down(
        self.table,
        key_column=0,
        detail_callback=self.open_custom_detail
    )

def open_custom_detail(self, key_value):
    # Custom logic for your specific widget
    dialog = MyCustomDetailDialog(self.db, key_value, self)
    dialog.exec()
```

## Database Requirements

All dashboards using drill-down must:
1. Have a unique business key in column 0 (reserve_number, employee_id, vehicle_id, etc.)
2. Define the related data queries in the detail widget
3. Implement save/lock/unlock/cancel methods if needed

## Future Enhancements

- [ ] Print charter detail view
- [ ] Export to PDF
- [ ] Email charter details
- [ ] Batch operations (lock multiple charters)
- [ ] Audit trail (track all changes)
- [ ] Custom field validation
- [ ] Real-time data sync
- [ ] Mobile app sync

## Testing Checklist

- [ ] Double-click opens detail dialog
- [ ] All 4 tabs load data correctly
- [ ] Edit charter details and save
- [ ] Lock/unlock toggles correctly
- [ ] Cancel shows confirmation
- [ ] Add/edit/delete orders work
- [ ] Add payment updates balance
- [ ] Filter by reserve # works
- [ ] Filter by balance due works
- [ ] Filter by status works
- [ ] Refresh reloads all data
