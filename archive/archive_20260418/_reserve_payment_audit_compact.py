from collections import Counter
from decimal import Decimal
import psycopg2, pyodbc

RESERVES = ['006341','012144','006311','012237','006318','007504']
pg = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
ac = pyodbc.connect(r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=L:\limo\db\lms2026d.mdb;")

def fa(v):
    return 'NULL' if v is None else f"{Decimal(v):.2f}"
def fd(v):
    if v is None: return 'NULL'
    try: return v.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        try: return v.strftime('%Y-%m-%d')
        except Exception: return str(v)
def donly(v):
    if v is None: return None
    try: return v.date().isoformat()
    except Exception:
        try: return v.isoformat()
        except Exception: return str(v)[:10]
def nk(v):
    return '' if v is None else str(v).strip()

pc = pg.cursor()
qm = ','.join(['%s']*len(RESERVES))
pc.execute(f"SELECT reserve_number, charter_id, charter_date, status, total_amount_due, amount_paid, balance_owing, payment_status FROM charters WHERE reserve_number IN ({qm}) ORDER BY reserve_number, charter_date NULLS LAST, charter_id", RESERVES)
charters = {}
for reserve, charter_id, charter_date, status, total_due, amount_paid, balance_owing, payment_status in pc.fetchall():
    charters.setdefault(reserve, []).append(f"{charter_id}|{fd(charter_date)}|{status}|due={fa(total_due)}|paid={fa(amount_paid)}|bal={fa(balance_owing)}|ps={payment_status}")

pc.execute(f"SELECT reserve_number, payment_id, payment_key, payment_date, amount, payment_method, notes FROM payments WHERE reserve_number IN ({qm}) ORDER BY reserve_number, payment_date NULLS LAST, payment_id", RESERVES)
localp = {}
localraw = {}
for reserve, payment_id, payment_key, payment_date, amount, payment_method, notes in pc.fetchall():
    localp.setdefault(reserve, []).append(f"{payment_id}|{payment_key}|{fd(payment_date)}|{fa(amount)}|{payment_method}|{repr(notes)}")
    localraw.setdefault(reserve, []).append((payment_id,payment_key,payment_date,amount))

pc.execute(f"SELECT c.reserve_number, cp.id, cp.payment_id, cp.charter_id, cp.charter_date, cp.payment_date, cp.amount, cp.payment_method, cp.payment_key, cp.source FROM charter_payments cp JOIN charters c ON c.charter_id::text = cp.charter_id WHERE c.reserve_number IN ({qm}) ORDER BY c.reserve_number, cp.payment_date NULLS LAST, cp.id", RESERVES)
cpay = {}
for reserve, id_, payment_id, charter_id, charter_date, payment_date, amount, payment_method, payment_key, source in pc.fetchall():
    cpay.setdefault(reserve, []).append(f"{id_}|pid={payment_id}|cid={charter_id}|cd={fd(charter_date)}|pd={fd(payment_date)}|amt={fa(amount)}|{payment_method}|{payment_key}|{source}")

acq = ac.cursor()
q2 = ','.join(['?']*len(RESERVES))
acq.execute(f"SELECT Reserve_No, PaymentID, [Key], LastUpdated, Amount FROM Payment WHERE Reserve_No IN ({q2}) ORDER BY Reserve_No, LastUpdated, PaymentID", RESERVES)
lms = {}
lmsraw = {}
for reserve, paymentid, key, lastupdated, amount in acq.fetchall():
    reserve = str(reserve)
    lms.setdefault(reserve, []).append(f"{paymentid}|{key}|{fd(lastupdated)}|{fa(amount)}")
    lmsraw.setdefault(reserve, []).append((paymentid,key,lastupdated,amount))

for r in RESERVES:
    lp = localraw.get(r, [])
    lm = lmsraw.get(r, [])
    lt = sum((Decimal(x[3]) for x in lp), Decimal('0'))
    mt = sum((Decimal(x[3]) for x in lm), Decimal('0'))
    lc = Counter((nk(x[1]), donly(x[2]), fa(x[3])) for x in lp)
    mc = Counter((nk(x[1]), donly(x[2]), fa(x[3])) for x in lm)
    extra = []
    for pat, cnt in lc.items():
        diff = cnt - mc.get(pat, 0)
        if diff > 0:
            ids = [str(x[0]) for x in lp if (nk(x[1]), donly(x[2]), fa(x[3])) == pat][:diff]
            extra.append(f"{pat[0]}|{pat[1]}|{pat[2]}|n={diff}|ids={','.join(ids)}")
    print(f"RESERVE {r}")
    print("CHARTERS: " + (' ; '.join(charters.get(r, ['<none>']))))
    print("LOCAL_PAYMENTS: " + (' ; '.join(localp.get(r, ['<none>']))))
    print("LOCAL_CHARTER_PAYMENTS: " + (' ; '.join(cpay.get(r, ['<none>']))))
    print("LMS_PAYMENTS: " + (' ; '.join(lms.get(r, ['<none>']))))
    print(f"TOTALS: local={fa(lt)} rows={len(lp)} ; lms={fa(mt)} rows={len(lm)}")
    print("EXTRA_LOCAL_NOT_IN_LMS: " + (' ; '.join(extra) if extra else 'NO'))
    print()
pg.close(); ac.close()
