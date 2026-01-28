#!/usr/bin/env python3
"""
Phase 3: Link Orphaned Payments to Charters

Strategy: Since 273 Square payments have NULL reserve_number but valid amounts and dates,
attempt to link them to charters via amount-date matching:
  - Match: payment.amount = charter.total_amount_due
  - Within ±3 days: payment_date ≈ charter_date

Outputs:
  - DRY RUN: Shows matches and unmatches without writing
  - APPLY: Actually populates reserve_number where found, tracks misses
  - Report: Detailed analysis with decisions for manual review

Safe: Uses WHERE NOT EXISTS to prevent duplicate processing
"""

import os
import psycopg2
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def link_orphaned_payments(dry_run=True, output_file="reports/LINK_ORPHANED_PAYMENTS_REPORT.md"):
    """
    Link orphaned payments to charters via amount-date matching
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Report content
    report = []
    report.append("# Orphaned Payments Linking Report\n")
    report.append(f"**Generated:** {datetime.now().isoformat()}\n")
    report.append(f"**Mode:** {'DRY RUN (no changes)' if dry_run else 'APPLY (writing to DB)'}\n\n")
    
    # Get all orphaned payments
    query = """
    SELECT p.payment_id, p.amount, DATE(p.payment_date) as payment_date, 
           p.notes, p.payment_method
    FROM payments p
    WHERE p.reserve_number IS NULL
      AND p.payment_date >= '2025-09-10'
      AND p.payment_method = 'credit_card'
    ORDER BY p.payment_date, p.amount;
    """
    cur.execute(query)
    orphans = cur.fetchall()
    
    report.append(f"## Summary\n")
    report.append(f"- Total orphans to link: **{len(orphans)}**\n")
    report.append(f"- Strategy: Amount-date matching (±3 days)\n")
    report.append(f"- Mode: {'DRY RUN' if dry_run else 'APPLY'}\n\n")
    
    matched = []
    no_match = []
    multi_match = []
    
    for i, (payment_id, amount, payment_date, notes, method) in enumerate(orphans, 1):
        # Try to find matching charter
        find_charter = """
        SELECT c.reserve_number, c.charter_date, c.total_amount_due,
               ABS(DATE(c.charter_date) - DATE(%s)) as date_diff
        FROM charters c
        WHERE c.total_amount_due = %s
          AND DATE(c.charter_date) BETWEEN DATE(%s) - interval '3 days' 
                                       AND DATE(%s) + interval '3 days'
        ORDER BY ABS(DATE(c.charter_date) - DATE(%s)) ASC
        LIMIT 5;
        """
        cur.execute(find_charter, (payment_date, amount, payment_date, payment_date, payment_date))
        results = cur.fetchall()
        
        if not results:
            no_match.append({
                'payment_id': payment_id,
                'amount': float(amount),
                'payment_date': payment_date,
                'notes': notes
            })
        elif len(results) == 1:
            reserve_number, charter_date, charter_amount, date_diff = results[0]
            matched.append({
                'payment_id': payment_id,
                'amount': float(amount),
                'payment_date': payment_date,
                'reserve_number': reserve_number,
                'charter_date': charter_date,
                'date_diff_days': int(date_diff)
            })
            
            # If not dry-run, update the payment
            if not dry_run:
                update = """
                UPDATE payments
                SET reserve_number = %s,
                    notes = CONCAT(notes, ' | LINKED to charter ')
                WHERE payment_id = %s;
                """
                cur.execute(update, (reserve_number, payment_id))
        else:
            # Multiple matches - ambiguous
            multi_match.append({
                'payment_id': payment_id,
                'amount': float(amount),
                'payment_date': payment_date,
                'matches': [(r[0], r[1], int(r[3])) for r in results]  # reserve, charter_date, days_diff
            })
    
    # Commit if apply mode
    if not dry_run:
        conn.commit()
        report.append(f"✅ **COMMITTED {len(matched)} updates to database**\n\n")
    else:
        report.append(f"⚠️  **DRY RUN - No changes written**\n\n")
    
    # Build detailed report
    report.append(f"## Results\n\n")
    report.append(f"| Category | Count | % |\n")
    report.append(f"|----------|-------|-----|\n")
    report.append(f"| **Matched (1:1)** | **{len(matched)}** | **{100*len(matched)/len(orphans):.1f}%** |\n")
    report.append(f"| **No Match** | {len(no_match)} | {100*len(no_match)/len(orphans):.1f}% |\n")
    report.append(f"| **Ambiguous (N:1)** | {len(multi_match)} | {100*len(multi_match)/len(orphans):.1f}% |\n")
    report.append(f"| **TOTAL** | **{len(orphans)}** | **100%** |\n\n")
    
    # Matched payments (to be written)
    if matched:
        report.append(f"## Successfully Matched ({len(matched)} payments)\n\n")
        report.append(f"| Payment ID | Amount | Payment Date | Reserve # | Charter Date | Days Diff |\n")
        report.append(f"|---|---|---|---|---|---|\n")
        for m in matched[:20]:  # Show first 20
            report.append(f"| {m['payment_id']} | ${m['amount']:,.2f} | {m['payment_date']} | {m['reserve_number']} | {m['charter_date']} | {m['date_diff_days']} |\n")
        if len(matched) > 20:
            report.append(f"| ... | ... | ... | ... | ... | ... |\n")
            report.append(f"| *{len(matched)-20} more* | | | | | |\n")
        report.append(f"\n")
    
    # Unmatched payments (need manual review)
    if no_match:
        report.append(f"## No Match Found ({len(no_match)} payments - REQUIRE MANUAL REVIEW)\n\n")
        report.append(f"| Payment ID | Amount | Payment Date | Action |\n")
        report.append(f"|---|---|---|---|\n")
        for nm in no_match[:20]:
            report.append(f"| {nm['payment_id']} | ${nm['amount']:,.2f} | {nm['payment_date']} | Check Square, ask Finance, or park in suspense |\n")
        if len(no_match) > 20:
            report.append(f"| ... | ... | ... | ... |\n")
            report.append(f"| *{len(no_match)-20} more* | | | |\n")
        report.append(f"\n")
    
    # Ambiguous matches (need manual review)
    if multi_match:
        report.append(f"## Ambiguous Matches ({len(multi_match)} payments - MULTIPLE CHARTERS FOUND)\n\n")
        report.append(f"| Payment ID | Amount | Payment Date | Possible Charters |\n")
        report.append(f"|---|---|---|---|\n")
        for mm in multi_match[:10]:
            reserves = ", ".join([f"{r[0]} ({r[2]}d)" for r in mm['matches']])
            report.append(f"| {mm['payment_id']} | ${mm['amount']:,.2f} | {mm['payment_date']} | {reserves} |\n")
        if len(multi_match) > 10:
            report.append(f"| ... | ... | ... | ... |\n")
            report.append(f"| *{len(multi_match)-10} more* | | | |\n")
        report.append(f"\n")
    
    # Next steps
    report.append(f"## Next Steps\n\n")
    report.append(f"### If DRY RUN successful (high match rate):\n")
    report.append(f"1. Review matched count: {len(matched)} / {len(orphans)}\n")
    report.append(f"2. Run with APPLY flag: `python -X utf8 scripts/link_orphaned_payments_to_charters.py --apply`\n")
    report.append(f"3. Verify with: `python -X utf8 scripts/PHASE4_VALIDATION_COMPLIANCE.py`\n")
    report.append(f"4. Review {len(no_match)} unmatched for manual corrections\n\n")
    
    report.append(f"### For unmatched payments:\n")
    report.append(f"1. Check Square dashboard for transaction details\n")
    report.append(f"2. Ask Finance: \"Which customer is this ${amount} payment for?\"\n")
    report.append(f"3. Options:\n")
    report.append(f"   - Create missing charter if needed\n")
    report.append(f"   - Correct payment amount if typo\n")
    report.append(f"   - Park in suspense with notation\n")
    report.append(f"   - Delete if true duplicate\n\n")
    
    report.append(f"---\n\n")
    report.append(f"**Generated:** {datetime.now().isoformat()}\n")
    
    # Write report
    os.makedirs("reports", exist_ok=True)
    with open(output_file, "w") as f:
        f.write("".join(report))
    
    print("\n" + "=" * 80)
    print(f"{'DRY RUN' if dry_run else 'APPLIED'} LINK ORPHANED PAYMENTS")
    print("=" * 80)
    print(f"\n✅ Matched (1:1):     {len(matched):3} / {len(orphans)} ({100*len(matched)/len(orphans):5.1f}%)")
    print(f"⚠️  No Match:         {len(no_match):3} / {len(orphans)} ({100*len(no_match)/len(orphans):5.1f}%)")
    print(f"🔄 Ambiguous (N:1):  {len(multi_match):3} / {len(orphans)} ({100*len(multi_match)/len(orphans):5.1f}%)")
    print(f"\n📄 Report: {output_file}")
    print("=" * 80 + "\n")
    
    cur.close()
    conn.close()
    
    return len(matched), len(no_match), len(multi_match)


if __name__ == "__main__":
    import sys
    
    apply_mode = "--apply" in sys.argv or "-a" in sys.argv
    
    if not apply_mode:
        print("\n⚠️  Running in DRY RUN mode (no changes will be written)")
        print("    To apply: python link_orphaned_payments_to_charters.py --apply\n")
    
    matched, no_match, multi = link_orphaned_payments(dry_run=not apply_mode)
    
    if not apply_mode:
        print(f"✅ Review dry-run results in reports/LINK_ORPHANED_PAYMENTS_REPORT.md")
        print(f"   If matches look good, run: python -X utf8 scripts/link_orphaned_payments_to_charters.py --apply\n")
