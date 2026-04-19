import pyodbc
reserves = ['012144','012237','007504']
conn = pyodbc.connect(r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\db\lms2026d.mdb;")
cur = conn.cursor()
print('--- Reserve selected fields ---')
q = "SELECT Reserve_No, Status, Cancelled, Closed, Balance, Deposit, Card_Amnt, Est_Charge, Invoice_No, Invoice_Dt, Pymt_Type, Name, PU_Date, Rate, Rate_Type FROM Reserve WHERE Reserve_No IN (?,?,?) ORDER BY Reserve_No"
for r in cur.execute(q, reserves).fetchall():
    print(r)
print('\n--- Charge rows ---')
for r in cur.execute("SELECT Reserve_No, Sequence, [Desc], Note, Rate, Amount, Closed, Frozen FROM Charge WHERE Reserve_No IN (?,?,?) ORDER BY Reserve_No, Sequence", reserves).fetchall():
    print(r)
print('\n--- Payment rows ---')
pays = cur.execute("SELECT Reserve_No, [Key], Amount, Account_No FROM Payment WHERE Reserve_No IN (?,?,?) ORDER BY Reserve_No, [Key], PaymentID", reserves).fetchall()
for r in pays:
    print(r)
keys = sorted({r[1] for r in pays if r[1] is not None})
print('\nKeys:', keys)
if keys:
    placeholders = ','.join('?' for _ in keys)
    print('\n--- Deposit rows for payment keys ---')
    for r in cur.execute(f"SELECT [Key], [Date], Number, Total, Transact, Type, CB_NO FROM Deposit WHERE [Key] IN ({placeholders}) ORDER BY [Key], [Date]", keys).fetchall():
        print(r)
conn.close()
