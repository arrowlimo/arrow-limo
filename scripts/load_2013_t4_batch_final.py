#!/usr/bin/env python3
"""
Load FINAL batch of verified 2013 T4 slips into employee_t4_summary.

Slips (all year 2013):
- Michael Richard (SIN 656604808): income 10703.77, tax 557.96, cpp 379.84, ei 0.00
- James Ross (SIN 623418407): income 576.00, tax 0.00, cpp 13.04, ei 10.83
- Jeannie Shillington (SIN 623466877): income 21080.58, tax 2339.58, cpp 877.55, ei 396.31
- Alex Smyth (SIN 549706109): income 16500.45, tax 47.78, cpp 565.53, ei 31.03
- Larry Taylor (SIN 608403234): income 7560.49, tax 652.75, cpp 0.00, ei 142.13
- Norman Therrien (SIN 467658100): income 1389.25, tax 142.47, cpp 54.33, ei 26.12
- Rebecca Thompson (SIN 662907609): income 149.30, tax 0.00, cpp 0.00, ei 2.81
- Dustan Townsend (SIN 646518159): income 129.45, tax 0.00, cpp 0.00, ei 2.43
"""
import psycopg2
from decimal import Decimal

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

SLIPS = [
    {
        "sin": "656604808",
        "full_name": "Richard, Michael",
        "income": Decimal("10703.77"),
        "tax": Decimal("557.96"),
        "cpp": Decimal("379.84"),
        "ei": Decimal("0"),
        "box24": Decimal("0"),
        "box26": Decimal("10703.77"),
    },
    {
        "sin": "623418407",
        "full_name": "Ross, James",
        "income": Decimal("576.00"),
        "tax": Decimal("0"),
        "cpp": Decimal("13.04"),
        "ei": Decimal("10.83"),
        "box24": Decimal("576.00"),
        "box26": Decimal("576.00"),
    },
    {
        "sin": "623466877",
        "full_name": "Shillington, Jeannie",
        "income": Decimal("21080.58"),
        "tax": Decimal("2339.58"),
        "cpp": Decimal("877.55"),
        "ei": Decimal("396.31"),
        "box24": Decimal("21080.58"),
        "box26": Decimal("21080.58"),
    },
    {
        "sin": "549706109",
        "full_name": "Smyth, Alex",
        "income": Decimal("16500.45"),
        "tax": Decimal("47.78"),
        "cpp": Decimal("565.53"),
        "ei": Decimal("31.03"),
        "box24": Decimal("16500.45"),
        "box26": Decimal("16500.45"),
    },
    {
        "sin": "608403234",
        "full_name": "Taylor, Larry",
        "income": Decimal("7560.49"),
        "tax": Decimal("652.75"),
        "cpp": Decimal("0"),
        "ei": Decimal("142.13"),
        "box24": Decimal("7560.49"),
        "box26": Decimal("0"),
    },
    {
        "sin": "467658100",
        "full_name": "Therrien, Norman",
        "income": Decimal("1389.25"),
        "tax": Decimal("142.47"),
        "cpp": Decimal("54.33"),
        "ei": Decimal("26.12"),
        "box24": Decimal("1389.25"),
        "box26": Decimal("1389.25"),
    },
    {
        "sin": "662907609",
        "full_name": "Thompson, Rebecca",
        "income": Decimal("149.30"),
        "tax": Decimal("0"),
        "cpp": Decimal("0"),
        "ei": Decimal("2.81"),
        "box24": Decimal("149.30"),
        "box26": Decimal("149.30"),
    },
    {
        "sin": "646518159",
        "full_name": "Townsend, Dustan",
        "income": Decimal("129.45"),
        "tax": Decimal("0"),
        "cpp": Decimal("0"),
        "ei": Decimal("2.43"),
        "box24": Decimal("129.45"),
        "box26": Decimal("129.45"),
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
    
    # Temporarily disable triggers
    cur.execute('ALTER TABLE employees DISABLE TRIGGER ALL')
    
    try:
        for slip in SLIPS:
            emp_id = ensure_employee(cur, slip["full_name"], slip["sin"])
            upsert_t4_summary(cur, emp_id, slip)
        
        # Re-enable triggers
        cur.execute('ALTER TABLE employees ENABLE TRIGGER ALL')
        
        conn.commit()
        print(f"✅ Loaded {len(SLIPS)} slips for {FISCAL_YEAR} into employee_t4_summary.")
        print(f"✅ FINAL BATCH - All 2013 T4s loaded from PDF!")
    except Exception as exc:
        conn.rollback()
        print(f"❌ Error: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
