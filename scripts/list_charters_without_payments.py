#!/usr/bin/env python3
"""
List charters that don't have matched payments.
Shows charters with charges but no payment records linked.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("CHARTERS WITHOUT MATCHED PAYMENTS")
    print("=" * 100)
    print()
    
    # Find charters with no payments linked
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.account_number,
            COALESCE(cl.client_name, '') as client_name,
            COALESCE(cc.total_charges, 0) as total_charges,
            COALESCE(c.balance, 0) as balance,
            c.status,
            c.cancelled
        FROM charters c
        LEFT JOIN (
            SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ) cc ON c.charter_id = cc.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND EXTRACT(YEAR FROM c.charter_date) BETWEEN 2007 AND 2024
        AND COALESCE(c.payment_excluded, FALSE) = FALSE
        ORDER BY c.charter_date DESC
    """)
    
    charters_no_payments = cur.fetchall()
    
    print(f"Total charters without matched payments (2007-2024): {len(charters_no_payments):,}")
    print()
    
    # Breakdown by year
    year_counts = {}
    year_charges = {}
    for row in charters_no_payments:
        charter_id, reserve_num, charter_date, account, client, charges, balance, status, cancelled = row
        if charter_date:
            year = charter_date.year
            year_counts[year] = year_counts.get(year, 0) + 1
            year_charges[year] = year_charges.get(year, 0) + float(charges)
    
    print("Breakdown by year:")
    print(f"{'Year':<8} {'Count':<10} {'Total Charges':<15}")
    print("-" * 40)
    for year in sorted(year_counts.keys()):
        count = year_counts[year]
        charges = year_charges[year]
        print(f"{year:<8} {count:<10,} ${charges:<14,.2f}")
    
    print()
    
    # Filter to charters with charges > 0
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.account_number,
            COALESCE(cl.client_name, '') as client_name,
            COALESCE(cc.total_charges, 0) as total_charges,
            COALESCE(c.balance, 0) as balance,
            c.status,
            c.cancelled
        FROM charters c
        LEFT JOIN (
            SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
            FROM charter_charges
            GROUP BY charter_id
        ) cc ON c.charter_id = cc.charter_id
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.charter_id = c.charter_id
        )
        AND EXTRACT(YEAR FROM c.charter_date) BETWEEN 2007 AND 2024
        AND COALESCE(cc.total_charges, 0) > 0
        ORDER BY cc.total_charges DESC
    """)
    
    charters_with_charges = cur.fetchall()
    
    print("=" * 100)
    print(f"CHARTERS WITH CHARGES BUT NO PAYMENTS: {len(charters_with_charges):,}")
    print("=" * 100)
    print()
    
    total_unpaid = sum(float(row[5]) for row in charters_with_charges)
    print(f"Total unpaid charges: ${total_unpaid:,.2f}")
    print()
    
    print("Top 50 charters with highest unpaid charges:")
    print(f"{'Charter ID':<12} {'Reserve':<10} {'Date':<12} {'Client':<30} {'Charges':<12} {'Status':<15}")
    print("-" * 100)
    
    for row in charters_with_charges[:50]:
        charter_id, reserve_num, charter_date, account, client, charges, balance, status, cancelled = row
        date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'N/A'
        client_short = (client[:27] + '...') if len(client) > 30 else client
        status_str = 'CANCELLED' if cancelled else (status or 'Unknown')
        
        print(f"{charter_id:<12} {reserve_num:<10} {date_str:<12} {client_short:<30} ${float(charges):<11,.2f} {status_str:<15}")
    
    if len(charters_with_charges) > 50:
        print(f"... and {len(charters_with_charges) - 50:,} more")
    
    # Cancelled charters
    cancelled_count = sum(1 for row in charters_with_charges if row[8])
    cancelled_amount = sum(float(row[5]) for row in charters_with_charges if row[8])
    
    print()
    print("=" * 100)
    print("CANCELLED CHARTERS (should have no payments):")
    print("=" * 100)
    print()
    print(f"Cancelled charters: {cancelled_count:,}")
    print(f"Total charges on cancelled: ${cancelled_amount:,.2f}")
    print()
    
    # Non-cancelled with charges
    active_count = len(charters_with_charges) - cancelled_count
    active_amount = total_unpaid - cancelled_amount
    
    print("=" * 100)
    print("NON-CANCELLED CHARTERS MISSING PAYMENTS:")
    print("=" * 100)
    print()
    print(f"Active charters without payments: {active_count:,}")
    print(f"Total unpaid (non-cancelled): ${active_amount:,.2f}")
    print()
    
    if active_count > 0:
        print("[WARN] These charters may have unmatched payments in the database")
        print("   or payments that need to be recorded.")
        print()
        print("Sample non-cancelled charters without payments:")
        print(f"{'Charter ID':<12} {'Reserve':<10} {'Date':<12} {'Client':<30} {'Charges':<12}")
        print("-" * 90)
        
        shown = 0
        for row in charters_with_charges:
            charter_id, reserve_num, charter_date, account, client, charges, balance, status, cancelled = row
            if not cancelled and shown < 20:
                date_str = charter_date.strftime('%Y-%m-%d') if charter_date else 'N/A'
                client_short = (client[:27] + '...') if len(client) > 30 else client
                print(f"{charter_id:<12} {reserve_num:<10} {date_str:<12} {client_short:<30} ${float(charges):<11,.2f}")
                shown += 1
    
    # Export to CSV
    print()
    print("=" * 100)
    print("EXPORTING TO CSV...")
    print("=" * 100)
    print()
    
    import csv
    output_file = r'L:\limo\charters_without_payments.csv'
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Charter ID', 'Reserve Number', 'Charter Date', 'Account Number', 
                        'Client Name', 'Total Charges', 'Balance', 'Status', 'Cancelled'])
        
        for row in charters_no_payments:
            charter_id, reserve_num, charter_date, account, client, charges, balance, status, cancelled = row
            date_str = charter_date.strftime('%Y-%m-%d') if charter_date else ''
            writer.writerow([
                charter_id,
                reserve_num,
                date_str,
                account or '',
                client or '',
                f"{float(charges):.2f}",
                f"{float(balance):.2f}",
                status or '',
                'Yes' if cancelled else 'No'
            ])
    
    print(f"[OK] Exported {len(charters_no_payments):,} charters to: {output_file}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
