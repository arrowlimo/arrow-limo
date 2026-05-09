import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)


def _connect():
    target = os.getenv("DB_TARGET", os.getenv("ALMS_DEFAULT_DB_TARGET", "neon"))
    if str(target).lower().strip() == "local":
        return psycopg2.connect(
            host=os.getenv("LOCAL_DB_HOST", "localhost"),
            port=int(os.getenv("LOCAL_DB_PORT", "5432")),
            dbname=os.getenv("LOCAL_DB_NAME", "almsdata"),
            user=os.getenv("LOCAL_DB_USER", "postgres"),
            password=os.getenv("LOCAL_DB_PASSWORD", ""),
            sslmode=os.getenv("LOCAL_DB_SSLMODE", "prefer") or "prefer",
        )

    return psycopg2.connect(
        host=os.getenv("NEON_DB_HOST", os.getenv("DB_HOST", "")),
        port=int(os.getenv("NEON_DB_PORT", os.getenv("DB_PORT", "5432"))),
        dbname=os.getenv("NEON_DB_NAME", os.getenv("DB_NAME", "neondb")),
        user=os.getenv("NEON_DB_USER", os.getenv("DB_USER", "")),
        password=os.getenv("NEON_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
        sslmode=os.getenv("NEON_DB_SSLMODE", os.getenv("DB_SSLMODE", "require")) or "require",
    )


conn = _connect()
cur = conn.cursor()

for tbl in ['employees', 'payroll_entries', 'vendor_accounts', 'banking_transactions', 'receipts']:
    cur.execute("""SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (tbl,))
    rows = cur.fetchall()
    print(f"\n=== {tbl} ({len(rows)} cols) ===")
    for r in rows: print(f"  {r[0]}  ({r[1]})")

# Check if t4_data or similar tables exist
cur.execute("""SELECT table_name FROM information_schema.tables
    WHERE table_schema='public' AND table_name ILIKE '%t4%' OR table_name ILIKE '%payroll%'""")
print("\n=== T4/payroll tables ===")
for r in cur.fetchall(): print(f"  {r[0]}")

# Check GL account types present
cur.execute("""SELECT DISTINCT account_type, COUNT(*) FROM general_ledger 
    WHERE account_type IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 20""")
print("\n=== GL account_type values ===")
for r in cur.fetchall(): print(f"  {r[0]}: {r[1]}")

# Check fiscal years available
cur.execute("SELECT DISTINCT EXTRACT(YEAR FROM date)::int as yr FROM general_ledger WHERE date IS NOT NULL ORDER BY 1")
print("\n=== GL years ===")
for r in cur.fetchall(): print(f"  {r[0]}")

cur.close(); conn.close()
