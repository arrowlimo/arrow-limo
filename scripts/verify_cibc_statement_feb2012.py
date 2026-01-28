#!/usr/bin/env python3
"""
Verify CIBC Account Statement - February 2012
Account: 74-61615, Branch: 00339
Statement Period: Feb 1 - Feb 29, 2012
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
from datetime import date

def get_db_connection():
    """Standard ALMS database connection."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

# Extracted transactions from CIBC statement (Feb 2012)
STATEMENT_TRANSACTIONS = [
    # Page 1 (starts Feb 01)
    {'date': '2012-02-01', 'description': 'Opening balance', 'withdrawals': None, 'deposits': None, 'balance': -49.17},
    {'date': '2012-02-01', 'description': 'DEBIT MEMO', 'withdrawals': 1244.81, 'deposits': None, 'balance': -1293.98},  # Crossed out
    {'date': '2012-02-01', 'description': 'MERCH4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-01', 'description': 'GBL MERCH FEES', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-01', 'description': 'CORRECTION 00339', 'withdrawals': None, 'deposits': 1244.81, 'balance': -49.17},
    {'date': '2012-02-01', 'description': 'NSF CHARGE 00339', 'withdrawals': 42.50, 'deposits': None, 'balance': -91.67},  # Handwritten: "red line"
    {'date': '2012-02-02', 'description': 'MISC PAYMENT', 'withdrawals': None, 'deposits': 241.25, 'balance': 149.58},
    {'date': '2012-02-02', 'description': 'AMEX 930305093', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-02', 'description': 'AMEX BANK OF CANADA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-02', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 258.75, 'balance': 408.33},
    {'date': '2012-02-02', 'description': '4017775 MC', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-02', 'description': 'GBL MC 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-02', 'description': 'CREDIT MEMO', 'withdrawals': None, 'deposits': 789.50, 'balance': 1197.83},
    {'date': '2012-02-02', 'description': '4017775 VISA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-02', 'description': 'GBL VI 4017775', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-03', 'description': 'MISC PAYMENT', 'withdrawals': None, 'deposits': 222.91, 'balance': 1420.74},
    {'date': '2012-02-03', 'description': 'AMEX 970383083', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-03', 'description': 'AMEX BANK OF CANADA', 'withdrawals': None, 'deposits': None, 'balance': None},
    {'date': '2012-02-03', 'description': 'PURCHASE00001215008', 'withdrawals': 55.10, 'deposits': None, 'balance': 1365.64},
    {'date': '2012-02-03', 'description': 'CENTEX PETROLEU', 'withdrawals': None, 'deposits': None, 'balance': None},
]

STATEMENT_SUMMARY = {
    'account_number': '74-61615',
    'branch': '00339',
    'statement_period': ('2012-02-01', '2012-02-29'),
    'opening_balance': Decimal('-49.17'),
    'closing_balance': Decimal('1014.49'),
    'total_withdrawals': Decimal('36119.68'),
    'total_deposits': Decimal('37183.34'),
}

def check_banking_transactions_table(conn):
    """Check if banking_transactions table exists and what columns it has."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check table existence
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'banking_transactions'
        );
    """)
    table_exists = cur.fetchone()['exists']
    
    if not table_exists:
        print("[FAIL] Table 'banking_transactions' does NOT exist")
        cur.close()
        return None
    
    print("[OK] Table 'banking_transactions' exists")
    
    # Get column names
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'banking_transactions'
        ORDER BY ordinal_position;
    """)
    columns = cur.fetchall()
    print(f"\n📋 Columns in banking_transactions ({len(columns)} total):")
    for col in columns:
        print(f"   - {col['column_name']} ({col['data_type']})")
    
    cur.close()
    return [col['column_name'] for col in columns]

def query_feb2012_transactions(conn, columns):
    """Query banking_transactions for February 2012."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Build query based on available columns
    account_filter = ""
    if 'account_number' in columns:
        account_filter = "AND account_number = '74-61615'"
    elif 'account_name' in columns:
        account_filter = "AND account_name LIKE '%CIBC%'"
    
    query = f"""
        SELECT *
        FROM banking_transactions
        WHERE transaction_date >= '2012-02-01'
          AND transaction_date <= '2012-02-29'
          {account_filter}
        ORDER BY transaction_date, transaction_id;
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    return rows

def match_statement_to_db(statement_txns, db_txns):
    """Match statement transactions to database records."""
    
    print(f"\n{'='*80}")
    print(f"CIBC STATEMENT VERIFICATION - FEBRUARY 2012")
    print(f"Account: 74-61615 | Branch: 00339")
    print(f"{'='*80}\n")
    
    print(f"📄 Statement transactions: {len(statement_txns)}")
    print(f"💾 Database transactions: {len(db_txns)}")
    
    if len(db_txns) == 0:
        print("\n[FAIL] NO DATABASE RECORDS FOUND for February 2012!")
        print("\n📋 Statement Summary:")
        print(f"   Period: {STATEMENT_SUMMARY['statement_period'][0]} to {STATEMENT_SUMMARY['statement_period'][1]}")
        print(f"   Opening Balance: ${STATEMENT_SUMMARY['opening_balance']:,.2f}")
        print(f"   Closing Balance: ${STATEMENT_SUMMARY['closing_balance']:,.2f}")
        print(f"   Total Withdrawals: ${STATEMENT_SUMMARY['total_withdrawals']:,.2f}")
        print(f"   Total Deposits: ${STATEMENT_SUMMARY['total_deposits']:,.2f}")
        print(f"   Transaction Count: {len([t for t in statement_txns if t['withdrawals'] or t['deposits']])}")
        
        print("\n🔍 Sample Statement Transactions (first 10):")
        count = 0
        for txn in statement_txns:
            if txn['withdrawals'] or txn['deposits']:
                amount = txn['withdrawals'] if txn['withdrawals'] else txn['deposits']
                txn_type = 'W' if txn['withdrawals'] else 'D'
                print(f"   {txn['date']} | {txn_type} ${amount:>10.2f} | {txn['description']}")
                count += 1
                if count >= 10:
                    break
        
        return {'matched': 0, 'missing': len(statement_txns), 'coverage': 0.0}
    
    # If we have DB records, do detailed matching
    matched = 0
    missing = []
    
    for stmt_txn in statement_txns:
        if stmt_txn['withdrawals'] is None and stmt_txn['deposits'] is None:
            continue  # Skip balance forward and incomplete rows
        
        stmt_date = stmt_txn['date']
        stmt_desc = stmt_txn['description']
        stmt_amount = stmt_txn['withdrawals'] if stmt_txn['withdrawals'] else stmt_txn['deposits']
        
        # Try to find match in DB
        found = False
        for db_txn in db_txns:
            db_date = str(db_txn.get('transaction_date', ''))
            if db_date != stmt_date:
                continue
            
            # Check amount match (debit or credit)
            db_debit = db_txn.get('debit_amount', 0) or 0
            db_credit = db_txn.get('credit_amount', 0) or 0
            
            if stmt_txn['withdrawals'] and abs(float(db_debit) - float(stmt_amount)) < 0.01:
                found = True
                matched += 1
                break
            elif stmt_txn['deposits'] and abs(float(db_credit) - float(stmt_amount)) < 0.01:
                found = True
                matched += 1
                break
        
        if not found:
            missing.append(stmt_txn)
    
    total_stmt_txns = len([t for t in statement_txns if t['withdrawals'] or t['deposits']])
    coverage = (matched / total_stmt_txns * 100) if total_stmt_txns > 0 else 0
    
    print(f"\n[OK] Matched: {matched}/{total_stmt_txns} ({coverage:.1f}%)")
    print(f"[FAIL] Missing: {len(missing)}")
    
    if missing and len(missing) <= 20:
        print("\n🔍 Missing Transactions:")
        for txn in missing:
            amount = txn['withdrawals'] if txn['withdrawals'] else txn['deposits']
            txn_type = 'W' if txn['withdrawals'] else 'D'
            print(f"   {txn['date']} | {txn_type} ${amount:>10.2f} | {txn['description']}")
    
    return {'matched': matched, 'missing': len(missing), 'coverage': coverage}

def main():
    print("🔍 Verifying CIBC Statement - February 2012\n")
    
    conn = get_db_connection()
    
    # Step 1: Check table structure
    columns = check_banking_transactions_table(conn)
    
    if columns is None:
        print("\n[WARN] Cannot proceed - banking_transactions table not found")
        conn.close()
        return
    
    # Step 2: Query February 2012 transactions
    print("\n🔎 Querying database for February 2012 CIBC transactions...")
    db_txns = query_feb2012_transactions(conn, columns)
    
    # Step 3: Match statement to database
    result = match_statement_to_db(STATEMENT_TRANSACTIONS, db_txns)
    
    # Step 4: Final verdict
    print(f"\n{'='*80}")
    if result['coverage'] >= 95:
        print("[OK] EXCELLENT - Statement data is in ALMS database")
    elif result['coverage'] >= 75:
        print("[WARN] GOOD - Most statement data in ALMS, some gaps")
    elif result['coverage'] >= 50:
        print("[WARN] PARTIAL - Significant gaps in database coverage")
    elif result['coverage'] > 0:
        print("[FAIL] POOR - Minimal database coverage")
    else:
        print("[FAIL] NOT FOUND - Statement data NOT in ALMS database")
    print(f"{'='*80}\n")
    
    conn.close()

if __name__ == '__main__':
    main()
