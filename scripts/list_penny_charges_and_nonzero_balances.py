#!/usr/bin/env python3
"""
List charters with 0.01 cent charges and charters with non-zero balances.
"""

import psycopg2
from decimal import Decimal

def main():
    conn = psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***',
        host='localhost'
    )
    cur = conn.cursor()
    
    print("=" * 140)
    print("CHARTERS WITH $0.01 CHARGES")
    print("=" * 140)
    print()
    
    # Find charters with $0.01 total_amount_due
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.cancelled,
            c.status
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.total_amount_due = 0.01
        ORDER BY c.charter_date DESC, c.reserve_number
    """)
    
    penny_charters = cur.fetchall()
    
    if penny_charters:
        print(f"Found {len(penny_charters)} charter(s) with $0.01 total_amount_due:\n")
        print(f"{'Reserve':<12} {'Charter Date':<14} {'Client Name':<35} {'Total Due':<12} {'Paid':<12} {'Balance':<12} {'Status':<15}")
        print("-" * 140)
        
        for charter_id, reserve, charter_date, client, total, paid, balance, cancelled, status in penny_charters:
            client_name = (client or 'Unknown')[:34]
            status_str = 'CANCELLED' if cancelled else (status or 'active')
            print(f"{reserve:<12} {str(charter_date):<14} {client_name:<35} ${total:>10,.2f} ${paid:>10,.2f} ${balance:>10,.2f} {status_str:<15}")
    else:
        print("✓ No charters found with $0.01 total_amount_due")
    
    print()
    print()
    print("=" * 140)
    print("CHARTERS WITH NON-ZERO BALANCES")
    print("=" * 140)
    print()
    
    # Find charters with non-zero balance
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.cancelled,
            c.status
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE ABS(c.balance) > 0.01
        ORDER BY c.balance DESC, c.charter_date DESC
    """)
    
    nonzero_balances = cur.fetchall()
    
    if nonzero_balances:
        print(f"Found {len(nonzero_balances)} charter(s) with non-zero balance:\n")
        
        # Calculate totals
        total_balance = sum(b[6] for b in nonzero_balances)
        positive_balance = sum(b[6] for b in nonzero_balances if b[6] > 0)
        negative_balance = sum(b[6] for b in nonzero_balances if b[6] < 0)
        cancelled_count = sum(1 for b in nonzero_balances if b[7])
        
        print(f"Total Outstanding Balance: ${total_balance:,.2f}")
        print(f"  Positive (owed to us):   ${positive_balance:,.2f} ({sum(1 for b in nonzero_balances if b[6] > 0)} charters)")
        print(f"  Negative (overpaid):     ${negative_balance:,.2f} ({sum(1 for b in nonzero_balances if b[6] < 0)} charters)")
        print(f"  Cancelled charters:      {cancelled_count}")
        print()
        
        print(f"{'Reserve':<12} {'Charter Date':<14} {'Client Name':<35} {'Total Due':<12} {'Paid':<12} {'Balance':<12} {'Status':<15}")
        print("-" * 140)
        
        for charter_id, reserve, charter_date, client, total, paid, balance, cancelled, status in nonzero_balances[:100]:
            client_name = (client or 'Unknown')[:34]
            status_str = 'CANCELLED' if cancelled else (status or 'active')
            balance_str = f"${balance:>10,.2f}"
            if balance < 0:
                balance_str = f"({balance_str[1:]})"  # Show negative in parentheses
            print(f"{reserve:<12} {str(charter_date):<14} {client_name:<35} ${total:>10,.2f} ${paid:>10,.2f} {balance_str:<12} {status_str:<15}")
        
        if len(nonzero_balances) > 100:
            print(f"\n... and {len(nonzero_balances) - 100} more charters")
    else:
        print("✓ No charters found with non-zero balance")
    
    print()
    print("=" * 140)
    
    # Export to CSV for Excel analysis
    print("\nExporting to CSV files...")
    
    import csv
    
    # Export penny charges
    if penny_charters:
        with open('L:/limo/reports/penny_charges.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Reserve Number', 'Charter Date', 'Client Name', 'Total Due', 'Paid Amount', 'Balance', 'Cancelled', 'Status'])
            for row in penny_charters:
                writer.writerow([row[1], row[2], row[3] or 'Unknown', row[4], row[5], row[6], 'Yes' if row[7] else 'No', row[8] or ''])
        print(f"✓ Exported {len(penny_charters)} penny charges to: L:/limo/reports/penny_charges.csv")
    
    # Export non-zero balances
    if nonzero_balances:
        with open('L:/limo/reports/nonzero_balances.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Reserve Number', 'Charter Date', 'Client Name', 'Total Due', 'Paid Amount', 'Balance', 'Cancelled', 'Status'])
            for row in nonzero_balances:
                writer.writerow([row[1], row[2], row[3] or 'Unknown', row[4], row[5], row[6], 'Yes' if row[7] else 'No', row[8] or ''])
        print(f"✓ Exported {len(nonzero_balances)} non-zero balances to: L:/limo/reports/nonzero_balances.csv")
    
    print()
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
