#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")
cur = conn.cursor()

# Get all payments for each reserve and delete the duplicate
for reserve in ['001764', '005711']:
    cur.execute(f"SELECT payment_id FROM payments WHERE reserve_number = '{reserve}' ORDER BY created_at DESC")
    rows = cur.fetchall()
    
    if len(rows) >= 2:
        payment_id = rows[1][0]  # Delete the older one
        cur.execute(f"DELETE FROM payments WHERE payment_id = {payment_id}")
        print(f"✓ Deleted payment {payment_id} from {reserve}")

conn.commit()

# Verify
for reserve in ['001764', '005711']:
    cur.execute(f"SELECT COALESCE(SUM(amount), 0) FROM charter_charges WHERE reserve_number = '{reserve}'")
    charges = float(cur.fetchone()[0])
    cur.execute(f"SELECT COALESCE(SUM(amount), 0) FROM payments WHERE reserve_number = '{reserve}'")
    payments = float(cur.fetchone()[0])
    balance = charges - payments
    print(f"{reserve}: Balance ${balance:.2f}")

cur.close()
conn.close()
