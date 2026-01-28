"""Analyze split receipts by year, focusing on 2012 and 2019."""
import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("SPLIT RECEIPTS BY YEAR")
print("=" * 80)
cur.execute(
    """
    SELECT EXTRACT(YEAR FROM receipt_date)::int AS yr,
           COUNT(*) AS split_rows,
           SUM(gross_amount) AS total_amount
    FROM receipts
    WHERE split_group_id IS NOT NULL
    GROUP BY yr
    ORDER BY yr
    """
)
rows = cur.fetchall()
for yr, cnt, amt in rows:
    print(f"{yr}: {cnt:6d} rows | ${amt:,.2f}")

# Helper to print group summaries for a given year

def summarize_year(target_year: int, limit: int = 25):
    print("\n" + "-" * 80)
    print(f"SPLIT GROUPS FOR {target_year}")
    print("-" * 80)
    cur.execute(
        """
        SELECT split_group_id,
               COUNT(*) AS parts,
               SUM(gross_amount) AS total_amount,
               MIN(receipt_date) AS min_date,
               MAX(receipt_date) AS max_date,
               string_agg(DISTINCT vendor_name, ', ' ORDER BY vendor_name) AS vendors
        FROM receipts
        WHERE split_group_id IS NOT NULL
          AND EXTRACT(YEAR FROM receipt_date)::int = %s
        GROUP BY split_group_id
        ORDER BY total_amount DESC, split_group_id
        LIMIT %s
        """,
        (target_year, limit),
    )
    groups = cur.fetchall()
    if not groups:
        print("(no split receipts found)")
        return
    for gid, parts, amt, dmin, dmax, vendors in groups:
        print(
            f"Group {gid}: {parts} parts | ${amt:,.2f} | {dmin} to {dmax} | Vendors: {vendors}"
        )

summarize_year(2012)
summarize_year(2019)

cur.close()
conn.close()
