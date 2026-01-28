# UI Standards - Quick Reference Card

## 📋 Import This
```python
from desktop_app.ui_standards import (
    setup_standard_table,      # Auto-size table columns
    SmartFormField,             # Create properly-sized fields
    enable_fuzzy_search,        # Add autocomplete to fields
    make_read_only_table,       # Exclude table from tab order
    TabOrderManager             # Set explicit tab order
)
```

## 📊 Tables - Before/After

### Before (15 lines)
```python
self.table = QTableWidget()
self.table.setColumnCount(4)
self.table.setHorizontalHeaderLabels(["Date", "Client", "Amount", "Status"])
header = self.table.horizontalHeader()
header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
self.table.setColumnWidth(0, 100)
header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
self.table.setColumnWidth(2, 110)
header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
self.table.setColumnWidth(3, 90)
self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
```

### After (3 lines) ✅
```python
self.table = QTableWidget()
setup_standard_table(self.table, ["Date", "Client", "Amount", "Status"])
make_read_only_table(self.table)
```

## 📝 Form Fields - Cheat Sheet

```python
# Date field (150px, calendar popup)
self.date = SmartFormField.date_edit()

# Time field (100px, 12-hour format)
self.time = SmartFormField.time_edit()

# Phone field (150px, format hint)
self.phone = SmartFormField.phone_field()

# Email field (250px, placeholder)
self.email = SmartFormField.email_field()

# Postal code (120px, T2P 1J9 format)
self.postal = SmartFormField.postal_code_field()

# Currency (150px, $ prefix, 2 decimals)
self.amount = SmartFormField.amount_field()

# Short text (200px, max 50 chars)
self.name = SmartFormField.short_text_field()

# Medium text (300px, max 100 chars)
self.description = SmartFormField.medium_text_field()

# Long text (400px, max 200 chars)
self.title = SmartFormField.long_text_field()

# Auto-expanding notes (60-300px, grows with content)
self.notes = SmartFormField.auto_expanding_text(max_height=300)
```

## 🔍 Fuzzy Search - 1 Line

```python
# Enable autocomplete on any QLineEdit
enable_fuzzy_search(self.client_search, ["Client A", "Client B", "Client C"])
```

## 🎯 Tab Order - Skip Read-Only Tables

```python
# Mark table as read-only (also excludes from tab order)
make_read_only_table(self.results_table)

# Or manually set tab order
TabOrderManager.set_tab_order(self, [
    self.field1,
    self.field2,
    self.field3,
    # ... (skip self.results_table)
])
```

## 📏 Column Width Reference

| Type | Width | Example |
|------|-------|---------|
| Date | 100px | 01/23/2026 |
| DateTime | 140px | 01/23/2026 10:30 PM |
| Time | 80px | 10:30 AM |
| Amount | 110px | $12,345.67 |
| Reserve # | 90px | 025123 |
| ID | 60-70px | 1234 |
| Status | 90px | Active |
| Phone | 120px | (403) 555-1234 |
| Email | 200px | email@example.com |
| Name | 150px | John Smith |
| Address | 250px | 123 Main St |
| Notes | Stretch | (fills remaining space) |

## ⚡ Auto-Applier - Bulk Update

```powershell
cd L:\limo
python apply_ui_standards.py
```

This will:
- ✅ Add ui_standards imports
- ✅ Convert tables to smart tables
- ✅ Replace phone/email/postal fields
- ✅ Convert notes to auto-expanding
- ✅ Create .bak backup files
- ✅ Generate detailed report

## 🎨 Visual Improvements

### Space Optimization
- Date fields: 400px → 100px (saves 300px)
- Empty notes: 100px → 60px (saves 40px when empty)
- Full notes: 100px → 300px (grows when needed)

### Tab Navigation
- Before: Tab through 30+ controls (including read-only)
- After: Tab through ~15 editable controls
- Result: 50% faster form navigation

### User Experience
- ✅ Fuzzy search finds "joh" → "John Smith"
- ✅ Date accepts "1/23/26" or "Jan 23 2026"
- ✅ Notes expand automatically (no scrolling until 300px)
- ✅ Tab key skips all result tables

## 📦 Files

| File | Purpose |
|------|---------|
| `ui_standards.py` | Core library (480 lines) |
| `apply_ui_standards.py` | Auto-applier script |
| `UI_CLEANUP_COMPLETE_GUIDE.md` | Full documentation |
| `UI_STANDARDS_QUICK_REFERENCE.md` | This file |

## ✅ Already Updated

- [x] client_drill_down.py (35+ changes)
  - 4 tables converted
  - 6 form fields converted
  - Read-only tables excluded from tab order

## 🔜 Next Steps

Apply to remaining widgets:
- [ ] enhanced_charter_widget.py
- [ ] enhanced_employee_widget.py
- [ ] vehicle_management_widget.py
- [ ] dispatch_management_widget.py
- [ ] All dashboard widgets (phases 4-13)

---

**Quick Start**: Copy/paste the import and use SmartFormField for all new forms!
