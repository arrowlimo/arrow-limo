#!/usr/bin/env python3
"""
Reconcile Square Capital activity (staging) to banking transactions.
- Requires square_capital_activity table (load via import_square_capital_activity.py)
- Matches 'Automatic payment' (negative amounts) to banking debits by date±1d and amount
- Matches loan credits to banking deposits by date±2d and amount
- Emits a simple summary by month and an unmatched list for review
"""
import os
from datetime import timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

SQL = {
    'monthly_summary': """
        with sc as (
            select activity_date,
                   description,
                   amount::numeric as amount,
                   case
                     when description ilike '%automatic payment%' then 'repayment'
                     when description ilike '%loan%' or description ilike '%payment from%' or description ilike '%credit%'
                          then 'credit'
                     else 'credit'
                   end as kind
            from square_capital_activity
        ), scm as (
            select date_trunc('month', activity_date)::date as month,
                   kind,
                   count(*) as cnt,
                   sum(case when kind='repayment' then -abs(amount) else abs(amount) end) as total
            from sc
            group by 1,2
        )
        select to_char(month, 'YYYY-MM') as month,
               kind, cnt, total
        from scm
        order by month, kind;
    """,
        'candidate_matches': """
        with sc as (
            select id, activity_date, description, amount::numeric as amount,
                   case
                     when description ilike '%automatic payment%' then 'repayment'
                     else 'credit'
                   end as kind
            from square_capital_activity
        ), bt as (
                        select transaction_id, transaction_date, description, debit_amount::numeric as debit_amount,
                                     credit_amount::numeric as credit_amount, account_number
            from banking_transactions
        )
        select sc.id as sc_id, sc.activity_date, sc.description as sc_desc, sc.amount as sc_amount, sc.kind,
               bt.transaction_id as bt_id, bt.transaction_date, bt.description as bt_desc,
               bt.debit_amount, bt.credit_amount, bt.account_number,
            case when sc.kind='repayment' then abs(sc.amount - bt.debit_amount)
                    else abs(sc.amount - bt.credit_amount) end as amt_diff,
            abs((bt.transaction_date - sc.activity_date)) as days_apart
        from sc
                join bt
                    on (
                        -- Only match credits (loan-related inflows) to banking credits that look like Square deposits
                        sc.kind = 'credit'
                        and bt.credit_amount > 0
                        and (bt.description ilike '%SQUARE%' or bt.description ilike 'SQC%')
                        and abs(sc.amount - bt.credit_amount) < 0.01
                    )
                 and bt.transaction_date between sc.activity_date - interval '2 day' and sc.activity_date + interval '4 day'
    """,
    'best_match': """
        with candidates as (
            select *, row_number() over (partition by sc_id order by days_apart asc, amt_diff asc, bt_id asc) as rn
            from ({candidate_sql}) x
        )
        select * from candidates where rn = 1
    """
}

def connect():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        port=os.getenv('DB_PORT','5432'),
        dbname=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','')
    )


def main():
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Summary
        cur.execute(SQL['monthly_summary'])
        rows = cur.fetchall()
        print('Monthly summary (Square Capital staging):')
        for r in rows:
            print(f"  {r['month']} {r['kind']:10s} cnt={r['cnt']:<4d} total={r['total']:+.2f}")
        print()

        # Best matches to banking
        candidate_sql = SQL['candidate_matches']
        cur.execute(SQL['best_match'].format(candidate_sql=candidate_sql))
        matches = cur.fetchall()

        sc_matched = {m['sc_id'] for m in matches}
        print(f"Matched {len(matches)} Square Capital rows to banking. Showing 10 samples:")
        for m in matches[:10]:
            side_amt = m['debit_amount'] if m['kind']=='repayment' else m['credit_amount']
            print(f"  {m['activity_date']} {m['kind']:<9} {m['sc_amount']:+.2f} -> {m['transaction_date']} {side_amt:+.2f} acct {m['account_number']} | {m['sc_desc']} || {m['bt_desc']}")
        print()

        # Unmatched
        cur.execute("""
            select id, activity_date, description, amount::numeric as amount
            from square_capital_activity
            where case when %s = '{}' then true else id not in %s end
            order by activity_date
        """, ('{}' if sc_matched else '{}', tuple(sc_matched) if sc_matched else tuple([-1]),))
        unmatched = cur.fetchall()
        print(f"Unmatched Square Capital rows: {len(unmatched)}")
        for u in unmatched[:20]:
            print(f"  {u['activity_date']} {u['amount']:+.2f} | {u['description']}")
        if len(unmatched) > 20:
            print(f"  ... {len(unmatched)-20} more")

if __name__ == '__main__':
    main()
