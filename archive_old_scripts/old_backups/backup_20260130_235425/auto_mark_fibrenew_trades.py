import psycopg2

TRADE_RECEIPT_IDS = [60057, 148628]

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Show current state
cur.execute(
    """
    SELECT receipt_id, vendor_name, receipt_date, gross_amount, gl_account_code, payment_method
    FROM receipts
    WHERE receipt_id = ANY(%s)
    ORDER BY receipt_id
    """,
    (TRADE_RECEIPT_IDS,)
)
print("Before:")
for r in cur.fetchall():
    print(r)

# Update to rent trade
cur.execute(
    """
    UPDATE receipts
    SET gl_account_code = %s,
        gl_account_name = %s,
        category = %s,
        payment_method = %s,
        verified_by_edit = %s,
        verified_at = NOW(),
        verified_by_user = %s
    WHERE receipt_id = ANY(%s)
    """,
    (
        '5410',
        'Rent Expense',
        'Rent',
        'trade_of_services',
        True,
        'auto_fibrenew_trade_update',
        TRADE_RECEIPT_IDS,
    ),
)
print(f"Updated {cur.rowcount} receipts to GL 5410 rent as trade_of_services")
conn.commit()

cur.execute(
    """
    SELECT receipt_id, vendor_name, receipt_date, gross_amount, gl_account_code, payment_method
    FROM receipts
    WHERE receipt_id = ANY(%s)
    ORDER BY receipt_id
    """,
    (TRADE_RECEIPT_IDS,)
)
print("\nAfter:")
for r in cur.fetchall():
    print(r)

cur.close()
conn.close()
