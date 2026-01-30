import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

# Get all Welcome Wagon receipts across all years
cur.execute("""
    SELECT 
        receipt_id, 
        receipt_date, 
        EXTRACT(YEAR FROM receipt_date) as year,
        vendor_name, 
        gross_amount, 
        is_voided,
        exclude_from_reports,
        banking_transaction_id,
        description
    FROM receipts 
    WHERE vendor_name ILIKE '%welcome wagon%' 
    ORDER BY receipt_date
""")

rows = cur.fetchall()

print("All Welcome Wagon receipts across all years:")
print("="*120)
print(f"{'Receipt ID':<12} {'Date':<12} {'Year':<6} {'Amount':<10} {'Voided':<8} {'Excluded':<10} {'Banking TX':<12} {'Description'}")
print('-' * 120)

for r in rows:
    r_id, r_date, year, vendor, amount, voided, excluded, bank_tx, desc = r
    print(f"{r_id:<12} {str(r_date):<12} {int(year):<6} ${amount:>8.2f} {str(voided):<8} {str(excluded):<10} {bank_tx or 'N/A':<12} {desc or ''}")

years = set([int(r[2]) for r in rows])
print(f"\nTotal: {len(rows)} receipts")
print(f"Years present: {sorted(years)}")

# Check if any are incorrectly dated
print("\n" + "="*120)
print("\nChecking for potential date typos (receipts outside 2012):\n")

for r in rows:
    r_id, r_date, year, vendor, amount, voided, excluded, bank_tx, desc = r
    if int(year) != 2012:
        print(f"⚠️  Receipt {r_id}: {r_date} (Year {int(year)}) - ${amount:.2f} - Banking TX {bank_tx or 'N/A'}")
        
        # Check if the banking transaction has a different year
        if bank_tx:
            cur.execute("SELECT transaction_date FROM banking_transactions WHERE transaction_id = %s", (bank_tx,))
            bank_date = cur.fetchone()
            if bank_date:
                print(f"    Banking transaction date: {bank_date[0]}")

cur.close()
conn.close()
