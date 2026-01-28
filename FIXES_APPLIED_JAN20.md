# Fixes Applied - January 20, 2026

## Issue 1: Split Manager Dialog Error
**Problem**: When clicking "Manage Splits", dialog crashed with parent widget error

**Root Cause**: `SplitReceiptManagerDialog` initialization wasn't passing `receipt_data` parameter

**Fix Applied**:
- Updated `SplitReceiptManagerDialog.__init__()` to accept optional `receipt_data` parameter
- Added error handling and try/except blocks for initialization
- Pass `parent=self` when creating dialog for proper Qt parent-child relationship
- Added traceback printing for debugging

**File Changed**: `desktop_app/split_receipt_manager_dialog.py`

---

## Issue 2: No Delete Button in Results Window
**Problem**: Users couldn't delete duplicate/split error receipts from the results table

**Fix Applied**:
- Added **"🗑️ Delete Selected"** button above the results table
- Implemented `_delete_selected_receipts()` method with:
  - Selection detection from table rows
  - Confirmation dialog showing receipt IDs to be deleted
  - Database cleanup (deletes receipt + any associated splits)
  - Auto-refresh of results after deletion

**File Changed**: `desktop_app/receipt_search_match_widget.py`

**New Method**: `_delete_selected_receipts()`

---

## How to Use

### To Split a Receipt:
1. Search for receipt (e.g., #140678)
2. **Click the row** in results table to select it
3. Click **"Manage Splits"** button
4. Add split allocations (GL codes + amounts)
5. Click **"✅ Save All & Reconcile"**

### To Delete a Duplicate Receipt:
1. Search for receipt in results table
2. **Click the row** to select it
3. Click **"🗑️ Delete Selected"** button
4. Confirm deletion in dialog
5. Receipt is deleted and table refreshes

---

## Testing Checklist

- [ ] Open Accounting & Finance → Receipts & Invoices
- [ ] Search for a receipt
- [ ] Click a result row
- [ ] Verify "Manage Splits" button works (no errors)
- [ ] Close split manager
- [ ] Click another result row
- [ ] Click "🗑️ Delete Selected" button
- [ ] Confirm deletion works and table refreshes

---

## Rollback Plan
If issues occur, revert these files:
```bash
git checkout desktop_app/split_receipt_manager_dialog.py
git checkout desktop_app/receipt_search_match_widget.py
```

---

**Status**: Ready to test
**Tested By**: [User testing]
**Date Applied**: 2026-01-20 12:27 PM
