# Arrow Limousine Management System - AI Agent Guide

## ⚠️ CRITICAL: Read This First Every Session

**File too big issue discovered (Dec 8, 2025):** This file was 200KB and stopped working. Streamlined to <30KB.

**Detailed reference documentation moved to:** `L:\limo\docs\FULL_SYSTEM_REFERENCE.md`

---

## 🚨 CURRENT SESSION STATUS (December 8, 2025)

**ACTIVE PROBLEM:** copilot-instructions.md grew to 200KB and stopped being read automatically by GitHub Copilot. This caused session restart failures where context was lost.

**WHAT WE'RE WORKING ON RIGHT NOW:**
- Streamlining this file to <30KB so it works again
- Testing if file size reduction fixes the automatic context loading

**LAST COMPLETED WORK (Dec 7 night):**
- Scotia Bank 2012-2014 verification and data cleanup
- Computer rebooted at midnight (12:10 AM) - lost uncommitted transactions
- Fibrenew and Centratech work lost (need to redo)

---

## Critical Development Rules

### 1. Reserve Number is ALWAYS the Business Key
```python
# ✅ CORRECT: Use reserve_number for charter-payment matching
SELECT c.*, SUM(p.amount) 
FROM charters c
LEFT JOIN payments p ON p.reserve_number = c.reserve_number
GROUP BY c.charter_id

# ❌ WRONG: charter_id (many payments have NULL charter_id)
```

### 2. Always Commit Database Changes
```python
import psycopg2
conn = psycopg2.connect(...)
cur = conn.cursor()
try:
    cur.execute("INSERT/UPDATE/DELETE...")
    conn.commit()  # ← CRITICAL
    print(f"✅ Committed: {cur.rowcount} rows")
except Exception as e:
    conn.rollback()
    print(f"❌ Rolled back: {e}")
finally:
    cur.close()
    conn.close()
```

### 3. Duplicate Prevention for Imports
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

### 4. Protected Receipt Patterns - DO NOT Delete
- **Recurring payments** (same amount, different dates) - LEGITIMATE
- **NSF charges without reversals** - LEGITIMATE (bank rejected)
- Only delete TRUE duplicates: SAME date + amount + vendor

---

## Database Connection

```python
import os
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
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
