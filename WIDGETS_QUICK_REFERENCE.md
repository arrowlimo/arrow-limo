# Quick Reference: New Management Widgets

## Files Created

| File | Purpose | Lines | Status |
|------|---------|-------|--------|
| [desktop_app/manage_receipts_widget.py](desktop_app/manage_receipts_widget.py) | Receipt management interface | 180 | ✅ Ready |
| [desktop_app/manage_banking_widget.py](desktop_app/manage_banking_widget.py) | Banking transaction browser | 200 | ✅ Ready |
| [desktop_app/manage_cash_box_widget.py](desktop_app/manage_cash_box_widget.py) | Cash box tracking | 180 | ✅ Ready |
| [desktop_app/manage_personal_expenses_widget.py](desktop_app/manage_personal_expenses_widget.py) | Personal expense management | 220 | ✅ Ready |
| [scripts/optimize_schema_analysis.py](scripts/optimize_schema_analysis.py) | Schema analysis tool | 120 | ✅ Ready |
| [scripts/drop_empty_columns.py](scripts/drop_empty_columns.py) | Column cleanup script | 100 | ✅ Ready |

## To Integrate into App

Edit **desktop_app/main.py**:

```python
# 1. Add imports at top
from desktop_app.manage_receipts_widget import ManageReceiptsWidget
from desktop_app.manage_banking_widget import ManageBankingWidget
from desktop_app.manage_cash_box_widget import ManageCashBoxWidget
from desktop_app.manage_personal_expenses_widget import ManagePersonalExpensesWidget

# 2. In your build_tabs() method, add these lines:
self.manage_receipts = ManageReceiptsWidget(self.conn)
self.tabs.addTab(self.manage_receipts, "📋 Manage Receipts")

self.manage_banking = ManageBankingWidget(self.conn)
self.tabs.addTab(self.manage_banking, "🏦 Manage Banking")

self.manage_cash_box = ManageCashBoxWidget(self.conn)
self.tabs.addTab(self.manage_cash_box, "💰 Manage Cash Box")

self.manage_expenses = ManagePersonalExpensesWidget(self.conn)
self.tabs.addTab(self.manage_expenses, "👤 Manage Personal Expenses")
```

## Data Sources

### Receipts Table
- **Records:** 33,983
- **Key fields:** receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, gl_account_code
- **Filter support:** Vendor (text), Date (range), GL (text), Amount (range)
- **Matched indicator:** banking_transaction_id non-null

### Banking Transactions Table
- **Key fields:** transaction_id, transaction_date, description, debit, credit, balance
- **Linked to:** receipts via banking_transaction_id
- **Filter support:** Account (dropdown), Date (range), Description (text), Amount (range)

### Cash Box Transactions Table
- **Structure:** id, transaction_date, type (Deposit/Withdrawal), amount, description
- **Calculation:** Running balance via window function
- **Filter support:** Type (dropdown), Date (range), Description (text), Amount (range)

### Personal Expenses Table
- **Key fields:** id, expense_date, employee_id, category, amount, status, description, notes
- **Related:** employees table (employee_id → first_name, last_name)
- **Filter support:** Employee (dropdown), Category (dropdown), Date (range), Status (dropdown), Amount (range)

## Schema Optimization Status

### Ready to Drop (22 columns, 0% data):
```sql
-- These are completely safe to remove
event_batch_id, reviewed, exported, date_added, tax, tip, type, 
classification, pay_account, mapped_expense_account_id, mapping_status, 
mapping_notes, reimbursed_via, reimbursement_date, cash_box_transaction_id, 
parent_receipt_id, amount_usd, fx_rate, due_date, period_start, 
period_end, verified_by_user

-- To drop all:
python scripts/drop_empty_columns.py
```

### Keep (56 columns):
- All 48 heavily-used columns (>20%)
- All 23 sparse columns (1-20%) with business value
- Total: 56 columns after cleanup

## Quick Start Commands

```bash
# 1. Analyze schema
python scripts/optimize_schema_analysis.py

# 2. Backup database
pg_dump -h localhost -U postgres -d almsdata -F c \
  -f almsdata_backup_BEFORE_DROP.dump

# 3. Drop empty columns (requires confirmation)
python scripts/drop_empty_columns.py

# 4. Verify integrity
psql -h localhost -U postgres -d almsdata \
  -c "SELECT COUNT(*) FROM receipts;"

# 5. Reindex for optimization (optional)
psql -h localhost -U postgres -d almsdata \
  -c "REINDEX TABLE receipts; ANALYZE receipts;"
```

## Widget Features Summary

| Feature | Receipts | Banking | Cash Box | Expenses |
|---------|----------|---------|----------|----------|
| Show All | ✓ | ✓ | ✓ | ✓ |
| Filter | ✓ | ✓ | ✓ | ✓ |
| Multi-Column Sort | ✓ | ✓ | ✓ | ✓ |
| Color Coding | ✓ | ✓ | ✓ | ✓ |
| Pagination | Limit 500 | Limit 500 | Limit 500 | Limit 500 |
| Export | — | — | — | — |
| Bulk Edit | — | — | — | — |

## Testing Checklist

```
Manage Receipts:
  [ ] Loads all 33,983 records (or first 500)
  [ ] Vendor filter works (partial match)
  [ ] Date range filter works
  [ ] GL account filter works
  [ ] Amount range works
  [ ] Matched status shows green when banking_transaction_id set

Manage Banking:
  [ ] Account dropdown populates
  [ ] Shows linked receipt count
  [ ] Unmatched transactions show count = 0
  [ ] Debit/credit amounts right-aligned
  [ ] Date filter works

Manage Cash Box:
  [ ] Deposit type shows green background
  [ ] Withdrawal type shows red background
  [ ] Running balance calculates correctly
  [ ] Transaction type filter works

Manage Personal Expenses:
  [ ] Employee dropdown populates
  [ ] Status color-codes correctly
  [ ] Category dropdown loads
  [ ] Amount range filter works
  [ ] Shows pending and reimbursed counts
```

## Common Customizations

### Change result limit:
```python
sql.append("ORDER BY ... LIMIT 1000")  # Change from 500
```

### Add new filter:
```python
filter_layout.addWidget(QLabel("New Filter:"))
self.new_filter = QLineEdit()
filter_layout.addWidget(self.new_filter)

# In _load_receipts():
if self.new_filter.text():
    sql.append("AND column_name = %s")
    params.append(self.new_filter.text())
```

### Change column display:
```python
self.table.setHorizontalHeaderLabels([
    "ID", "Date", "Vendor", "Amount",  # Your columns
    "New Column", "Another Column"
])

# Update _populate_table() to use row[4], row[5], etc.
```

### Add export button:
```python
export_btn = QPushButton("📊 Export CSV")
export_btn.clicked.connect(self._export_csv)
filter_layout.addWidget(export_btn)

def _export_csv(self):
    # Implement CSV export
    pass
```

## Performance Tips

1. **For large result sets:** Reduce limit or add pagination
2. **For slow filters:** Add database indexes on filtered columns
3. **For memory issues:** Enable lazy loading with QAbstractTableModel
4. **For query performance:** Use EXPLAIN to analyze SQL

## Architecture Notes

- All widgets inherit from `QWidget`
- Use `psycopg2` for database access
- StandardDateEdit handles date filtering with blank support
- QTableWidget with alternating row colors for readability
- Color coding for status visualization
- Monetary values right-aligned for easy scanning

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No data showing | Check database connection, verify table exists |
| Filter not working | Verify SQL parameter binding in `_load_*()` |
| Widgets won't import | Check file paths and Python import statements |
| Table shows empty | Check results_label.setText() was called |
| Numbers not aligned | Use `QTableWidgetItem.setTextAlignment()` |
| Colors not showing | Verify `QColor()` is imported and `setBackground()` used |

## Next Steps

1. ✅ **Create management widgets** - DONE
2. ✅ **Analyze schema** - DONE
3. ⬜ **Integrate widgets into main.py**
4. ⬜ **Test all 4 widgets**
5. ⬜ **Deploy to production**
6. ⬜ **Monitor for 1 week**
7. ⬜ **Run drop_empty_columns.py**
8. ⬜ **Reindex database**

---

**Created:** December 23, 2025  
**Status:** All 4 widgets + analysis tools complete and ready to integrate
