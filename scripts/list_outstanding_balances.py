#!/usr/bin/env python
"""List all charters with outstanding balances (unpaid or partially paid)."""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres', 
    password='***REMOVED***',
    host='localhost'
)
cur = conn.cursor()

# Get charters with outstanding balances > $0.01 (exclude Oct 2025 and later)
cur.execute("""
    SELECT 
        c.reserve_number,
        c.charter_date,
        cl.client_name,
        c.total_amount_due,
        c.paid_amount,
        c.balance,
        c.status,
        c.cancelled
    FROM charters c
    LEFT JOIN clients cl ON cl.client_id = c.client_id
    WHERE c.balance > 0.01
    AND (c.charter_date IS NULL OR c.charter_date < '2025-10-01')
    ORDER BY c.balance DESC, c.charter_date DESC
""")

rows = cur.fetchall()

print(f"\n{'='*100}")
print(f"OUTSTANDING BALANCES REPORT - Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*100}\n")

if not rows:
    print("✓ No outstanding balances! All charters are paid in full or overpaid.")
else:
    print(f"Found {len(rows)} charters with outstanding balances:\n")
    
    # Group by status
    active_charters = []
    cancelled_charters = []
    
    for row in rows:
        if row[7]:  # cancelled
            cancelled_charters.append(row)
        else:
            active_charters.append(row)
    
    # Show active charters first
    if active_charters:
        print(f"ACTIVE CHARTERS ({len(active_charters)} charters, ${sum([r[5] for r in active_charters]):,.2f} owing):")
        print("-" * 100)
        print(f"{'Reserve#':<10} {'Date':<12} {'Client':<30} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'Status':<15}")
        print("-" * 100)
        
        for r in active_charters:
            reserve, date, client, total, paid, balance, status, _ = r
            client_display = (client[:27] + '...') if client and len(client) > 30 else (client or 'Unknown')
            date_str = date.strftime('%Y-%m-%d') if date else 'N/A'
            status_str = status or 'N/A'
            print(f"{reserve:<10} {date_str:<12} {client_display:<30} ${total:>11.2f} ${paid:>11.2f} ${balance:>11.2f} {status_str:<15}")
    
    # Show cancelled charters separately
    if cancelled_charters:
        print(f"\nCANCELLED CHARTERS ({len(cancelled_charters)} charters, ${sum([r[5] for r in cancelled_charters]):,.2f} owing):")
        print("-" * 100)
        print(f"{'Reserve#':<10} {'Date':<12} {'Client':<30} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'Status':<15}")
        print("-" * 100)
        
        for r in cancelled_charters:
            reserve, date, client, total, paid, balance, status, _ = r
            client_display = (client[:27] + '...') if client and len(client) > 30 else (client or 'Unknown')
            date_str = date.strftime('%Y-%m-%d') if date else 'N/A'
            status_str = status or 'N/A'
            print(f"{reserve:<10} {date_str:<12} {client_display:<30} ${total:>11.2f} ${paid:>11.2f} ${balance:>11.2f} {status_str:<15}")
    
    # Summary statistics
    print("\n" + "="*100)
    print("SUMMARY:")
    print("="*100)
    
    total_owing = sum([r[5] for r in rows])
    total_billed = sum([r[3] for r in rows])
    total_paid = sum([r[4] for r in rows])
    
    print(f"\nTotal Charters with Outstanding Balance: {len(rows)}")
    print(f"  - Active: {len(active_charters)} charters")
    print(f"  - Cancelled: {len(cancelled_charters)} charters")
    
    print(f"\nTotal Amount Billed: ${total_billed:,.2f}")
    print(f"Total Amount Paid: ${total_paid:,.2f}")
    print(f"Total Amount Outstanding: ${total_owing:,.2f}")
    print(f"Collection Rate: {(total_paid/total_billed*100) if total_billed > 0 else 0:.1f}%")
    
    # Age analysis (exclude Oct 2025 and later)
    cur.execute("""
        SELECT 
            CASE 
                WHEN charter_date >= CURRENT_DATE - INTERVAL '30 days' THEN '0-30 days'
                WHEN charter_date >= CURRENT_DATE - INTERVAL '60 days' THEN '31-60 days'
                WHEN charter_date >= CURRENT_DATE - INTERVAL '90 days' THEN '61-90 days'
                WHEN charter_date >= CURRENT_DATE - INTERVAL '180 days' THEN '91-180 days'
                WHEN charter_date >= CURRENT_DATE - INTERVAL '365 days' THEN '181-365 days'
                ELSE 'Over 1 year'
            END as age_bucket,
            COUNT(*) as charter_count,
            SUM(balance) as total_owing
        FROM charters
        WHERE balance > 0.01
        AND (charter_date IS NULL OR charter_date < '2025-10-01')
        GROUP BY 1
        ORDER BY 
            CASE 
                WHEN CASE 
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '30 days' THEN '0-30 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '60 days' THEN '31-60 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '90 days' THEN '61-90 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '180 days' THEN '91-180 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '365 days' THEN '181-365 days'
                    ELSE 'Over 1 year'
                END = '0-30 days' THEN 1
                WHEN CASE 
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '30 days' THEN '0-30 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '60 days' THEN '31-60 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '90 days' THEN '61-90 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '180 days' THEN '91-180 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '365 days' THEN '181-365 days'
                    ELSE 'Over 1 year'
                END = '31-60 days' THEN 2
                WHEN CASE 
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '30 days' THEN '0-30 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '60 days' THEN '31-60 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '90 days' THEN '61-90 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '180 days' THEN '91-180 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '365 days' THEN '181-365 days'
                    ELSE 'Over 1 year'
                END = '61-90 days' THEN 3
                WHEN CASE 
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '30 days' THEN '0-30 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '60 days' THEN '31-60 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '90 days' THEN '61-90 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '180 days' THEN '91-180 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '365 days' THEN '181-365 days'
                    ELSE 'Over 1 year'
                END = '91-180 days' THEN 4
                WHEN CASE 
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '30 days' THEN '0-30 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '60 days' THEN '31-60 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '90 days' THEN '61-90 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '180 days' THEN '91-180 days'
                    WHEN charter_date >= CURRENT_DATE - INTERVAL '365 days' THEN '181-365 days'
                    ELSE 'Over 1 year'
                END = '181-365 days' THEN 5
                ELSE 6
            END
    """)
    
    age_rows = cur.fetchall()
    
    if age_rows:
        print("\nAGING ANALYSIS:")
        print("-" * 60)
        print(f"{'Age Range':<20} {'Count':>10} {'Amount Owing':>15}")
        print("-" * 60)
        for age_bucket, count, owing in age_rows:
            print(f"{age_bucket:<20} {count:>10} ${owing:>14,.2f}")

cur.close()
conn.close()
