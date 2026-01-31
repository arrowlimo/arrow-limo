import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='ArrowLimousine'
)

cur = conn.cursor()

# Find ALL transactions related to Welcome Wagon (including NSF)
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        check_number,
        category,
        is_nsf_charge,
        reconciliation_status,
        reconciliation_notes
    FROM banking_transactions 
    WHERE description ILIKE '%welcome wagon%' 
       OR description ILIKE '%check%215%'
       OR description ILIKE '%cheque%215%'
    ORDER BY transaction_date, transaction_id
""")

rows = cur.fetchall()

print(f"Found {len(rows)} Welcome Wagon related banking transactions:\n")
print(f"{'TX ID':<10} {'Date':<12} {'Description':<50} {'Debit':<10} {'Credit':<10} {'Check#':<10} {'NSF?':<6} {'Category'}")
print('-' * 150)

for row in rows:
    tx_id, tx_date, desc, debit, credit, balance, check_num, category, is_nsf, status, notes = row
    debit_str = f"{debit:.2f}" if debit else ""
    credit_str = f"{credit:.2f}" if credit else ""
    nsf_flag = "YES" if is_nsf else ""
    print(f"{tx_id:<10} {str(tx_date):<12} {desc[:50]:<50} {debit_str:>9} {credit_str:>9} {check_num or '':<10} {nsf_flag:<6} {category or ''}")
    if notes:
        print(f"           Notes: {notes}")

print(f"\nTotal transactions: {len(rows)}")

# Now check receipts linked to Welcome Wagon
print("\n" + "="*150)
print("\nRECEIPTS linked to Welcome Wagon:\n")

cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.banking_transaction_id,
        r.is_nsf,
        r.is_voided,
        r.category,
        bt.description as banking_desc,
        bt.check_number
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name ILIKE '%welcome wagon%'
    ORDER BY r.receipt_date, r.receipt_id
""")

receipt_rows = cur.fetchall()

print(f"{'Receipt ID':<12} {'Date':<12} {'Vendor':<35} {'Amount':<10} {'Banking ID':<12} {'NSF?':<6} {'Void?':<6} {'Check#':<10} {'Category'}")
print('-' * 150)

for row in receipt_rows:
    r_id, r_date, vendor, amount, bank_id, is_nsf, is_void, cat, bank_desc, check_num = row
    nsf_flag = "YES" if is_nsf else ""
    void_flag = "YES" if is_void else ""
    print(f"{r_id:<12} {str(r_date):<12} {vendor[:35]:<35} {amount:>9.2f} {bank_id or 'N/A':<12} {nsf_flag:<6} {void_flag:<6} {check_num or '':<10} {cat or ''}")

print(f"\nTotal receipts: {len(receipt_rows)}")

cur.close()
conn.close()
