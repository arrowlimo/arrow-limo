#!/usr/bin/env python3
"""
2012 Data Inventory Analysis
============================

Queries the database to show exactly what data exists for 2012 across all key tables:
- Banking transactions (all accounts)
- Receipts/expenses
- Payments/revenue
- Charters/reservations
- Payroll
- General ledger
- Journal entries

Outputs a comprehensive breakdown with counts, date ranges, and totals.

Safe: Read-only queries.
"""
from __future__ import annotations

import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime


DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)


def get_table_exists(conn, table_name: str) -> bool:
    """Check if table exists"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            (table_name,),
        )
        return cur.fetchone()[0]


def get_columns(conn, table: str) -> set[str]:
    """Get column names for a table"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


def find_date_column(cols: set[str]) -> str | None:
    """Find the most likely date column"""
    for c in ("transaction_date", "date", "receipt_date", "payment_date", "charter_date", "posting_date", "created_at"):
        if c in cols:
            return c
    return None


def find_amount_column(cols: set[str]) -> str | None:
    """Find the most likely amount column"""
    for c in ("amount", "gross_amount", "payment_amount", "total_amount", "debit_amount", "credit_amount"):
        if c in cols:
            return c
    return None


def analyze_table(conn, table_name: str, year: int = 2012) -> dict:
    """Analyze a table for the given year"""
    if not get_table_exists(conn, table_name):
        return {"exists": False, "error": "Table does not exist"}
    
    cols = get_columns(conn, table_name)
    if not cols:
        return {"exists": True, "error": "No columns found"}
    
    date_col = find_date_column(cols)
    if not date_col:
        # Try to count total records without date filter
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            total = cur.fetchone()[0]
        return {
            "exists": True,
            "has_date_column": False,
            "total_records": total,
            "note": "No date column found - showing total records"
        }
    
    amount_col = find_amount_column(cols)
    
    try:
        with conn.cursor() as cur:
            # Count records for the year
            cur.execute(
                f"""
                SELECT 
                    COUNT(*) as count,
                    MIN({date_col}) as min_date,
                    MAX({date_col}) as max_date
                    {f", SUM(COALESCE({amount_col}, 0)) as total_amount" if amount_col else ""}
                FROM {table_name}
                WHERE EXTRACT(YEAR FROM {date_col}) = %s
                """,
                (year,),
            )
            row = cur.fetchone()
            
            result = {
                "exists": True,
                "has_date_column": True,
                "date_column": date_col,
                "count": int(row[0]) if row[0] else 0,
                "min_date": str(row[1]) if row[1] else None,
                "max_date": str(row[2]) if row[2] else None,
            }
            
            if amount_col and len(row) > 3:
                result["amount_column"] = amount_col
                result["total_amount"] = float(row[3]) if row[3] else 0.0
            
            return result
    except Exception as e:
        return {"exists": True, "error": str(e)}


def analyze_banking_accounts(conn, year: int = 2012) -> dict:
    """Get banking breakdown by account"""
    if not get_table_exists(conn, "banking_transactions"):
        return {"error": "banking_transactions table does not exist"}
    
    cols = get_columns(conn, "banking_transactions")
    date_col = find_date_column(cols)
    
    if not date_col:
        return {"error": "No date column found in banking_transactions"}
    
    account_col = next((c for c in ("account_number", "account_name", "bank_account") if c in cols), None)
    
    try:
        with conn.cursor() as cur:
            if account_col:
                cur.execute(
                    f"""
                    SELECT 
                        COALESCE({account_col}, 'Unknown') as account,
                        COUNT(*) as count,
                        SUM(COALESCE(debit_amount, 0)) as total_debits,
                        SUM(COALESCE(credit_amount, 0)) as total_credits
                    FROM banking_transactions
                    WHERE EXTRACT(YEAR FROM {date_col}) = %s
                    GROUP BY 1
                    ORDER BY 2 DESC
                    """,
                    (year,),
                )
            else:
                cur.execute(
                    f"""
                    SELECT 
                        'All Accounts' as account,
                        COUNT(*) as count,
                        SUM(COALESCE(debit_amount, 0)) as total_debits,
                        SUM(COALESCE(credit_amount, 0)) as total_credits
                    FROM banking_transactions
                    WHERE EXTRACT(YEAR FROM {date_col}) = %s
                    """,
                    (year,),
                )
            
            accounts = []
            for row in cur.fetchall():
                accounts.append({
                    "account": row[0],
                    "count": int(row[1]),
                    "total_debits": float(row[2]) if row[2] else 0.0,
                    "total_credits": float(row[3]) if row[3] else 0.0,
                })
            
            return {"accounts": accounts}
    except Exception as e:
        return {"error": str(e)}


def main():
    print("=" * 80)
    print("2012 DATA INVENTORY ANALYSIS")
    print("=" * 80)
    print()
    
    tables_to_check = [
        ("banking_transactions", "Banking Transactions"),
        ("receipts", "Receipts/Expenses"),
        ("payments", "Payments/Revenue"),
        ("charters", "Charters/Reservations"),
        ("driver_payroll", "Driver Payroll"),
        ("employee_pay_entries", "Employee Pay Entries"),
        ("unified_general_ledger", "General Ledger"),
        ("journal", "Journal Entries"),
        ("clients", "Clients"),
        ("employees", "Employees"),
        ("vehicles", "Vehicles"),
    ]
    
    try:
        with psycopg2.connect(**DSN) as conn:
            for table_name, display_name in tables_to_check:
                print(f"\n{display_name} ({table_name})")
                print("-" * 60)
                
                result = analyze_table(conn, table_name, 2012)
                
                if not result.get("exists"):
                    print(f"  [FAIL] Table does not exist")
                    continue
                
                if result.get("error"):
                    print(f"  [WARN]  Error: {result['error']}")
                    continue
                
                if not result.get("has_date_column"):
                    print(f"  [WARN]  {result.get('note', 'No date column')}")
                    print(f"  📊 Total records (all time): {result.get('total_records', 0):,}")
                    continue
                
                count = result.get("count", 0)
                if count == 0:
                    print(f"  [FAIL] No records found for 2012")
                    continue
                
                print(f"  [OK] Records: {count:,}")
                print(f"  📅 Date range: {result.get('min_date')} to {result.get('max_date')}")
                
                if result.get("amount_column"):
                    total = result.get("total_amount", 0.0)
                    print(f"  💰 Total amount ({result['amount_column']}): ${total:,.2f}")
            
            # Special analysis for banking accounts
            print(f"\n\nBanking Accounts Breakdown (2012)")
            print("-" * 60)
            banking_result = analyze_banking_accounts(conn, 2012)
            
            if banking_result.get("error"):
                print(f"  [WARN]  Error: {banking_result['error']}")
            elif banking_result.get("accounts"):
                for acc in banking_result["accounts"]:
                    print(f"\n  Account: {acc['account']}")
                    print(f"    Transactions: {acc['count']:,}")
                    print(f"    Debits:  ${acc['total_debits']:,.2f}")
                    print(f"    Credits: ${acc['total_credits']:,.2f}")
                    print(f"    Net:     ${(acc['total_credits'] - acc['total_debits']):,.2f}")
            else:
                print("  [FAIL] No banking data found for 2012")
            
            print("\n" + "=" * 80)
            print("ANALYSIS COMPLETE")
            print("=" * 80)
            
    except Exception as e:
        print(f"\n[FAIL] Error connecting to database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
