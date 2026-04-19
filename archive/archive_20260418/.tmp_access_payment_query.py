import os
import sys
import pyodbc
from collections import defaultdict

candidates = [r"L:\lms2026b.mdb", r"L:\limo\db\lms2026c.mdb"]
db_path = next((p for p in candidates if os.path.exists(p)), None)
if not db_path:
    print("ERROR: Neither Access file exists:")
    for p in candidates:
        print(" -", p)
    sys.exit(1)

reserve_vals = ['012154','012574','013357']
placeholders = ','.join('?' for _ in reserve_vals)

conn_strs = [
    rf"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path};",
    rf"DRIVER={{Microsoft Access Driver (*.mdb)}};DBQ={db_path};"
]

conn = None
last_err = None
for cs in conn_strs:
    try:
        conn = pyodbc.connect(cs, autocommit=True)
        break
    except Exception as e:
        last_err = e

if conn is None:
    print(f"ERROR: Unable to connect via pyodbc. Last error: {last_err}")
    sys.exit(2)

sql = f"""
SELECT Account_No, Reserve_No, Amount, [Key], LastUpdated, PaymentID
FROM Payment
WHERE Reserve_No IN ({placeholders})
ORDER BY Reserve_No, PaymentID
"""

rows = []
with conn:
    cur = conn.cursor()
    cur.execute(sql, reserve_vals)
    rows = cur.fetchall()

print(f"DB_USED: {db_path}")
print("\n=== PAYMENT ROWS ===")
if not rows:
    print("<none>")
else:
    for r in rows:
        print(f"Account_No={r.Account_No} Reserve_No={r.Reserve_No} Amount={r.Amount} Key={getattr(r, 'Key', None)} LastUpdated={r.LastUpdated} PaymentID={r.PaymentID}")

totals = defaultdict(float)
for r in rows:
    try:
        amt = float(r.Amount) if r.Amount is not None else 0.0
    except Exception:
        amt = 0.0
    totals[str(r.Reserve_No)] += amt

print("\n=== TOTALS BY Reserve_No ===")
for rv in reserve_vals:
    print(f"Reserve_No={rv} TotalAmount={totals.get(rv, 0.0):.2f}")
