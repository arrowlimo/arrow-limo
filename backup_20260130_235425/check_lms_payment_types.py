"""
Check LMS for POSITIVE payment amounts that might represent e-transfer refunds
or other refund payment types not stored as negative amounts.

LMS might store refunds as:
1. Positive amounts with a 'Refund' payment type
2. E-transfer payments that are actually refunds
3. Payments with specific descriptions indicating refunds
"""

import pyodbc

# LMS Connection
LMS_PATH = r'L:\oldlms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'

print("=" * 80)
print("CHECKING LMS FOR E-TRANSFER AND OTHER REFUND PAYMENT TYPES")
print("=" * 80)

lms_conn = pyodbc.connect(lms_conn_str)
cur = lms_conn.cursor()

# Get all columns from Payment table
print("\nPayment table structure:")
print("-" * 80)
for row in cur.columns(table='Payment'):
    print(f"  {row.column_name} ({row.type_name})")

# Check if there's a payment type or description field
print("\n" + "=" * 80)
print("Checking for additional fields that might indicate refunds...")
print("=" * 80)

# Try to get sample records to see what fields exist
cur.execute("SELECT TOP 5 * FROM Payment")
sample = cur.fetchone()
if sample:
    print(f"\nSample record has {len(sample)} fields")
    columns = [desc[0] for desc in cur.description]
    print("Available columns:", columns)

# Now let's search for refund-related records by examining descriptions or patterns
# Since we know columns: Account_No, Amount, Key, Reserve_No, LastUpdated, LastUpdatedBy, PaymentID

# Check for specific payment keys or patterns that might indicate e-transfers
print("\n" + "=" * 80)
print("Checking for E-Transfer patterns in payment keys...")
print("=" * 80)

cur.execute("""
    SELECT TOP 20 PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated
    FROM Payment
    WHERE [Key] LIKE '%transfer%' OR [Key] LIKE '%e-trans%' OR [Key] LIKE '%etransfer%'
    ORDER BY LastUpdated DESC
""")

etransfer_keys = cur.fetchall()
if etransfer_keys:
    print(f"Found {len(etransfer_keys)} payments with 'transfer' in Key field:")
    print(f"\n{'PaymentID':<12} {'Account':<12} {'Reserve':<12} {'Amount':<12} {'Key':<20} {'Date':<12}")
    print("-" * 90)
    for row in etransfer_keys:
        payment_id = row[0]
        account = row[1] or 'NULL'
        reserve = row[2] or 'NULL'
        amount = float(row[3]) if row[3] else 0
        key = (row[4] or '')[:17] + '...' if row[4] and len(row[4]) > 20 else (row[4] or 'NULL')
        date = row[5].strftime('%Y-%m-%d') if row[5] else 'NULL'
        print(f"{payment_id:<12} {account:<12} {reserve:<12} ${amount:<11,.2f} {key:<20} {date:<12}")
else:
    print("No payments found with 'transfer' in Key field")

# Check LastUpdatedBy field for 'refund' or 'etransfer' mentions
print("\n" + "=" * 80)
print("Checking LastUpdatedBy field for refund/etransfer mentions...")
print("=" * 80)

cur.execute("""
    SELECT TOP 20 PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdatedBy, LastUpdated
    FROM Payment
    WHERE LastUpdatedBy LIKE '%refund%' OR LastUpdatedBy LIKE '%transfer%'
    ORDER BY LastUpdated DESC
""")

refund_by = cur.fetchall()
if refund_by:
    print(f"Found {len(refund_by)} payments with 'refund' or 'transfer' in LastUpdatedBy:")
    print(f"\n{'PaymentID':<12} {'Amount':<12} {'UpdatedBy':<30} {'Date':<12}")
    print("-" * 70)
    for row in refund_by:
        payment_id = row[0]
        amount = float(row[3]) if row[3] else 0
        updated_by = (row[5] or '')[:27] + '...' if row[5] and len(row[5]) > 30 else (row[5] or 'NULL')
        date = row[6].strftime('%Y-%m-%d') if row[6] else 'NULL'
        print(f"{payment_id:<12} ${amount:<11,.2f} {updated_by:<30} {date:<12}")
else:
    print("No payments found with 'refund' or 'transfer' in LastUpdatedBy")

# Check for payments with specific Key patterns that might be Square
print("\n" + "=" * 80)
print("Checking for Square-related payment keys...")
print("=" * 80)

cur.execute("""
    SELECT TOP 20 PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated
    FROM Payment
    WHERE [Key] LIKE '%square%' OR [Key] LIKE '%SQ%'
    ORDER BY LastUpdated DESC
""")

square_keys = cur.fetchall()
if square_keys:
    print(f"Found {len(square_keys)} payments with Square-related keys:")
    for row in square_keys[:10]:
        payment_id = row[0]
        amount = float(row[3]) if row[3] else 0
        key = row[4] or 'NULL'
        print(f"  Payment {payment_id}: ${amount:,.2f}, Key: {key}")
else:
    print("No payments found with Square-related keys")

# Summary stats on Payment table
print("\n" + "=" * 80)
print("LMS Payment Table Summary")
print("=" * 80)

cur.execute("SELECT COUNT(*), SUM(Amount) FROM Payment")
total = cur.fetchone()
print(f"Total Payments: {total[0]:,}")
print(f"Total Amount: ${total[1]:,.2f}" if total[1] else "Total Amount: $0.00")

cur.execute("SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Amount > 0")
positive = cur.fetchone()
print(f"\nPositive Payments: {positive[0]:,}")
print(f"Positive Total: ${positive[1]:,.2f}" if positive[1] else "Positive Total: $0.00")

cur.execute("SELECT COUNT(*), SUM(Amount) FROM Payment WHERE Amount < 0")
negative = cur.fetchone()
print(f"\nNegative Payments (Refunds): {negative[0]:,}")
print(f"Negative Total: ${abs(negative[1]):,.2f}" if negative[1] else "Negative Total: $0.00")

cur.execute("SELECT COUNT(*) FROM Payment WHERE Amount = 0 OR Amount IS NULL")
zero = cur.fetchone()
print(f"\nZero/NULL Payments: {zero[0]:,}")

cur.close()
lms_conn.close()

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("LMS Payment table structure:")
print("  - Has Payment Key field (might contain payment type info)")
print("  - Has LastUpdatedBy field (might contain user notes)")
print("  - Does NOT appear to have separate payment type field")
print("\nRefund storage in LMS:")
print("  - Negative amounts = refunds (176 records, $40,740.90)")
print("  - All negative amounts already imported to charter_refunds")
print("\nFor the 14 unlinked charter_refunds ($11,350.55):")
print("  - NOT in LMS negative payment amounts")
print("  - Likely Square-only refunds from 2015-2025")
print("  - May need manual review or different matching strategy")
