import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST','localhost'),
    dbname=os.environ.get('DB_NAME','almsdata'),
    user=os.environ.get('DB_USER','postgres'),
    password=os.environ.get('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()

# LMS payments from screenshot
lms_payments = [
    ('2024-09-23', 500.00, 'Master Card', 'DEPOSIT'),
    ('2025-05-05', 479.70, 'Master Card', 'DEPOSIT', 'Bill#6'),
    ('2025-07-29', 204.17, 'Master Card', 'RECEIVED'),
    ('2025-08-01', 712.05, 'Master Card', 'RECEIVED'),
]

print("LMS Payments (from screenshot):")
lms_total = 0
for pmt in lms_payments:
    date, amt = pmt[0], pmt[1]
    desc = pmt[3] if len(pmt) > 3 else ''
    note = pmt[4] if len(pmt) > 4 else ''
    print(f"  {date} ${amt:8.2f} {desc:10} {note}")
    lms_total += amt
print(f"LMS Total: ${lms_total:.2f}")

# Database payments
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key, notes
    FROM payments 
    WHERE reserve_number = '018885'
    ORDER BY payment_date
""")
db_payments = cur.fetchall()

print("\nDatabase Payments:")
db_total = 0
for pmt in db_payments:
    pid, amt, date, key, notes = pmt
    print(f"  {date} ${amt:8.2f} key:{key} notes:{notes}")
    db_total += amt
print(f"DB Total: ${db_total:.2f}")

print(f"\nMismatch: ${db_total:.2f} - ${lms_total:.2f} = ${db_total - lms_total:.2f}")

# Find specific discrepancies
print("\nDetailed Comparison:")
print("Date       | LMS     | DB      | Diff")
print("-----------+---------+---------+--------")

# Create dict by date for easier comparison
db_by_date = {}
for pmt in db_payments:
    date = str(pmt[2])
    if date not in db_by_date:
        db_by_date[date] = []
    db_by_date[date].append(pmt[1])

for lms_pmt in lms_payments:
    date = lms_pmt[0]
    lms_amt = lms_pmt[1]
    db_amts = db_by_date.get(date, [0])
    db_amt = sum(db_amts)
    diff = db_amt - lms_amt
    marker = " <--" if abs(diff) > 0.01 else ""
    print(f"{date} | ${lms_amt:7.2f} | ${db_amt:7.2f} | ${diff:7.2f}{marker}")

cur.close()
conn.close()
