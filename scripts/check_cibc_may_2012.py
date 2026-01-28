#!/usr/bin/env python3
"""
Check CIBC account May 2012 statement verification.

Context: We are validating Page 3 of the May 2012 CIBC Unlimited Business
Operating Account Statement (account number shown as 00339-7461615 in the PDF).
This script performs two layers of checks:
    1) Global May 2012 coverage overview (already implemented)
    2) Targeted match for the Page 3 line items (date + amount + keyword hints)

Rules:
- debit_amount > 0 means money leaving (purchases, cheques, PADs)
- credit_amount > 0 means money coming in (deposits, reversals)
"""
import psycopg2
import os
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("CIBC Account 00339 7461615 - May 2012 Statement Verification")
    print("=" * 80)
    
    # Search for this account number
    cur.execute("""
        SELECT COUNT(*), MIN(trans_date), MAX(trans_date),
               SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
               SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits
        FROM banking_transactions bt
        JOIN bank_accounts ba ON bt.bank_id = ba.bank_id
        WHERE ba.account_number LIKE '%00339%' OR ba.account_number LIKE '%7461615%'
    """)
    row = cur.fetchone()
    
    print(f"\n1. CIBC Account Search (by account number):")
    print(f"   Total transactions: {row[0]}")
    if row[0] > 0:
        print(f"   Date range: {row[1]} to {row[2]}")
        print(f"   Total debits: ${row[3]:,.2f}" if row[3] else "   Total debits: $0.00")
        print(f"   Total credits: ${row[4]:,.2f}" if row[4] else "   Total credits: $0.00")
    else:
        print("   [FAIL] No transactions found for this account number")
    
    # Check May 2012 transactions
    cur.execute("""
        SELECT COUNT(*), MIN(trans_date), MAX(trans_date),
               SUM(CASE WHEN debit_amount > 0 THEN debit_amount ELSE 0 END) as total_debits,
               SUM(CASE WHEN credit_amount > 0 THEN credit_amount ELSE 0 END) as total_credits
        FROM banking_transactions 
        WHERE trans_date BETWEEN '2012-05-01' AND '2012-05-31'
    """)
    row2 = cur.fetchone()
    
    print(f"\n2. May 2012 Banking Transactions (all accounts):")
    print(f"   Total transactions: {row2[0]}")
    if row2[0] > 0:
        print(f"   Date range: {row2[1]} to {row2[2]}")
        print(f"   Total debits: ${row2[3]:,.2f}" if row2[3] else "   Total debits: $0.00")
        print(f"   Total credits: ${row2[4]:,.2f}" if row2[4] else "   Total credits: $0.00")
    else:
        print("   [FAIL] No May 2012 transactions in database")
    
    # Check what account numbers exist in May 2012
    cur.execute("""
        SELECT DISTINCT account_number, COUNT(*) as txn_count
        FROM banking_transactions bt
        JOIN bank_accounts ba ON bt.bank_id = ba.bank_id
        WHERE trans_date BETWEEN '2012-05-01' AND '2012-05-31'
        GROUP BY account_number
        ORDER BY txn_count DESC
    """)
    accounts = cur.fetchall()
    
    print(f"\n3. May 2012 Account Numbers in Database:")
    if accounts:
        for acc, count in accounts:
            print(f"   {acc or 'NULL'}: {count} transactions")
    else:
        print("   [FAIL] No accounts found")
    
    # Sample some May 2012 transactions
    cur.execute("""
        SELECT trans_date, trans_description, debit_amount, credit_amount, balance_after
        FROM banking_transactions 
        WHERE trans_date BETWEEN '2012-05-01' AND '2012-05-31'
        ORDER BY trans_date, transaction_id
        LIMIT 10
    """)
    samples = cur.fetchall()
    
    print(f"\n4. Sample May 2012 Transactions:")
    if samples:
        for txn in samples:
            date, desc, debit, credit, bal = txn
            amt = f"-${debit:,.2f}" if debit else f"+${credit:,.2f}"
            print(f"   {date} | {amt:>12} | {desc[:50]}")
    else:
        print("   [FAIL] No transactions to display")
    
    # Targeted Page 3 verification (May 04 and May 07, 2012)
    print(f"\n5. Page 3 Targeted Line Items (May 04 & May 07, 2012):")
    targets = [
        # May 04 purchases
        {"date": "2012-05-04", "side": "debit",  "amount": 37.50,  "hints": ["CENTEX", "DEERPARK"]},
        {"date": "2012-05-04", "side": "debit",  "amount": 94.65,  "hints": ["LIQUOR"]},
        {"date": "2012-05-04", "side": "debit",  "amount": 80.52,  "hints": []},
        # May 07 items
        {"date": "2012-05-07", "side": "debit",  "amount": 1756.20, "hints": ["Cheque"]},
        {"date": "2012-05-07", "side": "debit",  "amount": 89.50,  "hints": ["CENTEX", "DEERPARK"]},
        {"date": "2012-05-07", "side": "credit", "amount": 572.67, "hints": ["DEPOSIT"]},
        {"date": "2012-05-07", "side": "debit",  "amount": 78.73,  "hints": ["FUTURE", "SHOP"]},
        {"date": "2012-05-07", "side": "debit",  "amount": 113.53, "hints": ["HUSKY", "ELBOW"]},
        {"date": "2012-05-07", "side": "debit",  "amount": 36.26,  "hints": ["FIVE", "GUYS"]},
        {"date": "2012-05-07", "side": "credit", "amount": 213.75, "hints": ["CREDIT", "MEMO"]},
        {"date": "2012-05-07", "side": "credit", "amount": 200.00, "hints": ["CREDIT", "MEMO"]},
        {"date": "2012-05-07", "side": "credit", "amount": 110.27, "hints": ["CREDIT", "MEMO"]},
        {"date": "2012-05-07", "side": "debit",  "amount": 101.14, "hints": ["PRE", "AUTH", "DEBIT"]},
    ]

    matched = 0
    missing = 0
    for t in targets:
        date = t["date"]
        amt = t["amount"]
        side = t["side"]
        hints = t["hints"]
        # Build WHERE clause
        amt_col = "debit_amount" if side == "debit" else "credit_amount"
        like_clause = ""
        params = [date, Decimal(str(amt))]
        if hints:
            like_clause = " AND " + " AND ".join(["LOWER(description) LIKE %s" for _ in hints])
            params.extend([f"%{h.lower()}%" for h in hints])

        sql = (
            """
            SELECT transaction_id, trans_date, trans_description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE trans_date = %s
              AND ({amt_col} > 0 AND ABS({amt_col} - %s) < 0.01)
              {like_clause}
            ORDER BY transaction_id
            LIMIT 3
            """
        ).format(amt_col=amt_col, like_clause=like_clause)
        cur.execute(sql, params)
        rows = cur.fetchall()
        label = f"{date} | {side.upper()} ${amt:.2f}"
        if rows:
            matched += 1
            print(f"   ✓ {label} - {rows[0][2][:60]}")
        else:
            missing += 1
            # Fallback: search same date by amount only (no hints)
            # Fallback 1: same date, amount only (same column/side)
            sql_amt_only = (
                """
                SELECT transaction_id, trans_date, trans_description, debit_amount, credit_amount
                FROM banking_transactions
                WHERE trans_date = %s
                  AND ({amt_col} > 0 AND ABS({amt_col} - %s) < 0.01)
                ORDER BY transaction_id
                LIMIT 3
                """
            ).format(amt_col=amt_col)
            cur.execute(sql_amt_only, [date, Decimal(str(amt))])
            rows2 = cur.fetchall()
            if rows2:
                matched += 1
                print(f"   ~ {label} (matched by amount only) - {rows2[0][2][:60]}")
            else:
                # Fallback 2: same date, match either column (handles swapped debit/credit cases)
                sql_either = (
                    """
                    SELECT transaction_id, trans_date, trans_description, debit_amount, credit_amount
                    FROM banking_transactions
                    WHERE trans_date = %s
                      AND (
                        (debit_amount > 0 AND ABS(debit_amount - %s) < 0.01) OR
                        (credit_amount > 0 AND ABS(credit_amount - %s) < 0.01)
                      )
                    ORDER BY transaction_id
                    LIMIT 3
                    """
                )
                cur.execute(sql_either, [date, Decimal(str(amt)), Decimal(str(amt))])
                rows3 = cur.fetchall()
                if rows3:
                    matched += 1
                    print(f"   ~ {label} (matched either column) - {rows3[0][2][:60]}")
                else:
                    # Fallback 3: near-date search +/- 1 day, either column, with hints if any
                    near_like = ""
                    near_params = [date, date, Decimal(str(amt)), Decimal(str(amt))]
                    # compute +/- 1 day bounds in SQL using BETWEEN date-1 and date+1
                    # We will do it via explicit bounds by casting to date and adding intervals
                    near_sql = (
                        """
                        SELECT transaction_id, trans_date, trans_description, debit_amount, credit_amount
                        FROM banking_transactions
                        WHERE trans_date BETWEEN (%s::date - INTERVAL '1 day') AND (%s::date + INTERVAL '1 day')
                          AND (
                            (debit_amount > 0 AND ABS(debit_amount - %s) < 0.01) OR
                            (credit_amount > 0 AND ABS(credit_amount - %s) < 0.01)
                          )
                        {near_like}
                        ORDER BY trans_date, transaction_id
                        LIMIT 3
                        """
                    )
                    if hints:
                        near_like = " AND " + " AND ".join(["LOWER(description) LIKE %s" for _ in hints])
                        near_params.extend([f"%{h.lower()}%" for h in hints])
                    cur.execute(near_sql.format(near_like=near_like), near_params)
                    rows4 = cur.fetchall()
                    if rows4:
                        matched += 1
                        print(f"   ~ {label} (near date ±1d) - {rows4[0][1]} | {rows4[0][2][:60]}")
                    else:
                        print(f"   ✗ {label} - NOT FOUND")

    print(f"\n   Page 3 targeted matches: {matched} found, {missing} not found")

    # Inspect all transactions on 2012-05-07 to diagnose mismatches
    print(f"\n6. All transactions on 2012-05-07 (any account):")
    cur.execute(
        """
        SELECT ba.account_number, bt.trans_date, bt.trans_description,
               bt.debit_amount, bt.credit_amount
        FROM banking_transactions bt
        JOIN bank_accounts ba ON bt.bank_id = ba.bank_id
        WHERE bt.trans_date = '2012-05-07'
        ORDER BY bt.transaction_id
        LIMIT 100
        """
    )
    day_rows = cur.fetchall()
    if day_rows:
        for acc, d, desc, deb, cred in day_rows:
            side = (f"- ${deb:,.2f}" if deb and deb > 0 else f"+ ${cred:,.2f}")
            print(f"   {acc or 'NULL'} | {d} | {side:>10} | {desc[:70] if desc else 'nan'}")
    else:
        print("   (No transactions on 2012-05-07)")

    # Also inspect the next posting day
    print(f"\n7. All transactions on 2012-05-08 (any account):")
    cur.execute(
        """
        SELECT ba.account_number, bt.trans_date, bt.trans_description,
               bt.debit_amount, bt.credit_amount
        FROM banking_transactions bt
        JOIN bank_accounts ba ON bt.bank_id = ba.bank_id
        WHERE bt.trans_date = '2012-05-08'
        ORDER BY bt.transaction_id
        LIMIT 100
        """
    )
    day_rows2 = cur.fetchall()
    if day_rows2:
        for acc, d, desc, deb, cred in day_rows2:
            side = (f"- ${deb:,.2f}" if deb and deb > 0 else f"+ ${cred:,.2f}")
            print(f"   {acc or 'NULL'} | {d} | {side:>10} | {desc[:70] if desc else 'nan'}")
    else:
        print("   (No transactions on 2012-05-08)")

    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
