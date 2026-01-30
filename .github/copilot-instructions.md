# Arrow Limousine Management System - AI Agent Guide

## ⚠️ CRITICAL: MANDATORY DATABASE REFERENCE GUIDE

**🔴 BEFORE WRITING ANY CODE:**
1. **ALWAYS consult** `L:\limo\docs\DATABASE_SCHEMA_REFERENCE.md`
2. **VERIFY all column names** match actual database schema
3. **NEVER assume column names** - cross-reference the guide
4. **EVERY database query must use business keys**, not IDs

**Most Recent Code Audit (Jan 21, 2026):**
- 4,723 files scanned
- 2,856 violations found (1,324 charter_id abuse, 1,423 currency-as-string)
- See: `L:\limo\docs\CODE_AUDIT_NAMING_VIOLATIONS.md`

---

## 🚨 CRITICAL DATABASE RULES (MEMORIZE THESE)

### BUSINESS KEYS vs PRIMARY KEYS
| Field | Type | Usage | Example |
|-------|------|-------|---------|
| `charter_id` | Primary Key | **RELATIONSHIPS ONLY** | `LEFT JOIN charters c` |
| `reserve_number` | **BUSINESS KEY** | **ALL BUSINESS LOGIC** | `WHERE c.reserve_number = %s` |
| `dispatch_id` | Primary Key | **RELATIONSHIPS ONLY** | `LEFT JOIN dispatches d` |
| `receipt_id` | Primary Key | **RELATIONSHIPS ONLY** | `LEFT JOIN receipts r` |
| `employee_id` | Primary Key | **RELATIONSHIPS ONLY** | `LEFT JOIN employees e` |
| `vehicle_id` | Primary Key | **RELATIONSHIPS ONLY** | `LEFT JOIN vehicles v` |

### RULE 1: Reserve Number is ALWAYS the Business Key
```python
# ✅ CORRECT: Match charters to payments via reserve_number
SELECT c.reserve_number, SUM(p.amount) as total_paid
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
WHERE c.reserve_number = %s
GROUP BY c.reserve_number

# ❌ WRONG: Using charter_id (not all payments have it!)
# ❌ WRONG: Using dispatch_id (wrong table entirely!)
```

### RULE 2: Verify Column Names Exist
```python
# Before writing query:
# 1. Open L:\limo\docs\DATABASE_SCHEMA_REFERENCE.md
# 2. Find the table name (e.g., "charters")
# 3. Check the column list
# 4. COPY the exact column name from the reference

# ✅ CORRECT: Column verified in reference guide
SELECT charter_date, total_amount_due FROM charters

# ❌ WRONG: Column name invented/guessed
SELECT charter_datetime, total_charge FROM charters  # ← these don't exist!
```

### RULE 3: Data Type Discipline
```python
# DECIMAL(12,2) - NEVER string for currency
# ❌ amount = "$500.00"    # WRONG
# ✅ amount = Decimal("500.00")  # CORRECT

# DATE (YYYY-MM-DD) - NEVER string for dates
# ❌ charter_date = "Jan 15, 2026"  # WRONG
# ✅ charter_date = date(2026, 1, 15)  # CORRECT
```

### RULE 4: Always Commit Database Changes
```python
import psycopg2
conn = psycopg2.connect(...)
cur = conn.cursor()
try:
    cur.execute("INSERT/UPDATE/DELETE...")
    conn.commit()  # ← CRITICAL - NO AUTO-COMMIT!
    print(f"✅ Committed: {cur.rowcount} rows")
except Exception as e:
    conn.rollback()
    print(f"❌ Rolled back: {e}")
finally:
    cur.close()
    conn.close()
```

### RULE 5: Duplicate Prevention for Imports
```python
# ALWAYS check for existing records before import
cur.execute("""
    INSERT INTO payments (reserve_number, amount, payment_date, ...)
    SELECT %s, %s, %s, ...
    WHERE NOT EXISTS (
        SELECT 1 FROM payments 
        WHERE reserve_number = %s AND amount = %s AND payment_date = %s
    )
""")
```

### RULE 6: Protected Receipt Patterns - DO NOT Delete
- **Recurring payments** (same amount, different dates) - LEGITIMATE
- **NSF charges without reversals** - LEGITIMATE (bank rejected)
- Only delete TRUE duplicates: SAME date + amount + vendor

### RULE 7: Banking Fee Deduplication Rule
- Fee-type receipts (EMAIL MONEY TRANSFER FEE, SERVICE CHARGE, PAYMENTECH CARD FEES) often repeat exact amounts, even multiple times per day — these are legitimate.
- Do not mark repeated fee amounts as duplicates by amount alone.
- Deduplicate only when: one receipt is banking-linked (`receipts.banking_transaction_id` set or `created_from_banking=true`) and extra receipts with the same date + amount remain that are not banking-linked and are not cash purchases.
- Exception: Cash purchases — allow repeated amounts without assuming duplication.


---

## Database Connection

```python
import os
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REDACTED***")
```

**Core Tables:**
- `charters` - Bookings (use `reserve_number` not `charter_id`)
- `payments` - Payments (link via `reserve_number`)
- `receipts` - Expenses
- `banking_transactions` - Bank statements
- `employees` - Staff/drivers
- `vehicles` - Fleet

**Bank Accounts:**
- CIBC 0228362 (primary) → `mapped_bank_account_id = 1`
- Scotia 903990106011 (secondary) → `mapped_bank_account_id = 2`

---

## Key Project Patterns

### GST Calculation (Tax Included)
```python
def calculate_gst(gross_amount, tax_rate=0.05):
    """GST is INCLUDED in amount (Alberta 5% GST)."""
    gst_amount = gross_amount * tax_rate / (1 + tax_rate)
    net_amount = gross_amount - gst_amount
    return round(gst_amount, 2), round(net_amount, 2)

# Example: $682.50 total INCLUDES $32.50 GST
gst, net = calculate_gst(682.50)  # gst=32.50, net=650.00
```

### Global Payments Merchant Services
**Card transaction abbreviations (GBL format):**
- **VCARD** = Global Payments Visa (GBL VI 41000XXXX)
- **MCARD** = Global Payments MasterCard (GBL MC 41000XXXX)
- **ACARD** = Global Payments Amex (GBL AX 41000XXXX)

**Standardized vendor names:**
- GLOBAL VISA DEPOSIT = Customer payments via Visa
- GLOBAL MASTERCARD DEPOSIT = Customer payments via MasterCard
- GLOBAL AMEX DEPOSIT = Customer payments via Amex
- GLOBAL VISA PAYMENT = Chargebacks/reversals/fees (money out)
- GLOBAL MASTERCARD PAYMENT = Chargebacks/reversals/fees (money out)
- GLOBAL AMEX PAYMENT = Chargebacks/reversals/fees (money out)

**NOT Global Payments (excluded):**
- DCARD = Debit card deposits (bank debit card, not merchant services)
- Capital One MasterCard = Personal credit card payments (company paying bill)

### Receipt-Banking Reconciliation
- `receipts.banking_transaction_id` → links to banking
- `receipts.created_from_banking` → auto-created flag
- `banking_receipt_matching_ledger` → junction table

### Data Import Safety
1. Always use dry-run mode first (`--dry-run`)
2. Create backups before modifications (`--backup`)
3. Generate deterministic hashes (SHA256) for deduplication
4. Use `WHERE NOT EXISTS` for idempotent imports

---

## Common Issues & Solutions

**Issue: Payment not matching charter**
- Solution: Check `reserve_number` match, not `charter_id`

**Issue: Duplicate receipts**
- Check: Are they recurring payments? (same amount, different dates = OK)
- Check: Are they NSF charges? (without reversal = OK)
- Only delete: TRUE duplicates (same date + amount + vendor)

**Issue: Balance discrepancies**
- Recalculate: `paid_amount = SUM(payments WHERE reserve_number = X)`
- Use `reserve_number` NOT `charter_id`

**Issue: Uncommitted transactions lost**
- Always call `conn.commit()` after modifications
- Check: Midnight reboot may have lost uncommitted work

---

## File Locations

- **This file:** `L:\limo\.github\copilot-instructions.md` (streamlined <30KB)
- **Full reference:** `L:\limo\docs\FULL_SYSTEM_REFERENCE.md` (detailed docs)
- **Scripts:** `L:\limo\scripts\` (300+ data processing scripts)
- **Reports:** `L:\limo\reports\` (analysis outputs)
- **Data:** `L:\limo\data\` (CSV/JSON staging)

---

## Essential Commands

```powershell
# Database verification
python scripts/verify_session_restart_status.py

# Drive health
Get-Volume -DriveLetter L

# Run script with UTF-8 encoding (Windows)
python -X utf8 scripts/script_name.py

# Common workflow
python scripts/analyze_*.py           # Analysis (no side effects)
python scripts/import_*.py --dry-run  # Preview import
python scripts/import_*.py --write    # Apply import
```

---

## Session Restart Protocol

**If context is lost on restart:**
1. Read this file (copilot-instructions.md)
2. Check `SESSION_CONTEXT_URGENT.md` if it exists
3. Run: `python scripts/verify_session_restart_status.py`
4. Ask user what we're working on (don't assume)
5. Don't start old tasks without confirmation

**Why context loss happens:**
- This file was too big (>200KB) and GitHub Copilot stopped reading it
- Now streamlined to <30KB to fix the issue

---

**Last Updated:** December 8, 2025, 1:33 AM (file size reduction)
**File Size Target:** <30KB (currently ~8KB)
**Status:** Testing if automatic context loading works now

---

## 🔥 CURRENT SESSION STATUS (December 23, 2025 - 10:30 PM)

**ACTIVE WORK:** Phase 1 QA Testing - Mega Menu Integration

**COMPLETED TODAY:**
- ✅ Mega menu integrated into desktop app (4-step integration complete)
- ✅ Fixed KeyError crash (domain/category missing in widget data)
- ✅ Fixed QFont.Worth typo (6 files)
- ✅ Fixed QMessageBox timing errors (4 widgets)
- ✅ Fixed database transaction rollback issues (4 widgets)
- ✅ Fixed column name errors (total_price → total_amount_due)
- ✅ Desktop app running successfully with Navigator tab
- ✅ Fleet Management widget launches (user tested)

**KNOWN ISSUES (Non-Critical):**
- 4 widgets show transaction errors during startup (handled gracefully)
- These are in Reports tab: Vehicle Fleet Cost, Driver Pay, Customer Payments, Profit & Loss

**NEXT SESSION START HERE:**
1. Launch app: `cd L:\limo && python -X utf8 desktop_app/main.py`
2. Test Fleet Management widget shows data (not blank)
3. Test 9 more sample widgets via Navigator tab (different domains)
4. Check for additional column name issues (search for `total_price`)

**SESSION LOG:** `L:\limo\SESSION_LOG_2025-12-23_Phase1_Testing.md` (full details)

**FILES MODIFIED TODAY:**
- desktop_app/main.py (mega menu integration)
- desktop_app/advanced_mega_menu_widget.py (domain/category fix)
- desktop_app/dashboard_classes.py (rollback + column names)
- desktop_app/dashboards_phase4_5_6.py (error handling)
- desktop_app/dashboards_phase11.py (QFont typo)
- desktop_app/dashboards_phase12.py (QFont typo)
- desktop_app/dashboards_phase13.py (QFont typo)

**TESTING PROGRESS:**
- Phase 1.1 (DB Connection): ✅ 100%
- Phase 1.2 (Mega Menu Integration): ✅ 100%
- Phase 1.3 (Widget Launches): ⏳ 10% (1 of 10 sample widgets)
- Phase 1.4 (All 136 Widgets): ❌ 0%
- Overall Phase 1: ~40% complete

---

## Next Session Auto-Resume Checklist

When the session restarts, automatically continue with these steps to keep momentum. These are safe, idempotent, and follow our current workflow and rules (reserve_number is the business key):

1. Start backend and verify API docs
    - Run: `uvicorn modern_backend.app.main:app --host 127.0.0.1 --port 8000`
    - Open API docs: http://127.0.0.1:8000/docs

2. Build or start the frontend (only if changes since last build)
    - Build: `npm run build --prefix frontend`
    - Or dev: `npm run serve --prefix frontend`

3. Charter-payment audit (reserve_number-based)
    - Task: VS Code task "Run charter-payment audit"
    - Confirms links via `reserve_number` and outputs CSVs under `reports/`

4. Payment method constraint check
    - Task: VS Code task "Inspect payment_method constraint"
    - Verify allowed set: cash, check, credit_card, debit_card, bank_transfer, trade_of_services, unknown

5. Neon read-only clone (optional if remote work planned)
    - Dump local: `pg_dump -h localhost -U postgres -d almsdata -F c -f almsdata.dump`
    - Restore to Neon: `pg_restore -h <neon-host> -U <neon-user> -d <neon-db> --clean --if-exists almsdata.dump`
    - Update env: `DB_HOST=<neon-host>`, `DB_NAME=almsdata`, `DB_USER=<neon-user>`, `DB_PASSWORD=<neon-password>`, SSL required
    - Create read-only role (recommended):
      ```sql
      CREATE ROLE app_readonly LOGIN PASSWORD '<strong-password>';
      GRANT CONNECT ON DATABASE almsdata TO app_readonly;
      GRANT USAGE ON SCHEMA public TO app_readonly;
      GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;
      ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_readonly;
      ```

6. Session restart protocol (quick)
    - Read this file
    - If present, read `SESSION_CONTEXT_URGENT.md`
    - Run: `python scripts/verify_session_restart_status.py`
    - Confirm current focus with user before modifying data

Notes:
- Reserve Number is ALWAYS the Business Key for charter-payment matching.
- Always `conn.commit()` after any INSERT/UPDATE/DELETE.
- Use `--dry-run` and `--backup` for imports; prefer idempotent `WHERE NOT EXISTS` patterns.

