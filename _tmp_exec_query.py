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
for tbl in ['driver_payroll', 'employee_t4_records', 'employee_t4_summary', 'payroll_remittances', 'cra_payroll_submissions']:
    cur.execute("""SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""", (tbl,))
    rows = cur.fetchall()
    print(f"\n=== {tbl} ({len(rows)} cols) ===")
    for r in rows: print(f"  {r[0]}  ({r[1]})")
# Sample row counts
for tbl in ['driver_payroll','employee_t4_records','employee_t4_summary','payroll_remittances']:
    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
    print(f"\n{tbl}: {cur.fetchone()[0]} rows")
# GL account_type with non-null
cur.execute("SELECT DISTINCT account_type FROM general_ledger WHERE account_type IS NOT NULL AND account_type != '' LIMIT 20")
print("\n=== GL account types (non-null) ===")
for r in cur.fetchall(): print(f"  {r[0]}")
# GL account distributions
cur.execute("""SELECT account, ROUND(SUM(COALESCE(debit,0)-COALESCE(credit,0))::numeric,2) as net, COUNT(*) as cnt 
    FROM general_ledger WHERE account IS NOT NULL AND account != '' 
    GROUP BY 1 ORDER BY ABS(SUM(COALESCE(debit,0)-COALESCE(credit,0))) DESC LIMIT 20""")
print("\n=== Top GL accounts by net ===")
for r in cur.fetchall(): print(f"  {r[0]}: net ${r[1]:,.2f} ({r[2]} entries)")
cur.close(); conn.close()
