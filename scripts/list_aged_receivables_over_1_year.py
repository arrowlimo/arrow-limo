"""
Generate focused collection list for aged receivables over 1 year old.
Priority list for collection efforts on the most aged outstanding balances.
"""
import psycopg2
from datetime import datetime, date

def get_db_connection():
    """Connect to PostgreSQL."""
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*100)
    print(f"AGED RECEIVABLES COLLECTION PRIORITY LIST - Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*100)
    print()
    print("Focusing on balances over 1 year old (pre-November 2024)")
    print()
    
    # Get charters over 1 year old with outstanding balances
    cur.execute("""
        SELECT 
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status,
            c.cancelled,
            CURRENT_DATE - c.charter_date as days_old,
            CASE 
                WHEN CURRENT_DATE - c.charter_date >= 730 THEN 'Over 2 years'
                WHEN CURRENT_DATE - c.charter_date >= 548 THEN '18-24 months'
                WHEN CURRENT_DATE - c.charter_date >= 365 THEN '12-18 months'
            END as age_category
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.balance > 0.01
        AND c.charter_date IS NOT NULL
        AND c.charter_date < '2025-10-01'
        AND CURRENT_DATE - c.charter_date > 365
        ORDER BY c.balance DESC, c.charter_date ASC
    """)
    
    results = cur.fetchall()
    
    # Group by age category
    by_age = {
        'Over 2 years': [],
        '18-24 months': [],
        '12-18 months': []
    }
    
    for row in results:
        age_cat = row[9]
        by_age[age_cat].append(row)
    
    # Summary
    total_aged = len(results)
    total_amount = sum(r[5] for r in results)
    
    print(f"Total Aged Receivables (>1 year): {total_aged} charters")
    print(f"Total Amount Outstanding: ${total_amount:,.2f}")
    print()
    
    # Age category summary
    print("DISTRIBUTION BY AGE:")
    print("-" * 100)
    print(f"{'Age Category':<20} {'Count':<10} {'Amount':<15} {'% of Total':<12}")
    print("-" * 100)
    
    for age_cat in ['Over 2 years', '18-24 months', '12-18 months']:
        count = len(by_age[age_cat])
        amount = sum(r[5] for r in by_age[age_cat])
        pct = (amount / total_amount * 100) if total_amount > 0 else 0
        print(f"{age_cat:<20} {count:<10} ${amount:>12,.2f} {pct:>10.1f}%")
    
    print()
    
    # Top 20 largest balances
    print("TOP 20 LARGEST AGED BALANCES (Priority Collection Targets):")
    print("-" * 100)
    print(f"{'Reserve#':<10} {'Date':<12} {'Days Old':<10} {'Client':<30} {'Balance':<12} {'Status':<12}")
    print("-" * 100)
    
    for reserve, charter_date, client, total, paid, balance, status, cancelled, days_old, age_cat in results[:20]:
        date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'N/A'
        client_str = (client or 'Unknown')[:28]
        status_str = 'CANCELLED' if cancelled else (status or 'N/A')
        print(f"{reserve:<10} {date_str:<12} {days_old:<10} {client_str:<30} ${balance:>10,.2f} {status_str:<12}")
    
    print()
    
    # Detailed lists by age category
    for age_cat in ['Over 2 years', '18-24 months', '12-18 months']:
        charters = by_age[age_cat]
        count = len(charters)
        amount = sum(r[5] for r in charters)
        
        print()
        print("=" * 100)
        print(f"{age_cat.upper()} - {count} charters, ${amount:,.2f} outstanding")
        print("=" * 100)
        print()
        
        # Active vs Cancelled
        active = [r for r in charters if not r[7]]
        cancelled = [r for r in charters if r[7]]
        
        if active:
            print(f"ACTIVE CHARTERS ({len(active)} charters, ${sum(r[5] for r in active):,.2f}):")
            print("-" * 100)
            print(f"{'Reserve#':<10} {'Date':<12} {'Client':<35} {'Total Due':<12} {'Paid':<12} {'Balance':<12}")
            print("-" * 100)
            
            for reserve, charter_date, client, total, paid, balance, status, cancelled, days_old, _ in active:
                date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'N/A'
                client_str = (client or 'Unknown')[:33]
                print(f"{reserve:<10} {date_str:<12} {client_str:<35} ${total:>10,.2f} ${paid:>10,.2f} ${balance:>10,.2f}")
            print()
        
        if cancelled:
            print(f"CANCELLED CHARTERS ({len(cancelled)} charters, ${sum(r[5] for r in cancelled):,.2f}):")
            print("-" * 100)
            print(f"{'Reserve#':<10} {'Date':<12} {'Client':<35} {'Total Due':<12} {'Paid':<12} {'Balance':<12}")
            print("-" * 100)
            
            for reserve, charter_date, client, total, paid, balance, status, cancelled, days_old, _ in cancelled:
                date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'N/A'
                client_str = (client or 'Unknown')[:33]
                print(f"{reserve:<10} {date_str:<12} {client_str:<35} ${total:>10,.2f} ${paid:>10,.2f} ${balance:>10,.2f}")
            print()
    
    # Client summary - which clients owe the most on aged accounts
    print()
    print("=" * 100)
    print("AGED RECEIVABLES BY CLIENT (Top 20)")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            cl.client_name,
            COUNT(*) as charter_count,
            SUM(c.balance) as total_owed,
            MIN(c.charter_date) as oldest_charter,
            MAX(c.charter_date) as newest_charter
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.balance > 0.01
        AND c.charter_date IS NOT NULL
        AND c.charter_date < '2025-10-01'
        AND CURRENT_DATE - c.charter_date > 365
        GROUP BY cl.client_name
        ORDER BY total_owed DESC
        LIMIT 20
    """)
    
    print(f"{'Client Name':<40} {'Charters':<10} {'Total Owed':<15} {'Date Range':<25}")
    print("-" * 100)
    
    for client, count, total, oldest, newest in cur.fetchall():
        client_str = (client or 'Unknown')[:38]
        oldest_str = oldest.strftime('%Y-%m-%d') if oldest else 'N/A'
        newest_str = newest.strftime('%Y-%m-%d') if newest else 'N/A'
        date_range = f"{oldest_str} to {newest_str}"
        print(f"{client_str:<40} {count:<10} ${total:>12,.2f} {date_range:<25}")
    
    print()
    print("=" * 100)
    print("COLLECTION RECOMMENDATIONS:")
    print("=" * 100)
    print()
    print("1. PRIORITY: Focus on top 20 largest balances first (high-value recovery)")
    print("2. Consider write-off analysis for 'Over 2 years' category (low recovery likelihood)")
    print("3. Review cancelled charters - determine if collectible or should be written off")
    print("4. Contact clients with multiple aged charters for bulk settlement")
    print("5. Document collection attempts for CRA audit trail")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
