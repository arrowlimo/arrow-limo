#!/usr/bin/env python3
"""
Load batch 2 of verified 2013 T4 slips into employee_t4_summary.

Slips (all year 2013):
- Jesse Gordon (SIN 650202153): income 29578.92, tax 3504.78, cpp 1282.11, ei 556.09
- Jonathan Korsh (SIN 655104115): income 3972.73, tax 396.90, cpp 167.78, ei 74.69
- Kevin Kosik (SIN 638279935): income 283.55, tax 0.00, cpp 0.00, ei 5.33
- Mark Linton (SIN 467760377): income 1223.65, tax 0.00, cpp 26.21, ei 23.00
- Stephen Meek (SIN 457972008): income 11263.66, tax 1355.33, cpp 485.36, ei 211.75

Paul Mansell (SIN 505900829) already loaded in previous batch - SKIP
"""
import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

SLIPS = [
    {
        "sin": "650202153",
        "full_name": "Gordon, Jesse",
        "income": Decimal("29578.92"),
        "tax": Decimal("3504.78"),
        "cpp": Decimal("1282.11"),
        "ei": Decimal("556.09"),
        "box24": Decimal("29578.92"),
        "box26": Decimal("29578.92"),
    },
    {
        "sin": "655104115",
        "full_name": "Korsh, Jonathan",
        "income": Decimal("3972.73"),
        "tax": Decimal("396.90"),
        "cpp": Decimal("167.78"),
        "ei": Decimal("74.69"),
        "box24": Decimal("3972.73"),
        "box26": Decimal("3972.73"),
    },
    {
        "sin": "638279935",
        "full_name": "Kosik, Kevin",
        "income": Decimal("283.55"),
        "tax": Decimal("0"),
        "cpp": Decimal("0"),
        "ei": Decimal("5.33"),
        "box24": Decimal("283.55"),
        "box26": Decimal("283.55"),
    },
    {
        "sin": "467760377",
        "full_name": "Linton, Mark",
        "income": Decimal("1223.65"),
        "tax": Decimal("0"),
        "cpp": Decimal("26.21"),
        "ei": Decimal("23.00"),
        "box24": Decimal("1223.65"),
        "box26": Decimal("1223.65"),
    },
    {
        "sin": "457972008",
        "full_name": "Meek, Stephen",
        "income": Decimal("11263.66"),
        "tax": Decimal("1355.33"),
        "cpp": Decimal("485.36"),
        "ei": Decimal("211.75"),
        "box24": Decimal("11263.66"),
        "box26": Decimal("11263.66"),
    },
]

FISCAL_YEAR = 2013
SOURCE = "CRA T4 PDF - Manual Verification"
NOTES_SUFFIX = "Loaded from verified CRA T4 PDF 2013; box24/box26 documented here."


def ensure_employee(cur, full_name: str, sin: str) -> int:
    cur.execute("SELECT employee_id FROM employees WHERE t4_sin = %s", (sin,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO employees (full_name, name, t4_sin, created_at) VALUES (%s, %s, %s, NOW()) RETURNING employee_id",
        (full_name, full_name, sin),
    )
    return cur.fetchone()[0]


def upsert_t4_summary(cur, employee_id: int, slip: dict):
    notes = f"{NOTES_SUFFIX} box24={slip['box24']} box26={slip['box26']}"
    cur.execute(
        "SELECT employee_id FROM employee_t4_summary WHERE employee_id = %s AND fiscal_year = %s",
        (employee_id, FISCAL_YEAR),
    )
    if cur.fetchone():
        cur.execute(
            """UPDATE employee_t4_summary
            SET t4_employment_income = %s, t4_federal_tax = %s, t4_cpp_contributions = %s, t4_ei_contributions = %s,
                source = %s, is_verified = TRUE, notes = %s, updated_at = NOW()
            WHERE employee_id = %s AND fiscal_year = %s""",
            (slip["income"], slip["tax"], slip["cpp"], slip["ei"], SOURCE, notes, employee_id, FISCAL_YEAR),
        )
    else:
        cur.execute(
            """INSERT INTO employee_t4_summary (employee_id, fiscal_year, t4_employment_income, t4_federal_tax,
                t4_cpp_contributions, t4_ei_contributions, source, is_verified, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, NOW())""",
            (employee_id, FISCAL_YEAR, slip["income"], slip["tax"], slip["cpp"], slip["ei"], SOURCE, notes),
        )


def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    try:
        for slip in SLIPS:
            emp_id = ensure_employee(cur, slip["full_name"], slip["sin"])
            upsert_t4_summary(cur, emp_id, slip)
        conn.commit()
        print(f"✅ Loaded {len(SLIPS)} slips for {FISCAL_YEAR} into employee_t4_summary.")
    except Exception as exc:
        conn.rollback()
        print(f"❌ Error: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
