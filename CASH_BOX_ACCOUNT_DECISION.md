# Cash Box Account Strategy - Analysis & Recommendations

## Current State

### What We Have
✅ **GL Accounts for Cash:**
- `1015` — Petty Cash (Asset)
- `1030` — Petty Cash (Asset) [appears to be duplicate of 1015]

✅ **`cash_box_transactions` table:**
- Tracks float transactions, floats in/out, balances
- Links to receipts and banking_transactions
- Separate from accounting GL posting

✅ **Cash payment pattern (already in split receipts):**
- "Cash" is a valid payment method option
- Split receipts support cash payment allocation

❌ **NO Separate Banking Account for Cash Box:**
- `bank_accounts` table has only:
  - CIBC Business Checking (0228362)
  - CIBC Business Deposit (3648117)
  - CIBC Vehicle Loans (8314462)
  - Legacy CIBC 74-61615
- **No "CASH BOX" dummy banking account**

### Current Cash Receipt Handling
Cash purchases in split receipt dialog:
1. Created with `payment_method = 'cash'` (text field)
2. **NOT linked to any `banking_transaction_id`** (leaves NULL)
3. Properly allocated to GL code (fuel, food, oil, etc.)
4. Tracked separately in `cash_box_transactions` if part of float system

## Two Approaches Analyzed

### Approach A: Keep Cash Unlinked (Current Pattern) ✅ RECOMMENDED
**Why This Works:**
- Cash receipts are inherently NOT from bank statements
- No reconciliation needed between banking and manual cash
- Float system (`cash_box_transactions`) handles cash tracking separately
- GL posting still happens (vendor → GL code is correct)
- Audit trail clear: payment_method='cash' + banking_transaction_id=NULL = manual cash

**Implementation:** No changes needed—split receipts already do this correctly.

**Audit Trail Example:**
```
Receipt #145331: $67.47 Oil | SPLIT/170.01 | payment_method='cash'
  → GL Code: 5100 (Oil)
  → banking_transaction_id: NULL  (intentional—not from bank)
  → cash_box_transactions: [optional float link if part of driver float]
```

### Approach B: Link Cash to Dummy "CASH BOX" Banking Account (Not Recommended)
**Why This Doesn't Fit:**
1. Would require creating artificial banking account (CASH BOX)
2. Creates false "reconciliation" between manual cash and bank statement (confusing)
3. Adds complexity without clear benefit
4. Float system (`cash_box_transactions`) already tracks cash separately
5. Hard to distinguish "manual unmonitored cash" from "tracked float cash"

## Recommendation

**Use Approach A: Keep Cash Unlinked**

The current pattern is already correct:
- Separate receipts with different GL codes ✅
- Cash payments tracked with `payment_method='cash'` ✅
- No false banking link ✅
- Float system (`cash_box_transactions`) handles cash tracking separately ✅

## No Code Changes Required

The split receipt implementation (`split_receipt_dialog.py`) already handles cash correctly:
- Accepts "Cash" as payment method
- Leaves `banking_transaction_id = NULL` for cash splits
- Allocates to correct GL codes (fuel, food, oil, etc.)
- Only links first split to original banking_transaction (if any)

## Summary

**Q: "Are we supposed to link cash purchases to a cash box?"**

**A:** No. Cash purchases are inherently non-banking receipts. The current pattern is correct:
- Keep `banking_transaction_id = NULL` for cash payments
- Track GL allocation (e.g., fuel, oil) via `gl_account_code`
- Use `cash_box_transactions` table for float management if needed
- No "CASH BOX" dummy banking account is needed or beneficial

---

**Status:** ✅ Verified & Confirmed  
**Action:** None—split receipt pattern is correct as-is  
**Last Updated:** 2025-01-XX  
