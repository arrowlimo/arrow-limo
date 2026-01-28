# Split Receipt UI - Quick Testing Guide

**Date:** January 17, 2026
**Status:** Ready to test
**All components compile:** ✅ YES

---

## Quick Start

### Step 1: Launch App
```powershell
cd L:\limo
python -X utf8 "L:\limo\desktop_app\main.py"
```

### Step 2: Enable Write Mode (if needed)
```powershell
$env:RECEIPT_WIDGET_WRITE_ENABLED = "true"
```

### Step 3: Navigate to Receipts Tab
- Click "Receipts" in left navigation
- Receipt search widget loads

---

## 3 New Features to Test

### Feature 1: Split Detection & Display ✂️
**What to look for:**
1. Find a receipt that has linked parts (e.g., split into 2-3 parts)
2. Load the receipt in the form
3. **Expected:** Red banner appears saying "📦 Split into X receipt(s)"
4. **Expected:** Side-by-side detail panels show below search table
   - 2 panels (one for each part) or 3 panels (if 3-part split)
   - If cash portion exists, extra 💰 panel appears
5. Each panel shows: Receipt ID, Date, Vendor, Amount (editable), Payment, GL, Status
6. Buttons available: [👁️ View Details] [🔽 Collapse] [❌ Remove Cash]

**Test Case:**
```
Find receipt #12345 (must be already split in database)
Load it
Verify banner + panels appear
Click [👁️ View Split Details] → dialog shows summary
Click [Open] on linked receipt → that receipt loads
Click [Collapse] → panels hide
```

### Feature 2: Create Split (2-3 parts with auto-fill) ✂️
**What to look for:**
1. Find a single receipt (NOT split) with amount ≥ $1000
2. Click [✂️ Create Split] button
3. **Expected:** Side-by-side creation dialog opens
4. **Expected:** Two panels appear side-by-side (Part 1 & Part 2)
5. **Expected:** Header shows original receipt info and total amount
6. Spinner control: "Split into: 2 parts" (or 3)

**Test Case - Auto-fill Logic:**
```
Receipt: $2200 total
Dialog opens with 2-part split

Step 1: Enter Part 1 amount = $1500
Step 2: Part 2 auto-fills = $700 (= $2200 - $1500) ✅
Step 3: Both panels turn GREEN (amounts valid)
Step 4: Check [☑ Add cash portion]
Step 5: Set cash = $300, Driver = John, Type = cash_received
Step 6: Click [✅ Save Split]
Step 7: Success: "Receipt split into 2 parts successfully!"
Step 8: Form reloads, split banner + 3 panels appear (2 receipt + 1 cash)
```

**Test Case - 3-Part Split:**
```
Change spinner: "2 parts" → "3 parts"
New panel appears: "Part 3 of 3"

Part 1: Enter $1500
Part 2: Auto-fills $350 (= ($2200-$1500) / 2)
Part 3: Auto-fills $350 (= ($2200-$1500) / 2)
All turn GREEN ✅
```

**Test Case - Validation:**
```
Edit Part 1: Change to $2500 (over total)
Part 2 becomes negative → RED indicator
Save button disabled
Error message: "⚠️ Difference: $300.00"

Fix Part 1: Back to $1500
Panels turn GREEN
Save enabled
```

### Feature 3: Add Cash Portion 💰
**What to look for:**
1. Find a receipt WITHOUT cash portion
2. Click [💰 Add Cash Portion] button
3. **Expected:** Dialog opens with controls:
   - Receipt Total: $2000 (display only)
   - Cash Amount: [spinner] $2000 (default to total)
   - Driver: [dropdown]
   - Type: [cash_received] (default)
   - Notes: [text field]

**Test Case:**
```
Click [💰 Add Cash Portion]
Dialog opens:
  Receipt Total: $2000
  Cash Amount: 2000.00
  Driver: [Select driver...]
  Type: cash_received
  
User adjusts:
  Cash Amount: 500
  Driver: John Doe
  
Click [✅ Add Cash Portion]
Success: "Cash portion of $500.00 added!"

Form reloads (if split):
  3-panel view with new cash panel
```

---

## Button Locations

All three new buttons appear in the form panel (below receipt table):

```
[💾 Update] [⟲ Clear Form] [🔍 Check Duplicates] 
[🔀 Manage Split Receipts] [✂️ Create Split] [💰 Add Cash Portion]
```

---

## Expected Database Changes

After creating/modifying splits:

**Table: receipt_splits**
```sql
SELECT * FROM receipt_splits WHERE receipt_id = 12345;
-- Expected: 1+ rows for each part with GL code, amount, payment method
```

**Table: receipt_cashbox_links**
```sql
SELECT * FROM receipt_cashbox_links WHERE receipt_id = 12345;
-- Expected: 1 row if cash portion added
```

**Table: audit_log**
```sql
SELECT * FROM audit_log WHERE entity_id = 12345 ORDER BY changed_at DESC;
-- Expected: Multiple entries for all changes
```

---

## Visual Reference

### Split Detection Banner (when receipt is split)
```
╔════════════════════════════════════════════════════════════╗
║ 📦 Split into 3 receipt(s) + 💰 Cash portion ($300) | Total: $2200 ║
║ [👁️ View Split Details] [🔽 Collapse Split View]             ║
╚════════════════════════════════════════════════════════════╝
```

### Side-by-Side Detail Panels
```
┌─────────────────┬─────────────────┬─────────────────┬──────────────┐
│ Receipt Part 1  │ Receipt Part 2  │ Receipt Part 3  │ 💰 Cash      │
│ ID: #12345      │ ID: #12345      │ ID: #12345      │ Amount: $300 │
│ Date: 1/17      │ Date: 1/17      │ Date: 1/17      │ Driver: John  │
│ Vendor: Acme    │ Vendor: Acme    │ Vendor: Acme    │ Type: cash_rx │
│ Amount: $1500   │ Amount: $500    │ Amount: $200    │ [Remove]     │
│ Payment: card   │ Payment: card   │ Payment: check  │              │
│ GL: 4100        │ GL: 4100        │ GL: 4100        │              │
│ [Open]          │ [Open]          │ [Open]          │              │
└─────────────────┴─────────────────┴─────────────────┴──────────────┘
```

### Split Creation Dialog (2-part, auto-fill)
```
╔════════════════════════════════════════════════════════════╗
║ Original Receipt #12345 | Date: 1/17 | Vendor: Acme       ║
║ Total Amount: $2200.00                                    ║
╠════════════════════════════════════════════════════════════╣
║ Split into: [2] parts  💡 Enter first, second auto-fills...║
╠════════════════════════════════════════════════════════════╣
║ ┌──────────────────────┬──────────────────────┐            ║
║ │ Part 1 of 2          │ Part 2 of 2          │            ║
║ │ Amount: [1500.00] ✓  │ Amount: [700.00] ✓   │            ║
║ │ Payment: [card]      │ Payment: [card]      │            ║
║ │ GL Code: [4100]      │ GL Code: [4100]      │            ║
║ │ Description: [...]   │ Description: [...]   │            ║
║ └──────────────────────┴──────────────────────┘            ║
║ ☑ Add cash portion                                         ║
║ Cash: [$500] Driver: [John Doe] Type: [cash_received]      ║
║                                                            ║
║ [✅ Save Split] [Cancel]                                  ║
╚════════════════════════════════════════════════════════════╝
```

---

## Troubleshooting

### Buttons Not Showing
- Check: Is RECEIPT_WIDGET_WRITE_ENABLED set to "true"?
- Check: Did you reload the receipts tab?
- Check: Do they compile? `python -m py_compile receipt_search_match_widget.py`

### Dialog Crashes
- Check: Are new widget files in desktop_app/?
- Check: Do they compile together?
  ```powershell
  python -X utf8 -m py_compile desktop_app/split_receipt_*.py
  ```
- Check: Database connection working? (test with psql)

### Split Not Showing
- Check: Is the receipt actually split in database?
  ```sql
  SELECT * FROM receipt_banking_links WHERE receipt_id = 12345;
  ```
- Check: Are both parts in receipts table?
  ```sql
  SELECT * FROM receipts WHERE receipt_id IN (12345, 12346);
  ```

### Auto-fill Not Working
- Check: Are you entering amount in Part 1 first?
- Check: Is the amount within receipt total?
- Check: Try reloading dialog

---

## Success Criteria

✅ **Split Detection:**
- Banner appears for split receipts
- Side-by-side panels show correct data
- Open button loads linked receipt

✅ **Create Split:**
- Dialog opens with correct header
- Auto-fill works (Part 2 = remainder)
- 3-part split creates 3 panels
- Validation shows Green/Red
- Save creates database records

✅ **Add Cash:**
- Dialog opens with correct fields
- Driver dropdown populated
- Save creates receipt_cashbox_links row

✅ **Database:**
- receipt_splits rows created
- receipt_cashbox_links rows created
- audit_log has entries
- Amounts sum correctly

---

## Test Execution Steps

1. **Start app** with RECEIPT_WIDGET_WRITE_ENABLED=true
2. **Go to Receipts tab**
3. **Search for test receipt** (or use receipt ID filter)
4. **Test Feature 1:** Load split receipt → see banner + panels
5. **Test Feature 2:** Create split → enter amounts → auto-fill works → save
6. **Test Feature 3:** Add cash portion → select driver → save
7. **Verify database:** Check receipt_splits, receipt_cashbox_links, audit_log
8. **Document findings** in test report

---

**Ready to test!** 🚀

All components compile without errors. No syntax issues.
Just run the app and follow the test cases above.
