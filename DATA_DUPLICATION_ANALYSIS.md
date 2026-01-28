# DATA DUPLICATION ANALYSIS & CONSOLIDATION ROADMAP
Generated: January 20, 2026

## Executive Summary

**The Good News:**
✅ Your core data (payments, receipts, charters, GL) uses relationships properly
✅ Foreign keys (reserve_number, charter_id, account_number) are correct pattern
✅ No critical duplication in main transaction tables

**The Problems:**
⚠️ **4,153 backup/duplicate tables** clogging the database (test tables, year-based copies)
⚠️ **229 tables with redundant amount columns** (storing calculated values)
⚠️ **890 duplicate column names** across tables (creates maintenance confusion)
⚠️ **Vendor data** duplicated in receipts + GL (should use relationship)

**The Impact:**
- Database bloat from unnecessary backups
- Data inconsistency risks (same data in multiple places)
- Query performance degradation
- Increased backup size and recovery time
- Hard to maintain and version control

---

## CRITICAL ISSUE: Backup/Duplicate Tables

### Scale of Problem
- **4,153 tables** identified as potential duplicates or backups
- Many are automatic snapshots from testing/debugging
- Examples:
  - 50+ `banking_transactions_*_backup` tables (mostly from 2012-2017)
  - 10+ `payments_backup_*` tables
  - Multiple `charters_backup_*` tables
  - Year-dated snapshots (Scotia 2012 has 7 backups)

### Impact
Each backup table = full copy of data. Example:
- `banking_transactions`: 27 columns × 100,000s rows = 50 MB
- × 50 backups = **2.5 GB of dead code**

### Recommendations

**Phase 3 - Backup Table Cleanup:**
```
TIER 1 (Delete immediately - safe):
- All `_backup_20XX` tables (test snapshots)
- All `_archive` tables (if data is in main table)
- All year-dated copies (2012-2017 backups)
- All `_dedup`, `_fix`, `_cleanup` tables
Estimated recovery: **1-2 GB**

TIER 2 (Archive to external, then delete):
- All banking_transactions_1615_backup_201X-2017 (10 tables)
- All scotia/cibc specific backups
- All qb, square, legacy payment backups
Reason: Historical reference, but not needed in live DB
Estimated recovery: **500 MB - 1 GB**

TIER 3 (Evaluate individually):
- Recent backups (last 30 days) - keep in DB
- Business logic copies (lms_charges, charter_charges versions)
- Staging/import tables (might need for audit trail)
Estimated recovery: **100-200 MB after evaluation**
```

---

## ISSUE 2: Redundant Amount Columns

### The Problem
Many tables store multiple amount values when they should store ONE source and calculate others:

**Example - Receipts Table:**
```
- gross_amount (total with tax)
- net_amount (total without tax)
- gst_amount (calculated)
- revenue (same as gross_amount? or net_amount?)
- fuel_amount (subset)
- owner_personal_amount (subset)
- gst_exempt (flag, not amount)
```

**Current:**
- Storing ALL 7 amounts independently
- Risk: gross ≠ net + gst (data corruption possible)
- Risk: If revenue changes, other amounts out of sync

**Better:**
- Store: `gross_amount`, `gst_rate`
- Calculate: `gst_amount = gross * gst_rate / (1 + gst_rate)`
- Calculate: `net_amount = gross_amount - gst_amount`
- Store: `revenue` only if it's genuinely different purpose (it's not - it's same as gross_amount)

### Tables with Redundant Amounts (229 total)
Top offenders:
- `accounting_entries`: debit_amount, credit_amount, balance (balance = sum of all debits/credits)
- `active_floats_detailed`: float_amount, collection_amount, expense (all related)
- `receipts`: 7 amount columns (see above)
- `charter_charges`: multiple charge types as separate columns
- `banking_transactions`: debit_amount, credit_amount, balance

### Recommendations

**Phase 3a - Consolidate Amount Columns:**
```
AUDIT (2 hours):
1. Verify which amounts are truly independent vs. calculated
   - Run: audit_amount_dependency.py (creates it)
2. Check if redundant amounts ever differ (data corruption check)
3. Identify any business logic that depends on storing ALL amounts

FIX (1 day):
1. For each table, keep ONLY atomic values
   - Delete: calculated amounts (store formula in view instead)
   - Delete: derived sums (use SUM() on original amounts)
2. Create VIEW that calculates all amounts on-the-fly
3. Update queries to use VIEW instead of table columns

Example:
  - Table receipts: keep gross_amount, gst_rate, fuel_amount (atomic)
  - DROP: net_amount, gst_amount, revenue (calculated)
  - CREATE VIEW receipts_calculated:
    SELECT *,
      gross_amount * gst_rate / (1 + gst_rate) as gst_amount,
      gross_amount - (gross_amount * gst_rate / (1 + gst_rate)) as net_amount
    FROM receipts

BENEFIT: 
  ✅ Single source of truth for each value
  ✅ Impossible to have mismatches
  ✅ Always calculated fresh (no stale data)
  ✅ Saves storage (fewer columns)
```

---

## ISSUE 3: Data Duplication Across Tables

### Pattern 1: Vendor Data Stored Multiple Places

**Current State:**
- Receipts: `vendor_name` (58,329 rows with vendor)
- Payments: No vendor column (relies on receipt lookup?)
- General Ledger: `memo_description` contains vendor names (83,285 rows)

**Risk:** 
- "ABC Plumbing" might be stored as:
  - "ABC PLUMBING" in receipts
  - "abc plumbing" in GL
  - "ABC Plumbing Inc." in vendor table
- Reports show 3 different vendors instead of 1

**Better Solution:**
```sql
-- Create vendor master table (ONE source of truth)
CREATE TABLE vendor_master (
  vendor_id SERIAL PRIMARY KEY,
  vendor_name VARCHAR NOT NULL UNIQUE,
  canonical_name VARCHAR,  -- "ABC Plumbing" normalizes all variants
  category VARCHAR,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Then update tables to use FK:
ALTER TABLE receipts ADD COLUMN vendor_id INTEGER REFERENCES vendor_master;
ALTER TABLE general_ledger ADD COLUMN vendor_id INTEGER REFERENCES vendor_master;

-- Benefits:
✅ Consistent vendor naming across all reports
✅ One place to fix misspellings
✅ Can add vendor categories, contact info, etc.
✅ Queries become: JOIN vendor_master ON vendor_id
```

### Pattern 2: Payment Method Data
Current: `payment_method` in 61+ tables, each might have different values
Better: Create `payment_method_master` table, use FKs

### Pattern 3: Charter/Account/Reserve Data
Current: ✅ CORRECT - Multiple tables have FK references (this is right)
Why?: Each transaction needs to link to customer/charter, so storing ID is correct pattern

---

## ISSUE 4: Column Name Proliferation

### The Problem
890 column names appear in multiple tables. Most are normal (id, created_at, updated_at), but some create confusion:

**Confusing Examples:**
- `debit_amount` in 59 tables (sometimes means money out, sometimes money in)
- `balance` in 70 tables (sometimes current, sometimes daily, sometimes cumulative?)
- `status` in 105 tables (each has different valid values)
- `amount` in 69 tables (amount of what? expense? payment? charge?)
- `description` in 164 tables (free text? standardized codes? rich text?)

### Impact
- New developers don't know what each column means
- Queries become ambiguous: "JOIN accounting_entries WHERE balance > 100"
- Hard to enforce consistency

### Better Practice
```sql
-- Use namespaced columns:
-- Banking table:
  banking_balance         (specific to account balance)
  banking_debit_amount    (payment out)
  banking_credit_amount   (payment in)

-- Receipt table:
  expense_amount          (how much was spent)
  receipt_status          (paid, pending, reimbursed, etc.)
  
-- Charter table:
  charter_status          (booked, completed, cancelled, etc.)
  charter_balance_due     (amount still owed)
```

---

## WHAT YOU'RE DOING RIGHT ✅

1. **Foreign Keys for Relationships** - CORRECT PATTERN
   - Multiple tables reference charter_id, reserve_number, account_number
   - This is the right way (use FK, not duplicate the data)

2. **Transaction-Level Detail** - CORRECT
   - Payments and receipts each store full detail
   - GL stores summary aggregations
   - This separation is good

3. **Tax Data** - CORRECT (verified in tax ledger audit)
   - Single general_ledger table with date column
   - No redundant yearly copies
   - Tax calculations preserved with precision

---

## IMPLEMENTATION ROADMAP

### Phase 3: Data Duplication Cleanup
```
Timeline: ~1-2 weeks (can be spread over time)

Week 1 - Preparation & Low-Risk Cleanup:
  Day 1-2: audit_amount_dependency.py (analyze)
  Day 2-3: Delete Tier 1 backup tables (automatic snapshots)
           → Recovery: 1-2 GB
  Day 3-4: Archive Tier 2 backup tables (historical, but not needed live)
           → Recovery: 500 MB - 1 GB

Week 2 - Master Table Creation:
  Day 1-2: Create vendor_master table
           Populate from distinct vendor_name values
           Add FK columns to receipts, general_ledger
  Day 2-3: Create payment_method_master (if needed)
  Day 3-4: Verify referential integrity

Week 3 - Views for Calculated Amounts:
  Day 1-2: Create views that calculate derived amounts
           Update dependent queries to use views
  Day 2-3: Test all reports still work
  Day 3-4: Clean up redundant columns (after confirming everything works)

Total Recovery Potential: 2-3 GB of storage
Benefits: Cleaner DB, faster backups, single source of truth
```

### Quick Wins (Can do this week):
```sql
-- 1. Count and list all backup tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND (table_name LIKE '%_backup%' OR table_name LIKE '%_archive%')
ORDER BY table_name;

-- 2. List which ones have zero rows (safe to delete)
SELECT t.table_name, ROUND(pg_total_relation_size(schemaname||'.'||tablename) / 1024.0, 2) as size_kb
FROM pg_tables t
WHERE schemaname = 'public'
  AND (table_name LIKE '%_backup%' OR table_name LIKE '%_archive%')
ORDER BY size_kb DESC;

-- 3. Create script to drop all 2012-2017 year-based backups
-- (safe because: we have full backups, and these are old snapshots)
```

---

## SUMMARY: To Answer Your Original Question

**"Are there tables or columns being duplicated? Relationships are better, are they not?"**

### YES, but with nuance:

**BAD Duplication (exists, should be fixed):**
- ❌ 4,153 backup/test tables (should be archived or deleted)
- ❌ 229 tables with redundant calculated columns (should use formulas)
- ❌ Vendor names in multiple places (should use vendor_master + FK)
- ❌ Payment methods duplicated across tables (should use payment_method_master)

**GOOD Use of Relationships (correct, keep this):**
- ✅ charter_id, reserve_number, account_number in multiple tables (these are FKs - correct!)
- ✅ GL aggregating from receipts/payments (correct transaction structure)
- ✅ Multiple tables referencing same customer (via FK - correct pattern)

**Your Statement is 100% Correct:**
> "I don't want same data in different tables, relationships are better"

This IS the right philosophy. The redundancy you have is mostly test artifacts and calculated values that shouldn't exist. Your core transaction structure (payments, receipts, charters) is using relationships correctly.

---

## Next Steps

1. **Review this analysis** - Do you want to proceed with Phase 3 cleanup?
2. **Create vendor_master?** - Would help consolidate vendor data?
3. **Archive backups now?** - Can clean up 1-2 GB immediately?
4. **Prioritize?** - Which issue bothers you most:
   - The storage waste from backups?
   - The redundant calculations in amount columns?
   - The vendor name inconsistencies?

Let me know what you want to tackle first!
