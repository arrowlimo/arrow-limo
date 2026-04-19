"""
Check remaining unlinked 2012 debit txns for account 1615 (excluding is_transfer=True ones).
Show reconciliation_status, business_personal, and any matching receipts by amount+date.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

ACCT = '1615'

cur.execute("""
    SELECT bt.transaction_id, bt.transaction_date, bt.debit_amount, bt.description,
           bt.reconciliation_status, bt.is_transfer, bt.business_personal, bt.check_number
    FROM banking_transactions bt
    WHERE bt.account_number=%s
    AND bt.transaction_date >= '2012-01-01' AND bt.transaction_date < '2013-01-01'
    AND bt.debit_amount IS NOT NULL
    AND NOT EXISTS (
        SELECT 1 FROM receipt_banking_links rbl WHERE rbl.transaction_id = bt.transaction_id
    )
    ORDER BY bt.transaction_date
""", (ACCT,))
rows = cur.fetchall()

print(f"Unlinked debit txns: {len(rows)}")
print(f"{'date':<12} {'debit':>8}  {'status':<15} {'transfer':<9} {'biz_pers':<15} {'chk':<6}  description")
print("-"*100)
for r in rows:
    tid, dt, debit, desc, status, is_xfer, biz_pers, chkno = r
    print(f"{str(dt):<12} ${float(debit):>7.2f}  {str(status):<15} {str(is_xfer):<9} {str(biz_pers):<15} {str(chkno or ''):<6}  {(desc or '')[:60]}  [id={tid}]")

print()
# For each unlinked non-transfer debit, look for matching receipts by amount +-1 day
print("=== Searching for matching receipts by amount+date ===")
for r in rows:
    tid, dt, debit, desc, status, is_xfer, biz_pers, chkno = r
    if is_xfer:
        continue
    cur.execute("""
        SELECT r.receipt_id, r.receipt_date, r.gross_amount, r.vendor_name, r.description, va.canonical_vendor
        FROM receipts r
        LEFT JOIN vendor_accounts va ON va.account_id = r.vendor_account_id
        WHERE r.gross_amount = %s
        AND r.receipt_date BETWEEN %s::date - interval '3 days' AND %s::date + interval '3 days'
        AND NOT EXISTS (SELECT 1 FROM receipt_banking_links rbl WHERE rbl.receipt_id = r.receipt_id)
        ORDER BY r.receipt_date
    """, (debit, dt, dt))
    matches = cur.fetchall()
    tag = "[TRANSFER]" if is_xfer else ""
    if matches:
        print(f"\n  bt {tid} {dt} ${float(debit):.2f} {desc} {tag}")
        for m in matches:
            print(f"    -> receipt {m[0]} {m[1]} ${float(m[2]):.2f} vendor={m[3]} canonical={m[5]} desc={str(m[4])[:50]}")
    else:
        print(f"\n  bt {tid} {dt} ${float(debit):.2f} {desc} {tag}  -- NO RECEIPT MATCH")

conn.close()
