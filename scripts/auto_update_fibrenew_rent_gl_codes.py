"""
Update Fibrenew GL 4110 receipts to GL 5410 (Rent Expense), excluding known trades.
- Keep receipt 60057 (trade/beverage) at GL 4110
- All other Fibrenew receipts currently at GL 4110 → GL 5410 Rent
"""

import psycopg2
import sys

EXCLUDE_RECEIPT_IDS = [60057]  # trade / beverage

def main():
    dry_run = '--dry-run' in sys.argv or '--write' not in sys.argv

    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()

    exclude_placeholders = ','.join(['%s'] * len(EXCLUDE_RECEIPT_IDS)) if EXCLUDE_RECEIPT_IDS else ''
    exclude_clause = f"receipt_id NOT IN ({exclude_placeholders})" if EXCLUDE_RECEIPT_IDS else 'TRUE'

    # Preview
    query = f"""
        SELECT receipt_id, receipt_date, gross_amount
        FROM receipts
        WHERE vendor_name ILIKE '%%fibrenew%%'
          AND gl_account_code = '4110'
          AND {exclude_clause}
        ORDER BY receipt_date
    """

    cur.execute(query, EXCLUDE_RECEIPT_IDS)
    rows = cur.fetchall()

    if not rows:
        print("No Fibrenew GL 4110 receipts to update (excluding trades)")
        cur.close()
        conn.close()
        return

    print("Fibrenew receipts to reclassify to GL 5410 (Rent):")
    print(f"{'ID':<8} {'Date':<12} {'Amount':>12}")
    print('-'*36)
    total = 0
    for r in rows:
        total += r[2]
        print(f"{r[0]:<8} {str(r[1]):<12} ${r[2]:>11,.2f}")
    print('-'*36)
    print(f"Count: {len(rows)}, Total: ${total:,.2f}")

    if dry_run:
        print("\nDRY RUN - no changes made. Use --write to apply.")
        cur.close()
        conn.close()
        return

    # Update
    update_query = f"""
        UPDATE receipts
        SET gl_account_code = %s,
            gl_account_name = %s,
            category = %s,
            verified_by_edit = %s,
            verified_at = NOW(),
            verified_by_user = %s
        WHERE vendor_name ILIKE '%%fibrenew%%'
          AND gl_account_code = '4110'
          AND {exclude_clause}
    """

    params = [
        '5410',
        'Rent Expense',
        'Rent',
        True,
        'auto_fibrenew_rent_update',
    ] + EXCLUDE_RECEIPT_IDS

    cur.execute(update_query, params)
    updated = cur.rowcount
    conn.commit()
    print(f"\n✅ Updated {updated} receipts to GL 5410 (Rent Expense), excluding trades: {EXCLUDE_RECEIPT_IDS}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
