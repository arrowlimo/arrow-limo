"""
Deep dive into the 123 unpaid charters.
Get full details including charge breakdowns and any patterns.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import csv
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def deep_dive():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 120)
    print("DEEP DIVE: UNPAID CHARTERS ANALYSIS")
    print("=" * 120)
    
    # Get detailed charter information with charge breakdown
    cur.execute("""
        WITH unpaid_charters AS (
            SELECT c.charter_id, c.reserve_number, c.charter_date, c.total_amount_due
            FROM charters c
            WHERE c.total_amount_due > 0
              AND (c.paid_amount IS NULL OR c.paid_amount = 0)
              AND c.cancelled = FALSE
        )
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.account_number,
            cl.client_name,
            c.total_amount_due,
            c.rate,
            c.balance,
            c.status,
            c.closed,
            c.booking_status,
            c.payment_status,
            c.notes,
            c.booking_notes,
            c.client_notes,
            c.special_requirements,
            c.pickup_address,
            c.dropoff_address,
            c.passenger_count,
            -- Charge details
            (SELECT json_agg(json_build_object(
                'description', cc.description,
                'amount', cc.amount,
                'charge_type', cc.charge_type
            ))
            FROM charter_charges cc 
            WHERE cc.charter_id = c.charter_id) as charges_detail,
            -- Check if it's in LMS
            (SELECT COUNT(*) FROM payments p 
             WHERE p.reserve_number = c.reserve_number 
                OR p.charter_id = c.charter_id) as payment_count_pg
        FROM charters c
        INNER JOIN unpaid_charters uc ON c.charter_id = uc.charter_id
        LEFT JOIN clients cl ON c.account_number = cl.client_id::text
        ORDER BY c.charter_date DESC, c.reserve_number DESC
    """)
    
    charters = cur.fetchall()
    
    print(f"\nTotal unpaid charters: {len(charters)}")
    print(f"Total amount: ${sum(ch['total_amount_due'] or 0 for ch in charters):,.2f}\n")
    
    # Analyze by year
    by_year = {}
    for ch in charters:
        year = ch['charter_date'].year if ch['charter_date'] else 'Unknown'
        if year not in by_year:
            by_year[year] = {'count': 0, 'amount': 0, 'charters': []}
        by_year[year]['count'] += 1
        by_year[year]['amount'] += ch['total_amount_due'] or 0
        by_year[year]['charters'].append(ch)
    
    print("BREAKDOWN BY YEAR:")
    print("-" * 120)
    for year in sorted(by_year.keys(), reverse=True):
        data = by_year[year]
        print(f"{year}: {data['count']} charters, ${data['amount']:,.2f}")
    
    # Check booking_status values
    print("\n" + "=" * 120)
    print("BOOKING STATUS DISTRIBUTION:")
    print("-" * 120)
    status_counts = {}
    for ch in charters:
        status = ch['booking_status'] or 'NULL'
        status_counts[status] = status_counts.get(status, 0) + 1
    
    for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {status}: {count}")
    
    # Check payment_status values
    print("\n" + "=" * 120)
    print("PAYMENT STATUS DISTRIBUTION:")
    print("-" * 120)
    payment_status_counts = {}
    for ch in charters:
        status = ch['payment_status'] or 'NULL'
        payment_status_counts[status] = payment_status_counts.get(status, 0) + 1
    
    for status, count in sorted(payment_status_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {status}: {count}")
    
    # Check closed flag
    print("\n" + "=" * 120)
    print("CLOSED FLAG DISTRIBUTION:")
    print("-" * 120)
    closed_counts = {'True': 0, 'False': 0, 'NULL': 0}
    for ch in charters:
        if ch['closed'] is True:
            closed_counts['True'] += 1
        elif ch['closed'] is False:
            closed_counts['False'] += 1
        else:
            closed_counts['NULL'] += 1
    
    for status, count in sorted(closed_counts.items()):
        print(f"  {status}: {count}")
    
    # Look for patterns in notes
    print("\n" + "=" * 120)
    print("COMMON PATTERNS IN NOTES:")
    print("-" * 120)
    
    keywords_found = {
        'COMPLIANCE': 0,
        'Gratuity': 0,
        'promotional': 0,
        'quoted': 0,
        'trade': 0,
        'cancelled': 0,
        'bad debt': 0,
        'write off': 0,
        'no show': 0
    }
    
    for ch in charters:
        all_notes = ' '.join([
            str(ch.get('notes') or ''),
            str(ch.get('booking_notes') or ''),
            str(ch.get('client_notes') or '')
        ]).lower()
        
        for keyword in keywords_found.keys():
            if keyword.lower() in all_notes:
                keywords_found[keyword] += 1
    
    for keyword, count in sorted(keywords_found.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  {keyword}: {count}")
    
    # Sample detailed look at different categories
    print("\n" + "=" * 120)
    print("SAMPLE DETAILED RECORDS:")
    print("=" * 120)
    
    # Show a few examples with full details
    categories = {
        'Recent (2024-2025)': [ch for ch in charters if ch['charter_date'] and ch['charter_date'].year >= 2024],
        'Old (2022-2023)': [ch for ch in charters if ch['charter_date'] and 2022 <= ch['charter_date'].year < 2024],
        'COMPLIANCE notes': [ch for ch in charters if ch['notes'] and 'COMPLIANCE' in ch['notes']]
    }
    
    for category, subset in categories.items():
        if subset:
            print(f"\n{category} ({len(subset)} charters):")
            for ch in subset[:3]:  # Show first 3
                print(f"\n  Reserve: {ch['reserve_number']}")
                print(f"  Date: {ch['charter_date']}")
                print(f"  Client: {ch['client_name']}")
                print(f"  Amount Due: ${ch['total_amount_due']:,.2f}")
                print(f"  Rate: ${ch['rate'] or 0:,.2f}")
                print(f"  Status: {ch['status']}")
                print(f"  Booking Status: {ch['booking_status']}")
                print(f"  Payment Status: {ch['payment_status']}")
                print(f"  Closed: {ch['closed']}")
                if ch['notes']:
                    print(f"  Notes: {ch['notes'][:200]}")
                if ch['charges_detail']:
                    print(f"  Charges: {ch['charges_detail']}")
    
    # Export full detailed CSV
    print("\n" + "=" * 120)
    print("EXPORTING FULL DETAILED REPORT...")
    
    with open('reports/unpaid_charters_full_details.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'reserve_number', 'charter_date', 'client_name', 'account_number',
            'total_amount_due', 'rate', 'balance', 'status', 'closed', 
            'booking_status', 'payment_status',
            'pickup_address', 'dropoff_address', 'passenger_count',
            'notes', 'booking_notes', 'client_notes', 'special_requirements',
            'charges_detail'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for ch in charters:
            writer.writerow({
                'reserve_number': ch['reserve_number'],
                'charter_date': ch['charter_date'],
                'client_name': ch['client_name'],
                'account_number': ch['account_number'],
                'total_amount_due': ch['total_amount_due'],
                'rate': ch['rate'],
                'balance': ch['balance'],
                'status': ch['status'],
                'closed': ch['closed'],
                'booking_status': ch['booking_status'],
                'payment_status': ch['payment_status'],
                'pickup_address': ch['pickup_address'],
                'dropoff_address': ch['dropoff_address'],
                'passenger_count': ch['passenger_count'],
                'notes': ch['notes'],
                'booking_notes': ch['booking_notes'],
                'client_notes': ch['client_notes'],
                'special_requirements': ch['special_requirements'],
                'charges_detail': str(ch['charges_detail']) if ch['charges_detail'] else ''
            })
    
    print(f"✓ Full details exported: reports/unpaid_charters_full_details.csv ({len(charters)} rows)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 120)
    print("ANALYSIS COMPLETE")
    print("=" * 120)

if __name__ == '__main__':
    deep_dive()
