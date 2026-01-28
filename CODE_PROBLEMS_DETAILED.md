# Code Problems Found - Technical Details

## Problem 1: GL Lookup Query Was Fundamentally Broken

### Original Code (split_receipt_manager_dialog.py)
```python
def _get_gl_codes(self) -> list:
    """Get list of available GL codes from database with descriptions."""
    try:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT DISTINCT r.gl_account_code, g.account_name
            FROM receipts r
            LEFT JOIN gl_transactions g ON r.gl_account_code = g.account_name
            WHERE r.gl_account_code IS NOT NULL 
            ORDER BY r.gl_account_code
        """)
        codes = cur.fetchall()
        
        if codes:
            formatted = [f"{code[0]} - {code[1] if code[1] else ''}" for code in codes]
            return formatted
        else:
            return ["-- Select GL Code --"]
```

### Why It Failed
```sql
-- Query returns EMPTY because these don't match:
receipts.gl_account_code = "6900"      (numeric GL code)
gl_transactions.account_name = "Opening Balance from Bank"  (transaction description)

-- These will NEVER be equal
```

### Database Reality
```sql
-- Receipts table contains:
SELECT DISTINCT gl_account_code FROM receipts WHERE gl_account_code IS NOT NULL;
-- Returns: 1000, 1010, 1020, 1030, 1135, 1200, 2010, 2100, 2110, 2200, 2500, 3000, 3100, ...

-- GL Transactions table contains:
SELECT DISTINCT account_name FROM gl_transactions LIMIT 10;
-- Returns: "Opening Balance from Bank", "SHELL FLYING J PURCHASE", 
--          "CIBC BANKING", "CIBC CC FEE", etc. (descriptions, not codes!)
```

### The Fix - Multiple Options
#### Option A: Create Master Table (RECOMMENDED)
```python
def _get_gl_codes(self) -> list:
    """Get list of available GL codes from master table."""
    try:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT gl_code, description
            FROM gl_code_master
            WHERE is_active = true
            ORDER BY gl_code
        """)
        codes = cur.fetchall()
        if codes:
            return [f"{code[0]} - {code[1]}" for code in codes]
        else:
            return ["-- Select GL Code --"]
```

#### Option B: Use Receipts Only (Fallback)
```python
def _get_gl_codes(self) -> list:
    """Get GL codes from receipts table directly."""
    try:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT DISTINCT r.gl_account_code
            FROM receipts r
            WHERE r.gl_account_code IS NOT NULL 
            ORDER BY r.gl_account_code
        """)
        codes = [row[0] for row in cur.fetchall()]
        return codes if codes else ["-- Select GL Code --"]
```

---

## Problem 2: Payment Method Hardcoding vs. Reality

### Original Code (split_receipt_manager_dialog.py)
```python
payment_methods = ["cash", "check", "credit_card", "debit_card", "bank_transfer", "trade_of_services", "unknown"]
```

### Actual Database Values
```sql
SELECT DISTINCT payment_method FROM receipts ORDER BY payment_method;
-- Returns 16 different values:
-- Aurora Premium Financing
-- Bank Debit
-- Bank Deposit  
-- bank_transfer
-- cash
-- check
-- CHEQUE
-- CIBC Banking
-- credit_card
-- debit
-- debit_card
-- gift_card
-- personal
-- trade_of_services
-- unknown
-- NULL (100+ records have NULL!)
```

### Problem: Cascading Failures
1. Dropdown shows: ["cash", "check", "credit_card", ...]
2. User selects "cash" ✓
3. Saves child receipt with payment_method = "cash"
4. Later query searches for receipts where payment_method IN [hardcoded list]
5. Misses records with "CHEQUE" or "Bank Debit" → data inconsistency

### The Fix
```python
def _get_payment_methods(self) -> list:
    """Get payment methods from master table (not hardcoded)."""
    try:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT method_code, description
            FROM payment_method_master
            WHERE is_active = true
            ORDER BY method_code
        """)
        methods = [row[0] for row in cur.fetchall()]
        return methods if methods else ["-- Select Payment Method --"]
    except:
        # Fallback if master table doesn't exist yet
        return ["cash", "check", "debit/credit_card", "bank_transfer", "gift_card", "personal", "trade_of_services", "unknown"]
```

---

## Problem 3: Nullable Key Columns Break Queries

### The Issue
```sql
-- receipts table has:
-- receipt_id INT NOT NULL PRIMARY KEY ✓ Good
-- split_group_id INT NULLABLE ← Problem!
-- charter_id INT NULLABLE ← Problem!
-- banking_transaction_id INT NULLABLE ← Problem!
```

### Why This Causes Bugs
```python
# Query to find split receipts:
cur.execute("""
    SELECT * FROM receipts 
    WHERE split_group_id = %s
""", (140678,))  # Looking for child receipts

# Returns: 2 records ✓ Correct

# Query to find receipts for a charter:
cur.execute("""
    SELECT * FROM receipts 
    WHERE charter_id = %s
""", (61295,))  # Looking for receipt

# Returns: Only 3 records
# But 10 receipts have charter_id = NULL!
# Missing data because NULL values are excluded
```

### Correct Pattern
```python
# Must explicitly check for NULL:
cur.execute("""
    SELECT * FROM receipts 
    WHERE charter_id = %s OR charter_id IS NULL
""", (61295,))  # Now returns 13 records (3 + 10 NULL)

# But this is WRONG! Why would we want receipts with NO charter?
# Real answer: charter_id should be NOT NULL or table design is wrong
```

### Database Constraint Needed
```sql
-- Enforce that key columns are NOT NULL:
ALTER TABLE receipts 
ALTER COLUMN split_group_id SET NOT NULL;

ALTER TABLE receipts 
ALTER COLUMN charter_id SET NOT NULL;

-- OR if truly optional, rename to clarify:
ALTER TABLE receipts 
RENAME COLUMN charter_id TO optional_charter_id;

-- OR add CHECK constraint:
ALTER TABLE receipts 
ADD CONSTRAINT check_charter_id 
CHECK (charter_id IS NOT NULL OR reason_for_null = 'manual_entry');
```

---

## Problem 4: 104 Backup Tables Creating Confusion

### Example Backups Found
```
payments_backup_20260110_025229        ← 4 days old
payments_backup_20260107_214335        ← 13 days old
payments_backup_20260107_213718        ← 13 days old
payments_backup_lms_sync_20251123      ← 57 days old
payments_2012_backup_v2                ← Unknown age (years?)

receipts_backup_pre_dedup_20251207_003854
receipts_backup_pre_live_delete_20251207_003927
receipts_backup_post_dedup_20251207_003927
receipts_backup_dedup_20251221_124543  ← More than one "dedup" backup!

charters_backup_link_by_account_20251201_164209
charters_backup_vehicle_id_20251224_202231
charters_retainer_cancel_fix_20251204
```

### Why This Is Bad
```python
# Developer accidentally queries backup:
cur.execute("SELECT * FROM payments_backup_20260110_025229 WHERE ...")
# Returns 3-week-old data instead of current data!

# Or worse, they don't notice:
SELECT COUNT(*) FROM payments  # 5,000 records
SELECT COUNT(*) FROM payments_backup_20260107_213718  # 4,999 records (is this the right one?)

# Maintenance nightmare - which backup is source of truth?
```

### The Pattern
Most backups created before data modifications:
1. Developer: "I'm about to delete 100 problematic receipts"
2. Developer: `CREATE TABLE receipts_backup_before_deletion AS SELECT * FROM receipts;`
3. Developer: `DELETE FROM receipts WHERE ...`
4. Developer: Never deletes the backup table → accumulates forever

### Solution
```python
# Instead of ad-hoc backups, use versioning:

# Create ONE backup manifest table:
CREATE TABLE table_backup_manifest (
    backup_id SERIAL PRIMARY KEY,
    source_table_name VARCHAR(255),
    backup_table_name VARCHAR(255),
    created_at TIMESTAMP,
    reason VARCHAR(500),  -- "before_dedup_20251207"
    row_count INT,
    archive_location VARCHAR(255)  -- "backup_db.payments_v2"
);

# Then instead of:
CREATE TABLE payments_backup_20260110_025229 AS SELECT * FROM payments;

# Do:
INSERT INTO table_backup_manifest VALUES (...);
-- Store backup in separate backup database, rotate daily
-- Keep only last 2 versions
-- Archive old versions to cold storage
```

---

## Problem 5: Duplicate Column Names Across 789 Instances

### Examples in Current Database
```sql
-- 'id' column exists in 50+ tables with different meanings:
SELECT table_name FROM information_schema.columns 
WHERE column_name = 'id';
-- Results: 50 different tables

-- 'amount' appears in 20+ tables:
SELECT DISTINCT table_name FROM information_schema.columns 
WHERE column_name = 'amount';
-- Results: accounting_records, bank_transactions_staging, billing_audit_issues, ...
-- But each stores different things (receipt total? payment amount? tax amount?)

-- 'date' is stored 3 different ways:
-- Some tables: 'date' (ambiguous)
-- Some tables: 'transaction_date' (specific)
-- Some tables: 'created_at' (even more specific)
```

### Code Problems This Causes
```python
# Ambiguous column reference in JOIN:
SELECT r.*, p.amount  # Which amount? Receipt total? Payment? Changed amount?
FROM receipts r
JOIN payments p ON r.receipt_id = p.receipt_id
# Developer has to guess or check schema manually

# Copilot gets confused:
# "Add a column for 'id'" - which table? Which type of ID?
# "Query all 'amounts'" - do you want receipts.gross_amount or payments.amount?
```

### Standard Naming Convention Needed
```python
NAMING_STANDARD = {
    "PRIMARY_KEY": "{table_name}_id",           # receipt_id, charter_id, payment_id
    "FOREIGN_KEY": "{referenced_table}_id",    # charter_id (in receipts, points to charters)
    "AMOUNT": "{type}_amount",                 # receipt_amount, payment_amount, refund_amount
    "DATE": "transaction_date",                # Never use "date" alone
    "CREATED": "created_at",                   # Timestamp
    "UPDATED": "updated_at",                   # Timestamp
    "STATUS": "{entity}_status",               # payment_status, booking_status (FK to enum)
    "BOOLEAN": "is_{adjective}",               # is_active, is_deleted, is_reconciled
}

# Examples:
receipts.receipt_id ✓ (not id, not receipt_id_pk, not r_id)
receipts.charter_id ✓ (FK to charters)
receipts.receipt_amount ✓ (not gross_amount, not amount, not total)
receipts.transaction_date ✓ (not date, not receipt_date, not created)
receipts.is_split_receipt ✓ (not split_flag, not is_splitted, not split)
```

---

## Summary: Why Split Manager Kept Failing

| Component | Problem | Root Cause | Fix |
|-----------|---------|-----------|-----|
| GL Dropdown | Empty | Joining gl_code to account_name | Create gl_code_master table |
| Payment Method | Wrong values | Hardcoded 7 values vs 16 actual | Query payment_method_master |
| Split creation | Key columns NULL | split_group_id nullable | ALTER TABLE ... NOT NULL |
| Data lookup | Returns incomplete | charter_id nullable excluded NULLs | Enforce NOT NULL constraints |
| Query validation | No early errors | No schema lookup system | Created schema_validator.py |
| Database bloat | 104 backups | No cleanup process | Implement versioning system |
| Naming confusion | Wrong table queries | No naming standard | Created standard above |

---

## Lessons Learned for Future Code

1. **Never hardcode enum values** → Always query master tables
2. **Never assume NOT NULL** → Check schema or add assertions
3. **Never create backup tables manually** → Use versioning system
4. **Always validate schema before queries** → Use schema_validator.py
5. **Always use standard naming** → Reference NAMING_STANDARD document
6. **Always test edge cases** → NULL values, empty results, wrong types

These 5 problems would have been caught with:
- Schema validation before code runs
- Naming standards document
- Master table pattern enforcement
- Code review checklist
