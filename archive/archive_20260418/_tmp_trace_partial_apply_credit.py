import pyodbc
from decimal import Decimal

LMS = r"L:\lms2026c.mdb"
conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
cur = conn.cursor()

# 1) Key details for the two Mathieson card entries
print('=== Deposit rows for keys 0015199/0015203 ===')
cur.execute("""
SELECT Date, [Key], Number, Total, Transact, Type
FROM Deposit
WHERE [Key] IN ('0015199','0015203')
ORDER BY Date, [Key]
""")
for r in cur.fetchall():
    print(r)

print('\n=== Payment rows for keys 0015199/0015203 ===')
cur.execute("""
SELECT PaymentID, Reserve_No, Amount, [Key], LastUpdated
FROM Payment
WHERE [Key] IN ('0015199','0015203')
ORDER BY LastUpdated, PaymentID
""")
for r in cur.fetchall():
    print(r)

# 2) Check all reserves under account 04761 around that period
print('\n=== Account 04761 reserves and payment totals (2018-09-01 to 2019-03-31) ===')
cur.execute("""
SELECT r.Reserve_No, r.PU_Date, r.Name, r.Est_Charge,
       SUM(p.Amount) AS pay_total
FROM Reserve r
LEFT JOIN Payment p ON p.Reserve_No = r.Reserve_No
WHERE r.Account_No='04761'
  AND r.PU_Date >= #2018-09-01# AND r.PU_Date <= #2019-03-31#
GROUP BY r.Reserve_No, r.PU_Date, r.Name, r.Est_Charge
ORDER BY r.PU_Date, r.Reserve_No
""")
for r in cur.fetchall():
    pay_total = Decimal(str(r.pay_total or 0))
    print((r.Reserve_No, r.PU_Date, r.Name, r.Est_Charge, pay_total))

# 3) Look for any payment amount equal to likely credit remainder 708.50
print('\n=== Any Payment rows with amount 708.50 (2018-09 onward) ===')
cur.execute("""
SELECT TOP 50 PaymentID, Reserve_No, Amount, [Key], LastUpdated
FROM Payment
WHERE Amount = 708.50
  AND LastUpdated >= #2018-09-01#
ORDER BY LastUpdated, PaymentID
""")
rows = cur.fetchall()
for r in rows:
    print(r)
print('count=', len(rows))

conn.close()
