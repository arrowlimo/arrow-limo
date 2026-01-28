#!/usr/bin/env python3
"""Check GST capture for ATB (Alberta Treasury Branch) auto loan payments.

Reports counts and totals for receipts with vendor/description matching ATB keywords,
and shows how many have gst_amount > 0 vs = 0, with a few sample rows.
"""
import psycopg2

DB = dict(dbname='almsdata', user='postgres', password='***REMOVED***', host='localhost')

KEYWORDS = [
    'atb',
    'atb financial',
    'alberta treasury',
    'alberta treasury branch',
    'atbfin',
]

conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Detect id column
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='receipts' AND column_name IN ('receipt_id','id') ORDER BY ordinal_position LIMIT 1")
id_col = cur.fetchone()
if not id_col:
    print('ERROR: receipts id column not found')
    raise SystemExit(1)
id_col = id_col[0]

like_clauses = []
params = []
for kw in KEYWORDS:
    like_clauses.append("LOWER(COALESCE(vendor_name,'')) LIKE %s")
    params.append(f"%{kw}%")
    like_clauses.append("LOWER(COALESCE(description,'')) LIKE %s")
    params.append(f"%{kw}%")
where_like = " OR ".join(like_clauses) if like_clauses else "FALSE"

print("\n================ ATB FINANCING GST STATUS ================")

# Totals
sql_totals = (
        "SELECT COUNT(*) AS total,"
        " SUM(gross_amount) AS gross,"
        " SUM(CASE WHEN COALESCE(gst_amount,0) > 0 THEN 1 ELSE 0 END) AS with_gst,"
        " SUM(CASE WHEN COALESCE(gst_amount,0) = 0 THEN 1 ELSE 0 END) AS without_gst,"
        " SUM(CASE WHEN COALESCE(gst_amount,0) > 0 THEN gst_amount ELSE 0 END) AS gst_captured"
        " FROM receipts"
        f" WHERE ({where_like}) AND COALESCE(gross_amount,0) > 0"
)
cur.execute(sql_totals, params)
row = cur.fetchone()
total, gross, with_gst, without_gst, gst_captured = row
print(f"Matches: {total or 0:,} | Gross: ${float(gross or 0):,.2f} | With GST: {int(with_gst or 0):,} | Without GST: {int(without_gst or 0):,}")
print(f"GST captured so far: ${float(gst_captured or 0):,.2f}")

# Sample missing GST
sql_samples = (
        f"SELECT {id_col} AS rid, receipt_date, vendor_name, description, gross_amount, gst_amount, category "
        "FROM receipts "
        f"WHERE ({where_like}) AND COALESCE(gross_amount,0) > 0 AND COALESCE(gst_amount,0) = 0 "
        "ORDER BY receipt_date DESC LIMIT 20"
)
cur.execute(sql_samples, params)
rows = cur.fetchall()
if rows:
    print("\n-- Sample receipts missing GST --")
    print(f"{'ID':<8} {'Date':<12} {'Vendor':<30} {'Gross':>12} {'GST':>10} {'Cat':<20}")
    for rid, rdate, vendor, desc, gross, gst, cat in rows:
        print(f"{rid:<8} {rdate} {((vendor or '')[:30]):<30} ${float(gross):>10,.2f} ${float(gst or 0):>8,.2f} {(cat or 'UNCAT'):<20}")
else:
    print("\nAll ATB-matching receipts already have GST.")

cur.close()
conn.close()
