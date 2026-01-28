from __future__ import annotations

import csv
from pathlib import Path
import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

OUT_CSV = Path(r"L:\\limo\\data\\EMPLOYEES_FOR_T4_MAPPING.csv")


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def main():
    conn = connect_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT employee_id, full_name, name, legacy_name, first_name, last_name, t4_sin
            FROM employees
            ORDER BY last_name, first_name
            """
        )
        rows = cur.fetchall()
        OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "employee_id",
                "full_name",
                "name",
                "legacy_name",
                "first_name",
                "last_name",
                "t4_sin",
            ])
            for r in rows:
                writer.writerow(list(r))
        print(f"✅ Exported employees: {OUT_CSV}")
        print(f"   Rows: {len(rows)}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
