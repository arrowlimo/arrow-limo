#!/usr/bin/env python3
"""
Load initial 2014 T4 slips into employee_t4_summary.

Currently includes only the first verified slip (Marc Cote). Add additional slips
by appending to SLIPS with income/tax/cpp/ei/box24/box26 values from the CRA PDF.
"""
import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

SLIPS = [
    {
        "sin": "626948285",
        "full_name": "Cote, Marc",
        "income": Decimal("905.10"),
        "tax": Decimal("0"),
        "cpp": Decimal("0"),
        "ei": Decimal("0"),
        "box24": Decimal("905.10"),
        "box26": Decimal("905.10"),
    },
    {
        "sin": "627482227",
        "full_name": "Peterson, Gordon",
        "income": Decimal("1510.96"),
        "tax": Decimal("21.15"),
        "cpp": Decimal("47.42"),
        "ei": Decimal("28.40"),
        "box24": Decimal("1510.96"),
        "box26": Decimal("1510.96"),
    },
    {
        "sin": "657628529",
        "full_name": "Pettitt, Tammy",
        "income": Decimal("24799.13"),
        "tax": Decimal("3395.28"),
        "cpp": Decimal("1054.29"),
        "ei": Decimal("466.23"),
        "box24": Decimal("24799.13"),
        "box26": Decimal("24799.13"),
    },
    {
        "sin": "453928863",
        "full_name": "Redmond, Doug",
        "income": Decimal("11040.80"),
        "tax": Decimal("1366.06"),
        "cpp": Decimal("435.84"),
        "ei": Decimal("207.57"),
        "box24": Decimal("11040.80"),
        "box26": Decimal("11040.80"),
    },
    {
        "sin": "637660614",
        "full_name": "Richard, Paul D",
        "income": Decimal("16199.59"),
        "tax": Decimal("1713.10"),
        "cpp": Decimal("628.63"),
        "ei": Decimal("0"),
        "box24": Decimal("0"),
        "box26": Decimal("16199.59"),
    },
    {
        "sin": "123556011",
        "full_name": "Saunders, Shondal",
        "income": Decimal("2917.00"),
        "tax": Decimal("200.00"),
        "cpp": Decimal("76.28"),
        "ei": Decimal("54.84"),
        "box24": Decimal("2917.00"),
        "box26": Decimal("2917.00"),
    },
    {
        "sin": "623466877",
        "full_name": "Shillington, Jeannie",
        "income": Decimal("24111.15"),
        "tax": Decimal("2746.33"),
        "cpp": Decimal("1020.26"),
        "ei": Decimal("453.29"),
        "box24": Decimal("24111.15"),
        "box26": Decimal("24111.15"),
    },
    {
        "sin": "608403234",
        "full_name": "Taylor, Larry",
        "income": Decimal("730.00"),
        "tax": Decimal("160.00"),
        "cpp": Decimal("0"),
        "ei": Decimal("13.73"),
        "box24": Decimal("730.00"),
        "box26": Decimal("0"),
    },
    {
        "sin": "467658100",
        "full_name": "Therrien, Norman",
        "income": Decimal("7794.53"),
        "tax": Decimal("393.60"),
        "cpp": Decimal("243.42"),
        "ei": Decimal("146.54"),
        "box24": Decimal("7794.53"),
        "box26": Decimal("7794.53"),
    },
]

FISCAL_YEAR = 2014
SOURCE = "CRA T4 PDF - Manual Verification"
NOTES_SUFFIX = "Loaded from verified CRA T4 PDF 2014; box24/box26 documented here."


def ensure_employee(cur, full_name: str, sin: str) -> int:
    cur.execute("SELECT employee_id FROM employees WHERE t4_sin = %s", (sin,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "SELECT COALESCE(MAX(CAST(employee_number AS INTEGER)), 0) + 1 FROM employees WHERE employee_number ~ '^[0-9]+$'"
    )
    next_num = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO employees (employee_number, full_name, name, t4_sin, created_at) VALUES (%s, %s, %s, %s, NOW()) RETURNING employee_id",
        (str(next_num), full_name, full_name, sin),
    )
    emp_id = cur.fetchone()[0]
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

    cur.execute('ALTER TABLE employees DISABLE TRIGGER ALL')

    try:
        for slip in SLIPS:
            emp_id = ensure_employee(cur, slip["full_name"], slip["sin"])
            upsert_t4_summary(cur, emp_id, slip)

        cur.execute('ALTER TABLE employees ENABLE TRIGGER ALL')

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
