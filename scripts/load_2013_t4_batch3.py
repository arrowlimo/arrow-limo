#!/usr/bin/env python3
"""
Load batch 3 of verified 2013 T4 slips into employee_t4_summary.

Slips (all year 2013):
- Dale Menard (SIN 632609251): income 191.15, tax 0.00, cpp 0.00, ei 3.59
- Logan Mosinsky (SIN 659162093): income 369.90, tax 0.00, cpp 3.34, ei 6.95
- Tammy Pettitt (SIN 657829529): income 4818.75, tax 611.25, cpp 195.22, ei 90.60
- Doug Redmond (SIN 453928863): income 27962.77, tax 3255.13, cpp 1196.48, ei 525.70
- Erik Richard (SIN 656650728): income 73.40, tax 0.00, cpp 0.00, ei 0.00
- Paul Richard (SIN 637660614): income 16467.99, tax 1511.87, cpp 641.92, ei 0.00
"""
import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

SLIPS = [
    {
        "sin": "632609251",
        "full_name": "Menard, Dale",
        "income": Decimal("191.15"),
        "tax": Decimal("0"),
        "cpp": Decimal("0"),
        "ei": Decimal("3.59"),
        "box24": Decimal("191.15"),
        "box26": Decimal("191.15"),
    },
    {
        "sin": "659162093",
        "full_name": "Mosinsky, Logan",
        "income": Decimal("369.90"),
        "tax": Decimal("0"),
        "cpp": Decimal("3.34"),
        "ei": Decimal("6.95"),
        "box24": Decimal("369.90"),
        "box26": Decimal("369.90"),
    },
    {
        "sin": "657829529",
        "full_name": "Pettitt, Tammy",
        "income": Decimal("4818.75"),
        "tax": Decimal("611.25"),
        "cpp": Decimal("195.22"),
        "ei": Decimal("90.60"),
        "box24": Decimal("4818.75"),
        "box26": Decimal("4818.75"),
    },
    {
        "sin": "453928863",
        "full_name": "Redmond, Doug",
        "income": Decimal("27962.77"),
        "tax": Decimal("3255.13"),
        "cpp": Decimal("1196.48"),
        "ei": Decimal("525.70"),
        "box24": Decimal("27962.77"),
        "box26": Decimal("27962.77"),
    },
    {
        "sin": "656650728",
        "full_name": "Richard, Erik",
        "income": Decimal("73.40"),
        "tax": Decimal("0"),
        "cpp": Decimal("0"),
        "ei": Decimal("0"),
        "box24": Decimal("0"),
        "box26": Decimal("0"),
    },
    {
        "sin": "637660614",
        "full_name": "Richard, Paul",
        "income": Decimal("16467.99"),
        "tax": Decimal("1511.87"),
        "cpp": Decimal("641.92"),
        "ei": Decimal("0"),
        "box24": Decimal("0"),
        "box26": Decimal("16467.99"),
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
    # Get next employee_number
    cur.execute("SELECT COALESCE(MAX(CAST(employee_number AS INTEGER)), 0) + 1 FROM employees WHERE employee_number ~ '^[0-9]+$'")
    next_num = cur.fetchone()[0]
    # Insert with employee_number
    cur.execute(
        "INSERT INTO employees (employee_number, full_name, name, t4_sin, created_at) VALUES (%s, %s, %s, %s, NOW()) RETURNING employee_id",
        (str(next_num), full_name, full_name, sin),
    )
    emp_id = cur.fetchone()[0]
    # Update to set is_chauffeur=false separately to avoid trigger issues
    cur.execute("UPDATE employees SET is_chauffeur = false WHERE employee_id = %s", (emp_id,))
    return emp_id


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
