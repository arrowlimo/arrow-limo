# Database Schema Standardization & Error Prevention Plan

**Generated:** January 20, 2026  
**Database:** almsdata  
**Status:** Critical Issues Detected

---

## Executive Summary

The database has **414 active tables**, **179 views**, but suffers from severe structural issues:

| Issue | Count | Severity | Impact |
|-------|-------|----------|--------|
| **Backup/Archive Tables** | ~200+ | High | Database bloat, confusion, outdated data copied |
| **Duplicate Column Names** | 789 | Critical | Copilot/developer naming errors when referencing |
| **Always-NULL Columns** | 10+ | Medium | Wasted space, dead code |
| **Nullable Key Columns** | 1000+ | Critical | Data integrity violations, missing constraints |
| **Orphaned Tables** | Many | Medium | Unknown purpose, no FK relationships |

---

## CRITICAL PROBLEMS DISCOVERED

### Problem 1: Massive Backup Table Explosion
**Symptom:** ~200 backup tables like:
- `payments_backup_20260107_213544`
- `receipts_backup_pre_dedup_20251207_002226`
- `charters_backup_link_by_account_20251201_164209`

**Root Cause:** No automated cleanup; developers creating manual backups before data modifications

**Impact:**
- Database size bloated (harder to scan, slower queries)
- Copilot gets confused with duplicate table/column names
- Data inconsistency (which version is source of truth?)
- Maintenance nightmare

**Solution:** 
1. Create versioning table: `table_versions` (table_name, version, created_at, description)
2. Archive backups older than 30 days to separate backup database
3. Enforce naming: `tablename_v1_YYYYMMDD` format (single version at a time)

---

### Problem 2: 789 Duplicate Column Names Across Tables
**Examples:**
- `id` in 50+ tables (no naming convention)
- `amount` appears in 20+ tables with different meanings
- `date` / `created_at` / `timestamp` - three different column names for same thing
- `charter_id` nullable in receipts, payments (should be NOT NULL or FK)

**Root Cause:** No database design guidelines; each developer uses own naming

**Impact:**
```python
# WRONG: Copilot can't tell which table to query
SELECT * FROM receipts WHERE charter_id = 123
# Returns: 150 rows (NULL, NULL, NULL... - useless)

# CORRECT but requires manual inspection:
SELECT * FROM receipts WHERE charter_id IS NOT NULL AND charter_id = 123
```

**Solution:** Standardize column naming:
```
PRIMARY KEYS:     table_name_id (e.g., receipt_id, charter_id)
FOREIGN KEYS:     parent_table_name_id (e.g., receipt_id, charter_id)
AMOUNTS:          amount_decimal (cents stored as integer?)
DATES:            transaction_date, created_at, updated_at (standardize on one)
STATUS:           status_code (enum reference)
FLAGS:            is_active, is_deleted, is_reconciled (boolean prefix)
```

---

### Problem 3: 1000+ Nullable Key Columns
**Critical Issues:**
- `receipts.charter_id` - NULLABLE but used for linking
- `payments.reserve_number` - NULLABLE but used for linking
- `receipts.split_group_id` - NULLABLE (breaks split receipt logic!)
- `banking_transactions.receipt_id` - NULLABLE (confuses reconciliation)

**Root Cause:** Columns created as flexible but never converted to NOT NULL after rules defined

**Impact:**
```sql
-- This query silently excludes 30% of receipts:
SELECT * FROM receipts WHERE charter_id = 123
-- Missing: receipts with charter_id = NULL

-- Correct query requires:
SELECT * FROM receipts WHERE charter_id = 123 OR charter_id IS NULL
```

**Solution:**
1. Audit each key column to determine: required or truly optional?
2. If required: `ALTER TABLE ... SET NOT NULL`
3. If optional: rename to `optional_` prefix to warn developers
4. Add CHECK constraints for valid values

---

### Problem 4: Orphaned/Unused Tables (No Foreign Keys)
**Examples:**
- `alcohol_business_tracking` (all columns always NULL!)
- `beverage_menu`, `beverage_cart`
- `qb_accounts_staging` (outdated QB sync table)
- Many audit/staging tables from old migration projects

**Root Cause:** Failed migration projects left behind tables

**Impact:**
- Developers waste time trying to understand unused code
- Takes up backup space
- Increases data refresh time

**Solution:**
1. List all tables with 0 rows
2. Archive those with creation date >2 years old
3. Create `schema_metadata` table documenting each table's purpose & status

---

### Problem 5: Confusing GL Code Storage
**Current Problem:**
- GL codes stored as TEXT in `receipts.gl_account_code`
- Descriptions in `gl_transactions.account_name` (different data!)
- No single GL master table
- Query requires manual LEFT JOIN that often returns NULL

**Why This Broke Splits:**
```python
# Split manager tried to query GL codes:
cur.execute("""
    SELECT DISTINCT r.gl_account_code, g.account_name
    FROM receipts r
    LEFT JOIN gl_transactions g ON r.gl_account_code = g.account_name
    WHERE r.gl_account_code IS NOT NULL 
""")
# Returns: Empty list (no matches on account_name!)
```

**Solution:**
1. Create `gl_code_master` table:
   ```sql
   CREATE TABLE gl_code_master (
       gl_code VARCHAR(20) PRIMARY KEY,
       description VARCHAR(500) NOT NULL,
       category VARCHAR(100),
       is_active BOOLEAN DEFAULT true,
       created_at TIMESTAMP,
       updated_at TIMESTAMP
   );
   ```
2. Add FK constraint: `receipts.gl_account_code` → `gl_code_master.gl_code`
3. Populate from existing distinct codes

---

## STANDARDIZATION ROADMAP (Phase-by-Phase)

### Phase 1: Schema Inventory & Documentation (DONE ✅)
- [x] Generated `DATABASE_SCHEMA_INVENTORY.json` - machine-readable schema
- [x] Generated `DATABASE_SCHEMA_REPORT.md` - human-readable issues
- [x] Identified 2,446 issues

**Next:** Create decision log for each issue

---

### Phase 2: Core Table Standardization (1 week)
**Priority Order:**
1. **receipts** - Most used in splits, contains 40+ columns, inconsistent
2. **payments** - Critical for reconciliation, 15+ columns with duplicates
3. **charters** - Heavy backup bloat, 5+ backup versions
4. **banking_transactions** - Foundation for GL reconciliation

**Actions per table:**
- [ ] Audit each column: required or optional?
- [ ] Fix nullable keys (add NOT NULL or rename to optional_)
- [ ] Create foreign keys to master tables
- [ ] Document column purposes in comments
- [ ] Create migration scripts for cleanup

---

### Phase 3: Master Table Creation (2 weeks)
Create canonical master tables (one source of truth):

```sql
-- GL Code Master (replaces ad-hoc storage)
CREATE TABLE gl_code_master (...);

-- Payment Methods Master
CREATE TABLE payment_method_master (
    method_code VARCHAR(20) PRIMARY KEY,
    description VARCHAR(200),
    is_cash_equivalent BOOLEAN,
    is_active BOOLEAN
);
-- Values: cash, check, debit/credit_card, bank_transfer, gift_card, personal, trade_of_services, unknown

-- Bank Accounts Master (single source for CIBC, Scotia)
CREATE TABLE bank_account_master (
    bank_account_id INT PRIMARY KEY,
    bank_name VARCHAR(100),
    account_number VARCHAR(50),
    account_type VARCHAR(50),
    currency VARCHAR(3)
);

-- Vendor Master (consolidate duplicates)
CREATE TABLE vendor_master (
    vendor_id INT PRIMARY KEY,
    vendor_name_canonical VARCHAR(500),
    vendor_aliases TEXT, -- JSON array of known names
    is_active BOOLEAN
);
```

---

### Phase 4: Naming Convention Enforcement (3 weeks)
Apply standards to ALL 414 tables:

| Element | Standard | Example |
|---------|----------|---------|
| Primary Keys | `table_name_id` | `receipt_id`, `charter_id` |
| Foreign Keys | `referenced_table_id` | `charter_id` (not `charter`, not `charter_fk`) |
| Amounts | `amount` or `amount_cents` (clarify currency) | `receipt_amount`, `payment_amount_cents` |
| Dates | `transaction_date`, `created_at`, `updated_at` | No mix of `date`, `trans_date`, `booking_date` |
| Status | `status_code` (FK to status_master) | `booking_status_code`, `payment_status_code` |
| Flags | `is_active`, `is_deleted`, `is_reconciled` | `is_split_receipt`, `is_banking_matched` |
| Computed | `_calc` suffix or in VIEW | `total_amount_due_calc` |

---

### Phase 5: Backup Table Cleanup (1 week)
Execute removal plan:

```sql
-- STEP 1: Identify old backups
SELECT table_name, 
       (SELECT MAX(created_at) FROM backup_metadata 
        WHERE source_table = REPLACE(table_name, '_backup_*', '')) as backup_date
FROM information_schema.tables
WHERE table_name LIKE '%_backup_%'
ORDER BY backup_date DESC;

-- STEP 2: Archive old backups (keep only last 2)
CREATE TABLE public.backup_manifest (
    backup_id SERIAL PRIMARY KEY,
    source_table_name VARCHAR(255),
    backup_table_name VARCHAR(255),
    created_at TIMESTAMP,
    row_count INT,
    size_mb NUMERIC,
    reason TEXT
);
-- Archive existing backup tables to this manifest

-- STEP 3: Drop old backups
DROP TABLE payments_backup_20260107_213544;
DROP TABLE receipts_backup_pre_dedup_20251207_002226;
-- ... (100+ more)

-- STEP 4: Create proper versioning
CREATE TABLE IF NOT EXISTS table_version_history (
    version_id SERIAL PRIMARY KEY,
    table_name VARCHAR(255),
    version_number INT,
    created_at TIMESTAMP,
    reason VARCHAR(500),
    row_count INT,
    archived_location VARCHAR(255) -- reference to backup database
);
```

---

### Phase 6: Code Validation Rules (2 weeks)
**For Copilot & future developers:**

Create `SCHEMA_REFERENCE.md` in workspace root:

```markdown
# Database Schema Reference
**DO NOT USE BACKUP TABLES - THEY ARE ARCHIVED**

## Core Tables (Active)
- receipts ← Use for expenses
- payments ← Use for income/payments
- charters ← Use for bookings
- banking_transactions ← Use for reconciliation

## Always Check
- Is this column NOT NULL? Yes → required
- Is this column nullable? Yes → may return NULL, use COALESCE()
- Is this table a backup? Yes → WRONG TABLE. Use active version

## Column Naming Quick Reference
- `*_id` = Primary/Foreign Key
- `is_*` = Boolean flag
- `*_at` = Timestamp
- `*_code` = Reference to master table
```

---

## IMPLEMENTATION: Next Steps for Split Manager

### Immediate Fix (Done Today)
✅ Added `gl_code_master` table creation script  
✅ Fixed payment method dropdown with database values  
✅ Changed to combined `debit/credit_card` option

### Short-term (This Week)
1. [ ] Query `gl_code_master` in split manager (not ad-hoc GL list)
2. [ ] Add description display: "6900 - Vehicle Maintenance"
3. [ ] Validate payment_method against `payment_method_master`
4. [ ] Add light blue background for split receipts (instead of red)

### Medium-term (Next 2 weeks)
1. [ ] Standardize all key columns (NOT NULL enforcement)
2. [ ] Remove 100+ backup tables
3. [ ] Document final schema in code comments
4. [ ] Create automated tests to prevent regressions

---

## File References
- **Comprehensive Inventory:** `DATABASE_SCHEMA_INVENTORY.json` (machine-readable)
- **Issue Report:** `DATABASE_SCHEMA_REPORT.md` (human-readable)
- **This Plan:** `SCHEMA_STANDARDIZATION_PLAN.md` (action items)
- **Audit Script:** `audit_database_schema.py` (regenerate anytime)

---

## Key Takeaway

**The system works despite chaos, not because of order.**

Code needs:
1. **One source of truth** (not 5 backup versions)
2. **Consistent naming** (not id, ID, Id, _id, tableid)
3. **Enforced constraints** (NOT NULL where needed)
4. **Master tables** (GL codes, payment methods, vendors - not scattered)
5. **Documentation** (why does this column exist? Is it used?)

Without these, every feature (like Split Receipts) requires manual workarounds and Copilot can't help because the schema is too ambiguous.
