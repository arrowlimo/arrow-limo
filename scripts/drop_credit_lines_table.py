#!/usr/bin/env python3
"""
Backup and drop the credit_lines table (and overview).
- Creates backup table: credit_lines_backup_<timestamp>
- Exports CSV to reports/credit_lines_backup_<timestamp>.csv
- Drops credit_lines_overview (view or table) if exists
- Drops credit_lines
"""

import os
import csv
import datetime
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
os.makedirs(REPORT_DIR, exist_ok=True)
TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_PATH = os.path.join(REPORT_DIR, f"credit_lines_backup_{TS}.csv")
BACKUP_TABLE = f"credit_lines_backup_{TS}"

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Check existence
cur.execute("""
    SELECT COUNT(*) FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'credit_lines'
""")
exists = cur.fetchone()[0] > 0
if not exists:
    print("credit_lines table does not exist; nothing to drop.")
    cur.close(); conn.close();
    raise SystemExit(0)

# Export CSV
cur.execute("SELECT * FROM credit_lines")
rows = cur.fetchall()
colnames = [desc[0] for desc in cur.description]
with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(colnames)
    writer.writerows(rows)
print(f"CSV backup written: {CSV_PATH} ({len(rows)} rows)")

try:
    # Backup table copy
    cur.execute(f"CREATE TABLE {BACKUP_TABLE} AS TABLE credit_lines")
    print(f"Backup table created: {BACKUP_TABLE}")

    # Drop foreign key from interest_allocations referencing credit_lines
    cur.execute("ALTER TABLE IF EXISTS interest_allocations DROP CONSTRAINT IF EXISTS interest_allocations_credit_line_id_fkey")

    # Drop overview if exists (view or table)
    cur.execute("DROP VIEW IF EXISTS credit_lines_overview")
    cur.execute("DROP TABLE IF EXISTS credit_lines_overview")

    # Drop main table
    cur.execute("DROP TABLE IF EXISTS credit_lines")
    conn.commit()
    print("Dropped: credit_lines (and overview if present)")
except Exception as e:
    conn.rollback()
    print(f"ERROR during drop: {e}")
    raise
finally:
    cur.close(); conn.close()
