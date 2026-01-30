"""
Record Fibrenew Office Rent and 50% Utilities invoices, and try to match to banking transactions.

Invoices provided:
- 2019-10-01 invoice 8979: Rent base 650.00 + GST 32.50 = 682.50
- 2019-10-01 invoice 8980: 0.5 of energy bill 27.31 + 0.5 of Enmax 118.04 + GST 7.27 = 152.62
- 2019-07-01 invoice 8832: Rent base 650.00 + GST 32.50 = 682.50
- 2019-07-11 invoice 8833: 0.5 Enmax 28.07 + 0.5 Direct Energy 28.70 + GST 7.29 + other utilities 117.77? total 153.13

Notes:
- We'll insert into receipts table with source_system='MANUAL_ENTRY' and source_hash unique per invoice.
- We'll not insert net_amount (generated). We'll set gst_amount explicitly.
- We'll try to locate bank debits equal to totals within +/- 10 days of invoice_date and add TXID to receipts.comment.
"""
import argparse
import psycopg2
from decimal import Decimal

def conn():
    return psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

INVOICES = [
    {
        'invoice_number': '8979',
        'invoice_date': '2019-10-01',
        'vendor_name': 'Fibrenew Office Rent',
        'description': 'Office Rent base $650.00 + GST $32.50 (Invoice 8979)',
        'gross_amount': Decimal('682.50'),
        'gst_amount': Decimal('32.50'),
        'category': 'Office Rent',
    },
    {
        'invoice_number': '8980',
        'invoice_date': '2019-10-01',
        'vendor_name': 'Fibrenew Office Rent',
        'description': 'Utilities 50%: Energy $27.31 + Enmax $118.04 + GST $7.27 (Invoice 8980)',
        'gross_amount': Decimal('152.62'),
        'gst_amount': Decimal('7.27'),
        'category': 'Utilities',
    },
    {
        'invoice_number': '8832',
        'invoice_date': '2019-07-01',
        'vendor_name': 'Fibrenew Office Rent',
        'description': 'Office Rent base $650.00 + GST $32.50 (Invoice 8832)',
        'gross_amount': Decimal('682.50'),
        'gst_amount': Decimal('32.50'),
        'category': 'Office Rent',
    },
    {
        'invoice_number': '8833',
        'invoice_date': '2019-07-11',
        'vendor_name': 'Fibrenew Office Rent',
        'description': 'Utilities 50%: Enmax $28.07 + Direct Energy $28.70 + GST $7.29 + other $117.77 (Invoice 8833)',
        'gross_amount': Decimal('153.13'),
        'gst_amount': Decimal('7.29'),
        'category': 'Utilities',
    },
    {
        'invoice_number': '8942',
        'invoice_date': '2019-09-04',
        'vendor_name': 'Fibrenew Office Rent',
        'description': 'Office Rent base $650.00 + GST $32.50 (Invoice 8942)',
        'gross_amount': Decimal('682.50'),
        'gst_amount': Decimal('32.50'),
        'category': 'Office Rent',
    },
    {
        'invoice_number': '8943',
        'invoice_date': '2019-09-04',
        'vendor_name': 'Fibrenew Office Rent',
        'description': 'Utilities 50%: Direct Energy $33.08 + Enmax $142.07 + GST $8.76 (Invoice 8943)',
        'gross_amount': Decimal('183.91'),
        'gst_amount': Decimal('8.76'),
        'category': 'Utilities',
    },
]

def ensure_unique(cur, inv):
    # Use unique source hash
    sh = f"FIBRENEW_{inv['invoice_number']}_{inv['invoice_date']}_{inv['gross_amount']}"
    return sh


def upsert_receipt(cur, inv):
    source_hash = ensure_unique(cur, inv)
    # Check existing
    cur.execute("SELECT id FROM receipts WHERE source_hash = %s", (source_hash,))
    row = cur.fetchone()
    if row:
        return row[0], False
    # Insert
    cur.execute(
        """
        INSERT INTO receipts (receipt_date, vendor_name, gross_amount, gst_amount, description, category, source_system, source_reference, validation_status, source_hash)
        VALUES (%s, %s, %s, %s, %s, %s, 'MANUAL_ENTRY', %s, 'VERIFIED', %s)
        RETURNING id
        """,
        (inv['invoice_date'], inv['vendor_name'], inv['gross_amount'], inv['gst_amount'], inv['description'], inv['category'], f"Invoice {inv['invoice_number']}", source_hash)
    )
    rid = cur.fetchone()[0]
    return rid, True


def find_bank_matches(cur, inv, window_days=10):
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description, debit_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s::date - INTERVAL '%s days' AND %s::date + INTERVAL '%s days'
          AND debit_amount IS NOT NULL AND ABS(debit_amount - %s) < 0.01
        ORDER BY ABS(transaction_date - %s::date), transaction_date
        LIMIT 5
        """,
        (inv['invoice_date'], window_days, inv['invoice_date'], window_days, inv['gross_amount'], inv['invoice_date'])
    )
    return cur.fetchall()


def annotate_receipt_with_match(cur, receipt_id, txid):
    # Add the TXID to comment field (append)
    cur.execute("SELECT comment FROM receipts WHERE id=%s", (receipt_id,))
    prev = cur.fetchone()[0]
    note = f"Matched banking TX {txid}"
    new_comment = note if not prev else (prev + '; ' + note)
    cur.execute("UPDATE receipts SET comment=%s WHERE id=%s", (new_comment, receipt_id))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply inserts and comment updates')
    args = ap.parse_args()

    cn = conn()
    try:
        cur = cn.cursor()
        inserted = []
        print("\nFibrenew Office Rent & Utilities processing\n")
        for inv in INVOICES:
            rid, created = upsert_receipt(cur, inv)
            action = 'INSERTED' if created else 'EXISTS'
            print(f"{action}: receipt_id={rid} {inv['invoice_date']} {inv['invoice_number']} {inv['vendor_name']} ${inv['gross_amount']}")
            matches = find_bank_matches(cur, inv)
            if matches:
                print("  Candidates:")
                for (txid, tdate, desc, debit) in matches:
                    print(f"   • TX {txid} {tdate} ${debit:,.2f} {desc}")
                # pick best (first)
                if args.write:
                    annotate_receipt_with_match(cur, rid, matches[0][0])
            else:
                print("  No banking match within +/-10 days for exact amount.")
        if args.write:
            cn.commit()
            print("\nSaved inserts and annotations.")
        else:
            print("\nDry-run only. Re-run with --write to save.")
    finally:
        cn.close()

if __name__ == '__main__':
    main()
