from _db_connect import connect_db

conn = connect_db()
cur = conn.cursor()

# Fix 020048 (charter_id=19232): clear the inherited amount_paid / paid_amount.
# There are no actual payment records for this charter — amount_paid was
# incorrectly inherited from the duplicate source (020047).
cur.execute("""
    UPDATE charters
    SET amount_paid = 0,
        paid_amount = 0,
        balance_owing = grand_total,
        updated_at = NOW()
    WHERE charter_id = 19232
      AND reserve_number = '020048'
""")
print(f"Updated rows: {cur.rowcount}")
conn.commit()

# Verify
cur.execute("""
    SELECT charter_id, reserve_number, grand_total, amount_paid, balance_owing
    FROM charters WHERE reserve_number IN ('020047','020048') ORDER BY reserve_number
""")
print("After fix:")
for r in cur.fetchall():
    print(r)
conn.close()
