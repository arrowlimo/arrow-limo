import pyodbc

LMS = r"L:\lms2026c.mdb"
conn = pyodbc.connect(f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS};")
cur = conn.cursor()

terms = ['dKL1','myvn']

print('=== Reserve card fields for 013602/013603 ===')
cur.execute("""
SELECT Reserve_No, Card_No, Card_Appr, Card_Type, Card_Amnt, CardTrx, CardMsg, LastUpdated
FROM Reserve
WHERE Reserve_No IN ('013602','013603')
""")
for r in cur.fetchall():
    print(r)

print('\n=== Deposit rows containing dKL1/myvn ===')
for t in terms:
    cur.execute("""
    SELECT Date, [Key], Number, Total, Transact, Type
    FROM Deposit
    WHERE Number LIKE ? OR [Key] LIKE ? OR Transact LIKE ?
    ORDER BY Date
    """, (f'%{t}%', f'%{t}%', f'%{t}%'))
    rows = cur.fetchall()
    print(f'term={t} count={len(rows)}')
    for r in rows[:20]:
        print(' ', r)

print('\n=== CheckBook rows containing dKL1/myvn ===')
for t in terms:
    cur.execute("""
    SELECT Date, Number, Memo_Line, Payee, Type, Deposit, Withdrawal
    FROM CheckBook
    WHERE Number LIKE ? OR Memo_Line LIKE ? OR Payee LIKE ?
    ORDER BY Date
    """, (f'%{t}%', f'%{t}%', f'%{t}%'))
    rows = cur.fetchall()
    print(f'term={t} count={len(rows)}')
    for r in rows[:20]:
        print(' ', r)

print('\n=== Payment rows around reserve 013602 date range with same account 04761 ===')
cur.execute("""
SELECT p.PaymentID, p.Reserve_No, p.Amount, p.[Key], p.LastUpdated, r.Account_No, r.Name
FROM Payment p
LEFT JOIN Reserve r ON r.Reserve_No = p.Reserve_No
WHERE r.Account_No='04761'
  AND p.LastUpdated >= #2018-08-01# AND p.LastUpdated < #2018-10-15#
ORDER BY p.LastUpdated, p.PaymentID
""")
for r in cur.fetchall():
    print(r)

conn.close()
