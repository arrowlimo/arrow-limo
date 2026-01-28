# Duplicate Banking Receipts Cleanup Report
**Date:** December 22, 2025  
**Task:** Audit and clean up duplicate receipts linked to same banking transactions

---

## Executive Summary

Found **551 banking transactions** with multiple receipts linked (1,148 total duplicate receipts). Successfully cleaned up **216 cases of true duplicates**, deleting **242 duplicate receipts**. Remaining **335 cases** require manual review due to differing amounts.

---

## Cleanup Results

| Metric | Count |
|--------|-------|
| **Initial duplicates found** | 551 banking transactions |
| **Total duplicate receipts** | 1,148 receipts |
| **True duplicates deleted** | 242 receipts |
| **Banking transactions cleaned** | 216 |
| **Remaining for manual review** | 335 banking transactions |

### Breakdown by Type

**True Duplicates (Cleaned ✅):**
- Same amount + same vendor (or no vendor)
- Kept oldest receipt (lowest receipt_id)
- Deleted duplicates
- **Result:** 216 banking transactions now have single receipt

**Need Manual Review (📋):**
- Different amounts between receipts
- May be:
  - Data entry errors (one wrong, one correct)
  - Legitimate split transactions (need split_key marking)
  - Fee adjustments (NSF fees, etc.)
- **Exported to:** `l:/limo/reports/duplicate_receipts_manual_review_20251222_163420.csv`

---

## Examples of Cleaned Duplicates

### Email Transfer Duplicates
- **TX #24101:** 2 receipts of $500.00 → Kept #59819, deleted #59825
- **TX #24267:** 3 receipts of $500.00 → Kept #59965, deleted 2 duplicates
- **TX #26082:** 4 receipts of $500.00 → Kept #61800, deleted 3 duplicates

### Cash Withdrawal Duplicates
- **TX #24238:** 2 receipts of $200.00 → Kept #59959, deleted #100878
- **TX #31029:** 3 receipts of $500.00 → Kept #66731, deleted 2 duplicates

### Payment Duplicates
- **TX #30515:** 3 receipts for Money Mart $500.00 → Kept #66217, deleted 2 duplicates
- **TX #29202:** 3 receipts for Fibrenew $500.00 → Kept #64920, deleted 2 duplicates

---

## Manual Review Cases (Examples)

These cases have different amounts and need investigation:

### 1. E-Transfer Discrepancies
**TX #24135** - 3 receipts with different amounts:
- Receipt #59853: $400.00
- Receipt #59855: $385.45
- Receipt #70783: $410.00
- **Issue:** Amounts don't sum to bank amount ($795.45 difference)

**TX #24392** - Email transfer to Vanessa Thomas:
- Receipt #60110: $2,092.21
- Receipt #60113: $2,172.43
- **Issue:** $2,172.43 difference - likely one is correct, one is error

### 2. Cash Withdrawal Discrepancies
**TX #24167:**
- Receipt #54000: $250.00
- Receipt #100947: $243.00
- **Issue:** Different amounts for same ATM withdrawal

**TX #24250:**
- Receipt #54018: $600.00
- Receipt #59970: $609.08
- **Issue:** $9.08 difference - possible fee?

### 3. Vendor Payment Discrepancies
**TX #31708** - Lacombe Ford:
- Receipt #67426: $2,950.00
- Receipt #67428: $2,934.36
- **Issue:** $15.64 difference - which is correct?

**TX #29751** - Plenty of Liquor:
- Receipt #65469: $2,900.00
- Receipt #65477: $3,028.11
- **Issue:** $128.11 difference - significant discrepancy

---

## Distribution by Account

| Account | Initial Duplicates | After Cleanup |
|---------|-------------------|---------------|
| **CIBC 0228362** | 140 | ~95 (estimated) |
| **Scotia 903990106011** | 411 | ~240 (estimated) |

---

## Root Causes

Based on analysis, duplicates likely occurred from:

1. **Multiple Import Runs:** Same banking data imported multiple times
2. **Email Parser Duplicates:** Email-to-receipt conversion created duplicates
3. **Manual Entry + Auto-Import:** Receipt entered manually, then auto-created from banking
4. **Split Transaction Confusion:** One banking withdrawal → multiple expenses not properly marked

---

## Next Steps

### Immediate Action Required
1. **Review Manual Review CSV** (`duplicate_receipts_manual_review_20251222_163420.csv`)
   - 335 cases to investigate
   - Determine which receipt is correct
   - Delete incorrect ones or mark as legitimate splits

### Recommended Approach for Manual Review
```python
# For each case in the CSV:
# 1. Look up the banking transaction
# 2. Compare receipt amounts to actual bank amount
# 3. Check if amounts sum (split) or one is clearly wrong
# 4. Decision tree:
if sum(receipt_amounts) == bank_amount:
    # Legitimate split - mark with split_key
    UPDATE receipts SET split_key = 'BANK_TX_#####', is_split_receipt = TRUE
elif one_receipt_matches_bank_amount:
    # Keep matching, delete others
    DELETE FROM receipts WHERE receipt_id IN (wrong_ids)
else:
    # Investigation needed - check source documents
    # Flag for Paul/Karen review
```

### Prevention Going Forward
1. **Add Unique Constraint:**
   ```sql
   CREATE UNIQUE INDEX idx_one_receipt_per_banking_tx 
   ON receipts(banking_transaction_id) 
   WHERE banking_transaction_id IS NOT NULL 
   AND is_split_receipt = FALSE;
   ```

2. **Import Validation:** Check for existing `banking_transaction_id` before creating new receipts

3. **Split Transaction Protocol:** Always set `split_key` and `is_split_receipt=TRUE` for legitimate splits

---

## Files Generated

1. **Audit Report:** `l:/limo/reports/duplicate_banking_receipts_20251222_163249.csv`
   - Complete list of all duplicates found
   - Banking transaction details
   - Receipt details for each duplicate

2. **Manual Review File:** `l:/limo/reports/duplicate_receipts_manual_review_20251222_163420.csv`
   - 335 cases requiring investigation
   - Includes amounts, vendors, reasons for flagging

3. **Cleanup Script:** `l:/limo/scripts/cleanup_duplicate_banking_receipts.py`
   - Can be re-run after manual decisions
   - Safe to use (backs up to banking_transactions.receipt_id before delete)

---

## Database Changes Made

✅ **Deleted:** 242 duplicate receipts  
✅ **Updated:** banking_transactions.receipt_id references (pointed to kept receipts)  
✅ **Preserved:** All banking transaction data intact  
✅ **Maintained:** Referential integrity (no orphaned records)

---

**Status:** ✅ Phase 1 Complete (Automated cleanup)  
**Next:** 📋 Phase 2 Manual Review (335 cases)  
**Priority:** High - affects financial accuracy and reporting
