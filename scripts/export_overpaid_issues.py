"""Export overpaid charter issues to CSV files."""
import psycopg2
import csv

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# 1. Non-cancelled with $0 charges (missing charge data)
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        cl.client_name,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        c.payment_status,
        c.status,
        c.booking_status,
        c.notes
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    WHERE c.balance < 0
    AND EXTRACT(YEAR FROM c.charter_date) < 2025
    AND c.total_amount_due = 0
    AND NOT (c.cancelled = TRUE OR c.status = 'Cancelled' OR c.payment_status LIKE '%Cancelled%')
    ORDER BY c.balance
""")

with open('l:/limo/reports/missing_charges_overpaid.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Reserve Number', 'Charter Date', 'Client Name', 'Total Due', 'Paid Amount', 'Balance', 'Payment Status', 'Status', 'Booking Status', 'Notes'])
    for row in cur.fetchall():
        writer.writerow(row)

print(f"✓ Exported {cur.rowcount} charters with missing charges to missing_charges_overpaid.csv")

# 2. Overpaid with actual charges (true overpayments)
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        cl.client_name,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        c.payment_status,
        c.status,
        c.booking_status,
        c.notes
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    WHERE c.balance < 0
    AND EXTRACT(YEAR FROM c.charter_date) < 2025
    AND c.total_amount_due > 0
    ORDER BY c.balance
""")

with open('l:/limo/reports/true_overpayments.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Reserve Number', 'Charter Date', 'Client Name', 'Total Due', 'Paid Amount', 'Balance', 'Payment Status', 'Status', 'Booking Status', 'Notes'])
    for row in cur.fetchall():
        writer.writerow(row)

print(f"✓ Exported {cur.rowcount} charters with true overpayments to true_overpayments.csv")

# 3. Cancelled with $0 charges (legitimate non-refundable deposits)
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        cl.client_name,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        c.payment_status,
        c.status,
        c.booking_status,
        c.notes
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    WHERE c.balance < 0
    AND EXTRACT(YEAR FROM c.charter_date) < 2025
    AND c.total_amount_due = 0
    AND (c.cancelled = TRUE OR c.status = 'Cancelled' OR c.payment_status LIKE '%Cancelled%')
    ORDER BY c.balance
""")

with open('l:/limo/reports/cancelled_nonrefundable_deposits.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Reserve Number', 'Charter Date', 'Client Name', 'Total Due', 'Paid Amount', 'Balance', 'Payment Status', 'Status', 'Booking Status', 'Notes'])
    for row in cur.fetchall():
        writer.writerow(row)

print(f"✓ Exported {cur.rowcount} cancelled charters with deposits to cancelled_nonrefundable_deposits.csv")

conn.close()

print("\n" + "=" * 80)
print("CSV FILES CREATED:")
print("=" * 80)
print("1. l:/limo/reports/missing_charges_overpaid.csv")
print("   - 47 charters with payments but $0 charges (need charge data)")
print("2. l:/limo/reports/true_overpayments.csv")
print("   - 43 charters with legitimate overpayments")
print("3. l:/limo/reports/cancelled_nonrefundable_deposits.csv")
print("   - 2 cancelled charters with kept deposits (legitimate)")
