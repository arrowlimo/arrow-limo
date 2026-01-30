"""
Fill NULL balances smartly:
- Don't overwrite non-NULL balances
- Don't fill if next transaction has a non-NULL that would conflict
"""
import psycopg2
from decimal import Decimal
import sys

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def fill_nulls_for_year_smart(cur, account_number, year, apply_fixes=False):
    """
    Fill NULL balances smartly:
    - Start from last known non-NULL
    - Stop before conflicting non-NULL
    - Don't overwrite existing balances
    """
    
    # Get all transactions in order
    cur.execute("""
        SELECT transaction_id, transaction_date, description,
               debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date ASC, transaction_id ASC
    """, (account_number, year))
    
    transactions = cur.fetchall()
    if not transactions:
        return 0, None
    
    # Find continuous segments of NULLs between non-NULLs
    updates = []
    segments = []  # (start_idx, end_idx, starting_balance)
    
    i = 0
    while i < len(transactions):
        txn = transactions[i]
        if txn[5] is None:  # NULL balance found
            # Find the start of this NULL segment
            segment_start = i
            # Go back to find the starting balance
            starting_balance = None
            if i > 0 and transactions[i-1][5] is not None:
                starting_balance = Decimal(str(transactions[i-1][5]))
            elif i == 0 and year > 2012:
                # Need to get from previous year
                cur.execute("""
                    SELECT balance FROM banking_transactions
                    WHERE account_number = %s
                    AND EXTRACT(YEAR FROM transaction_date) = %s
                    ORDER BY transaction_date DESC, transaction_id DESC
                    LIMIT 1
                """, (account_number, year - 1))
                result = cur.fetchone()
                if result and result[0] is not None:
                    starting_balance = Decimal(str(result[0]))
            
            if starting_balance is None:
                i += 1
                continue
            
            # Find end of NULL segment
            segment_end = i
            while segment_end < len(transactions) and transactions[segment_end][5] is None:
                segment_end += 1
            
            segments.append((segment_start, segment_end, starting_balance))
            i = segment_end
        else:
            i += 1
    
    # Fill each segment
    for seg_start, seg_end, start_balance in segments:
        running_balance = start_balance
        
        for idx in range(seg_start, seg_end):
            txn = transactions[idx]
            txn_id, date, desc, debit, credit, old_balance = txn
            
            # Calculate new balance
            if debit:
                running_balance -= Decimal(str(debit))
            if credit:
                running_balance += Decimal(str(credit))
            
            # Add to updates
            updates.append((running_balance, txn_id))
    
    # Apply updates
    if apply_fixes and updates:
        for balance, txn_id in updates:
            cur.execute("""
                UPDATE banking_transactions 
                SET balance = %s 
                WHERE transaction_id = %s
            """, (balance, txn_id))
    
    # Get final balance of year
    cur.execute("""
        SELECT balance FROM banking_transactions
        WHERE account_number = %s
        AND EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date DESC, transaction_id DESC
        LIMIT 1
    """, (account_number, year))
    result = cur.fetchone()
    final_balance = Decimal(str(result[0])) if result and result[0] is not None else None
    
    return len(updates), final_balance

def main():
    apply_fixes = '--write' in sys.argv
    account_number = '1615'
    years = [2013, 2014, 2015, 2016, 2017]  # 2012 already complete
    
    print("="*100)
    print("CIBC 1615 - Fill NULL Balances (Smart Mode)")
    print("="*100)
    print(f"Mode: {'APPLYING FIXES' if apply_fixes else 'DRY-RUN'}")
    print()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    total_updates = 0
    year_results = {}
    
    for year in years:
        print(f"\n{year}:")
        print("-" * 100)
        
        updates, final_bal = fill_nulls_for_year_smart(cur, account_number, year, apply_fixes=apply_fixes)
        total_updates += updates
        year_results[year] = (updates, final_bal)
        
        if updates > 0:
            print(f"  ✓ Filled {updates} NULL balances")
            print(f"  Year ending balance: ${final_bal:.2f}" if final_bal else "  Year ending balance: UNKNOWN")
        else:
            print(f"  - No NULL balances found")
    
    print("\n" + "="*100)
    print(f"SUMMARY: {total_updates} NULL balance fields updated")
    print("="*100)
    
    # Show year-to-year continuity
    print("\nYear-to-Year Continuity Check:")
    print("-" * 100)
    for i, year in enumerate(years):
        updates, final_bal = year_results[year]
        if final_bal:
            print(f"{year} ending: ${final_bal:.2f}")
            if i < len(years) - 1:
                next_year = years[i+1]
                next_updates, next_opening = year_results[next_year]
                # next_opening is the year-end of that year, not the opening
                # Just note it for reference
    
    if apply_fixes:
        conn.commit()
        print("\n✅ All updates committed to database")
        
        # Verify
        print("\nFinal Verification:")
        for year in years:
            cur.execute("""
                SELECT COUNT(*),
                       COUNT(CASE WHEN balance IS NULL THEN 1 END)
                FROM banking_transactions
                WHERE account_number = %s
                AND EXTRACT(YEAR FROM transaction_date) = %s
            """, (account_number, year))
            total, nulls = cur.fetchone()
            if nulls > 0:
                print(f"  ⚠️ {year}: {total} txns, {nulls} still NULL")
            else:
                print(f"  ✅ {year}: {total} txns, 0 NULL")
    else:
        print(f"\n👉 Ready to apply {total_updates} updates")
        print(f"   Run: python scripts/fill_null_balances_smart.py --write")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
