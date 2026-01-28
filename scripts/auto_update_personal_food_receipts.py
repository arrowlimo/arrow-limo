"""
Auto-update personal food/entertainment receipts for fast food/coffee/sushi/cineplex vendors.
Rule: default to personal draws unless already marked business entertainment/meals.
- Vendors: McDonalds, Wendys, Tim Hortons, Sushi variants, Cineplex.
- Skip if GL or category already mentions 'entertain' or 'meal' (business entertainment meals).
- Update others to GL 9999 (Personal Draws), category 'Food - Personal', payment_method 'personal'.
"""

import psycopg2
import sys

VENDOR_PATTERNS = [
    '%mcdonald%',
    '%wendy%',
    '%tim hortons%',
    '%tim horton%',
    '%tim hortin%',
    '%sushi%',
    '%susi%',
    '%cineplex%',
    '%ciniplex%',
]

EXCLUDE_BIZ = [
    '%entertain%',
    '%meal%',
]

def main():
    dry_run = '--dry-run' in sys.argv or '--write' not in sys.argv

    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
    cur = conn.cursor()

    vendor_like = ["LOWER(vendor_name) LIKE %s" for _ in VENDOR_PATTERNS]
    vendor_cond = "(" + " OR ".join(vendor_like) + ")"

    exclude_like = [
        "(LOWER(gl_account_name) LIKE %s OR LOWER(category) LIKE %s)" for _ in EXCLUDE_BIZ
    ]
    exclude_pairs = []
    for p in EXCLUDE_BIZ:
        exclude_pairs.extend([p, p])
    exclude_cond = "(" + " OR ".join(exclude_like) + ")"

    params_preview = VENDOR_PATTERNS + exclude_pairs

    cur.execute(f"""
        SELECT vendor_name, gl_account_code, gl_account_name, category, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE {vendor_cond}
          AND NOT {exclude_cond}
          AND (gl_account_code != '9999' OR gl_account_code IS NULL)
        GROUP BY vendor_name, gl_account_code, gl_account_name, category
        ORDER BY SUM(gross_amount) DESC
    """, params_preview)

    rows = cur.fetchall()
    if not rows:
        print("\n✅ Nothing to update; all are already personal or marked business entertainment/meals")
        cur.close(); conn.close(); return

    print("Personal-food receipts to move to GL 9999 (Personal Draws), excluding entertainment/meals:")
    print(f"{'Vendor':<40} {'GL':<8} {'GL Name':<35} {'Category':<25} {'Count':>6} {'Amount':>12}")
    print('-'*140)
    total_c = 0; total_a = 0
    for r in rows:
        total_c += r[4]; total_a += r[5] or 0
        print(f"{r[0][:39]:<40} {str(r[1] or 'NULL'):<8} {str(r[2] or '')[:34]:<35} {str(r[3] or '')[:24]:<25} {r[4]:>6} ${r[5]:>11,.2f}")
    print('-'*140)
    print(f"Total to update: {total_c} receipts, ${total_a:,.2f}")

    if dry_run:
        print("\nDRY RUN - no changes. Use --write to apply.")
        cur.close(); conn.close(); return

    update_query = f"""
        UPDATE receipts
        SET gl_account_code = %s,
            gl_account_name = %s,
            category = %s,
            payment_method = %s,
            verified_by_edit = %s,
            verified_at = NOW(),
            verified_by_user = %s
        WHERE {vendor_cond}
          AND NOT {exclude_cond}
          AND (gl_account_code != %s OR gl_account_code IS NULL)
    """

    params_update = [
        '9999',
        'Personal Draws',
        'Food - Personal',
        'personal',
        True,
        'auto_personal_food_update',
    ] + VENDOR_PATTERNS + exclude_pairs + ['9999']

    cur.execute(update_query, params_update)
    updated = cur.rowcount
    conn.commit()
    print(f"\n✅ Updated {updated} receipts to GL 9999 (Personal Draws)")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
