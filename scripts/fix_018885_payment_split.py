import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST','localhost'),
    dbname=os.environ.get('DB_NAME','almsdata'),
    user=os.environ.get('DB_USER','postgres'),
    password=os.environ.get('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("Fixing incorrect payment split for 018885...")

# Delete the incorrectly split payment from 019127
cur.execute("DELETE FROM payments WHERE payment_id = 78951")
print(f"✓ Deleted split payment 78951 from 019127")

# Restore payment 78672 to full amount for 018885
cur.execute("""
    UPDATE payments
    SET amount = 204.17,
        notes = 'Imported from LMS Payment ID 25122 | Corrected: was incorrectly split to 019127'
    WHERE payment_id = 78672
""")
print(f"✓ Restored payment 78672 to full $204.17 for 018885")

# Recalculate 018885
cur.execute("""
    UPDATE charters
    SET paid_amount = (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '018885'),
        balance = total_amount_due - (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '018885')
    WHERE reserve_number = '018885'
""")

# Recalculate 019127
cur.execute("""
    UPDATE charters
    SET paid_amount = (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '019127'),
        balance = total_amount_due - (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '019127')
    WHERE reserve_number = '019127'
""")

# Get updated balances
cur.execute("SELECT total_amount_due, paid_amount, balance FROM charters WHERE reserve_number = '018885'")
c1 = cur.fetchone()
print(f"\n018885: total=${c1[0]} paid=${c1[1]} balance=${c1[2]}")

cur.execute("SELECT total_amount_due, paid_amount, balance FROM charters WHERE reserve_number = '019127'")
c2 = cur.fetchone()
print(f"019127: total=${c2[0]} paid=${c2[1]} balance=${c2[2]}")

conn.commit()
print("\n✓ Fix complete")

cur.close()
conn.close()
