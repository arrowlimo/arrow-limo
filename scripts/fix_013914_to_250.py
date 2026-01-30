"""
Fix 013914 to show $250 payment (not $1,000).
User confirmed: 013914 paid $250 total.
Currently has 2 x $500 payments = $1,000 (incorrect).

Options:
1. Keep one $500 payment and adjust amount to $250
2. Remove one $500 payment and adjust remaining to $250
3. Remove both and verify if there's a $250 payment elsewhere
"""
import psycopg2, os, sys

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("="*80)
print("Charter 013914 Payment Analysis")
print("="*80)
print()

# Get charter info
cur.execute("""
    SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance
    FROM charters WHERE reserve_number = '013914'
""")
row = cur.fetchone()
print(f"Charter: {row[0]}")
print(f"Date: {row[1]}")
print(f"Total Due: ${row[2]:.2f}")
print(f"Currently Paid: ${row[3]:.2f}")
print(f"Balance: ${row[4]:.2f}")
print()

# Current payments
print("Current Payments:")
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key, payment_method
    FROM payments
    WHERE reserve_number = '013914'
    ORDER BY payment_date
""")
for row in cur.fetchall():
    pid, amt, pdate, key, method = row
    print(f"  ID {pid}: ${amt:.2f} on {pdate}, key={key}, method={method}")
print()

# Check if there's a $250 payment anywhere for this charter
cur.execute("""
    SELECT payment_id, amount, payment_date, payment_key, reserve_number, charter_id
    FROM payments
    WHERE (reserve_number = '013914' OR charter_id IN (SELECT charter_id FROM charters WHERE reserve_number = '013914'))
    AND amount = 250
""")
result = cur.fetchall()
if result:
    print("Found $250 payment(s):")
    for row in result:
        print(f"  ID {row[0]}: ${row[1]:.2f} on {row[2]}, key={row[3]}, res={row[4]}, charter_id={row[5]}")
else:
    print("No $250 payment found. Need to adjust one of the $500 payments to $250.")

print()
print("="*80)
print("RECOMMENDATION:")
print("="*80)
print("Keep the LMS-keyed payment (16378) and adjust amount to $250.")
print("Remove the other payment (28070).")
print()

if '--apply' in sys.argv:
    print("APPLYING FIX...")
    
    # Backup
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments_backup_013914_250fix_20251123 AS
        SELECT * FROM payments WHERE reserve_number = '013914'
    """)
    
    # Update LMS-keyed payment to $250
    cur.execute("""
        UPDATE payments 
        SET amount = 250.00
        WHERE payment_id = 16378
    """)
    print(f"✓ Updated payment 16378 to $250.00")
    
    # Remove the other payment
    cur.execute("""
        UPDATE payments
        SET reserve_number = NULL, charter_id = NULL
        WHERE payment_id = 28070
    """)
    print(f"✓ Unlinked payment 28070")
    
    # Recalculate charter
    cur.execute("""
        UPDATE charters
        SET paid_amount = 250.00,
            balance = total_amount_due - 250.00
        WHERE reserve_number = '013914'
    """)
    print(f"✓ Recalculated charter 013914")
    
    conn.commit()
    print("\n✓ COMPLETE: Charter 013914 now shows $250 paid")
    
    # Verify
    cur.execute("SELECT total_amount_due, paid_amount, balance FROM charters WHERE reserve_number = '013914'")
    due, paid, bal = cur.fetchone()
    print(f"\nVerification: Due ${due:.2f}, Paid ${paid:.2f}, Balance ${bal:.2f}")
else:
    print("DRY RUN - use --apply to execute")

cur.close()
conn.close()
