import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# First restore the bad GL codes back
print("Restoring corrupted GL codes...")
cur.execute("""
    UPDATE receipts
    SET gl_account_code = CASE
        WHEN gl_account_code LIKE '%%fas gas%%' THEN '5110'
        WHEN gl_account_code LIKE '%%petro%%' THEN '5110'
        WHEN gl_account_code LIKE '%%shell%%' THEN '5110'
        WHEN gl_account_code LIKE '%%esso%%' THEN '5110'
        ELSE gl_account_code
    END,
    gl_account_name = NULL,
    category = NULL,
    verified_by_edit = FALSE,
    verified_at = NULL,
    verified_by_user = NULL
    WHERE verified_by_user = 'auto_fuel_gl_update'
""")
print(f"✅ Rolled back {cur.rowcount} corrupted receipts")

conn.commit()
cur.close()
conn.close()
