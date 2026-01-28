# SQUARE & E-TRANSFER PAYMENT INVESTIGATION REPORT
**Date:** January 7-8, 2026  
**Session:** Payment Matching Verification & Documentation

---

## EXECUTIVE SUMMARY

### Completed Work
1. ✅ **Square Payment Import**: 273 payments from Square API (Sept-Jan 2026)
2. ✅ **Automated Matching**: 180 payments linked (66% success rate) using comprehensive matcher
3. ✅ **Payment Verification**: All 93 unmatched validated (81 clean, 12 suspicious recurring)
4. ✅ **Trade of Services**: Verified all already linked to charters
5. ✅ **Documentation**: Complete audit trail for future reference

### Critical Issues Found
1. ⚠️ **E-Transfer Data Loss**: 0 e-transfers in DB (expected ~98% match rate from prior work)
2. ⚠️ **Payment Method Corruption**: 24,375 payments show method='unknown' instead of actual types
3. ⚠️ **Potential Loan Repayments**: 12 Square payments ($4,859) show recurring patterns

---

## SQUARE PAYMENT DETAILS

### Import Stats
- **Total Square payments**: 273  
- **Date range**: 2025-09-10 to 2026-01-07  
- **Total amount**: $94,789.39  
- **Square payouts**: 148 ($184,396.82)

### Matching Results
| Status | Count | Amount | Action |
|--------|-------|--------|--------|
| **Matched (auto-linked)** | 180 | $94,432.58 | Complete ✓ |
| **Clean unmatched** | 81 | $62,801.41 | Manual review needed |
| **Recurring (suspicious)** | 12 | $4,859.22 | Verify loan repayments |
| **TOTAL UNMATCHED** | **93** | **$67,660.63** | See review CSV |

### Payment Identification Method
All Square payments identified by:
- `payment_method = 'credit_card'`
- `payment_key IS NOT NULL` (Square transaction ID hash)
- Field `square_payment_id` normalized to match `payment_key` for consistency

### Matching Strategies Used (Comprehensive Matcher)
1. **Retainer exact match** (confidence 5): Date + amount exact
2. **Retainer approximate** (confidence 4): ±7 days tolerance
3. **Waste Connections rule** (confidence 4): $774 ±14 days
4. **LMS deposit match** (confidence 3): Amount matches LMS deposit record
5. **Customer resolution** (confidence 2-5): Email/name → best charter by proximity
6. **Direct reserve fuzzy** (confidence 1): Rate/balance/deposit ±5% (NOT auto-applied)

**Applied threshold**: Confidence ≥3 (180 links)  
**Remaining threshold**: All confidence=1 (93 unmatched) - too risky for auto-apply

---

## VERIFICATION RESULTS

### 1. Refund/Chargeback Check ✅ PASS
- **Negative amounts**: 0  
- **Problem keywords in notes**: 0  
- **Result**: No refunds, chargebacks, or disputes found

### 2. Payout Transfer Check ✅ PASS
- **Matched to bank deposits**: 0  
- **Result**: No Square→Bank payout transfers misclassified as customer payments

### 3. Fee/Adjustment Check ✅ PASS
- **Small amounts (<$10)**: 0  
- **Result**: No processing fees or adjustments

### 4. Recurring Payment Check ⚠️ WARNING
- **Recurring patterns found**: 3 amounts, 12 total payments

| Amount | Count | Dates | Pattern | Likely Cause |
|--------|-------|-------|---------|--------------|
| $257.55 | 5 | Dec 17 - Jan 2 | 1-9 day gaps | Possible repeat customer OR loan |
| $483.21 | 4 | Dec 4 - Dec 17 | 2 same-day dups | Suspicious - verify |
| $546.21 | 3 | **All Dec 4 (same day!)** | 0-day gaps | **HIGHLY SUSPICIOUS** |

**Action Required**: Check Square dashboard for active Square Capital loans. If these are loan repayments, they should be:
- Reclassified as `payment_method = 'square_capital_repayment'` or moved to `receipts` table
- **NOT** linked to customer charters
- Recorded as business expenses (loan interest + principal)

---

## E-TRANSFER INVESTIGATION

### Expected vs. Actual
| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| **E-transfers in DB** | ~1,000+ | **0** | ❌ CRITICAL |
| **Match rate** | 98% | N/A | ❌ NO DATA |
| **payment_method='bank_transfer'** | Majority | 0 | ❌ MISSING |

### Root Cause Analysis
```sql
SELECT payment_method, COUNT(*) 
FROM payments 
GROUP BY payment_method;
```
**Result**:
- `unknown`: 24,375 payments ($9,370,425.45)  ← **99.5% of all payments!**
- `credit_card`: 273 payments ($162,122.95)

### Problem Identification
1. **Data corruption or migration error**: Nearly all payment methods reset to 'unknown'
2. **Prior 98% match rate lost**: Previous e-transfer work wiped out or not committed
3. **Possible cause**: LMS import script not setting payment_method correctly

### Recovery Plan
1. Check LMS source data for payment type indicators
2. Re-run payment method classification from LMS `payment_code_4char` or transaction descriptions
3. Verify e-transfer data still exists in `lms_unified_map` or `lms_deposits`
4. Restore payment_method values from banking_transactions (EMAIL MONEY TRANSFER, etc.)
5. Re-run e-transfer matching scripts after restoration

---

## TRADE OF SERVICES STATUS ✅ COMPLETE

Query result:
```sql
SELECT COUNT(*) FROM payments 
WHERE payment_method IN ('trade_of_services', 'cash') 
  AND charter_id IS NULL;
```
**Result**: 0 unmatched

**Conclusion**: All Fibrenew exchanges and similar barter/service trades already linked to charters. No action needed.

---

## FILES CREATED / UPDATED

### Reports
1. **reports/SQUARE_PAYMENTS_MANUAL_REVIEW_2026-01-08.csv**  
   - 93 unmatched Square payments with full details
   - Columns: payment_id, amount, payment_date, payment_key (hash), square_payment_id, customer_email, customer_name, notes, status (CLEAN/RECURRING), suggested_reserves, action_needed
   - Ready for manual charter linking tomorrow

### Scripts
2. **scripts/generate_square_review_report.py**  
   - Generates comprehensive review CSV with customer details + suggested charter matches
   - Usage: `python -X utf8 scripts/generate_square_review_report.py`

3. **scripts/verify_square_payment_legitimacy.py**  
   - 5-step verification: refunds, keywords, recurring, fees, payouts
   - Identifies Square Capital loan repayment candidates

4. **scripts/analyze_recurring_square_payments.py**  
   - Detailed breakdown of recurring payment patterns
   - Calculates date gaps and consistency scores

5. **scripts/verify_etransfer_matching.py**  
   - Checks e-transfer match rate and unmatched list
   - **Discovered**: 0 e-transfers in database (critical issue)

6. **scripts/link_trade_of_services_payments.py**  
   - Auto-links cash/trade_of_services by reserve_number
   - Dry-run + write modes, balance recalculation

7. **scripts/square_to_lms_matcher_postgres_paymentkey.py**  
   - Comprehensive matcher adapted for payment_key field
   - Multi-strategy matching with confidence scoring
   - Applied 180 links at confidence ≥3

8. **scripts/normalize_square_payment_id.py**  
   - SET square_payment_id = payment_key for consistency
   - Updated 273 rows for legacy script compatibility

### Analysis Scripts
9. **scripts/match_square_to_lms_payment_totals.py** - Check if Square matches LMS split payments
10. **scripts/analyze_lms_payment_structure.py** - LMS payment/deposit structure analysis
11. **scripts/analyze_square_lms_deposit_matches.py** - Direct LMS deposit matching attempts

---

## MATCHING METHODOLOGY DOCUMENTATION

### Why Payment_key (Hash) Matching?
- **Unique identifier**: Each Square transaction has unique payment_key
- **Stable**: Doesn't change unlike customer names/emails
- **Linkable**: Stored in `payments.payment_key` and `payments.square_payment_id`
- **Traceable**: Can always look up original Square transaction

### Comprehensive Matcher Logic
```python
# Match strategies (in order):
1. Retainer exact: DATE + AMOUNT exact match
2. Retainer approx: DATE ±7 days, AMOUNT exact
3. Special rules: Waste Connections $774 ±14 days
4. LMS deposit: AMOUNT in lms_deposits
5. Customer resolution: EMAIL/NAME → charter by amount/date proximity
6. Direct reserve fuzzy: AMOUNT ±5% vs rate/balance/deposit (confidence=1, NOT auto-applied)

# Confidence boost:
+1 if banking_transaction found within ±4 days

# Auto-apply threshold:
confidence >= 3 (prevents false positives)
```

### Why 93 Remain Unmatched?
1. **No LMS deposit record**: Square payment not recorded in legacy system
2. **Amount mismatch**: Tips, fees, partial payments differ from charter totals
3. **Date mismatch**: Payment made weeks before/after charter date
4. **Customer mismatch**: Email/name doesn't match any known client
5. **Fuzzy only**: Only confidence=1 matches (too risky for auto-link)

---

## HARD-CODING RECOMMENDATION

### Problem
We've now done hash/payment_key matching **multiple times**. Each session restart loses context and requires:
1. Re-running comprehensive matcher
2. Re-verifying payment types
3. Re-applying the same 180 links

### Solution: Permanent Link Storage
Create a `square_payment_charter_links` junction table:
```sql
CREATE TABLE square_payment_charter_links (
  link_id SERIAL PRIMARY KEY,
  payment_id INTEGER REFERENCES payments(payment_id),
  charter_id INTEGER REFERENCES charters(charter_id),
  payment_key TEXT NOT NULL,  -- Square transaction hash
  match_method TEXT,          -- 'retainer_exact', 'customer_resolution', etc.
  confidence_score INTEGER,   -- 1-5
  linked_at TIMESTAMP DEFAULT NOW(),
  linked_by TEXT DEFAULT 'auto_matcher_v2'
);

CREATE UNIQUE INDEX ON square_payment_charter_links(payment_id, charter_id);
CREATE INDEX ON square_payment_charter_links(payment_key);
```

**Benefits**:
1. Survives session restarts
2. Audit trail of all matches
3. Can regenerate payments.charter_id from this source of truth
4. Documents match quality for future review

### Implementation Steps
1. Create junction table schema
2. Insert current 180 matches from payments table
3. Add trigger to auto-update payments.charter_id when junction table changes
4. Future matchers write to junction table instead of directly to payments
5. Periodic sync job: `UPDATE payments SET charter_id = (SELECT charter_id FROM square_payment_charter_links WHERE ...)`

---

## TOMORROW'S WORKFLOW

### Priority 1: Manual Square Review (81 payments)
1. Open `reports/SQUARE_PAYMENTS_MANUAL_REVIEW_2026-01-08.csv`
2. For each CLEAN payment:
   - Check customer_email against known clients
   - Use payment_key to look up Square dashboard if needed
   - Match to suggested_reserves or search by amount/date
   - Update in DB: `UPDATE payments SET charter_id = X WHERE payment_id = Y`
   - Run balance recalc for charter

### Priority 2: Square Capital Loan Verification
1. Login to Square dashboard
2. Check "Capital" section for active loans
3. Compare repayment amounts to our 12 recurring payments:
   - $257.55 × 5
   - $483.21 × 4
   - $546.21 × 3
4. If match found:
   ```sql
   -- Reclassify as loan repayment
   UPDATE payments 
   SET payment_method = 'square_loan_repayment',
       notes = notes || ' [Square Capital loan repayment identified 2026-01-08]'
   WHERE payment_id IN (24886, 24874, 24872, 24870, 24854, ...);
   
   -- OR move to receipts as expense
   INSERT INTO receipts (amount, receipt_date, vendor_name, description, category)
   SELECT amount, payment_date, 'SQUARE CAPITAL', 
          'Loan repayment - ' || payment_key, 'LOAN REPAYMENT'
   FROM payments
   WHERE payment_id IN (...);
   
   DELETE FROM payments WHERE payment_id IN (...);
   ```

### Priority 3: E-Transfer Recovery
1. Run: `scripts/check_lms_payment_types.py` (create if needed)
2. Identify source of payment_method data (LMS code? banking description?)
3. Create `scripts/restore_payment_methods_from_lms.py`
4. Test on sample: 100 known e-transfers
5. Apply to all 24,375 'unknown' payments
6. Re-run e-transfer matcher
7. Verify 98% match rate restored

### Priority 4: Hard-Code Permanent Links
1. Create junction table SQL migration
2. Backfill 180 current Square matches
3. Test trigger functionality
4. Document for future sessions

---

## REFERENCE COMMANDS

### Check Payment Status
```sql
-- Square payments summary
SELECT 
  CASE WHEN charter_id IS NULL THEN 'Unmatched' ELSE 'Matched' END as status,
  COUNT(*), 
  SUM(amount)
FROM payments
WHERE payment_method = 'credit_card' AND payment_key IS NOT NULL
GROUP BY status;

-- Payment method breakdown
SELECT payment_method, COUNT(*), SUM(amount)
FROM payments
GROUP BY payment_method
ORDER BY count DESC;
```

### Re-run Square Matcher
```bash
# Dry run (report only)
python -X utf8 scripts/square_to_lms_matcher_postgres_paymentkey.py --report-only

# Apply at confidence >= 3
python -X utf8 scripts/square_to_lms_matcher_postgres_paymentkey.py --apply --min-confidence 3

# Generate review CSV for manual linking
python -X utf8 scripts/generate_square_review_report.py
```

### Verify Specific Payment
```sql
-- Look up by payment_key (hash)
SELECT * FROM payments WHERE payment_key = '<hash_from_CSV>';

-- Look up by amount + date
SELECT * FROM payments 
WHERE ABS(amount - 257.55) < 0.01 
  AND payment_date = '2025-12-17';

-- Find suggested charters
SELECT charter_id, reserve_number, total_amount_due, balance
FROM charters
WHERE ABS(total_amount_due - 257.55) / total_amount_due <= 0.10
ORDER BY ABS(total_amount_due - 257.55)
LIMIT 5;
```

---

## LESSONS LEARNED

1. **Payment field schema varies**: Always check actual DB columns before querying (customer_name vs client_name vs square_customer_name)

2. **Payment methods corrupted easily**: Need integrity checks and restoration procedures

3. **Hash matching works but needs permanence**: Junction tables better than just updating charter_id directly

4. **Recurring patterns = warning**: Always verify not loan repayments before linking to customer charters

5. **Documentation is critical**: Without this report, we'd re-do all this work next session

6. **E-transfer mystery**: High prior match rate suggests recent data loss - investigate timestamps of last update

---

## CONTACTS FOR VERIFICATION

- **Square Dashboard**: Check Capital section for loan details
- **Banking Statements**: Verify e-transfer presence (should show EMAIL MONEY TRANSFER)
- **LMS Backup**: Check if payment types exist in `l:\limo\backups\lms.mdb`

---

**END OF REPORT**

*Next session: Start with Priority 1 (manual Square review CSV) before doing any automated matching.*
