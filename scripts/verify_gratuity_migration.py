import psycopg2, os
from datetime import datetime

DB_HOST=os.environ.get('DB_HOST','localhost')
DB_NAME=os.environ.get('DB_NAME','almsdata')
DB_USER=os.environ.get('DB_USER','postgres')
DB_PASSWORD=os.environ.get('DB_PASSWORD',os.environ.get("DB_PASSWORD"))

def get_conn():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def main():
    print("==== Verify Gratuity Migration ====", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    conn=get_conn(); cur=conn.cursor()

    # Detect backup table (latest with migration run timestamp)
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_name LIKE 'receipts_gratuity_migration_backup_%'
        ORDER BY table_name DESC
        LIMIT 1
    """)
    backup_row=cur.fetchone()
    backup_table=backup_row[0] if backup_row else None
    print(f"Backup table detected: {backup_table}")

    # Original gratuity totals from backup (pre reclass)
    if backup_table:
        cur.execute(f"""
            SELECT COUNT(*) , COALESCE(SUM(gross_amount),0), MIN(receipt_date), MAX(receipt_date)
            FROM {backup_table}
        """)
        b_count, b_sum, b_min, b_max = cur.fetchone()
    else:
        b_count=b_sum=b_min=b_max=None

    # Current reclassified receipts (do not depend on description marker; case-insensitive category)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount),0), MIN(receipt_date), MAX(receipt_date)
        FROM receipts
        WHERE LOWER(category)='gratuity_income' AND gross_amount>0
    """)
    r_count, r_sum, r_min, r_max = cur.fetchone()

    # Ledger entries (unified_general_ledger) created
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(credit_amount),0), MIN(transaction_date), MAX(transaction_date)
        FROM unified_general_ledger
        WHERE account_code='4150' AND description LIKE '[gratuity:%' AND credit_amount>0
    """)
    l_count, l_sum, l_min, l_max = cur.fetchone()

    # Duplicate detection: any receipt id appearing more than once in ledger descriptions
    # Regex adjusted to stop at pipe after receipt_id
    cur.execute("""
        SELECT substring(description from '\\[gratuity:(\\d+)\\|') AS rid, COUNT(*) cnt, SUM(credit_amount)
        FROM unified_general_ledger
        WHERE account_code='4150' AND description LIKE '[gratuity:%' AND credit_amount>0
        GROUP BY 1 HAVING COUNT(*)>1 ORDER BY cnt DESC
    """)
    dup_rows=cur.fetchall()

    # Missing ledger entries: receipts without corresponding ledger entry
    cur.execute("""
        SELECT r.receipt_id
        FROM receipts r
        LEFT JOIN unified_general_ledger ugl
          ON ugl.account_code='4150' AND ugl.description LIKE '[gratuity:'||r.receipt_id||'%'
        WHERE LOWER(r.category)='gratuity_income' AND r.gross_amount>0 AND ugl.id IS NULL
        LIMIT 25
    """)
    missing_rows=cur.fetchall()

    # Reserve number coverage
    cur.execute("""
        SELECT COUNT(*) FILTER (WHERE reserve_number IS NOT NULL), COUNT(*)
        FROM gratuity_income_links
    """)
    rn_with, rn_total = cur.fetchone()

    print("\n--- Summary Totals ---")
    print(f"Backup (pre-migration): count={b_count} sum={b_sum} range=({b_min},{b_max})")
    print(f"Receipts reclassified (category change): count={r_count} sum={r_sum} range=({r_min},{r_max})")
    print(f"Ledger entries:        count={l_count} sum={l_sum} range=({l_min},{l_max})")
    diff_sum = (r_sum or 0) - (l_sum or 0)
    print(f"Amount difference receipts - ledger: {diff_sum:,.2f}")

    status = []
    # Double-count logic: if receipts not reclassified (r_count==0) but ledger matches backup, treat as ledger-only migration
    if r_count == 0 and b_count == l_count and abs((b_sum or 0) - (l_sum or 0)) < 0.01:
        status.append("OK: ledger entries match backup; receipts left unchanged (ledger-only migration)")
    elif b_sum == l_sum == r_sum and b_count == r_count == l_count:
        status.append("OK: counts & sums match backup → no double-count")
    else:
        status.append("WARN: mismatch between backup / receipts / ledger totals")

    if not dup_rows:
        status.append("OK: no duplicate ledger gratuity entries")
    else:
        status.append(f"WARN: {len(dup_rows)} duplicate ledger receipt_ids (check regex)")

    if not missing_rows:
        status.append("OK: all reclassified receipts have ledger entry")
    else:
        status.append(f"WARN: {len(missing_rows)} receipts missing ledger entry (sample listed)")

    coverage = (rn_with / rn_total * 100) if rn_total else 0
    status.append(f"Reserve number coverage: {rn_with}/{rn_total} ({coverage:.1f}%)")

    print("\n--- Status ---")
    for s in status:
        print("* " + s)

    if dup_rows:
        print("\nDuplicate ledger entries (receipt_id,count,sum):")
        for rid, cnt, tsum in dup_rows[:15]:
            print(f"  {rid} | {cnt} | {tsum}")
    # If mismatch, show sample of receipts for inspection
    if r_count != b_count and r_count > 0:
        print("\nSample reclassified receipts (first 10):")
        cur.execute("""
            SELECT receipt_id, receipt_date, gross_amount, category, description
            FROM receipts WHERE LOWER(category)='gratuity_income' AND gross_amount>0
            ORDER BY receipt_date LIMIT 10
        """)
        for rec_id, rec_date, rec_gross, rec_cat, rec_desc in cur.fetchall():
            print(f"  {rec_id} | {rec_date} | {rec_gross:.2f} | {rec_cat} | {rec_desc[:60]}")
    if missing_rows:
        print("\nSample missing ledger receipt_ids:")
        for (rid,) in missing_rows:
            print(f"  {rid}")

    conn.close()

if __name__=='__main__':
    main()
