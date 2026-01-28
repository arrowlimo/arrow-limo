#!/usr/bin/env python3
"""
Check Chart of Accounts Structure
==============================
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor

def connect_db():
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="almsdata",
            user="postgres", 
            password="***REMOVED***"
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def check_chart_structure():
    """Check chart of accounts table structure"""
    
    conn = connect_db()
    if not conn:
        return
    
    try:
        cur = conn.cursor(cursor_factory=DictCursor)
        
        # Get table structure
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'chart_of_accounts' 
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        print("📋 chart_of_accounts table structure:")
        for col in columns:
            print(f"   {col['column_name']:<25} {col['data_type']}")
        
        # Basic stats
        cur.execute("SELECT COUNT(*) FROM chart_of_accounts")
        total_rows = cur.fetchone()[0]
        print(f"\n📊 Usage summary:")
        print(f"   Total rows: {total_rows}")

        cur.execute(
            """
            SELECT account_type, COUNT(*) AS cnt
            FROM chart_of_accounts
            GROUP BY account_type
            ORDER BY cnt DESC NULLS LAST
            """
        )
        acct_by_type = cur.fetchall()
        if acct_by_type:
            print("   By account_type:")
            for acct_type, cnt in acct_by_type:
                print(f"     {acct_type}: {cnt}")

        # Foreign key usage
        cur.execute(
            """
            SELECT tc.table_schema, tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = 'chart_of_accounts'
            ORDER BY tc.table_schema, tc.table_name
            """
        )
        fk_refs = cur.fetchall()
        if fk_refs:
            print("   Referenced by:")
            for schema, table, column in fk_refs:
                cur.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                        sql.Identifier(schema), sql.Identifier(table)
                    )
                )
                total = cur.fetchone()[0]
                cur.execute(
                    sql.SQL(
                        "SELECT COUNT(DISTINCT {}) FROM {}.{} WHERE {} IS NOT NULL"
                    ).format(
                        sql.Identifier(column),
                        sql.Identifier(schema),
                        sql.Identifier(table),
                        sql.Identifier(column),
                    )
                )
                distinct_refs = cur.fetchone()[0]
                print(
                    f"     {schema}.{table}.{column}: rows={total}, distinct_accounts={distinct_refs}"
                )

        # Inspect key mapping tables (if present)
        mapping_tables = [
            ("category_mappings", "new_account_code"),
            ("category_to_account_map", "gl_account_code"),
        ]
        for table, code_col in mapping_tables:
            try:
                cur.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}" ).format(sql.Identifier(table))
                )
                total = cur.fetchone()[0]
                print(f"\n📎 {table}: rows={total}")

                cur.execute(
                    sql.SQL(
                        "SELECT {code}, COUNT(*) AS cnt\n"
                        "FROM {tbl}\n"
                        "WHERE {code} IS NOT NULL\n"
                        "GROUP BY {code}\n"
                        "ORDER BY cnt DESC\n"
                        "LIMIT 10"
                    ).format(
                        code=sql.Identifier(code_col),
                        tbl=sql.Identifier(table),
                    )
                )
                top_codes = cur.fetchall()
                if top_codes:
                    print("   Top account codes:")
                    for code_val, cnt in top_codes:
                        print(f"     {code_val}: {cnt}")
            except Exception as e:  # pragma: no cover - best effort diagnostics
                print(f"   Skipped {table}: {e}")

        # Get sample records
        cur.execute("SELECT * FROM chart_of_accounts ORDER BY 1 LIMIT 5")
        sample = cur.fetchall()

        if sample:
            print(f"\n📋 Sample records:")
            column_names = [desc[0] for desc in cur.description]
            for i, record in enumerate(sample, 1):
                print(f"\nRecord {i}:")
                for col_name, value in zip(column_names, record):
                    if value is not None and value != "":
                        print(f"  {col_name}: {value}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("CHART OF ACCOUNTS STRUCTURE CHECK")
    print("=" * 35)
    check_chart_structure()

if __name__ == "__main__":
    main()