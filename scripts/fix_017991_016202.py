import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=== Fixing Charters 017991 and 016202 ===\n")

# 1. Cancel 017991 and set charges/balance to 0
print("1. Cancelling 017991...")
cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, status
    FROM charters
    WHERE reserve_number = '017991'
""")
charter_017991 = cur.fetchone()
if charter_017991:
    print(f"   Before: Total=${charter_017991[2]} | Paid=${charter_017991[3]} | Balance=${charter_017991[4]} | Status={charter_017991[5]}")
    
    cur.execute("""
        UPDATE charters
        SET total_amount_due = 0,
            paid_amount = 0,
            balance = 0,
            status = 'Cancelled'
        WHERE reserve_number = '017991'
    """)
    print(f"   After: Total=$0 | Paid=$0 | Balance=$0 | Status=Cancelled")
    print(f"   ✅ 017991 cancelled\n")
else:
    print("   ❌ 017991 not found\n")

# 2. Fix 016202 based on actual payments
print("2. Fixing 016202 based on actual payments...")
cur.execute("""
    SELECT SUM(amount) FROM payments WHERE reserve_number = '016202'
""")
actual_paid_016202 = cur.fetchone()[0] or 0.0

cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, balance, status
    FROM charters
    WHERE reserve_number = '016202'
""")
charter_016202 = cur.fetchone()
if charter_016202:
    total = float(charter_016202[2] or 0)
    calculated_balance = total - float(actual_paid_016202)
    
    print(f"   Before: Total=${charter_016202[2]} | Paid=${charter_016202[3]} | Balance=${charter_016202[4]}")
    print(f"   Actual payments in table: ${actual_paid_016202}")
    
    cur.execute("""
        UPDATE charters
        SET paid_amount = %s,
            balance = %s
        WHERE reserve_number = '016202'
    """, (actual_paid_016202, calculated_balance))
    
    print(f"   After: Total=${total} | Paid=${actual_paid_016202} | Balance=${calculated_balance}")
    print(f"   ✅ 016202 updated\n")
else:
    print("   ❌ 016202 not found\n")

conn.commit()

# Verify
print("=== Verification ===")
for reserve in ['017991', '016202']:
    cur.execute("""
        SELECT reserve_number, total_amount_due, paid_amount, balance, status
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    result = cur.fetchone()
    if result:
        print(f"{result[0]}: Total=${result[1]} | Paid=${result[2]} | Balance=${result[3]} | Status={result[4]}")

cur.close()
conn.close()

print("\n✅ Both charters fixed")
