#!/usr/bin/env python3
"""
Apply categories to 2012 banking transactions based on description patterns.
This will fix the NULL category issue and enable proper receipt matching.
"""
import os
import psycopg2
import argparse

def connect():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    )

def categorize_2012_banking(dry_run=True):
    conn = connect()
    cur = conn.cursor()

    # Category patterns (from existing codebase patterns)
    patterns = [
        ('withdrawal', ['withdrawal', 'atm', 'cash advance']),
        ('pos_purchase', ['point of sale', 'pos purchase', 'interac purchase', 'retail purchase']),
        ('transfer', ['electronic funds transfer', 'e-transfer', 'internet banking', 'online transfer']),
        ('deposit', ['deposit', 'credit memo']),
        ('bank_fee', ['service charge', 'monthly fee', 'account fee', 'nsf', 'overdraft fee']),
        ('bill_payment', ['bill payment', 'pre-authorized debit', 'pad']),
        ('cheque', ['cheque', 'check']),
    ]

    print("=" * 80)
    print("CATEGORIZING 2012 BANKING TRANSACTIONS")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'APPLYING CHANGES'}\n")

    updates = {}
    for category, keywords in patterns:
        # Build LIKE pattern
        conditions = " OR ".join([f"LOWER(description) LIKE %s" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]

        # Count matches
        cur.execute(f"""
            SELECT COUNT(*)
            FROM banking_transactions
            WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
              AND category IS NULL
              AND ({conditions})
        """, params)
        count = cur.fetchone()[0]
        
        if count > 0:
            print(f"{category:20s}: {count:4,} transactions")
            updates[category] = (conditions, params, count)

    total_categorized = sum(info[2] for info in updates.values())
    
    # Count remaining NULL
    cur.execute("""
        SELECT COUNT(*)
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND category IS NULL
    """)
    remaining = cur.fetchone()[0]

    print(f"\n{'Total to categorize':20s}: {total_categorized:4,} transactions")
    print(f"{'Remaining NULL':20s}: {remaining - total_categorized:4,} transactions")

    if not dry_run:
        print("\n" + "=" * 80)
        print("APPLYING CATEGORIES...")
        print("=" * 80)
        
        for category, (conditions, params, count) in updates.items():
            cur.execute(f"""
                UPDATE banking_transactions
                SET category = %s
                WHERE transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
                  AND category IS NULL
                  AND ({conditions})
            """, [category] + params)
            print(f"✓ Updated {cur.rowcount:,} {category} transactions")
        
        conn.commit()
        print("\n[OK] All categories applied successfully!")
    else:
        print("\n💡 Run with --apply to update the database")

    cur.close()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description='Categorize 2012 banking transactions')
    parser.add_argument('--apply', action='store_true', help='Apply changes to database (default is dry-run)')
    args = parser.parse_args()

    categorize_2012_banking(dry_run=not args.apply)

if __name__ == '__main__':
    main()
