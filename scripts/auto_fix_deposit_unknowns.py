"""
Normalize DEPOSIT / DEPOSIT #X / UNKNOWN PAYEE to bank deposits.
- Set GL to 1010 (Cash & Bank Accounts)
- Category: Bank Deposit
- Keep vendor_name as-is (optional rename noted below)
- Keep banking_transaction_id links intact
"""

import psycopg2
import sys

TARGET_GL = '1010'
TARGET_GL_NAME = 'Cash & Bank Accounts'
TARGET_CATEGORY = 'Bank Deposit'
TARGET_VERIFIED_BY = 'auto_deposit_normalize'

VENDORS = ['DEPOSIT', 'DEPOSIT #X', 'UNKNOWN PAYEE']

RENAME_DEPOSIT_X = False  # set True if you want vendor_name changed to 'DEPOSIT'


def main():
    dry_run = '--dry-run' in sys.argv or '--write' not in sys.argv

    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()

    placeholders = ','.join(['%s'] * len(VENDORS))

    # Preview
    cur.execute(
        f"""
        SELECT vendor_name, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE vendor_name IN ({placeholders})
          AND (gl_account_code != %s OR gl_account_code IS NULL
               OR gl_account_name IS NULL OR category IS NULL
               OR LOWER(gl_account_name) LIKE '%%unknown%%'
               OR LOWER(category) LIKE '%%unknown%%')
        GROUP BY vendor_name
        ORDER BY SUM(gross_amount) DESC
        """,
        VENDORS + [TARGET_GL],
    )
    rows = cur.fetchall()
    print("Deposits needing normalization:")
    if not rows:
        print("  None")
    else:
        for r in rows:
            print(f"  {r[0]:<15} {r[1]:>5} receipts, ${r[2]:>13,.2f}")

    if dry_run:
        print("\nDRY RUN - no changes. Use --write to apply.")
        cur.close(); conn.close(); return

    # Update
    if RENAME_DEPOSIT_X:
        update_query = f"""
            UPDATE receipts
            SET gl_account_code = %s,
                gl_account_name = %s,
                category = %s,
                vendor_name = CASE WHEN vendor_name = 'DEPOSIT #X' THEN 'DEPOSIT' ELSE vendor_name END,
                verified_by_edit = %s,
                verified_at = NOW(),
                verified_by_user = %s
            WHERE vendor_name IN ({placeholders})
        """
    else:
        update_query = f"""
            UPDATE receipts
            SET gl_account_code = %s,
                gl_account_name = %s,
                category = %s,
                verified_by_edit = %s,
                verified_at = NOW(),
                verified_by_user = %s
            WHERE vendor_name IN ({placeholders})
        """

    params = [
        TARGET_GL,
        TARGET_GL_NAME,
        TARGET_CATEGORY,
        True,
        TARGET_VERIFIED_BY,
    ] + VENDORS

    cur.execute(update_query, params)
    updated = cur.rowcount
    conn.commit()
    print(f"\n✅ Updated {updated} receipts to GL {TARGET_GL} ({TARGET_GL_NAME}), category '{TARGET_CATEGORY}'")
    if RENAME_DEPOSIT_X:
        print("Vendor 'DEPOSIT #X' renamed to 'DEPOSIT'.")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
