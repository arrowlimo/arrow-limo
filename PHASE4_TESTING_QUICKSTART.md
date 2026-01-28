# Phase 4 Testing Quick Start

## What Was Just Completed

✅ **Phase 3 Integration Complete** (Dec 23, 10:45 PM)

Three components now fully integrated and working together:
1. Receipt Search & Match Widget → Button added
2. Split Receipt Manager Dialog → Banking picker hooked up
3. Banking Transaction Picker Dialog → Ready to use

All code compiles without syntax errors.

---

## How to Test (Next Session)

### Step 1: Start the Desktop App
```powershell
cd l:\limo
python -X utf8 desktop_app/main.py
```

### Step 2: Navigate to Receipts Tab
- Click "Receipts" in left navigation
- Receipt search widget should load

### Step 3: Find a Test Receipt
- Search for any receipt (e.g., by date range)
- Click on a result to load it in the form

### Step 4: Test "Manage Split Receipts" Button
- Look for "🔀 Manage Split Receipts" button in form
- Button should be **enabled** (if RECEIPT_WIDGET_WRITE_ENABLED=true)
- Click it → Should open SplitReceiptManagerDialog

### Step 5: Test Banking Picker (Main Feature)
- In Split Manager dialog, go to "Bank Match" tab
- Click "🔗 Link Banking Transaction"
- BankingTransactionPickerDialog should open
- Should show unmatched banking transactions from last 3 months
- Select a transaction → Click "✅ Link"
- Transaction should appear in banking tab table
- Unlink button should remove it

### Step 6: Test GL Splits
- In Split Manager dialog, go to "GL Splits" tab
- Add a GL split with amount
- Amount should turn green if it matches receipt total
- Save the split

### Step 7: Test Cash Box
- In "Cash Box" tab, enter amount and select driver
- Choose float type (float_out, reimbursed, cash_received, other)
- Save

### Step 8: Save Everything
- Click "✅ Save All & Reconcile" button
- Should show success message
- Receipt form should refresh
- Check database: receipt_splits, receipt_banking_links, audit_log should have new rows

---

## What to Look For

### ✅ Success Indicators
- "🔀 Manage Split Receipts" button appears and is clickable
- Dialog opens without crashes
- Banking picker shows transactions
- Transactions can be linked/unlinked
- Amounts are validated (green when correct, red when wrong)
- Save creates database records
- Audit log has entries

### ❌ Problem Indicators
- Button missing or disabled (need RECEIPT_WIDGET_WRITE_ENABLED=true)
- Dialog crashes on open (syntax error or DB issue)
- Banking picker shows no transactions (DB connection issue)
- Amount validation always red (logic error)
- Save fails (DB constraint error)

---

## Environment Setup for Testing

### Enable Write Mode
```powershell
# PowerShell - temporary for this session
$env:RECEIPT_WIDGET_WRITE_ENABLED = "true"

# Then start app
python -X utf8 desktop_app/main.py
```

### Or Update .env File
```
RECEIPT_WIDGET_WRITE_ENABLED=true
DB_HOST=localhost
DB_NAME=almsdata
DB_USER=postgres
DB_PASSWORD=***REMOVED***
```

---

## Database Verification (After Testing)

### Check if splits were saved:
```powershell
psql -h localhost -U postgres -d almsdata

# Inside psql:
SELECT * FROM receipt_splits WHERE receipt_id = <test_receipt_id>;
SELECT * FROM receipt_banking_links WHERE receipt_id = <test_receipt_id>;
SELECT * FROM audit_log WHERE entity_id = <test_receipt_id> ORDER BY changed_at DESC;
```

### Expected Results:
- `receipt_splits` should have 1+ rows with GL codes and amounts
- `receipt_banking_links` should have transaction links
- `audit_log` should have entries for all changes
- All amounts should sum correctly

---

## Troubleshooting

### If Button Missing
- Check: Is RECEIPT_WIDGET_WRITE_ENABLED set to "true"?
- Check: Did receipt_search_match_widget.py import correctly?
- Run: `python -m py_compile desktop_app/receipt_search_match_widget.py`

### If Dialog Crashes
- Check: Are both dialog files in desktop_app/?
- Check: Do they compile? `python -m py_compile split_receipt_manager_dialog.py banking_transaction_picker_dialog.py`
- Check: Is database connection working? (test with psql)

### If Banking Picker Shows No Transactions
- Check: Are there unmatched banking transactions in the database?
  ```sql
  SELECT COUNT(*) FROM banking_transactions WHERE receipt_id IS NULL AND reconciliation_status IS NULL;
  ```
- Check: Is date range filter too narrow? (default: last 3 months)

### If Save Fails
- Check: Do receipt_splits sum to receipt total?
- Check: Are GL codes valid?
- Check: Check database error in terminal output
- Check: `receipt_banking_links` may need banking_transactions.receipt_id update

---

## Files Modified This Session

1. **l:\limo\desktop_app\receipt_search_match_widget.py**
   - Added imports for split manager + banking picker
   - Added "🔀 Manage Split Receipts" button
   - Added `_open_split_manager()` method

2. **l:\limo\desktop_app\split_receipt_manager_dialog.py**
   - Added import for banking picker
   - Implemented `_link_banking()` method (was stub)
   - Added `_unlink_banking_transaction()` method

3. **l:\limo\desktop_app\banking_transaction_picker_dialog.py**
   - Already complete, no changes this session

---

## Success Metrics (Phase 4)

**Minimum Success:**
- [ ] Button appears and launches dialog
- [ ] Dialog shows without crashes
- [ ] Banking picker works (shows + links transactions)
- [ ] Save creates database records

**Full Success:**
- [ ] All 8 test steps complete without errors
- [ ] Database records match expectations
- [ ] Audit log shows all changes
- [ ] Multiple receipts can be split simultaneously
- [ ] Unlink + relink works correctly

---

## Next Steps After Testing

1. If all tests pass → Move to Phase 4.2 (Reporting)
2. If issues found → Debug + re-test
3. If DB errors → Check schema (migration may have failed)
4. If UI errors → Check Python syntax again

---

**Ready to test!** Start with Step 1 in your next session. 🚀
