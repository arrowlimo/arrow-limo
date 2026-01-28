"""
Audit Reservations with Balances Owing

Analyzes charters with outstanding balances to identify:
- Total outstanding amounts
- Age of outstanding balances
- Payment patterns and history
- Discrepancies between total_amount_due, paid_amount, and balance
"""

import psycopg2
import os
from datetime import datetime, date
from decimal import Decimal

def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def analyze_outstanding_balances(cur):
    """Analyze all charters with outstanding balances."""
    
    print("=" * 80)
    print("OUTSTANDING BALANCES ANALYSIS")
    print("=" * 80)
    print()
    
    # Get charters with positive balances
    cur.execute("""
        SELECT 
            charter_id,
            reserve_number,
            charter_date,
            client_id,
            total_amount_due,
            paid_amount,
            balance,
            status,
            cancelled,
            closed
        FROM charters
        WHERE balance > 0
        ORDER BY balance DESC, charter_date DESC
    """)
    
    charters_owing = cur.fetchall()
    
    if not charters_owing:
        print("✓ No charters with outstanding balances found")
        return
    
    print(f"Found {len(charters_owing)} charters with outstanding balances")
    print()
    
    # Calculate totals and age distribution
    total_owing = Decimal('0')
    by_age = {
        'current': [],      # < 30 days
        '30-60': [],        # 30-60 days
        '60-90': [],        # 60-90 days
        '90+': []           # > 90 days
    }
    
    today = date.today()
    
    for charter in charters_owing:
        charter_id, reserve_number, charter_date, client_id, total_due, paid, balance, status, cancelled, closed = charter
        total_owing += balance
        
        # Calculate age
        if charter_date:
            age_days = (today - charter_date).days
            if age_days < 30:
                by_age['current'].append((charter_id, reserve_number, balance, age_days))
            elif age_days < 60:
                by_age['30-60'].append((charter_id, reserve_number, balance, age_days))
            elif age_days < 90:
                by_age['60-90'].append((charter_id, reserve_number, balance, age_days))
            else:
                by_age['90+'].append((charter_id, reserve_number, balance, age_days))
    
    # Summary by age
    print("=" * 80)
    print("AGING SUMMARY")
    print("=" * 80)
    print(f"{'Age Range':<15} {'Count':<10} {'Total Owing':<20}")
    print("-" * 80)
    
    for age_range in ['current', '30-60', '60-90', '90+']:
        count = len(by_age[age_range])
        total = sum(b[2] for b in by_age[age_range])
        print(f"{age_range:<15} {count:<10} ${total:>18,.2f}")
    
    print("-" * 80)
    print(f"{'TOTAL':<15} {len(charters_owing):<10} ${total_owing:>18,.2f}")
    print()
    
    # Top 10 largest outstanding balances
    print("=" * 80)
    print("TOP 10 LARGEST OUTSTANDING BALANCES")
    print("=" * 80)
    print(f"{'Reserve':<10} {'Date':<12} {'Total Due':<15} {'Paid':<15} {'Balance':<15} {'Status'}")
    print("-" * 80)
    
    for charter in charters_owing[:10]:
        charter_id, reserve_number, charter_date, client_id, total_due, paid, balance, status, cancelled, closed = charter
        date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'N/A'
        status_str = f"{'CANC' if cancelled else ''} {'CLOSED' if closed else ''} {status or ''}".strip()
        print(f"{reserve_number:<10} {date_str:<12} ${total_due or 0:>13,.2f} ${paid or 0:>13,.2f} ${balance:>13,.2f} {status_str}")
    
    print()
    
    # Check for calculation discrepancies
    print("=" * 80)
    print("BALANCE CALCULATION VERIFICATION")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            charter_id,
            reserve_number,
            total_amount_due,
            paid_amount,
            balance,
            (COALESCE(total_amount_due, 0) - COALESCE(paid_amount, 0)) as calculated_balance
        FROM charters
        WHERE balance > 0
        AND ABS(balance - (COALESCE(total_amount_due, 0) - COALESCE(paid_amount, 0))) > 0.01
    """)
    
    discrepancies = cur.fetchall()
    
    if discrepancies:
        print(f"[WARN]  Found {len(discrepancies)} charters with balance calculation discrepancies:")
        print()
        print(f"{'Reserve':<10} {'Total Due':<15} {'Paid':<15} {'Balance':<15} {'Calculated':<15} {'Diff'}")
        print("-" * 80)
        
        for row in discrepancies[:20]:
            charter_id, reserve_number, total_due, paid, balance, calc_balance = row
            diff = balance - calc_balance
            print(f"{reserve_number:<10} ${total_due or 0:>13,.2f} ${paid or 0:>13,.2f} ${balance:>13,.2f} ${calc_balance:>13,.2f} ${diff:>13,.2f}")
    else:
        print("✓ All balance calculations are correct")
    
    print()
    
    # Check for payment history
    print("=" * 80)
    print("PAYMENT HISTORY FOR TOP 5 OUTSTANDING")
    print("=" * 80)
    
    for charter in charters_owing[:5]:
        charter_id, reserve_number, charter_date, client_id, total_due, paid, balance, status, cancelled, closed = charter
        
        print()
        print(f"Reserve: {reserve_number} | Balance: ${balance:,.2f}")
        print("-" * 80)
        
        cur.execute("""
            SELECT 
                payment_date,
                amount,
                payment_method,
                notes
            FROM payments
            WHERE charter_id = %s
            ORDER BY payment_date
        """, (charter_id,))
        
        payments = cur.fetchall()
        
        if payments:
            print(f"{'Date':<12} {'Amount':<15} {'Method':<20} {'Notes'}")
            for payment_date, amount, method, notes in payments:
                date_str = payment_date.strftime('%Y-%m-%d') if payment_date else 'N/A'
                print(f"{date_str:<12} ${amount:>13,.2f} {method or 'N/A':<20} {notes or ''}")
        else:
            print("  No payments recorded")
        
        # Check for charges
        cur.execute("""
            SELECT 
                description,
                amount
            FROM charter_charges
            WHERE charter_id = %s
            ORDER BY charge_id
        """, (charter_id,))
        
        charges = cur.fetchall()
        
        if charges:
            print()
            print(f"  Charges:")
            for desc, amt in charges:
                print(f"    {desc}: ${amt:,.2f}")
    
    print()

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        analyze_outstanding_balances(cur)
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
