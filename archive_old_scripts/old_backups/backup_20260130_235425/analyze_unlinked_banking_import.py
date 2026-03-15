#!/usr/bin/env python
"""Inspect unlinked receipts where source_system in banking_import variants."""
import psycopg2, os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD",os.environ.get("DB_PASSWORD"))

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

variants=("banking_import","BANKING_IMPORT")
for variant in variants:
    print("\n"+"="*80)
    print(f"Unlinked receipts for source_system='{variant}'")
    print("="*80)
    cur.execute("""
        SELECT COUNT(*), ROUND(SUM(COALESCE(gross_amount,0))::numeric,2)
        FROM receipts
        WHERE banking_transaction_id IS NULL AND source_system = %s
    """, (variant,))
    cnt,total=cur.fetchone()
    print(f"Count: {cnt} | Total: ${float(total):,.2f}")

    cur.execute("""
        SELECT source_file, COUNT(*) as c, ROUND(SUM(COALESCE(gross_amount,0))::numeric,2) as s
        FROM receipts
        WHERE banking_transaction_id IS NULL AND source_system = %s
        GROUP BY source_file
        ORDER BY c DESC
        LIMIT 10
    """, (variant,))
    rows=cur.fetchall()
    print("\nTop source_files:")
    for sf,c,s in rows:
        print(f"  {sf or 'None':<30} {c:>5} | ${float(s):>12.2f}")

    cur.execute("""
        SELECT receipt_date, vendor_name, gross_amount, description, source_file
        FROM receipts
        WHERE banking_transaction_id IS NULL AND source_system = %s
        ORDER BY receipt_date DESC
        LIMIT 10
    """, (variant,))
    print("\nSample rows (most recent):")
    for r in cur.fetchall():
        date,vendor,amt,desc,sf=r
        print(f"  {date} | {vendor[:30] if vendor else 'None':<30} | ${float(amt):>10.2f} | { (desc or '')[:60]} | {sf or 'None'}")

cur.close(); conn.close()
