#!/usr/bin/env python3
"""
Summarize how charters correspond to available driver pay records and report gratuity tracking.
- Confirms matched vs missing (with +/- 7 day date tolerance and name normalization)
- Reports dates with potential name mismatches
- Summarizes gratuity: in charters (driver_gratuity) vs staged pay entries (pay_type='gratuity' or memo hints)

Environment variables respected (fallbacks provided):
  PGDATABASE, PGUSER, PGHOST, PGPORT, PGPASSWORD
"""
import os
import psycopg2
from collections import defaultdict
from datetime import timedelta

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')


def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )


def normalize_driver_name(name: str | None) -> str:
    if not name:
        return ''
    s = ' '.join(name.lower().split())
    s = s.replace('driver', '').strip()
    if s.startswith('dr') and len(s) > 2:
        s = s[2:]
    return s


def fetch_charters(cur):
    cur.execute(
        """
        SELECT 
            charter_date,
            driver_name,
            driver,
            charter_id,
            reserve_number,
            client_id,
            driver_total,
            driver_paid,
            driver_gratuity
        FROM charters
        WHERE charter_date IS NOT NULL
          AND cancelled = FALSE
          AND (driver IS NOT NULL OR driver_name IS NOT NULL)
        ORDER BY charter_date, charter_id
        """
    )
    return cur.fetchall()


def fetch_staging_pay(cur):
    cur.execute(
        """
        SELECT txn_date, driver_name, amount, source_file, memo, pay_type
        FROM staging_driver_pay
        WHERE driver_name IS NOT NULL AND txn_date IS NOT NULL
        ORDER BY driver_name, txn_date
        """
    )
    return cur.fetchall()


def summarize_matches(charters, pay_records):
    # Build lookup of (norm_name, date) -> list of payments
    pay_by_name_date: dict[tuple[str, object], list] = defaultdict(list)
    for txn_date, driver_name, amount, source_file, memo, pay_type in pay_records:
        pay_by_name_date[(normalize_driver_name(driver_name), txn_date)].append(
            {
                'amount': float(amount) if amount is not None else None,
                'source': source_file,
                'memo': memo,
                'pay_type': pay_type,
            }
        )

    missing = 0
    matched = 0
    name_mismatch_dates: dict[object, list] = defaultdict(list)

    # Check each charter for a pay record on same date or within +/- 7 days
    for charter in charters:
        charter_date, driver_name_col, driver_code, charter_id, reserve_number, client_id, driver_total, driver_paid, driver_gratuity = charter
        driver_names = [d for d in (driver_name_col, driver_code) if d]
        if not driver_names or charter_date is None:
            continue
        found = False
        for dn in driver_names:
            n = normalize_driver_name(dn)
            if (n, charter_date) in pay_by_name_date:
                found = True
                break
            # +-7 day window
            for off in range(-7, 8):
                if off == 0:
                    continue
                d2 = charter_date + timedelta(days=off)
                if (n, d2) in pay_by_name_date:
                    found = True
                    break
            if found:
                break
        if found:
            matched += 1
        else:
            missing += 1
            # if any pay exists that day under a different driver name, record it as a potential mismatch
            for (pn, d), recs in pay_by_name_date.items():
                if d == charter_date and all(normalize_driver_name(x) != pn for x in driver_names):
                    name_mismatch_dates[charter_date].append({
                        'charter_driver': ', '.join(driver_names),
                        'pay_driver': pn,
                        'charter_id': charter_id,
                        'count': len(recs)
                    })

    return matched, missing, name_mismatch_dates


def summarize_gratuity(cur):
    # Charter-side gratuity
    cur.execute("SELECT COUNT(*), COALESCE(SUM(driver_gratuity),0) FROM charters WHERE cancelled=FALSE AND COALESCE(driver_gratuity,0) > 0")
    ch_count, ch_sum = cur.fetchone()
    # Staging-side potential gratuity (explicit pay_type or memo keywords)
    cur.execute(
        """
        SELECT 
            SUM(CASE WHEN LOWER(COALESCE(pay_type,'')) = 'gratuity' THEN 1 ELSE 0 END) AS gratuity_rows,
            COALESCE(SUM(CASE WHEN LOWER(COALESCE(pay_type,'')) = 'gratuity' THEN amount ELSE 0 END),0) AS gratuity_amount,
            SUM(CASE WHEN memo ILIKE '%gratuity%' OR memo ILIKE '%tip%' THEN 1 ELSE 0 END) AS memo_hint_rows,
            COALESCE(SUM(CASE WHEN memo ILIKE '%gratuity%' OR memo ILIKE '%tip%' THEN amount ELSE 0 END),0) AS memo_hint_amount
        FROM staging_driver_pay
        """
    )
    st_rows, st_amt, memo_rows, memo_amt = cur.fetchone()
    return {
        'charter_gratuity_rows': ch_count,
        'charter_gratuity_total': float(ch_sum),
        'staging_gratuity_rows': int(st_rows or 0),
        'staging_gratuity_total': float(st_amt or 0.0),
        'staging_gratuity_memo_rows': int(memo_rows or 0),
        'staging_gratuity_memo_total': float(memo_amt or 0.0),
    }


def main():
    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                print('Fetching charters and staging pay...')
                charters = fetch_charters(cur)
                pay = fetch_staging_pay(cur)
                print(f'  Charters with drivers: {len(charters):,}')
                print(f'  Staging pay rows (with driver & date): {len(pay):,}')

                print('\nAnalyzing matches...')
                matched, missing, name_mismatch_dates = summarize_matches(charters, pay)
                print(f'  Matched charters: {matched:,}')
                print(f'  Missing pay for charters: {missing:,}')
                print(f'  Dates with potential name mismatches: {len(name_mismatch_dates):,}')

                if name_mismatch_dates:
                    # show up to 5 sample dates
                    from itertools import islice
                    print('\nSample potential name mismatch dates (up to 5):')
                    for dt, items in islice(sorted(name_mismatch_dates.items()), 5):
                        print(f'  {dt}: {len(items)} issue(s)')

                print('\nGratuity tracking:')
                g = summarize_gratuity(cur)
                print(f"  Charters with gratuity>0: {g['charter_gratuity_rows']:,} totaling {g['charter_gratuity_total']:,.2f}")
                print(f"  Staging pay with pay_type='gratuity': {g['staging_gratuity_rows']:,} totaling {g['staging_gratuity_total']:,.2f}")
                print(f"  Staging pay with gratuity/tip in memo: {g['staging_gratuity_memo_rows']:,} totaling {g['staging_gratuity_memo_total']:,.2f}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
