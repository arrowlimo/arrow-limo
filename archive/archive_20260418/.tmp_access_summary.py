import pyodbc
from collections import defaultdict
reserves = ['012144','012237','007504']
conn = pyodbc.connect(r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\db\lms2026d.mdb;")
cur = conn.cursor()
reserve_rows = cur.execute("SELECT Reserve_No, Name, PU_Date, Status, Cancelled, Closed, Balance, Deposit, Card_Amnt, Est_Charge, Rate, Rate_Type, Pymt_Type, Account_No FROM Reserve WHERE Reserve_No IN (?,?,?) ORDER BY Reserve_No", reserves).fetchall()
charge_rows = cur.execute("SELECT Reserve_No, Sequence, [Desc], Amount FROM Charge WHERE Reserve_No IN (?,?,?) ORDER BY Reserve_No, Sequence", reserves).fetchall()
payment_rows = cur.execute("SELECT Reserve_No, [Key], Amount FROM Payment WHERE Reserve_No IN (?,?,?) ORDER BY Reserve_No, [Key], PaymentID", reserves).fetchall()
keys = sorted({r[1] for r in payment_rows if r[1] is not None})
deposits = {}
if keys:
    placeholders = ','.join('?' for _ in keys)
    for r in cur.execute(f"SELECT [Key], [Date], Number, Total, Transact, Type FROM Deposit WHERE [Key] IN ({placeholders})", keys).fetchall():
        deposits[r[0]] = r
charges_by = defaultdict(list)
for r in charge_rows:
    charges_by[r[0]].append(r)
pay_by = defaultdict(list)
for r in payment_rows:
    pay_by[r[0]].append(r)
for rr in reserve_rows:
    reserve_no,name,pu_date,status,cancelled,closed,balance,deposit,card_amnt,est_charge,rate,rate_type,pymt_type,account_no = rr
    charge_total = sum(c[3] for c in charges_by[reserve_no])
    pay_total = sum(p[2] for p in pay_by[reserve_no])
    print(f"Reserve {reserve_no} | {name} | PU {pu_date:%Y-%m-%d} | Status={status} | Cancelled={cancelled} | Closed={closed}")
    print(f"  Reserve fields: Est_Charge={est_charge:.2f}, Deposit={deposit:.2f}, Balance={balance:.2f}, Card_Amnt={card_amnt:.2f}, Rate={rate:.2f} ({rate_type}), Pymt_Type={pymt_type}, Account_No={account_no}")
    print(f"  Charge sum={charge_total:.2f}")
    for c in charges_by[reserve_no]:
        print(f"    Charge seq {c[1]}: {c[2]} = {c[3]:.2f}")
    print(f"  Payment sum={pay_total:.2f}")
    for p in pay_by[reserve_no]:
        d = deposits.get(p[1])
        if d:
            print(f"    Payment key {p[1]}: {p[2]:.2f} | Deposit Date={d[1]:%Y-%m-%d} Type={d[5]} Transact={d[4]} Ref={d[2]}")
        else:
            print(f"    Payment key {p[1]}: {p[2]:.2f}")
    print()
conn.close()
