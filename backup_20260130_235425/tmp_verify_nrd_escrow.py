import psycopg2
from decimal import Decimal

RESERVES = [
    '015998','015799','015541','015542','015280','015279'
]

def conn():
    return psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')

with conn() as c:
    cur = c.cursor()
    total_escrow = Decimal('0')
    for rn in RESERVES:
        cur.execute("SELECT charter_id, COALESCE(total_amount_due,0), COALESCE(paid_amount,0), COALESCE(balance,0), COALESCE(cancelled,false) FROM charters WHERE reserve_number=%s", (rn,))
        ch = cur.fetchone()
        cur.execute("SELECT COALESCE(SUM(amount),0), COUNT(*) FROM charter_charges WHERE reserve_number=%s", (rn,))
        cc_sum, cc_cnt = cur.fetchone()
        cc_sum = Decimal(str(cc_sum or 0))
        cur.execute("SELECT COALESCE(SUM(credit_amount),0) FROM charter_credit_ledger WHERE source_reserve_number=%s AND credit_reason='NRD_ESCROW'", (rn,))
        cred_sum = Decimal(str(cur.fetchone()[0] or 0))
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number=%s AND ABS(amount-500.00)<0.005", (rn,))
        cnt_500 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM payments WHERE reserve_number=%s AND notes ILIKE %s", (rn, '%NRD_ESCROW%'))
        cnt_note = cur.fetchone()[0]
        total_escrow += cred_sum
        print(f"{rn}: charges_cnt={cc_cnt} sum={cc_sum} | credit_escrow={cred_sum} | $500_payments={cnt_500} | noted={cnt_note} | charter={ch}")
    print(f"Total NRD_ESCROW credits: {total_escrow}")
