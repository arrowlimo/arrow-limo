#!/usr/bin/env python3
"""Investigate 10 orphaned payments (no matching charter via reserve_number)."""

import os
import sys
from datetime import datetime
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def get_orphaned_payments():
    """Query database for orphaned payments."""
    logger.info("🔍 Querying orphaned payments...")
    
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Orphaned payments: reserve_number not found in charters
        query = """
        SELECT
          p.payment_id,
          p.reserve_number,
          p.amount,
          p.payment_date,
          p.payment_method,
          p.account_number,
          p.notes,
          p.charter_id,
          p.client_id,
          p.status,
          p.created_at
        FROM payments p
        LEFT JOIN charters c ON p.reserve_number = c.reserve_number
        WHERE c.reserve_number IS NULL OR p.reserve_number IS NULL
        ORDER BY p.payment_date NULLS LAST, p.payment_id;
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        logger.info(f"✅ Found {len(rows)} orphaned payments")
        return rows
    
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return []


def generate_report(orphaned_payments):
    """Generate report of orphaned payments."""
    logger.info("📄 Generating investigation report...")
    
    timestamp = datetime.now().isoformat()
    
    report = f"""# Orphaned Payments Investigation Report

**Generated:** {timestamp}  
**Total Orphaned Payments:** {len(orphaned_payments)}

---

## Summary

An orphaned payment is one where `reserve_number` exists in the `payments` table but has no matching record in the `charters` table. This indicates:

1. **Missing Charter:** The charter was deleted or never created
2. **Typo in reserve_number:** Payment reserve_number doesn't match any charter
3. **Data Quality Issue:** Orphaned data from import or manual entry

---

## Detailed List

"""
    
    if not orphaned_payments:
        report += "**No orphaned payments found.** ✅\n"
    else:
        report += f"| ID | Reserve | Amount | Date | Method | Status | Notes |\n"
        report += "|---|---|---|---|---|---|---|\n"
        
        for row in orphaned_payments:
            payment_id = row['payment_id']
            reserve = row['reserve_number'] or "(NULL)"
            amount = f"${row['amount']:.2f}" if row['amount'] else "N/A"
            date = row['payment_date'] or "N/A"
            method = row['payment_method'] or "N/A"
            status = row['status'] or "N/A"
            notes = (row['notes'] or "")[:50] if row['notes'] else ""
            
            report += f"| {payment_id} | {reserve} | {amount} | {date} | {method} | {status} | {notes} |\n"
    
    report += "\n---\n\n## Investigation Actions\n\n"
    
    report += """### For Each Orphaned Payment:

**Step 1: Determine Root Cause**
- `SELECT * FROM charters WHERE reserve_number = '<reserve_number>';`
- If no result: Charter missing, may need restoration or creation
- If matches: Check if payment is linked to correct charter

**Step 2: Resolution Options**

**Option A: Restore Missing Charter**
```sql
-- If charter was deleted, restore from backup or recreation
INSERT INTO charters (reserve_number, ...)
VALUES ('<reserve_number>', ...);
```

**Option B: Correct reserve_number Typo**
```sql
-- If payment reserve_number is misspelled, find the correct one and update
UPDATE payments
SET reserve_number = '<correct_reserve_number>'
WHERE payment_id = <payment_id>;
```

**Option C: Park in Suspense**
```sql
-- If truly stray, create suspense account or note for manual review
UPDATE payments
SET notes = CONCAT(notes, ' | ORPHANED - REQUIRES INVESTIGATION')
WHERE payment_id = <payment_id>;
```

**Step 3: Verification**
```sql
-- Re-run validation to confirm orphan is resolved
SELECT p.payment_id FROM payments p
LEFT JOIN charters c ON p.reserve_number = c.reserve_number
WHERE p.payment_id = <payment_id> AND c.reserve_number IS NOT NULL;
```

---

## Recommended Process

1. **Manual Review (1-2 hours)**
   - Review each of the 10 payments above
   - Check backup or LMS (legacy system) for missing charters
   - Determine if typo or missing data

2. **Data Correction (30 min)**
   - Apply Option A (restore), Option B (correct), or Option C (suspend) per payment
   - Document decision in payment notes field
   - Verify corrections with re-run of validation

3. **Approval**
   - Have finance or operations manager review changes
   - Sign off on reconciliation

4. **Post-Correction Validation**
   - Re-run: `python -X utf8 scripts/PHASE4_VALIDATION_COMPLIANCE.py`
   - Confirm orphaned payment count is now 0

---

## Next Steps

- [ ] Review 10 payments above (detailed list above)
- [ ] Determine root cause for each
- [ ] Apply corrections (restore, fix typo, or suspend)
- [ ] Document decision in payment notes
- [ ] Re-validate to confirm fix
- [ ] Confirm with management

---

**Generated:** {timestamp}
"""
    
    return report


def main():
    """Main execution."""
    logger.info("=" * 80)
    logger.info("ORPHANED PAYMENTS INVESTIGATION")
    logger.info("=" * 80)
    
    try:
        # Query database
        orphaned_payments = get_orphaned_payments()
        
        # Generate report
        report = generate_report(orphaned_payments)
        
        # Save report
        report_file = REPORTS_DIR / "ORPHANED_PAYMENTS_INVESTIGATION.md"
        with open(report_file, 'w') as f:
            f.write(report)
        
        logger.info(f"\n✅ Report saved: {report_file}")
        
        # Display summary
        logger.info(f"\n📊 Summary:")
        logger.info(f"   Orphaned Payments: {len(orphaned_payments)}")
        
        if orphaned_payments:
            logger.info(f"\n   Reserve Numbers:")
            for row in orphaned_payments:
                reserve = row['reserve_number'] or "(NULL)"
                amount = f"${row['amount']:.2f}" if row['amount'] else "N/A"
                logger.info(f"      • {reserve:20} | {amount:12} | {row['payment_date']}")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ INVESTIGATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"See: {report_file}")
        logger.info("=" * 80 + "\n")
        
        return 0
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
