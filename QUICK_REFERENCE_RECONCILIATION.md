# QUICK REFERENCE - Reconciliation Audit
**Print this or keep handy**

---

## The 3 Critical Issues (In Priority Order)

### 🚨 Issue #1: $867k Unmatched Banking Deposits
```
713 banking deposits with NO matching payment record
Total: $867,745.22

Why: 
- Date window too small (7 days)?
- Amount tolerance too strict (±$0.01)?
- Payment records don't exist?
- Non-customer deposits mixed in?

Fix:
- Expand date window to 60 days
- Expand amount tolerance to ±$1.00
- Create missing payment records if needed
- Filter non-customer deposits
```

### 🔴 Issue #2: 36 Charters with $0 Due But Payments Exist
```
Charter due = $0
But payments = $50-$200+
Status = Closed

What it means:
Charges were deleted but payments were never reversed

What to do:
A) Restore charges if deleted in error
B) Refund payment if charge correctly deleted
C) Mark as retainer if nonrefundable deposit
D) Other (investigate case-by-case)

Example: Charter 165 (Reserve 001188)
  Due: $0
  Paid: $206.70
  Question: Where is the $206.70?
```

### 🟠 Issue #3: 47 Actual Overpayments (Non-Retainer)
```
47 charters where: Paid > Due (and NOT marked retainer)

Examples:
- Charter 56: Due $1,073 → Paid $7,541 (Overpay $6,468)
- Charter 51: Due $1,250 → Paid $7,392 (Overpay $6,142)
- Charter 1:  Due $250  → Paid $2,279 (Overpay $2,029)

Questions for each:
1. Is customer due a refund?
2. Should this be marked as retainer?
3. Is this a duplicate payment entry?
4. Is there a data entry error?
```

---

## The Business Rule You Must Remember

### 🔑 reserve_number is the BUSINESS KEY

```sql
✅ CORRECT:
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number

❌ WRONG:
LEFT JOIN payments p ON p.charter_id = c.charter_id
(This will NOT work - charter_id missing on many payments)
```

**If you forget this rule, you'll corrupt the reconciliation!**

---

## Files Navigation

| Need... | Open This File |
|---------|----------------|
| Schema reference | `DATABASE_SCHEMA_REFERENCE.md` |
| What was found | `SESSION_RECONCILIATION_SUMMARY_20260120.md` |
| Make decisions | `RECONCILIATION_ACTION_CHECKLIST.md` |
| Full details | `RECONCILIATION_AUDIT_COMPLETE_FINDINGS.md` |
| Navigation | `RECONCILIATION_INDEX_START_HERE.md` |
| Re-run audit | `reconciliation_phase1_fixed.py` |
| Execute fixes | `reconciliation_fixes_*.sql` |

---

## Decision Template

### For Each of 36 Zero-Due Charters

```
Charter ID: _____
Reserve: _____
Paid: $_____
Status: _____

Categorize as:
☐ A) RESTORE charges (if deleted in error)
☐ B) REFUND payment (if charge correctly deleted)
☐ C) MARK RETAINER (if nonrefundable deposit)
☐ D) OTHER (describe): _____

Decision made by: _________ Date: _____
```

### For Each of 47 Overpayment Charters

```
Charter ID: _____
Reserve: _____
Due: $_____ Paid: $_____
Overpayment: $_____

Is customer due refund? ☐ YES ☐ NO
Mark as retainer? ☐ YES ☐ NO
Duplicate payment? ☐ YES ☐ NO
Data entry error? ☐ YES ☐ NO

Action: _____
Decision by: _________ Date: _____
```

---

## SQL Query Reference

### Find unmatched deposits
```sql
SELECT * FROM banking_transactions bt
WHERE credit_amount > 0
  AND NOT EXISTS (
    SELECT 1 FROM payments p 
    WHERE ABS(p.amount - bt.credit_amount) < 0.01
      AND ABS(p.payment_date - bt.transaction_date) <= 7
  )
ORDER BY transaction_date DESC;
```

### Find zero-due with payments
```sql
SELECT c.charter_id, c.reserve_number, c.total_amount_due,
       COUNT(p.payment_id), SUM(p.amount)
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.total_amount_due < 0.01
GROUP BY c.charter_id
HAVING COUNT(p.payment_id) > 0;
```

### Find overpayments
```sql
SELECT c.charter_id, c.reserve_number, c.total_amount_due,
       SUM(p.amount) as paid,
       SUM(p.amount) - c.total_amount_due as overpay
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
GROUP BY c.charter_id
HAVING SUM(p.amount) > c.total_amount_due + 0.01;
```

---

## Before Running Any Fixes

- [ ] 1. Backup database
- [ ] 2. Get business owner approval
- [ ] 3. Review SQL script
- [ ] 4. Make all manual decisions (36 + 47)
- [ ] 5. Document decisions
- [ ] 6. Then execute

---

## After Running Fixes

- [ ] 1. Run Phase 1 audit again with new parameters
- [ ] 2. Check if unmatched deposits reduced
- [ ] 3. Spot-check 20 random charters
- [ ] 4. Verify zero-due situations resolved
- [ ] 5. Generate final report
- [ ] 6. Document lessons learned

---

## Key Concepts

**balance = total_amount_due - SUM(payments)**
- Positive = customer owes money
- Zero = fully paid
- Negative = overpaid (stored as 0 for accounting)

**reserve_number = charter key**
- Use this to link charters ↔ payments
- DO NOT use charter_id

**Retainer = nonrefundable deposit**
- Usually on cancelled charters
- OK to keep (not a refund)

**$0.01 rounding = penny difference**
- Add $0.01 charge to balance to $0
- Common after conversions/conversions

---

## Status Check

| What | Status | Where |
|------|--------|-------|
| Audit phase 1 | ✅ Done | reconciliation_phase1_fixed.py |
| Audit phase 2-3 | ✅ Done | reconciliation_phase2_3_fixes.py |
| Schema docs | ✅ Done | DATABASE_SCHEMA_REFERENCE.md |
| Manual decisions | 🔄 Pending | RECONCILIATION_ACTION_CHECKLIST.md |
| Fixes ready | ✅ Done | reconciliation_fixes_*.sql |
| Execute | 🔄 Ready | After decisions approved |

---

## Contact Points

**If unsure about schema:**
→ Read: DATABASE_SCHEMA_REFERENCE.md

**If unsure about what was found:**
→ Read: SESSION_RECONCILIATION_SUMMARY_20260120.md

**If unsure about what to do:**
→ Read: RECONCILIATION_ACTION_CHECKLIST.md

**If need all context:**
→ Read: RECONCILIATION_INDEX_START_HERE.md

---

**Generated:** January 20, 2026  
**Print & Keep Handy:** YES  
**Update:** After manual decisions made
