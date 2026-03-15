#!/usr/bin/env python3
"""
Categorize unlinked banking transactions by description patterns to understand what remains.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD')
    )


def get_columns(cur, table):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))
    return [r['column_name'] for r in cur.fetchall()]


def amount_expr(cols):
    if 'debit_amount' in cols and 'credit_amount' in cols:
        return '(COALESCE(credit_amount,0) - COALESCE(debit_amount,0))'
    elif 'amount' in cols:
        return 'amount'
    return '0'


CATEGORIES = {
    'withdrawal': ['withdrawal', 'atm', 'abm withdrawal'],
    'deposit': ['deposit', 'cheque', 'check', 'ck ', 'cash deposit', 'visa deposit', 'debit deposit'],
    'transfer': ['transfer', 'e-transfer', 'interac', 'eft'],
    'payment_out': ['payment', 'cheque #', 'chq #', 'ck#', 'electronic payment'],
    'direct_deposit': ['direct deposit', 'payroll deposit', 'dd '],
    'pos': ['pos purchase', 'point of sale', 'debit purchase', 'visa purchase'],
    'preauth': ['pre-authorization', 'preauth', 'pre-auth'],
    'reversal': ['reversal', 'reversed', 'return'],
}


def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    bt_cols = get_columns(cur, 'banking_transactions')
    amt = amount_expr(bt_cols)

    # Total unlinked
    cur.execute("SELECT COUNT(*) AS c FROM banking_transactions WHERE receipt_id IS NULL")
    total_unlinked = cur.fetchone()['c']

    print('='*80)
    print('UNLINKED BANKING TRANSACTIONS BREAKDOWN')
    print('='*80)
    print(f"Total unlinked: {total_unlinked}\n")

    results = []
    covered = 0

    for cat, patterns in CATEGORIES.items():
        like_clauses = " OR ".join(["LOWER(description) LIKE %s" for _ in patterns])
        params = [f"%{p.lower()}%" for p in patterns]

        cur.execute(
            f"""
            SELECT COUNT(*) AS c,
                   SUM(CASE WHEN ({amt}) < 0 THEN 1 ELSE 0 END) AS outflows,
                   SUM(CASE WHEN ({amt}) > 0 THEN 1 ELSE 0 END) AS inflows,
                   SUM(CASE WHEN ({amt}) = 0 THEN 1 ELSE 0 END) AS zero
            FROM banking_transactions
            WHERE receipt_id IS NULL
              AND ({like_clauses})
            """,
            params
        )
        row = cur.fetchone()
        count = row['c'] or 0
        results.append((cat, count, row['outflows'] or 0, row['inflows'] or 0, row['zero'] or 0))
        covered += count

    # Sort by count descending
    results.sort(key=lambda x: x[1], reverse=True)

    print(f"{'Category':<20} {'Count':>8} {'Outflows':>10} {'Inflows':>10} {'Zero':>8}")
    print('-'*64)
    for cat, count, out, inf, zero in results:
        if count > 0:
            print(f"{cat:<20} {count:>8} {out:>10} {inf:>10} {zero:>8}")

    print(f"\nCategorized: {covered}")
    print(f"Uncategorized: {total_unlinked - covered}")

    # Show top 15 uncategorized descriptions
    all_patterns = []
    for patterns in CATEGORIES.values():
        all_patterns.extend(patterns)

    not_like = " AND ".join(["LOWER(description) NOT LIKE %s" for _ in all_patterns])
    params = [f"%{p.lower()}%" for p in all_patterns]

    cur.execute(
        f"""
        SELECT description, COUNT(*) AS c
        FROM banking_transactions
        WHERE receipt_id IS NULL
          AND {not_like}
        GROUP BY description
        ORDER BY c DESC
        LIMIT 15
        """,
        params
    )
    uncategorized = cur.fetchall()

    if uncategorized:
        print('\nTop uncategorized descriptions:')
        for r in uncategorized:
            print(f"  {r['description'][:60]}: {r['c']}")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
