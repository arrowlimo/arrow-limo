#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import json
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "schema.json")

BUSINESS_KEYS = {
    "charters": ["reserve_number"],
    "payments": ["reserve_number"],
    "receipts": [],
    "employees": [],
    "vehicles": []
}

EXCLUDE_SCHEMAS = {"pg_catalog", "information_schema"}


def fetchall_dict(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN %s
        ORDER BY table_schema, table_name
        """,
        (tuple(EXCLUDE_SCHEMAS),)
    )
    tables = cur.fetchall()

    schema = {"database": DB_NAME, "tables": {}}

    for table_schema, table_name in tables:
        full = f"{table_schema}.{table_name}" if table_schema != "public" else table_name
        schema["tables"][full] = {
            "columns": {},
            "primary_key": [],
            "foreign_keys": [],
            "checks": [],
            "indexes": [],
            "business_keys": BUSINESS_KEYS.get(table_name, [])
        }

        # Columns
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_schema, table_name)
        )
        for row in fetchall_dict(cur):
            schema["tables"][full]["columns"][row["column_name"]] = {
                "type": row["data_type"],
                "nullable": row["is_nullable"] == "YES",
                "default": row["column_default"]
            }

        # Primary key
        cur.execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = %s
              AND tc.table_name = %s
              AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY kcu.ordinal_position
            """,
            (table_schema, table_name)
        )
        schema["tables"][full]["primary_key"] = [r[0] for r in cur.fetchall()]

        # Foreign keys
        cur.execute(
            """
            SELECT
              kcu.column_name AS column_name,
              ccu.table_schema AS foreign_table_schema,
              ccu.table_name AS foreign_table_name,
              ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
            ORDER BY kcu.position_in_unique_constraint NULLS LAST
            """,
            (table_schema, table_name)
        )
        for col, f_s, f_t, f_c in cur.fetchall():
            ref = f"{f_s}.{f_t}" if f_s != "public" else f_t
            schema["tables"][full]["foreign_keys"].append({
                "column": col,
                "references": {"table": ref, "column": f_c}
            })

        # Checks
        cur.execute(
            """
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE contype = 'c' AND n.nspname = %s AND t.relname = %s
            """,
            (table_schema, table_name)
        )
        schema["tables"][full]["checks"] = [
            {"name": name, "definition": definition}
            for name, definition in cur.fetchall()
        ]

        # Indexes (names only)
        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = %s AND tablename = %s
            ORDER BY indexname
            """,
            (table_schema, table_name)
        )
        schema["tables"][full]["indexes"] = [r[0] for r in cur.fetchall()]

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"✅ Wrote schema JSON to: {OUTPUT_PATH}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
