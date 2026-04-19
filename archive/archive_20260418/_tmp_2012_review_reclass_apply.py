import csv
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

out_dir=Path(r'l:\limo\data\audit')
out_dir.mkdir(parents=True, exist_ok=True)
stamp=datetime.now().strftime('%Y%m%d_%H%M%S')

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

try:
    cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, description, gross_amount, gl_account_code, category, exclude_from_reports
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date)=2012
      AND receipt_source='auto_2012_unlinked_debit_review_backfill'
    ORDER BY receipt_id
    """)
    rows=cur.fetchall()

    updates=[]
    for r in rows:
        rid=r['receipt_id']
        vendor=(r['vendor_name'] or '').upper()
        desc=(r['description'] or '').upper()

        new_vendor=r['vendor_name']
        new_gl=r['gl_account_code']
        new_cat=r['category']
        new_excl=r['exclude_from_reports']
        rule=None

        if 'HEFFNER' in vendor or 'HEFFNER' in desc or 'LEXUS' in vendor or 'LEXUS' in desc:
            new_vendor='HEFFNER AUTO LEASE'
            new_gl='5150'
            new_cat='Vehicle Lease Payments'
            new_excl=False
            rule='HEFFNER_LEASE'
        elif 'IFS PREMIUM' in desc or 'IFS PREMIUM' in vendor or (vendor.startswith('IFS') and 'FINANC' in desc):
            new_vendor='IFS PREMIUM FINANCING'
            new_gl='5130'
            new_cat='Insurance'
            new_excl=False
            rule='IFS_INSURANCE'
        elif 'REGISTR' in vendor or 'REGISTR' in desc:
            new_vendor='RED DEER REGISTRIES'
            new_gl='5140'
            new_cat='Vehicle Registration'
            new_excl=False
            rule='REGISTRIES_VEHICLE_REG'
        elif vendor in {'SHELL','PETRO-CANADA','HUSKY','CO-OP GAS','FAS GAS','RUNNING ON EMPTY',"RUN'N ON EMPTY"}:
            new_gl='5110'
            new_cat='Fuel'
            new_excl=False
            rule='FUEL_VENDOR'
        elif 'VCARD PAYMENT' in vendor or 'MCARD PAYMENT' in vendor or 'VCARD PAYMENT' in desc or 'MCARD PAYMENT' in desc:
            new_gl='5720'
            new_cat='Card Fee/Refund Review'
            new_excl=True
            rule='VCARD_MCARD_REVIEW'

        if rule:
            updates.append((rid, rule, r['vendor_name'], r['gl_account_code'], r['category'], r['exclude_from_reports'], new_vendor, new_gl, new_cat, new_excl, float(r['gross_amount'] or 0)))

    for u in updates:
        rid=u[0]
        new_vendor=u[6]
        new_gl=u[7]
        new_cat=u[8]
        new_excl=u[9]
        cur.execute("""
        UPDATE receipts
        SET vendor_name=%s,
            gl_account_code=%s,
            category=%s,
            exclude_from_reports=%s,
            updated_at=NOW()
        WHERE receipt_id=%s
        """, (new_vendor, new_gl, new_cat, new_excl, rid))

    conn.commit()

    out_csv=out_dir / f'2012_review_reclass_applied_{stamp}.csv'
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['receipt_id','rule','old_vendor','old_gl','old_category','old_exclude','new_vendor','new_gl','new_category','new_exclude','gross_amount'])
        for u in updates:
            w.writerow(u)

    print('RECLASS_ROWS_APPLIED:', len(updates))
    print('RECLASS_CSV:', out_csv)

    # Post summary
    cur.execute("""
    SELECT rule, COUNT(*) AS cnt, COALESCE(SUM(gross_amount),0) AS amt
    FROM (
      SELECT
        CASE
          WHEN vendor_name='HEFFNER AUTO LEASE' AND gl_account_code='5150' THEN 'HEFFNER_LEASE'
          WHEN vendor_name='IFS PREMIUM FINANCING' AND gl_account_code='5130' THEN 'IFS_INSURANCE'
          WHEN vendor_name='RED DEER REGISTRIES' AND gl_account_code='5140' THEN 'REGISTRIES_VEHICLE_REG'
          WHEN gl_account_code='5110' AND category='Fuel' THEN 'FUEL_VENDOR'
          WHEN gl_account_code='5720' AND category='Card Fee/Refund Review' THEN 'VCARD_MCARD_REVIEW'
          ELSE 'OTHER'
        END AS rule,
        gross_amount
      FROM receipts
      WHERE EXTRACT(YEAR FROM receipt_date)=2012
        AND receipt_source='auto_2012_unlinked_debit_review_backfill'
    ) z
    GROUP BY rule
    ORDER BY amt DESC
    """)
    print('POST_RULE_SUMMARY:', cur.fetchall())

except Exception:
    conn.rollback()
    raise
finally:
    cur.close(); conn.close()
