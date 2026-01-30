import psycopg2, os
conn = psycopg2.connect(host=os.environ.get("DB_HOST", "localhost"), database=os.environ.get("DB_NAME", "almsdata"), user=os.environ.get("DB_USER", "postgres"), password=os.environ.get("DB_PASSWORD", "***REDACTED***"))
cur = conn.cursor()

# Method 1: Using the all-charters count we know from comprehensive audit
cur.execute("""
    WITH charter_payments AS (
        SELECT 
            c.charter_id,
            c.total_amount_due,
            COALESCE(SUM(p.amount), 0) as total_paid
        FROM charters c
        LEFT JOIN payments p ON p.reserve_number = c.reserve_number
        GROUP BY c.charter_id, c.total_amount_due
    )
    SELECT 
        COUNT(*) as all_charters,
        SUM(CASE WHEN total_amount_due - total_paid > 0 THEN 1 ELSE 0 END) as unpaid,
        SUM(CASE WHEN total_amount_due - total_paid < 0 THEN 1 ELSE 0 END) as overpaid,
        SUM(CASE WHEN total_amount_due - total_paid = 0 THEN 1 ELSE 0 END) as fully_paid
    FROM charter_payments
""")

all_c, unpaid, overpaid, fully_paid = cur.fetchone()
print(f"All charters: {all_c}")
print(f"Unpaid (balance > 0): {unpaid}")
print(f"Overpaid (balance < 0): {overpaid}")
print(f"Fully paid (balance = 0): {fully_paid}")

# Check what the comprehensive audit showed
cur.execute("SELECT SUM(total_amount_due) FROM charters")
total_billed = cur.fetchone()[0]
print(f"\nTotal billed in system: ${total_billed:,.2f}")

cur.execute("""
    WITH all_charters AS (
        SELECT COUNT(*) as total FROM charters
    )
    SELECT total FROM all_charters
""")
total_charters = cur.fetchone()[0]
print(f"Total charters in system: {total_charters}")

cur.close()
conn.close()
