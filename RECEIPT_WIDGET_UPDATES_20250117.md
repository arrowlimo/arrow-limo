# Receipt Widget Updates - January 17, 2026

## Changes Made

### 1. ✅ Restored Amount Checkbox
**Location:** `desktop_app/receipt_search_match_widget.py` - Lines 140-165

- Added `self.amount_check = QCheckBox("Match Total")` 
- Positioned in the "Amount & ID" row of the search panel
- Allows users to filter receipts by matching total amounts
- Default: unchecked

**UI Layout:**
```
Amount: [Input ±$] [Match Total checkbox]  ID: [Input]
```

### 2. ✅ Banking Link Opening on Double-Click
**Location:** `desktop_app/receipt_search_match_widget.py` - Lines 221 and 742-778

**Implementation:**
- Changed double-click handler from `_populate_form_from_selection` to `_on_receipt_double_clicked()`
- New method `_on_receipt_double_clicked()` checks if receipt has a banking link
- If banking ID exists: Opens `BankingTransactionPickerDialog` with the linked banking transaction
- If no banking link: Falls back to normal form population

**Code Flow:**
```
User double-clicks receipt in table
    ↓
_on_receipt_double_clicked() called
    ↓
Check if Banking ID column has a value
    ↓
    If YES: Open BankingTransactionPickerDialog with that transaction
    If NO: Populate form normally (same as single-click)
```

### 3. ✅ Split Receipt Integration (Already Working)
- When a receipt is loaded, `split_details_widget.load_receipt()` is called
- If receipt is part of a split (SPLIT/ pattern in description), split details panel appears
- User can see all linked receipts in the split

## Testing Instructions

### Test 1: Amount Checkbox Visibility
1. Open app → Receipts tab
2. Look for "Match Total" checkbox in the search panel
3. Verify it appears to the right of the ±$ amount range spinner

### Test 2: Single-Click (Form Population)
1. Click any receipt row (not highlighted)
2. Verify form populates with receipt data below
3. Verify split details load if it's a split receipt

### Test 3: Double-Click with Banking Link (FAS GAS Receipt #16753)
1. Find receipt with Banking ID filled in (e.g., FAS GAS $166.89)
2. **Double-click** that receipt row
3. Expected: Banking Transaction Picker dialog opens showing the linked banking transaction
4. Click [Open] in dialog to view banking transaction details

### Test 4: Double-Click without Banking Link
1. Find a receipt with empty Banking ID column
2. **Double-click** that receipt row
3. Expected: Form populates normally (same as single-click)

### Test 5: Split Receipt FAS GAS ($166.89)
1. Find FAS GAS receipt $166.89 (receipt #16753 from 2017-11-03)
2. Click it once to select
3. Verify in split details panel below:
   - Shows split into 2-3 parts
   - Part 1: $128.00 (Fuel)
   - Part 2: Remaining amount (Client Beverages/Food)
4. Click [Open] on second part to navigate to linked receipt

## Features

- ✅ Amount checkbox for total amount filtering
- ✅ Banking link opening via double-click
- ✅ Form population via single-click
- ✅ Split receipt detection and display
- ✅ Graceful error handling (fallback to form population)

## File Modified

- `desktop_app/receipt_search_match_widget.py` (1212 lines total)
  - Lines 140-165: Amount checkbox UI
  - Line 221: Double-click connection
  - Lines 742-778: New `_on_receipt_double_clicked()` method

## App Status

✅ **Running successfully**
- All imports working
- No syntax errors
- Receipts tab functional
- Banking links ready to test
