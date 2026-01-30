"""Verify Scotia Bank opening and closing balances for 2011-2012."""

import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)

cur = conn.cursor()

print("="*80)
print("SCOTIA BANK BALANCE VERIFICATION")
print("="*80)
print()

# Check Dec 31, 2011 closing balance
print("Dec 31, 2011 - Looking for closing balance...")
print()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date = '2011-12-31'
    ORDER BY transaction_id DESC
""")

dec_2011_rows = cur.fetchall()
if dec_2011_rows:
    print(f"Found {len(dec_2011_rows)} transaction(s) on Dec 31, 2011:")
    print()
    for date, desc, debit, credit, balance in dec_2011_rows:
        desc = (desc or "")[:50]
        debit_str = f"${debit:.2f}" if debit else ""
        credit_str = f"${credit:.2f}" if credit else ""
        bal_str = f"${balance:.2f}" if balance is not None else "NULL"
        print(f"  {date} | {desc:<50} | D: {debit_str:>10} | C: {credit_str:>10} | Bal: {bal_str:>12}")
    
    last_balance_2011 = dec_2011_rows[0][4]
    if last_balance_2011 is not None:
        print()
        print(f"📊 Dec 31, 2011 Closing Balance: ${last_balance_2011:,.2f}")
        if abs(float(last_balance_2011) - 952.04) < 0.01:
            print("   ✅ MATCHES expected $952.04")
        else:
            print(f"   ❌ DOES NOT MATCH expected $952.04 (difference: ${abs(float(last_balance_2011) - 952.04):.2f})")
else:
    print("❌ No transactions found on Dec 31, 2011")
    print()
    print("Checking last transaction BEFORE Jan 1, 2012...")
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date < '2012-01-01'
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 5
    """)
    
    prev_rows = cur.fetchall()
    if prev_rows:
        print(f"Last {len(prev_rows)} transaction(s) before 2012:")
        print()
        for date, desc, debit, credit, balance in prev_rows:
            desc = (desc or "")[:50]
            debit_str = f"${debit:.2f}" if debit else ""
            credit_str = f"${credit:.2f}" if credit else ""
            bal_str = f"${balance:.2f}" if balance is not None else "NULL"
            print(f"  {date} | {desc:<50} | D: {debit_str:>10} | C: {credit_str:>10} | Bal: {bal_str:>12}")
        
        last_balance_2011 = prev_rows[0][4]
        if last_balance_2011 is not None:
            print()
            print(f"📊 Last 2011 Balance: ${last_balance_2011:,.2f}")
            if abs(float(last_balance_2011) - 952.04) < 0.01:
                print("   ✅ MATCHES expected $952.04")
            else:
                print(f"   ⚠️  DOES NOT MATCH expected $952.04 (difference: ${abs(float(last_balance_2011) - 952.04):.2f})")
    else:
        print("❌ No transactions found before 2012")

print()
print("="*80)
print()

# Check Jan 1, 2012 opening balance
print("Jan 1, 2012 - Looking for opening balance...")
print()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date = '2012-01-01'
    ORDER BY transaction_id
""")

jan_2012_rows = cur.fetchall()
if jan_2012_rows:
    print(f"Found {len(jan_2012_rows)} transaction(s) on Jan 1, 2012:")
    print()
    for date, desc, debit, credit, balance in jan_2012_rows:
        desc = (desc or "")[:50]
        debit_str = f"${debit:.2f}" if debit else ""
        credit_str = f"${credit:.2f}" if credit else ""
        bal_str = f"${balance:.2f}" if balance is not None else "NULL"
        print(f"  {date} | {desc:<50} | D: {debit_str:>10} | C: {credit_str:>10} | Bal: {bal_str:>12}")
    
    opening_balance_2012 = jan_2012_rows[0][4]
    if opening_balance_2012 is not None:
        print()
        print(f"📊 Jan 1, 2012 Opening Balance: ${opening_balance_2012:,.2f}")
        if abs(float(opening_balance_2012) - 40.00) < 0.01:
            print("   ✅ MATCHES expected $40.00")
        else:
            print(f"   ⚠️  DOES NOT MATCH expected $40.00 (difference: ${abs(float(opening_balance_2012) - 40.00):.2f})")
else:
    print("❌ No transactions found on Jan 1, 2012")

print()
print("="*80)
print()

# Check Dec 31, 2012 closing balance
print("Dec 31, 2012 - Looking for closing balance...")
print()

cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND transaction_date = '2012-12-31'
    ORDER BY transaction_id DESC
""")

dec_2012_rows = cur.fetchall()
if dec_2012_rows:
    print(f"Found {len(dec_2012_rows)} transaction(s) on Dec 31, 2012:")
    print()
    for date, desc, debit, credit, balance in dec_2012_rows:
        desc = (desc or "")[:50]
        debit_str = f"${debit:.2f}" if debit else ""
        credit_str = f"${credit:.2f}" if credit else ""
        bal_str = f"${balance:.2f}" if balance is not None else "NULL"
        print(f"  {date} | {desc:<50} | D: {debit_str:>10} | C: {credit_str:>10} | Bal: {bal_str:>12}")
    
    closing_balance_2012 = dec_2012_rows[0][4]
    if closing_balance_2012 is not None:
        print()
        print(f"📊 Dec 31, 2012 Closing Balance: ${closing_balance_2012:,.2f}")
        if abs(float(closing_balance_2012) - 40.00) < 0.01:
            print("   ⚠️  MATCHES expected closing of $40.00 (but this seems unusual)")
        else:
            print(f"   Actual closing: ${closing_balance_2012:,.2f}")
else:
    print("❌ No transactions found on Dec 31, 2012")
    print()
    print("Checking last transaction of 2012...")
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 5
    """)
    
    last_2012_rows = cur.fetchall()
    if last_2012_rows:
        print(f"Last {len(last_2012_rows)} transaction(s) of 2012:")
        print()
        for date, desc, debit, credit, balance in last_2012_rows:
            desc = (desc or "")[:50]
            debit_str = f"${debit:.2f}" if debit else ""
            credit_str = f"${credit:.2f}" if credit else ""
            bal_str = f"${balance:.2f}" if balance is not None else "NULL"
            print(f"  {date} | {desc:<50} | D: {debit_str:>10} | C: {credit_str:>10} | Bal: {bal_str:>12}")
        
        closing_balance_2012 = last_2012_rows[0][4]
        if closing_balance_2012 is not None:
            print()
            print(f"📊 Last 2012 Balance: ${closing_balance_2012:,.2f}")

print()
print("="*80)
print("SUMMARY")
print("="*80)
print()
print("Expected:")
print(f"  Dec 31, 2011 Closing: $952.04")
print(f"  Jan 1, 2012 Opening:  $40.00")
print(f"  Dec 31, 2012 Closing: $40.00 (verify if this is correct)")
print()

cur.close()
conn.close()
