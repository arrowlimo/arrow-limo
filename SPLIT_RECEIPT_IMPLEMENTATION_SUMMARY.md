# Split Receipt Implementation - What Changed

## Summary
Corrected the split receipt system to match your working version from 2 days ago:
- **Delete parent receipt** (was causing accounting confusion)
- **Create child receipts** with split_group_id, is_split_receipt=true, and split_group_total
- **Search on combined amount** via split_group_total column
- **Display split indicator** in results table in red

## Files Modified

### 1. `desktop_app/split_receipt_manager_dialog.py`
**Method:** `_save_all_splits()` (lines 398-485)

**What it does:**
1. Validates split amounts sum to original receipt total
2. **Deletes** original receipt (no parent kept)
3. **Creates** child receipts with:
   - `split_group_id = original_receipt_id` (for linking)
   - `is_split_receipt = true` (mark as split child)
   - `split_group_total = original_amount` (for search)
   - Each child has its own GL code and amount
4. **Creates audit trail** in receipt_splits table
5. Shows success message with child receipt IDs

**Example:**
```
Receipt #140678 $58.24 SPLITS INTO:
  → Receipt #99999 $28.05 GL 6900 (is_split_receipt=true)
  → Receipt #99998 $30.19 GL 6500 (is_split_receipt=true)
Both have split_group_id=99999 and split_group_total=$58.24
Original #140678 is DELETED
```

---

### 2. `desktop_app/receipt_search_match_widget.py`
**Method A:** `_do_search()` (lines 619-636, amount filter)

**Changed:**
- Now searches BOTH `gross_amount` AND `split_group_total`
- "Match Total" mode: `(gross_amount = X) OR (split_group_total = X)`
- "Tolerance" mode: `(gross_amount BETWEEN x AND y) OR (split_group_total BETWEEN x AND y)`

**Example:**
```
Search "$58.24" finds:
  ✓ Receipt #99999 $28.05 (split_group_total=$58.24)
  ✓ Receipt #99998 $30.19 (split_group_total=$58.24)
  ✓ Any other receipt with gross_amount=$58.24
```

---

**Method B:** `_populate_table()` (lines 868-967)

**Changed:**
1. Added 11th column "Status" (was 10 columns)
2. Extract `is_split_receipt` from row data (index 17)
3. For split receipts: display "split" label in **red**, **bold** text
4. Color coding:
   - Split receipt: light red background
   - Matched to banking: light green background
   - Unmatched: light red background
5. Updated header resize modes for new column

**Result:**
```
Results Table:
ID   | Date  | Vendor   | Amount  | GL   | ... | Status
-----|-------|----------|---------|------|-----|--------
99999| 1/20  | SAFEWAY  | $28.05  | 6900 | ... | split    ← red
99998| 1/20  | SAFEWAY  | $30.19  | 6500 | ... | split    ← red
```

---

### 3. `split_receipt_details_widget.py`
**Status:** Not modified (already loads splits correctly via split_group_id)
- When you click receipt #99999, it queries split_group_id=99999
- Loads receipt #99998 as linked sibling
- Shows banner: "📦 Split into 2 linked receipt(s) | Total: $58.24"
- Displays both side-by-side

---

## Database Behavior

**Before (Incorrect - kept parent):**
```
INSERT INTO receipts (split_group_id=140678, is_split_receipt=false)  ← Parent kept
INSERT INTO receipts (split_group_id=140678, is_split_receipt=true)   ← Child
INSERT INTO receipts (split_group_id=140678, is_split_receipt=true)   ← Child
  → Accounting sees 3 rows totaling $87.48 (original $58.24 + 2 children)
```

**After (Correct - deletes parent):**
```
DELETE FROM receipts WHERE receipt_id=140678                          ← Parent deleted
INSERT INTO receipts (split_group_id=140678, is_split_receipt=true)   ← Child
INSERT INTO receipts (split_group_id=140678, is_split_receipt=true)   ← Child
  → Accounting sees only 2 rows totaling $58.24 (correct!)
```

---

## Testing Checklist

When you test the split functionality:

1. **Find receipt #140678 in search** ($58.24 SAFEWAY)
   - [ ] Receipt appears in results table

2. **Click "Manage Splits" button**
   - [ ] Dialog opens with receipt details
   - [ ] Table shows original receipt data

3. **Add two split lines:**
   - [ ] Row 1: GL 6900, Amount $28.05
   - [ ] Row 2: GL 6500, Amount $30.19
   - [ ] Total shows $58.24 ✓

4. **Click "Save"**
   - [ ] Success message shows child receipt IDs
   - [ ] Dialog closes

5. **Back in results window**
   - [ ] Receipt #140678 no longer appears (deleted)
   - [ ] Receipt #99999 appears with "split" label (red)
   - [ ] Receipt #99998 appears with "split" label (red)
   - [ ] Background is light red for both

6. **Search for original amount**
   - [ ] Search "$58.24" in amount field
   - [ ] Both child receipts appear in results

7. **Click child receipt in results**
   - [ ] Details panel opens
   - [ ] Banner shows: "📦 Split into 2 linked receipt(s) | Total: $58.24"
   - [ ] Both receipts displayed side-by-side
   - [ ] Green "View Split Details" button available

---

## Accounting Verification

After split, run:
```sql
SELECT SUM(gross_amount) FROM receipts 
WHERE split_group_id = 140678;
-- Result: $58.24 ✓ (not $87.48)

SELECT * FROM receipt_splits 
WHERE parent_id = 140678;
-- Result: 2 rows with child_id=99999, 99998 ✓

SELECT receipt_id FROM receipts WHERE receipt_id = 140678;
-- Result: (empty) ✓ Parent deleted
```

---

## Rollback Plan (if needed)

If something goes wrong:
1. Check database backups in `l:\limo\` (*.dump or *.sql files)
2. Restore from backup before split attempt
3. Report error with:
   - Original receipt ID
   - Amounts and GL codes used
   - Error message from dialog
   - Database logs if available
