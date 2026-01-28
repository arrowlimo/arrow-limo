# Reconciliation Audit - Action Checklist
**Generated:** January 20, 2026  
**Status:** Audit complete, manual decisions needed before fixes can execute

---

## Pre-Execution Checklist (Before Running Any Fixes)

### ☐ 1. Review Audit Findings
- [ ] Read: `RECONCILIATION_AUDIT_COMPLETE_FINDINGS.md`
- [ ] Review: Top 20 unmatched deposits (in CSV export)
- [ ] Review: All 36 zero-due charters (in audit output)
- [ ] Review: All 47 actual overpayments (in audit output)

### ☐ 2. Commit Schema to Memory
- [ ] Read: `DATABASE_SCHEMA_REFERENCE.md`
- [ ] Memorize: reserve_number is BUSINESS KEY (NOT charter_id!)
- [ ] Memorize: Key tables (charters, payments, banking_transactions, receipts)
- [ ] Understand: Reconciliation query patterns

### ☐ 3. Categorize Zero-Due Situations (36 charters)

**For each of the 36 zero-due charters, manually determine:**

**Pattern A: Charges should be restored**
- If: Customer was charged, paid partially, but charge was mistakenly deleted
- Action: RESTORE charge records
- Count: _____

**Pattern B: Payment should be refunded**
- If: Charge was correctly deleted, but payment wasn't refunded
- Action: REFUND customer or convert to credit
- Count: _____

**Pattern C: Retainer/Nonrefundable**
- If: Charge was intentionally deleted, payment is nonrefundable deposit
- Action: Mark retainer_received = TRUE in charters
- Count: _____

**Pattern D: Other/Unknown**
- If: Unclear why charges deleted or payment exists
- Action: Investigate with business owner
- Count: _____

**Total must equal 36: A + B + C + D = 36**

### ☐ 4. Categorize Actual Overpayments (47 charters)

**For each of the 47 overpayment charters, verify:**

**Question 1: Is this customer due a refund?**
- YES: Include in refund batch
- NO: Proceed to Question 2
- Count Y/N: _____

**Question 2: Should this be marked as a retainer?**
- YES: Update status + mark retainer_received = TRUE
- NO: Proceed to Question 3
- Count Y/N: _____

**Question 3: Is this a duplicate payment entry?**
- YES: Mark as duplicate for removal/investigation
- NO: Proceed to Question 4
- Count Y/N: _____

**Question 4: Is there a data entry error?**
- YES: Note the error and fix
- NO: Accept as-is (legitimate overpayment)
- Count Y/N: _____

### ☐ 5. Investigate $867k Unmatched Deposits

**Before re-running Phase 1 with new parameters, understand the gap:**

**Step 1: Sample 10-20 unmatched deposits**
- Look in CSV export: `unmatched_deposits_*.csv`
- For each, manually search for matching payment in database
- Does matching payment exist? If YES:
  - Date difference: How many days?
  - Amount difference: How much off?
  - Note the gap

**Step 2: Determine new matching parameters**
- Current: Amount ±$0.01, Date ±7 days
- Proposed: Amount ±$1.00, Date ±60 days (for old transactions)
- Does this help? _____

**Step 3: Identify non-customer deposits**
- Which unmatched deposits are NOT customer payments?
  - Bank transfers? Count: _____
  - Vendor refunds? Count: _____
  - Interest/fees? Count: _____
  - Other? Count: _____
- Filter these OUT before matching

---

## Fix Execution Checklist (After Manual Decisions)

### ☐ 6. Backup Database
```sql
-- In SQL terminal:
pg_dump -h localhost -U postgres -d almsdata -F c > backup_before_reconciliation_fixes.dump
```
- [ ] Backup completed successfully
- [ ] Backup file size: _________ MB

### ☐ 7. Apply Generated Fixes
- [ ] Open: `reconciliation_fixes_20260120_171950.sql`
- [ ] Review each fix (already generated - ready to execute)
- [ ] Execute: Run penny rounding fixes
  ```sql
  -- Copy/paste from fix script
  ```
- [ ] Execute: Verify retainers marked
  ```sql
  -- Copy/paste from fix script
  ```

### ☐ 8. Manual Fixes (Based on Categorization)

**Fix Pattern A: Restore charges (if needed)**
- [ ] Create charges for zero-due charters where decided to restore
- For each: `INSERT INTO receipts (...) VALUES (...)`
- Commit after each batch

**Fix Pattern B: Process refunds (if needed)**
- [ ] Generate refund list for customers owed money
- [ ] Determine refund method (credit, reversal, cash)
- [ ] Document in notes: "Refund - overpayment reconciliation"

**Fix Pattern C: Mark retainers (if applicable)**
- [ ] Update charters to mark retainer_received = TRUE for legitimate retainers
- [ ] Verify status is set correctly

**Fix Pattern D: Investigate/Escalate**
- [ ] Document any unclear situations for business owner review

### ☐ 9. Re-run Phase 1 with New Parameters

**Update Phase 1 script with new matching rules:**
```python
# OLD: AND ABS(p.payment_date - %s) <= 7
# NEW: AND ABS(p.payment_date - %s) <= 60

# OLD: WHERE ABS(p.amount - %s) < 0.01
# NEW: WHERE ABS(p.amount - %s) < 1.00
```

- [ ] Update `reconciliation_phase1_fixed.py` with new parameters
- [ ] Run: `python -X utf8 reconciliation_phase1_fixed.py`
- [ ] Compare results to original Phase 1

**Questions:**
- How many newly matched? _____
- How much remaining unmatched? $____
- Is gap closed to acceptable level? YES / NO

### ☐ 10. Validation Tests

**Test 1: Spot-check 20 random charters**
```sql
SELECT c.charter_id, c.reserve_number, c.total_amount_due, 
       SUM(p.amount) as total_paid,
       c.total_amount_due - SUM(p.amount) as calc_balance,
       c.balance as stored_balance
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.charter_id IN (100, 500, 1000, 2000, 5000, 10000, 15000, 18000, ...)
GROUP BY c.charter_id
```

- [ ] Run query for 20 random charters
- [ ] Verify: calc_balance = stored_balance (or documented reason if not)
- [ ] Pass/Fail: _____

**Test 2: Zero-due with payments should be 0**
```sql
SELECT COUNT(*)
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.total_amount_due < 0.01
  AND p.payment_id IS NOT NULL
GROUP BY c.charter_id
HAVING COUNT(p.payment_id) > 0
```

- [ ] Expected: 0 (after fixes)
- [ ] Actual: _____
- [ ] Pass/Fail: _____

**Test 3: Verify overpayments categorized**
- [ ] Run query to check status of 47 overpayment charters
- [ ] Verify marked as: retainer, refund-required, or other
- [ ] Pass/Fail: _____

### ☐ 11. Generate Final Reconciliation Report

After all fixes, generate summary:
```
- Charters reconciled: 18,679
- Issues found: 115
- Issues fixed: _____
- Issues remaining (documented): _____
- Unmatched deposits gap: $867k → $_____ (improved by $___k)
```

---

## Sign-Off Checklist

### ☐ 12. Confirm with Business Owner

Before closing reconciliation:
- [ ] Reviewed findings with owner
- [ ] Owner approval for refunds (if any): _________ amount approved
- [ ] Owner approval for retainer markings: _________ count approved
- [ ] Owner approval for charge restorations: _________ count approved

### ☐ 13. Document Results

- [ ] Create final reconciliation report
- [ ] Archive all fix scripts and backups
- [ ] Document any remaining open issues
- [ ] Update procedures for going-forward (prevent future issues)

### ☐ 14. Commit Changes

```sql
-- After all fixes verified:
COMMIT;
```

- [ ] All changes committed to database
- [ ] No uncommitted transactions
- [ ] Backup of final state created: `backup_after_reconciliation_fixes.dump`

---

## Decision Tracking

### Zero-Due Categorization Results

| Category | Count | % | Notes |
|----------|-------|---|-------|
| A: Restore charges | ___ | __% | |
| B: Refund payment | ___ | __% | |
| C: Mark retainer | ___ | __% | |
| D: Other/investigate | ___ | __% | |
| **TOTAL** | **36** | **100%** | |

### Overpayment Categorization Results

| Question | YES | NO | Notes |
|----------|-----|----|----|
| Refund due? | ___ | ___ | |
| Mark retainer? | ___ | ___ | |
| Duplicate entry? | ___ | ___ | |
| Data error? | ___ | ___ | |

### Unmatched Deposits Investigation

| Finding | Count | Action |
|---------|-------|--------|
| Date mismatch (>7 days) | ___ | Increase window to 60 days |
| Amount mismatch (>$0.01) | ___ | Increase tolerance to $1.00 |
| Non-customer deposits | ___ | Filter out |
| Missing payment records | ___ | Create payment records |
| **Remaining unmatched** | **$___** | Document reason |

---

## Time Estimate

| Task | Time | Status |
|------|------|--------|
| Manual review (36 zero-due) | 30-45 min | |
| Manual review (47 overpayments) | 30-45 min | |
| Investigate $867k gap | 30-45 min | |
| Execute fixes | 15-30 min | |
| Re-run Phase 1 | 10-15 min | |
| Validation tests | 15-30 min | |
| **TOTAL ESTIMATE** | **2-3 hours** | |

---

## Next Session Start Here

If session resets:

1. ✅ Read: `DATABASE_SCHEMA_REFERENCE.md` (schema in memory)
2. ✅ Read: `SESSION_RECONCILIATION_SUMMARY_20260120.md` (what we found)
3. 🔄 Fill out: This checklist with manual categorization results
4. 🔄 Execute: Approved fixes
5. 🔄 Validate: Re-run Phase 1 and tests
6. 🚀 Complete: Document final results

---

**Generated:** January 20, 2026  
**Expected completion:** Within 2-3 hours after manual decisions  
**Backup taken:** Before starting fixes  
**Status:** Ready to execute once manual categorizations complete
