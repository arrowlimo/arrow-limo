#!/usr/bin/env python3
import os, psycopg2

def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )
    cur = conn.cursor()
    cur.execute('SELECT count(*) FROM receipts WHERE created_from_banking=TRUE')
    banking_receipts_total = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM banking_receipt_matching_ledger")
    receipt_links_total = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM banking_receipt_matching_ledger WHERE match_type='auto_fees'")
    auto_fees_links = cur.fetchone()[0]
    cur.execute('SELECT count(*) FROM banking_payment_links')
    payment_links_total = cur.fetchone()[0]
    cur.execute("SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, created_at FROM receipts WHERE created_from_banking=TRUE ORDER BY created_at DESC LIMIT 5")
    recent_receipts = cur.fetchall()
    cur.execute("SELECT banking_transaction_id, payment_id, link_confidence, created_at FROM banking_payment_links ORDER BY created_at DESC LIMIT 5")
    recent_payment_links = cur.fetchall()
    print('banking_receipts_total', banking_receipts_total)
    print('receipt_links_total', receipt_links_total)
    print('auto_fees_links', auto_fees_links)
    print('payment_links_total', payment_links_total)
    print('recent_banking_receipts', recent_receipts)
    print('recent_payment_links', recent_payment_links)
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
