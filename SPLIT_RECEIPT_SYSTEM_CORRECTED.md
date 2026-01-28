# Split Receipt System - Corrected Implementation

## Overview
The split receipt system has been corrected to match your working implementation from 2 days ago. **No parent receipt** is created - only child receipts that are linked via `split_group_id`.

## How It Works

### Before Split
- Receipt #140678: $58.24 (SAFEWAY)
- Single record in receipts table

### After Split (User clicks "Manage Splits" and adds two allocations)
1. Original receipt **#140678 is DELETED**
2. Two child receipts are **created**:
   - Receipt #99999: $28.05, GL 6900 (Vehicle Maintenance)
   - Receipt #99998: $30.19, GL 6500 (Driver Meal on Duty)

3. **Both child receipts have:**
   - `split_group_id = 99999` (links them together)
   - `is_split_receipt = true` (marks them as split children)
   - `split_group_total = $58.24` (the original combined amount)

4. **Linking via `receipt_splits` table:**
   - `parent_id = 140678, child_id = 99999, child_amount = $28.05`
   - `parent_id = 140678, child_id = 99998, child_amount = $30.19`

## Benefits Over Old System
- **No accounting confusion** - parent receipt deleted, only allocations remain
- **Searchable by original amount** - search for "$58.24" finds both children
- **Visible split indicator** - results table shows "split" in red for child receipts
- **Linked display** - click either child, see both in details panel

## Search Behavior

### Searching by Amount
- Search "$58.24" finds:
  - Both child receipts (via `split_group_total = 58.24`)
  - Any other receipt with gross_amount = $58.24 ± tolerance

### Result Table Display
- Split receipts show **"split"** label in **red** in Status column
- Background color: light red for split receipts
- All other details (date, vendor, GL, amount) shown normally

### Click Any Receipt
- If receipt is split child, details panel shows:
  - Banner: "📦 Split into 2 linked receipt(s) | Total: $58.24"
  - Both receipts displayed side-by-side
  - "View Split Details" button with full breakdown

## Database Schema

### receipts table columns (relevant)
- `receipt_id` - Unique ID
- `split_group_id` - ID linking related split receipts
- `is_split_receipt` - boolean flag (true = child receipt)
- `split_group_total` - Original combined amount (for search)
- `gross_amount` - This receipt's amount
- `gl_account_code` - GL code for this allocation
- All other normal fields (date, vendor, payment_method, etc.)

### receipt_splits table (audit trail)
- `parent_id` - Original receipt ID (now deleted)
- `child_id` - Child receipt ID
- `child_amount` - Amount for this child
- `child_category` - GL category for this child

## Code Changes Made

### 1. split_receipt_manager_dialog.py (_save_all_splits method)
- Deleted original receipt from receipts table
- Created child receipts with split_group_id = original receipt_id
- Set is_split_receipt = true on all children
- Set split_group_total = original amount
- Inserted audit trail in receipt_splits table

### 2. receipt_search_match_widget.py (_do_search method)
- Modified amount filter to search BOTH:
  - `gross_amount` (normal receipts)
  - `split_group_total` (split children)
- With tolerance: `(gross_amount BETWEEN x AND y) OR (split_group_total BETWEEN x AND y)`

### 3. receipt_search_match_widget.py (_populate_table method)
- Added `is_split_receipt` to SELECT query
- Added "Status" column to results table
- Display "split" label in red for children
- Light red background for split receipts

## Accounting Impact
✅ Original receipt deleted - no double-counting
✅ Each allocation GL code gets its own row in GL ledger
✅ Total GL postings = original amount (matched)
✅ Audit trail preserved in receipt_splits table
✅ Searchable by original combined amount

## Next Steps
Try splitting receipt #140678 ($58.24) into:
- GL 6900: $28.05
- GL 6500: $30.19

Expected results:
1. Receipt #140678 disappears from results
2. Two new receipts (#99999, #99998) appear in results
3. Both show "split" label in red
4. Searching "$58.24" finds both children
5. Clicking either shows both in details panel with split banner
