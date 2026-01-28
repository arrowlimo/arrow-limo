# TO-DO LIST - RECEIVABLES CLEANUP
## Date: January 11, 2026

---

## 🔴 PRIORITY 1 - IMMEDIATE (Do First)

### 1. Fix Comprehensive Audit Script
**File:** `scripts/comprehensive_billing_payment_audit.py`

**Problem:** Uses `charter_id` join instead of `reserve_number`, causing massive overstatement

**Fix Required:**
```python
# Line 97-103: Change FROM:
WITH charter_payments AS (
    SELECT charter_id, SUM(amount) AS total_paid
    FROM payments
    WHERE charter_id IS NOT NULL
    GROUP BY charter_id
)

# TO:
WITH charter_payments AS (
    SELECT 
        c.charter_id,
        COALESCE(SUM(p.amount), 0) as total_paid
    FROM charters c
    LEFT JOIN payments p ON p.reserve_number = c.reserve_number
    GROUP BY c.charter_id
)
```

**Apply same fix to:**
- Line 147-157 (status breakdown section)
- Any other CTEs using charter_id join

---

### 2. Verify 363 Unpaid Charters Against Legacy LMS Access Program
**Estimated Time:** 2-3 hours

**Process:**
1. Export 363 unpaid charter list with reserve numbers
2. Open legacy LMS Access program
3. For EACH charter, verify:
   - ✅ Actual charge amount (does it match `total_amount_due`?)
   - ✅ Payment status (is it paid in LMS but not in almsdata?)
   - ✅ Charter type:
     - [ ] Trade/barter (no payment expected)
     - [ ] Free promotional
     - [ ] Cancelled (should be $0)
     - [ ] Complimentary
     - [ ] Staff/owner personal use
   - ✅ Notes field (any special instructions?)

**Expected Outcome:**
- Identify charters that SHOULD be $0 (trade/free/cancelled)
- Identify payments recorded in LMS but missing from almsdata
- Identify true bad debt

**Script to Create:**
```bash
# Create export for LMS verification
scripts/export_unpaid_for_lms_verification.py
  - Output: reports/unpaid_charters_for_lms_check_2026-01-11.csv
  - Columns: charter_id, reserve_number, charter_date, customer_name, 
             total_amount_due, total_paid, outstanding, status, notes
```

---

### 3. Categorize the 363 Unpaid Charters
**After LMS verification, group into:**

**Category A: Write-Offs (Bad Debt)**
- Bankruptcies (including $29K production company)
- Customers who ghosted/disappeared
- Uncollectable after reasonable attempts
- **Action:** Create write-off entries with proper accounting

**Category B: Should Be Zero (No Payment Expected)**
- Trade/barter agreements
- Complimentary charters
- Staff/owner personal use
- Promotional giveaways
- **Action:** Update `total_amount_due = 0` and add notes

**Category C: Cancelled But Not Marked**
- Charters cancelled but still showing charges
- **Action:** Update `status = 'cancelled'` and `total_amount_due = 0`

**Category D: Payments Missing from System**
- Paid in LMS but not in almsdata
- Check stubs/receipts exist but not recorded
- **Action:** Add missing payment records

**Category E: Legitimate Receivables (Active Collection)**
- Recent charters (< 90 days)
- Customers on payment plans
- Invoices sent, awaiting payment
- **Action:** Generate collection report, send reminders

---

## ⚠️ PRIORITY 2 - IMPORTANT (Do Second)

### 4. Process $29,000 Production Company Bankruptcy Write-Off
**Estimated Time:** 30-60 minutes

**Information Needed:**
- [ ] Company name: ________________________________
- [ ] Charter ID(s): ________________________________
- [ ] Reserve number(s): ____________________________
- [ ] Date of bankruptcy: ___________________________
- [ ] Bankruptcy court case #: ______________________
- [ ] Supporting documents: _________________________

**Process:**
1. Verify amount ($29,000) against LMS Access program
2. Create accounting entries:
   ```sql
   -- Mark charters as written off
   UPDATE charters 
   SET status = 'written_off_bankruptcy',
       notes = CONCAT(notes, ' | Write-off: Production Company XYZ bankruptcy [date]')
   WHERE reserve_number IN (...);
   
   -- Create accounting journal entry (if needed)
   -- Bad Debt Expense: $29,000 (DR)
   -- Accounts Receivable: $29,000 (CR)
   ```
3. Generate write-off report for accounting/tax purposes
4. File bankruptcy documentation

---

### 5. Investigate 171 Negative Payments (-$40,136.60)
**File:** Already analyzed in `scripts/analyze_negative_payments.py`

**Review Required:**
1. Top 20 largest negatives (output from script):
   - Charter 009583: -$1,760.00
   - Charter 017301: -$1,458.00
   - Charter 017012: -$1,302.00
   - etc.

2. Verify each is properly offset:
   ```sql
   -- For each reserve number with negative payment:
   SELECT 
       p.payment_id,
       p.payment_date,
       p.amount,
       p.payment_method,
       p.notes
   FROM payments p
   WHERE p.reserve_number = 'XXXXXX'
   ORDER BY p.payment_date;
   ```

3. Check if negatives are:
   - [ ] Refunds (should match earlier positive payment)
   - [ ] Chargebacks (card reversals)
   - [ ] Corrections (duplicate payment reversals)
   - [ ] NSF fees (bank rejected payment)

**Action:** Create `scripts/validate_negative_payments.py` to auto-match

---

### 6. Process 62 Overpaid Charters ($38,438.22)
**Top 10 Overpayments:**
- Charter 019619: $6,150.00 overpaid
- Charter 019666: $5,565.25 overpaid
- Charter 019648: $5,558.03 overpaid
- Charter 019669: $3,651.29 overpaid (marked as `refund_pair`)
- etc.

**For Each Overpaid Charter:**
1. Check if refund already issued (look for negative payment)
2. Contact customer:
   - Option A: Issue refund check
   - Option B: Apply credit to future booking
   - Option C: Customer wants to donate (get written authorization)

3. Process refund:
   ```sql
   -- If issuing refund, add negative payment record:
   INSERT INTO payments (reserve_number, amount, payment_date, payment_method, notes)
   VALUES ('019619', -6150.00, CURRENT_DATE, 'check_refund', 'Overpayment refund - Check #XXXX');
   ```

---

## 📊 PRIORITY 3 - ROUTINE (Do Third)

### 7. Create Corrected Receivables Report
**Script:** Fix `scripts/analyze_outstanding_receivables_v2.py` (has date arithmetic bugs)

**Output:**
- Age analysis (30/60/90/180/365+ days old)
- Amount distribution ($0-100, $100-500, etc.)
- Top 20 largest outstanding
- Status breakdown
- Customer breakdown

**Use for:**
- Monthly management review
- Collection priority ranking
- Financial statement preparation

---

### 8. Normalize Charter Status Field
**Problem:** Inconsistent capitalization:
- "Closed" vs "closed" vs "CLOSED"
- "Cancelled" vs "cancelled" vs "CANCELLED"

**Fix:**
```sql
UPDATE charters
SET status = LOWER(TRIM(status))
WHERE status IS NOT NULL;

-- Standardize common values:
UPDATE charters SET status = 'closed' WHERE status IN ('Closed', 'CLOSED');
UPDATE charters SET status = 'cancelled' WHERE status IN ('Cancelled', 'CANCELLED', 'Canceled');
UPDATE charters SET status = 'paid_in_full' WHERE status IN ('Paid in Full', 'PAID IN FULL');
```

**Create enum or constraint:**
```sql
ALTER TABLE charters
ADD CONSTRAINT chk_status
CHECK (status IN ('closed', 'cancelled', 'paid_in_full', 'deposit_received', 
                  'confirmed', 'in_route', 'completed', 'refund_pair', 
                  'written_off_bankruptcy', 'trade_barter', 'complimentary'));
```

---

### 9. Update Session Documentation
**File:** `CHARTER_BILLING_PAYMENT_AUDIT_FINDINGS.md`

**Problem:** Based on buggy audit data (shows $9.5M outstanding instead of $208K)

**Action:**
- [ ] Add prominent warning banner at top: "⚠️ DATA IN THIS REPORT IS INCORRECT - See SESSION_LOG_2026-01-10_Receivables_Audit.md for corrected figures"
- [ ] OR: Regenerate entire report with corrected data
- [ ] OR: Delete and replace with corrected version

---

### 10. Create Monthly Receivables Monitoring Script
**New Script:** `scripts/monthly_receivables_report.py`

**Features:**
- Aging analysis (current, 30, 60, 90, 120+ days)
- Trend analysis (compare to prior month)
- Collection rate calculation
- Top 10 largest outstanding
- Auto-email to management

**Schedule:** Run on 1st of each month

---

## 🛠️ PRIORITY 4 - TECHNICAL CLEANUP

### 11. Archive/Delete Buggy Scripts
**Files to review:**
- `scripts/delete_orphaned_payments.py` - DONE, keep for reference
- `scripts/comprehensive_billing_payment_audit.py` - FIX, don't delete (useful once corrected)
- `CHARTER_BILLING_PAYMENT_AUDIT_FINDINGS.md` - MARK AS INCORRECT or regenerate

---

### 12. Create Data Validation Tests
**New Script:** `scripts/test_receivables_calculations.py`

**Tests:**
1. Verify all payments link to charters via reserve_number
2. Verify no charter has both charter_id payments AND reserve_number payments
3. Verify total_amount_due >= 0 for all non-cancelled charters
4. Verify no overpaid charters without corresponding refund record
5. Verify negative payments have matching positive payments

**Run:** Weekly or before/after major data imports

---

## 📅 TIMELINE

### Day 1 (January 11, 2026):
- [ ] **Morning:** Fix comprehensive audit script, export unpaid list
- [ ] **Afternoon:** LMS verification (363 charters) - batch 1 of 2

### Day 2 (January 12, 2026):
- [ ] **Morning:** LMS verification - batch 2 of 2
- [ ] **Afternoon:** Categorize results, create action lists

### Day 3 (January 13, 2026):
- [ ] **Morning:** Process write-offs (including $29K)
- [ ] **Afternoon:** Update zero-balance charters

### Day 4 (January 14, 2026):
- [ ] **Morning:** Process overpaid refunds
- [ ] **Afternoon:** Validate negative payments

### Day 5 (January 15, 2026):
- [ ] **Morning:** Generate corrected reports
- [ ] **Afternoon:** Create monitoring scripts for ongoing use

---

## ✅ SUCCESS CRITERIA

**Project Complete When:**
- [ ] All 363 charters verified against LMS Access program
- [ ] Zero-balance charters updated (trade/free/cancelled)
- [ ] $29K bankruptcy write-off processed
- [ ] Overpaid charters resolved (refunds issued or credits applied)
- [ ] Negative payments validated and documented
- [ ] Corrected receivables report generated
- [ ] Monthly monitoring script created and tested
- [ ] Comprehensive audit script fixed and re-run
- [ ] Documentation updated with corrected figures

**Final Outcome:**
- Accurate receivables report showing ~$208K outstanding
- Clear categorization of all unpaid balances
- Automated monthly monitoring in place
- Clean, validated data ready for financial statements

---

## 📝 NOTES

### Important Reminders:
1. **ALWAYS use `reserve_number` for payment-charter joins, NEVER `charter_id`**
2. Verify against legacy LMS Access before making bulk changes
3. Keep backups before any UPDATE/DELETE operations
4. Document all write-offs with supporting evidence
5. Get customer authorization for any refunds over $1,000

### Questions for User:
1. What is the production company name for $29K write-off?
2. Do you have access to legacy LMS Access program files?
3. Who should approve write-offs? (Owner/CFO/Controller?)
4. What's the refund policy for overpayments?
5. Any known trade/barter agreements we should account for?

---

**Prepared by:** GitHub Copilot  
**Date:** January 10, 2026, 3:30 AM  
**Next Session:** January 11, 2026 (morning)  
**Estimated Total Time:** 16-20 hours over 5 days
