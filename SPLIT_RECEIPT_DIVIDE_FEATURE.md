# Split Receipt Implementation Complete ✅

## Overview
**Feature**: "Divide by Payment Methods" — Split a receipt into multiple receipts with different GL codes and payment methods (2019-style pattern).

**Pattern**: One physical receipt (banking transaction) → Multiple logical receipts with SPLIT/<amount> tag.

---

## What Was Implemented

### 1. **UI Button** 
- Added "📊 Divide by Payment Methods" button in receipt form
- Visible only when a receipt is loaded (appears alongside Update/Delete buttons)
- Orange background (#fd7e14) for visual distinction
- Tooltip explains the feature

### 2. **SplitReceiptDialog** (New Class)
**File**: [desktop_app/split_receipt_dialog.py](desktop_app/split_receipt_dialog.py)

Dialog workflow:
1. Shows original receipt details (vendor, amount, date, banking link)
2. User selects number of splits (2-10)
3. For each split, user enters:
   - **Amount**: Currency input
   - **GL Code**: Dropdown from `chart_of_accounts`
   - **Payment Method**: Cash, Debit, Check, Credit Card, Bank Transfer, Gift Card, Rebate, Float
   - **Memo**: Optional description (Fuel, Food, Oil, Smokes, etc.)
4. Real-time validation: Total must equal original receipt gross amount ±$0.01
5. **Create** button only enabled when totals match

### 3. **Split Creation Logic**
- Inserts N new receipts into database
- All receipts share: `SPLIT/<original_amount>` tag in description field
- Each receipt gets unique: amount, GL code, payment method, memo
- **Banking link**: Only first split keeps the original banking link
- **GST calculation**: Per-line GST = gross × 0.05 / 1.05 (if gst_code = GST_INCL_5)
- **Ledger entries**: Only first split gets `banking_receipt_matching_ledger` entry
- **Description format**: `<vendor> | <memo> | SPLIT/<amount>`

### 4. **Database Integration**
New receipts created with:
```sql
INSERT INTO receipts (
    receipt_date, vendor_name, canonical_vendor, gross_amount,
    gst_amount, gst_code, sales_tax, tax_category,
    description, category, source_reference, payment_method,
    banking_transaction_id, is_driver_reimbursement, vehicle_id,
    gl_account_code, gl_account_name, owner_personal_amount, fuel_amount
)
```

Banking ledger entry for first split:
```sql
INSERT INTO banking_receipt_matching_ledger (
    banking_transaction_id, receipt_id, match_date, match_type,
    match_status, match_confidence, notes, created_by
)
VALUES (banking_id, receipt_id, NOW(), 'split_first', 'linked', 0.95, 
        'First split of SPLIT/<amount>', 'desktop_app_divide')
```

---

## Testing: Banking ID 69364 Example

### Original Banking Transaction
- **ID**: 69364
- **Date**: 2012-09-24
- **Vendor**: CENTEX
- **Amount**: $170.01 (Debit)

### Split Configuration
| Split | Amount | GL Code | GL Name | Payment | Memo |
|-------|--------|---------|---------|---------|------|
| 1 | $102.54 | 5110 | Fuel Expense | Debit | Fuel |
| 2 | $67.47 | 5100 | Vehicle Operating Expenses | Debit | Oil |
| **Total** | **$170.01** | | | | |

### Result: ✅ Success
**Receipt #145330** (Fuel split)
```
Date: 2012-09-24
Vendor: Centex
Amount: $102.54 (GST: $4.88)
GL Code: 5110 (Fuel Expense)
Payment: Debit
Banking ID: 69364 ← LINKED
Description: Centex | Fuel | SPLIT/170.01
```

**Receipt #145331** (Oil split)
```
Date: 2012-09-24
Vendor: Centex
Amount: $67.47 (GST: $3.21)
GL Code: 5100 (Vehicle Operating Expenses)
Payment: Debit
Banking ID: None ← NOT LINKED
Description: Centex | Oil | SPLIT/170.01
```

**Banking Ledger**:
```
Banking 69364 → Receipt #145330 (split_first, linked)
  Notes: "First split of SPLIT/170.01"
```

---

## Advantages Over Previous Patterns

### ✅ vs. Single-Copy "Split Receipt"
- Old: Duplicate receipt with `[SPLIT with #<id>]` one-way tag (confusing audit trail)
- New: Multiple receipts with symmetric `SPLIT/<amount>` tag (searchable, auditable)

### ✅ vs. Internal GL Distributions
- Old: Add table inside receipt form (complex UI, balance validation)
- New: Separate receipts (familiar form, natural flow, proven in 2019)

### ✅ vs. Manual Multiple Tenders
- Old: Create 2-3 receipts manually for each split (time-consuming)
- New: Dialog auto-creates all splits with one click (efficient, validated)

---

## How to Use (End User)

1. **Open Receipt Search & Match** widget in desktop app
2. **Search** and load a receipt (or find via banking transaction)
3. Click **"📊 Divide by Payment Methods"** button
4. Dialog appears:
   - Confirm number of splits (e.g., 2 for fuel + food)
   - Enter **Amount** for each split (totals auto-validate)
   - Choose **GL Code** (Fuel Expense, Other Expense, etc.)
   - Select **Payment Method** (Cash, Debit, Gift Card, Rebate, etc.)
   - Optional: Add **Memo** (Fuel, Food, Smokes, etc.)
5. Click **"✅ Create Splits"**
6. Confirmation shows new receipt IDs
7. **Search results** auto-refresh to show all splits with SPLIT/ tag

---

## Code Files Modified

### Modified:
- [desktop_app/receipt_search_match_widget.py](desktop_app/receipt_search_match_widget.py)
  - Added divide_btn button (line ~1060)
  - Added divide_btn visibility control in _clear_form (line ~3000)
  - Added divide_btn visibility on receipt load (line ~1804, ~1914)
  - Added _divide_by_payment_methods method (line ~3430)

### Created:
- [desktop_app/split_receipt_dialog.py](desktop_app/split_receipt_dialog.py) — Complete dialog class
- [scripts/test_split_receipts_69364.py](scripts/test_split_receipts_69364.py) — Test/demo script
- [scripts/verify_split_receipts_69364.py](scripts/verify_split_receipts_69364.py) — Verification script

---

## Future Enhancements

1. **Bulk splits**: Dialog option to load 2019 split examples as templates
2. **Preset configurations**: Save/load split templates (e.g., "Fuel + Food", "Fuel + Rebate")
3. **Auto-GL suggestion**: Based on vendor history (e.g., Fas Gas → Fuel)
4. **Split preview**: Show proposed GL posting before creating
5. **Undo splits**: Dialog to reverse a split group (delete all with same SPLIT/ tag)
6. **Report view**: GL allocation breakdown when viewing banking transaction

---

## Audit Trail & Compliance

- **Banking reconciliation**: Banking amount = First split amount (only first split linked)
- **GL posting**: Each split creates separate GL line (no double-counting)
- **Searchability**: `SPLIT/<amount>` tag appears in all related receipts
- **Ledger tracking**: First split recorded in `banking_receipt_matching_ledger`
- **GST accuracy**: Per-line GST calculated correctly (tax-inclusive or exclusive)
- **Payment method tracking**: Each split's payment method recorded (cash, debit, etc.)

---

## Technical Notes

### GST Calculation
For tax-inclusive receipts (gst_code = 'GST_INCL_5'):
```
line_gst = gross_amount × 0.05 / 1.05
net_amount = gross_amount - line_gst
```

Example: $102.54 gross
- GST: $102.54 × 0.05 / 1.05 = $4.88
- Net: $102.54 - $4.88 = $97.66

### Database Consistency
- Sum of all split grosses = original banking amount
- Sum of all split GSTs = original receipt GST (approximately)
- Only first split has non-NULL banking_transaction_id
- All splits share identical SPLIT/ tag in description

### Performance
- Dialog loads GL codes on open (cached if connection fails)
- Validation runs on every cell change (real-time feedback)
- Batch insert: All N receipts + 1 ledger entry in single transaction (atomic)
- Rollback on error (no orphan receipts)

---

**Status**: ✅ **COMPLETE AND TESTED**  
**Date**: January 9, 2026  
**Test Case**: Banking 69364 ($170.01) → Receipts #145330, #145331 (SPLIT/170.01)
