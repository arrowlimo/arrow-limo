#!/usr/bin/env python3
"""
Load verified 2013 T4 slips into employee_t4_summary.

Slips (all year 2013):
- Kevin Boulley (SIN 492717913): income 6227.90, tax 410.65, cpp 207.22, ei 117.09
- Jeffrey Brill (SIN 491174132): income 1096.21, tax 0.00,   cpp 22.08,  ei 206.31
- Shawn Callin (SIN 637005133): income 233.00,  tax 0.00,   cpp 0.00,   ei 4.38
- Marc Cote (SIN 626948285):   income 4107.65, tax 14.50,  cpp 108.87, ei 77.22
- Pat Fraser (SIN 635890171):  income 1488.95, tax 0.00,   cpp 24.70,  ei 28.00

Note: employee_t4_summary does not store box24/box26; they are documented in notes.
"""
import psycopg2
from decimal import Decimal
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

SLIPS = [
    {
        "sin": "492717913",
        "full_name": "Boulley, Kevin",
        "income": Decimal("6227.90"),
        "tax": Decimal("410.65"),
        "cpp": Decimal("207.22"),
        "ei": Decimal("117.09"),
        "box24": Decimal("6227.90"),
        "box26": Decimal("6227.90"),
    },
    {
        "sin": "491174132",
        "full_name": "Brill, Jeffrey",
        "income": Decimal("1096.21"),
        "tax": Decimal("0"),
        "cpp": Decimal("22.08"),
        "ei": Decimal("206.31"),
        "box24": Decimal("1096.21"),
        "box26": Decimal("1096.21"),
    },
    {
        "sin": "637005133",
        "full_name": "Callin, Shawn",
        "income": Decimal("233.00"),
        "tax": Decimal("0"),
        "cpp": Decimal("0"),
        "ei": Decimal("4.38"),
        "box24": Decimal("233.00"),
        "box26": Decimal("233.00"),
    },
    {
        "sin": "626948285",
        "full_name": "Cote, Marc",
        "income": Decimal("4107.65"),
        "tax": Decimal("14.50"),
        "cpp": Decimal("108.87"),
        "ei": Decimal("77.22"),
        "box24": Decimal("4107.65"),
        "box26": Decimal("4107.65"),
    },
    {
        "sin": "635890171",
        "full_name": "Fraser, Pat",
        "income": Decimal("1488.95"),
        "tax": Decimal("0"),
        "cpp": Decimal("24.70"),
        "ei": Decimal("28.00"),
        "box24": Decimal("1488.95"),
        "box26": Decimal("1488.95"),
    },
]

FISCAL_YEAR = 2013
SOURCE = "CRA T4 PDF - Manual Verification"
NOTES_SUFFIX = "Loaded from verified CRA T4 PDF 2013; box24/box26 documented here."


def ensure_employee(cur, full_name: str, sin: str) -> int:
    cur.execute(
        """
        SELECT employee_id FROM employees
        WHERE t4_sin = %s
        """,
        (sin,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    # Create employee
    cur.execute(
        """
        INSERT INTO employees (full_name, name, t4_sin, created_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING employee_id
        """,
        (full_name, full_name, sin),
    )
    return cur.fetchone()[0]


def upsert_t4_summary(cur, employee_id: int, slip: dict):
    notes = (
        f"{NOTES_SUFFIX} box24={slip['box24']} box26={slip['box26']}"
    )
    # Check existing
    cur.execute(
        """
        SELECT employee_id
        FROM employee_t4_summary
        WHERE employee_id = %s AND fiscal_year = %s
        """,
        (employee_id, FISCAL_YEAR),
    )
    if cur.fetchone():
        cur.execute(
            """
            UPDATE employee_t4_summary
            SET t4_employment_income = %s,
                t4_federal_tax = %s,
                t4_cpp_contributions = %s,
                t4_ei_contributions = %s,
                source = %s,
                is_verified = TRUE,
                notes = %s,
                updated_at = NOW()
            WHERE employee_id = %s AND fiscal_year = %s
            """,
            (
                slip["income"],
                slip["tax"],
                slip["cpp"],
                slip["ei"],
                SOURCE,
                notes,
                employee_id,
                FISCAL_YEAR,
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO employee_t4_summary (
                employee_id, fiscal_year,
                t4_employment_income, t4_federal_tax, t4_cpp_contributions, t4_ei_contributions,
                source, is_verified, notes, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, %s, NOW())
            """,
            (
                employee_id,
                FISCAL_YEAR,
                slip["income"],
                slip["tax"],
                slip["cpp"],
                slip["ei"],
                SOURCE,
                notes,
            ),
        )


def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    cur = conn.cursor()
    try:
        for slip in SLIPS:
            emp_id = ensure_employee(cur, slip["full_name"], slip["sin"])
            upsert_t4_summary(cur, emp_id, slip)
        conn.commit()
        print(f"Loaded {len(SLIPS)} slips for {FISCAL_YEAR} into employee_t4_summary.")
    except Exception as exc:
        conn.rollback()
        print(f"Error: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
