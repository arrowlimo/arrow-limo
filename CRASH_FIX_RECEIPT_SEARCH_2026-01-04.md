# Receipt Search & Match Crash Fix

**Date:** January 4, 2026  
**Issue:** Desktop app crashes when clicking "Clear" button after adding a receipt

## Root Cause

The `_clear_filters()` method was incomplete and missing several widget resets:

1. **Missing `date_from` and `date_to` reset** - Date range widgets were not being reset to default values
2. **Missing enabled state reset** - Date and amount widgets' enabled states were not being reset to `False`
3. **Missing `amount_tolerance` reset** - Tolerance value was not being reset
4. **Missing `date_7days` button reset** - Quick date button state was not being reset
5. **No exception handling** - Any error in clearing would crash the entire widget

## Technical Details

When a receipt is added via the "Add New Receipt" form:
1. The code commits the receipt to the database
2. It manually clears some filter widgets (vendor, date checkbox, amount checkbox)
3. It sets the vendor filter to show the newly added receipt
4. It calls `_do_search()` to refresh results

However, when the user then clicks "Clear":
- The old `_clear_filters()` only reset 5 widgets out of 15
- If `use_date_filter` was checked earlier, `_do_search()` would try to read `date_from.date()` and `date_to.date()`
- But these widgets might be in an inconsistent state (disabled but with old values)
- This could cause a crash or incorrect SQL query

## Fix Applied

Updated `_clear_filters()` method in `receipt_search_match_widget.py`:

```python
def _clear_filters(self):
    """Reset all filters"""
    try:
        self.vendor_input.clear()
        self.use_date_filter.setChecked(False)
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_to.setDate(QDate.currentDate())
        self.date_from.setEnabled(False)
        self.date_to.setEnabled(False)
        self.date_7days.setEnabled(False)
        self.year_combo.setCurrentIndex(0)
        self.month_combo.setCurrentIndex(0)
        self.use_amount_filter.setChecked(False)
        self.amount_spin.setValue(0)
        self.amount_spin.setEnabled(False)
        self.amount_tolerance.setValue(0.01)
        self.amount_tolerance.setEnabled(False)
        self.results_table.setRowCount(0)
        self.results_label.setText("")
        self.detail_text.clear()
    except Exception as e:
        print(f"Error in _clear_filters: {e}")
        import traceback
        traceback.print_exc()
```

### Changes Made:
1. ✅ Reset `date_from` to default (-7 days)
2. ✅ Reset `date_to` to current date
3. ✅ Disable `date_from`, `date_to`, `date_7days`
4. ✅ Reset `amount_spin` to 0 and disable
5. ✅ Reset `amount_tolerance` to 0.01 and disable
6. ✅ Added try/except for error handling and debugging

## Testing Checklist

- [ ] Launch desktop app: `python -X utf8 desktop_app/main.py`
- [ ] Navigate to "Receipt Search & Match" widget
- [ ] Add a new receipt (any vendor, any amount)
- [ ] Verify receipt appears in search results
- [ ] Click "Clear" button
- [ ] Verify no crash occurs
- [ ] Verify all filters are cleared:
  - Vendor input is empty
  - Date filter checkbox is unchecked
  - Date widgets are disabled
  - Amount filter checkbox is unchecked
  - Amount widgets are disabled
  - Results table is empty
- [ ] Test with date filter enabled before clearing
- [ ] Test with amount filter enabled before clearing

## Files Modified

- `desktop_app/receipt_search_match_widget.py` (lines 899-922)

## Status

**FIXED** - Ready for testing
