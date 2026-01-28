"""
Analyze receipts coverage by year and report years with zero entries.
Outputs a markdown report to reports/receipts_coverage_by_year.md
"""
import os
import psycopg2
from collections import defaultdict
from datetime import date

DB = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'dbname': os.getenv('DB_NAME', 'almsdata'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '***REMOVED***'),
}

START_YEAR = int(os.getenv('RECEIPTS_START_YEAR', '2007'))
END_YEAR = int(os.getenv('RECEIPTS_END_YEAR', '2026'))  # exclusive end for range()

conn = psycopg2.connect(**DB)
cur = conn.cursor()

# Verify column exists
cur.execute("""
    SELECT 1 
    FROM information_schema.columns 
    WHERE table_name='receipts' AND column_name='receipt_date'
""")
if cur.fetchone() is None:
    raise SystemExit("receipts.receipt_date column not found")

cur.execute("""
    SELECT EXTRACT(YEAR FROM receipt_date)::int AS yr,
           COUNT(*) AS cnt,
           COALESCE(SUM(gross_amount),0) AS total
    FROM receipts
    WHERE receipt_date IS NOT NULL
    GROUP BY yr
    ORDER BY yr
""")

rows = cur.fetchall()
counts = {r[0]: (r[1], float(r[2])) for r in rows}

years = list(range(START_YEAR, END_YEAR))
missing = [y for y in years if y not in counts]

report_lines = []
report_lines.append("# Receipts Coverage by Year")
report_lines.append("")
report_lines.append(f"Range analyzed: {START_YEAR}–{END_YEAR-1}")
report_lines.append("")
report_lines.append("## Summary")
report_lines.append(f"- Years with no receipts: {len(missing)}")
if missing:
    report_lines.append(f"- Missing years: {', '.join(str(y) for y in missing)}")
else:
    report_lines.append("- Missing years: none")
report_lines.append("")
report_lines.append("## Counts by Year")
report_lines.append("Year | Count | Total Gross")
report_lines.append("---- | ----: | ----------:")
for y in years:
    cnt, total = counts.get(y, (0, 0.0))
    report_lines.append(f"{y} | {cnt} | ${total:,.2f}")

# Write report
os.makedirs(os.path.join('l:\\limo', 'reports'), exist_ok=True)
report_path = os.path.join('l:\\limo', 'reports', 'receipts_coverage_by_year.md')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write("\n".join(report_lines))

print("Receipts coverage report written:", report_path)
print("\nTop missing years:", ", ".join(str(y) for y in missing[:10]) or "none")

cur.close()
conn.close()
