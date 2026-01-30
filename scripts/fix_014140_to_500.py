"""
Fix 014140 to show $500 payment (not $1,000).
User confirmed: 014140 paid in full $500.
Currently has 2 x $500 payments = $1,000 (incorrect).
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
print("Charter 014140 Payment Fix")
print("="*80)
print()

# Get charter info
cur.execute("""
    SELECT reserve_number, charter_date, total_amount_due, paid_amount, balance
    FROM charters WHERE reserve_number = '014140'
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
    WHERE reserve_number = '014140'
    ORDER BY payment_date
""")
for row in cur.fetchall():
    pid, amt, pdate, key, method = row
    print(f"  ID {pid}: ${amt:.2f} on {pdate}, key={key}, method={method}")
print()

print("="*80)
print("FIX: Keep LMS-keyed payment (16860), remove duplicate (27797)")
print("="*80)
print()

if '--apply' in sys.argv:
    print("APPLYING FIX...")
    
    # Backup
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments_backup_014140_500fix_20251123 AS
        SELECT * FROM payments WHERE reserve_number = '014140'
    """)
    
    # Remove the non-keyed payment
    cur.execute("""
        UPDATE payments
        SET reserve_number = NULL, charter_id = NULL
        WHERE payment_id = 27797
    """)
    print(f"✓ Unlinked payment 27797")
    
    # Recalculate charter
    cur.execute("""
        UPDATE charters
        SET paid_amount = 500.00,
            balance = total_amount_due - 500.00
        WHERE reserve_number = '014140'
    """)
    print(f"✓ Recalculated charter 014140")
    
    conn.commit()
    print("\n✓ COMPLETE: Charter 014140 now shows $500 paid")
    
    # Verify
    cur.execute("SELECT total_amount_due, paid_amount, balance FROM charters WHERE reserve_number = '014140'")
    due, paid, bal = cur.fetchone()
    print(f"\nVerification: Due ${due:.2f}, Paid ${paid:.2f}, Balance ${bal:.2f}")
else:
    print("DRY RUN - use --apply to execute")

cur.close()
conn.close()
