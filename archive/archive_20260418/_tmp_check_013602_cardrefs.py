import pyodbc
from decimal import Decimal

LMS = r"L:\lms2026c.mdb"
conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
cur = conn.cursor()

print('=== Payment rows for 013602/013603 ===')
cur.execute("""
SELECT PaymentID, Reserve_No, Amount, [Key], LastUpdated, LastUpdatedBy
FROM Payment
WHERE Reserve_No IN ('013602','013603')
ORDER BY Reserve_No, LastUpdated, PaymentID
""")
rows = cur.fetchall()
for r in rows:
    print(r)

print('\n=== CardResults rows for 013602/013603 ===')
cur.execute("""
SELECT Reserve_No, Number, Reference, TransType, TransDate, AuthCode
FROM CardResults
WHERE Reserve_No IN ('013602','013603')
ORDER BY Reserve_No, TransDate
""")
rows = cur.fetchall()
for r in rows:
    print(r)
print('count=', len(rows))

print('\n=== CardResults rows containing dKL1/myvn (if any) ===')
cur.execute("""
SELECT Reserve_No, Number, Reference, TransType, TransDate, AuthCode
FROM CardResults
WHERE Number LIKE '%dKL1%'
   OR Number LIKE '%myvn%'
   OR Reference LIKE '%dKL1%'
   OR Reference LIKE '%myvn%'
ORDER BY TransDate
""")
rows = cur.fetchall()
for r in rows:
    print(r)
print('count=', len(rows))

print('\n=== Any Payment keys that could tie to 808.50 ===')
cur.execute("""
SELECT TOP 20 PaymentID, Reserve_No, Amount, [Key], LastUpdated
FROM Payment
WHERE Amount IN (808.50, 500.00, 100.00)
  AND LastUpdated >= #2018-09-01# AND LastUpdated < #2018-09-15#
ORDER BY LastUpdated, PaymentID
""")
for r in cur.fetchall():
    print(r)

conn.close()
