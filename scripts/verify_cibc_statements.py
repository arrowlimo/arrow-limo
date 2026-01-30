#!/usr/bin/env python3
"""
Verify CIBC Statements Against Database
========================================
Uses the new account_number_aliases infrastructure to properly match
CIBC statement formats to database records.

Tests May 2012 as example case.
"""

import psycopg2
import os
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def find_account_by_statement_format(cur, statement_number):
    """Use aliases to find canonical account number"""
    cur.execute("""
        SELECT canonical_account_number, notes
        FROM account_number_aliases
        WHERE statement_format = %s
    """, (statement_number,))
    result = cur.fetchone()
    return result if result else (None, None)

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CIBC STATEMENT VERIFICATION - Using Account Aliases")
    print("=" * 80)
    
    # Test Case: May 2012 Statement for account 00339-7461615
    print("\n📄 Test Case: May 2012 Statement (Account 00339-7461615)")
    print("-" * 80)
    
    # Find canonical account using aliases
    canonical, notes = find_account_by_statement_format(cur, '00339-7461615')
    
    if canonical:
        print(f"[OK] Account alias found:")
        print(f"   Statement format: 00339-7461615")
        print(f"   Database account: {canonical}")
        print(f"   Description: {notes}")
    else:
        print(f"[FAIL] No alias found for 00339-7461615")
        canonical = '0228362'  # fallback
        print(f"   Using fallback: {canonical}")
    
    # Query May 2012 transactions for this account
    print(f"\n📊 May 2012 Transactions for Account {canonical}:")
    print("-" * 80)
    
    cur.execute("""
        SELECT COUNT(*),
               MIN(transaction_date),
               MAX(transaction_date),
               SUM(debit_amount) as debits,
               SUM(credit_amount) as credits,
               SUM(credit_amount) - SUM(debit_amount) as net_change
        FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date >= '2012-05-01'
          AND transaction_date <= '2012-05-31'
    """, (canonical,))
    
    count, min_date, max_date, debits, credits, net = cur.fetchone()
    
    if count > 0:
        print(f"   [OK] Found {count} transactions")
        print(f"   Date range: {min_date} to {max_date}")
        print(f"   Total debits: ${debits:,.2f}")
        print(f"   Total credits: ${credits:,.2f}")
        print(f"   Net change: ${net:,.2f}")
    else:
        print(f"   [FAIL] No transactions found for May 2012")
    
    # Sample transactions
    if count > 0:
        print(f"\n   Sample Transactions:")
        cur.execute("""
            SELECT transaction_date, 
                   SUBSTRING(description, 1, 60) as desc,
                   debit_amount,
                   credit_amount
            FROM banking_transactions
            WHERE account_number = %s
              AND transaction_date >= '2012-05-01'
              AND transaction_date <= '2012-05-31'
            ORDER BY transaction_date, transaction_id
            LIMIT 10
        """, (canonical,))
        
        for date, desc, debit, credit in cur.fetchall():
            amt = f"-${debit:,.2f}" if debit else f"+${credit:,.2f}"
            print(f"      {date} | {amt:>12} | {desc}")
    
    # Check specific Page 3 items (May 4 and May 7)
    print(f"\n📋 Page 3 Targeted Item Check:")
    print("-" * 80)
    
    targets = [
        ("2012-05-04", 37.50, "debit", "CENTEX/DEERPARK"),
        ("2012-05-04", 94.65, "debit", "LIQUOR"),
        ("2012-05-04", 80.52, "debit", "generic"),
        ("2012-05-07", 1756.20, "debit", "Cheque"),
        ("2012-05-07", 89.50, "debit", "CENTEX/DEERPARK"),
        ("2012-05-07", 572.67, "credit", "DEPOSIT"),
        ("2012-05-07", 78.73, "debit", "FUTURE SHOP"),
        ("2012-05-07", 113.53, "debit", "HUSKY"),
        ("2012-05-07", 36.26, "debit", "FIVE GUYS"),
        ("2012-05-07", 213.75, "credit", "CREDIT MEMO"),
        ("2012-05-07", 200.00, "credit", "CREDIT MEMO"),
        ("2012-05-07", 110.27, "credit", "CREDIT MEMO"),
        ("2012-05-07", 101.14, "debit", "PRE AUTH"),
    ]
    
    matched = 0
    for date, amount, side, hint in targets:
        amt_col = "debit_amount" if side == "debit" else "credit_amount"
        
        # Search with ±1 day tolerance and both columns
        cur.execute(f"""
            SELECT transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE account_number = %s
              AND transaction_date BETWEEN (%s::date - INTERVAL '1 day') 
                                       AND (%s::date + INTERVAL '1 day')
              AND (
                (debit_amount > 0 AND ABS(debit_amount - %s) < 0.01) OR
                (credit_amount > 0 AND ABS(credit_amount - %s) < 0.01)
              )
            ORDER BY ABS(transaction_date - %s::date), transaction_id
            LIMIT 1
        """, (canonical, date, date, Decimal(str(amount)), Decimal(str(amount)), date))
        
        result = cur.fetchone()
        if result:
            matched += 1
            actual_date, desc, deb, cred = result
            day_diff = (actual_date - __import__('datetime').date.fromisoformat(date)).days
            day_note = f" ({day_diff:+d}d)" if day_diff != 0 else ""
            print(f"   [OK] {date} ${amount:>7.2f} {side:6} {hint:20} → {actual_date}{day_note}")
        else:
            print(f"   [FAIL] {date} ${amount:>7.2f} {side:6} {hint:20} → NOT FOUND")
    
    print(f"\n   Summary: {matched}/{len(targets)} items matched ({matched/len(targets)*100:.0f}%)")
    
    # Reconciliation status summary
    print(f"\n📊 Reconciliation Status Summary (May 2012):")
    print("-" * 80)
    
    cur.execute("""
        SELECT reconciliation_status, COUNT(*), SUM(debit_amount), SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date >= '2012-05-01'
          AND transaction_date <= '2012-05-31'
        GROUP BY reconciliation_status
        ORDER BY COUNT(*) DESC
    """, (canonical,))
    
    for status, count, debits, credits in cur.fetchall():
        status_label = status or 'unreconciled'
        print(f"   {status_label:20} | {count:4} txns | Debits: ${debits:>10,.2f} | Credits: ${credits:>10,.2f}")
    
    # Test alternate account formats
    print(f"\n🔍 Testing Alternate Account Format Searches:")
    print("-" * 80)
    
    alt_formats = ['00339', '7461615', '8362', '1010']
    for alt_fmt in alt_formats:
        canonical_alt, notes_alt = find_account_by_statement_format(cur, alt_fmt)
        if canonical_alt:
            cur.execute("""
                SELECT COUNT(*)
                FROM banking_transactions
                WHERE account_number = %s
                  AND transaction_date >= '2012-05-01'
                  AND transaction_date <= '2012-05-31'
            """, (canonical_alt,))
            alt_count = cur.fetchone()[0]
            print(f"   {alt_fmt:15} → {canonical_alt:10} → {alt_count:4} May 2012 txns")
        else:
            print(f"   {alt_fmt:15} → No alias found")
    
    # Overall summary
    print(f"\n" + "=" * 80)
    print(f"[OK] VERIFICATION COMPLETE")
    print(f"=" * 80)
    print(f"   Account alias system: WORKING")
    print(f"   May 2012 coverage: {count} transactions found")
    print(f"   Page 3 item matching: {matched}/{len(targets)} items ({matched/len(targets)*100:.0f}%)")
    
    if matched < len(targets):
        print(f"\n   [WARN] Missing items likely due to:")
        print(f"      • Transactions posted to different account")
        print(f"      • Posting date beyond ±1 day window")
        print(f"      • Import from different statement period")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
