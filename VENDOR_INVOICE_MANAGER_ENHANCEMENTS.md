# Vendor Invoice Manager Enhancements
**Date:** December 30, 2025  
**Version:** 2.0 (Enhanced)

## Summary of Improvements

### 1. **Running Balance Due Column** ✅
- **What Changed:** Added an 8th column "Running Balance" to the invoice table
- **How It Works:** 
  - Shows cumulative amount due in chronological order
  - Each invoice displays what was owed up to that point
  - Helps identify exactly what needs to be paid
- **Example:**
  ```
  Date        Amount   Balance   Running Balance
  2024-01-15  $500     $500      $500       (owed $500)
  2024-02-20  $300     $300      $800       (owed $800 total)
  2024-03-10  $200     $200      $1000      (owed $1000 total)
  ```
- **Why It Matters for WCB:** WCB statements show running balances, which made it unclear if you were double-paying. Now you can see exactly what the cumulative amount should be.

### 2. **Compact Amount Input Field** ✅
- **What Changed:** Amount field is now compact (max 6 digits) with integrated calculator button
- **Old Behavior:** Amount field was right-aligned and took up lots of horizontal space
- **New Behavior:**
  - Maximum width of 100px instead of stretching across
  - Accepts up to 999,999.99
  - Built-in calculator button (🧮) to the right
  - Takes up less space in the form
- **Calculator Button:**
  - Click the "🧮" button to open a calculator dialog
  - Input your amount (no need to type in the field)
  - Amount automatically populates back into the field

### 3. **Fee Split Function** ✅
- **What Changed:** Added optional split function to separate vendor charges from fees
- **When to Use:**
  - WCB invoices with overdue/late payment fees
  - CRA adjustments that aren't regular charges
  - Service charges, penalties, interest
- **How It Works:**
  1. Check "Split this invoice into vendor charge + separate fee"
  2. Enter:
     - **Base Charge Amount:** The actual invoice/charge amount
     - **Fee/Adjustment Amount:** Overdue fees, penalties, etc.
     - **Fee Type:** Select from dropdown (Overdue Fee, Interest, Penalty, etc.)
  3. Total must equal the sum of base + fee
  4. Fee is tracked in a separate ledger entry

- **Fee Type Options:**
  - Overdue Fee
  - Interest Charge
  - Penalty
  - Service Charge
  - Late Payment Fee
  - CRA Adjustment
  - Other

### 4. **CRA Reporting Compliance** ✅
- **Key Point:** Overdue fees and penalties are tracked separately and NOT counted in income calculations
- **Why It Matters:** CRA requires that late fees, interest, and penalties be reported separately from business income
- **What Gets Tracked:**
  - Base charge → regular expense category
  - Fees → separate ledger entry marked "Not counted in income calculation"
- **Invoice Description Example:**
  ```
  WCB Invoice | Base: $1500.00 + Overdue Fee: $75.00
  ```

### 5. **Compact Payment Form** ✅
- **What Changed:** Payment tab now includes all necessary fields with compact layout
- **Payment Form Now Includes:**
  - Payment Amount (compact with calculator button)
  - Reference (check number, description, etc.)
  - Payment Date
  - Banking TX ID (optional)
  - Action buttons for single or multi-invoice allocation

### 6. **Enhanced UI/UX**
- Updated hints and tooltips
- Better visual hierarchy
- Running balance shown in bold dark blue
- Fee note clearly states "Not counted as income"

## How to Use the New Features

### Adding an Invoice with Split Fees (WCB Example)

1. **Select Vendor:** Type "WCB" in search box
2. **Click ➕ Add Invoice Tab**
3. **Fill Basic Info:**
   - Invoice Number: `9876543`
   - Invoice Date: `12/30/2024`
   - Amount: `1575.00` (total)
   - Category: `6400 - WCB`
   - Description: `WCB Invoice Dec 2024`

4. **Enable Fee Split:**
   - ✓ Check "Split this invoice into vendor charge + separate fee"
   - Base Charge Amount: `1500.00`
   - Fee/Adjustment Amount: `75.00`
   - Fee Type: `Overdue Fee`

5. **Click ✅ Add Invoice**

**Result:**
- Invoice created with $1575 total
- Description shows breakdown
- Fee tracked separately in vendor ledger
- CRA knows the $75 is a fee, not income

### Paying Multiple Invoices Using Running Balance

1. **Select Vendor:** View all invoices
2. **Review Running Balance Column:**
   - See cumulative amounts at a glance
   - Identify exactly what's unpaid
   
3. **Apply Payment:**
   - Ctrl+Click to select multiple invoices
   - Click 💰 Pay Multiple Invoices
   - Payment allocates to oldest invoices first (auto-allocate button)
   - Running balance updates after payment

### Using the Calculator

1. **In Any Amount Field:**
   - Click the 🧮 button next to the amount
   - Enter your calculation result
   - Click OK, amount auto-fills

2. **Common Calculations:**
   - Multi-invoice total
   - Tax adjustments
   - Fee calculations

## Database Changes (Optional, Not Required)

The fee tracking uses the existing `vendor_account_ledger` table (created in migration 2025-12-27_create_vendor_accounts.sql):

```sql
INSERT INTO vendor_account_ledger (
    account_id, entry_date, entry_type, amount, 
    source_table, source_id, notes
) VALUES (
    account_id, 
    invoice_date,
    'ADJUSTMENT',
    fee_amount,
    'receipts',
    'receipt_id_fee',
    'Overdue Fee - Not counted in income calculation'
);
```

If the vendor ledger table doesn't exist, the fee split still works—the breakdown is just recorded in the invoice description.

## Field Width Changes

| Field | Before | After |
|-------|--------|-------|
| Amount Input | Stretch (full width) | 100px max + calculator |
| Invoice Table | 7 columns | 8 columns (added Running Balance) |
| Payment Form | Minimal | Compact with calculator |

## Backward Compatibility ✅

- All existing invoices continue to work
- Non-split invoices work exactly as before
- Running balance calculated automatically for all vendors
- No database migration required

## Next Steps (Optional Future Enhancements)

1. **Running Balance Forecast:** Show projected balance after proposed payment
2. **Fee Waiver:** Allow marking fees as waived (CRA reporting)
3. **Auto-Split Rules:** Define rules per vendor (e.g., "WCB always splits overdue fees")
4. **Fee Report:** Generate CRA-compliant fee report by vendor/type
5. **Payment Scheduling:** Schedule split payments to clear invoices by date

## Testing Checklist

- [ ] Add invoice without split → works as before
- [ ] Add WCB invoice with overdue fee → splits correctly
- [ ] Running balance column shows cumulative amounts
- [ ] Calculator button opens and populates amount
- [ ] Pay multiple invoices → oldest paid first
- [ ] Check invoice description includes fee breakdown
- [ ] Print/export still works with new column

## Questions?

Refer to the running balance column to verify what WCB actually owes you at each point in time. This prevents accidentally overpaying due to cumulative invoice confusion.
