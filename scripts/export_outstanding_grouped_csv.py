"""
Export all outstanding balances to CSV sorted by age, grouped by cancellation status.
Groups: 1) Cancelled, 2) Not Cancelled, 3) All Outstanding
"""
import psycopg2
import csv
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get all outstanding balances, excluding future charters (Oct 2025+)
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
            c.notes,
            CURRENT_DATE - c.charter_date as days_old
        FROM charters c
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE c.balance > 0.01
        AND (c.charter_date IS NULL OR c.charter_date < '2025-10-01')
        ORDER BY 
            CASE WHEN c.cancelled THEN 1 ELSE 2 END,
            c.charter_date ASC NULLS FIRST
    """)
    
    results = cur.fetchall()
    
    # Prepare CSV filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_file = f'L:\\limo\\reports\\outstanding_balances_grouped_{timestamp}.csv'
    
    # Write to CSV
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'Group',
            'Reserve Number',
            'Charter Date',
            'Days Old',
            'Client Name',
            'Total Amount Due',
            'Amount Paid',
            'Outstanding Balance',
            'Status',
            'Cancelled',
            'Notes'
        ])
        
        # Group 1: Cancelled charters
        cancelled_count = 0
        cancelled_balance = 0
        
        for reserve, charter_date, client, total_due, paid, balance, status, cancelled, notes, days_old in results:
            if cancelled:
                cancelled_count += 1
                cancelled_balance += balance
                
                writer.writerow([
                    'CANCELLED',
                    reserve,
                    charter_date.strftime('%Y-%m-%d') if charter_date else '',
                    days_old if days_old else '',
                    client or 'Unknown',
                    f'{total_due:.2f}' if total_due else '0.00',
                    f'{paid:.2f}' if paid else '0.00',
                    f'{balance:.2f}' if balance else '0.00',
                    status or '',
                    'Yes' if cancelled else 'No',
                    notes or ''
                ])
        
        # Blank row separator
        writer.writerow([])
        
        # Summary row for cancelled
        writer.writerow([
            'CANCELLED SUBTOTAL',
            f'{cancelled_count} charters',
            '',
            '',
            '',
            '',
            '',
            f'{cancelled_balance:.2f}',
            '',
            '',
            ''
        ])
        
        # Blank row separator
        writer.writerow([])
        writer.writerow([])
        
        # Group 2: Not cancelled charters
        active_count = 0
        active_balance = 0
        
        for reserve, charter_date, client, total_due, paid, balance, status, cancelled, notes, days_old in results:
            if not cancelled:
                active_count += 1
                active_balance += balance
                
                writer.writerow([
                    'NOT CANCELLED',
                    reserve,
                    charter_date.strftime('%Y-%m-%d') if charter_date else '',
                    days_old if days_old else '',
                    client or 'Unknown',
                    f'{total_due:.2f}' if total_due else '0.00',
                    f'{paid:.2f}' if paid else '0.00',
                    f'{balance:.2f}' if balance else '0.00',
                    status or '',
                    'Yes' if cancelled else 'No',
                    notes or ''
                ])
        
        # Blank row separator
        writer.writerow([])
        
        # Summary row for not cancelled
        writer.writerow([
            'NOT CANCELLED SUBTOTAL',
            f'{active_count} charters',
            '',
            '',
            '',
            '',
            '',
            f'{active_balance:.2f}',
            '',
            '',
            ''
        ])
        
        # Blank row separator
        writer.writerow([])
        writer.writerow([])
        
        # Grand total
        total_count = cancelled_count + active_count
        total_balance = cancelled_balance + active_balance
        
        writer.writerow([
            'GRAND TOTAL',
            f'{total_count} charters',
            '',
            '',
            '',
            '',
            '',
            f'{total_balance:.2f}',
            '',
            '',
            ''
        ])
    
    print("="*80)
    print("OUTSTANDING BALANCES CSV EXPORT")
    print("="*80)
    print()
    print(f"✓ Exported to: {csv_file}")
    print()
    print("SUMMARY:")
    print("-" * 80)
    print(f"Group 1 - CANCELLED:        {cancelled_count:>3} charters  ${cancelled_balance:>12,.2f}")
    print(f"Group 2 - NOT CANCELLED:    {active_count:>3} charters  ${active_balance:>12,.2f}")
    print("-" * 80)
    print(f"TOTAL:                      {total_count:>3} charters  ${total_balance:>12,.2f}")
    print()
    print("Data sorted by:")
    print("  1. Cancellation status (Cancelled first, then Not Cancelled)")
    print("  2. Charter date (oldest first within each group)")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
