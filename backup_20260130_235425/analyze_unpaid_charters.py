"""
Analyze charters with charges but no payments.
Identify reasons: promotional, trade, cancelled, quoted, etc.
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
        password='***REDACTED***'
    )

def analyze_unpaid_charters():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 100)
    print("ANALYZING CHARTERS WITH CHARGES BUT NO PAYMENTS")
    print("=" * 100)
    
    # Get charters with charges but no payments
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.account_number,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status,
            c.cancelled,
            c.closed,
            c.booking_status,
            c.payment_status,
            c.notes,
            c.booking_notes,
            c.client_notes,
            cl.client_name as client_name,
            -- Check for payments
            (SELECT COUNT(*) FROM payments p 
             WHERE p.reserve_number = c.reserve_number 
                OR p.charter_id = c.charter_id) as payment_count,
            -- Check for charges
            (SELECT SUM(amount) FROM charter_charges cc 
             WHERE cc.charter_id = c.charter_id) as total_charges,
            (SELECT COUNT(*) FROM charter_charges cc 
             WHERE cc.charter_id = c.charter_id) as charge_count
        FROM charters c
        LEFT JOIN clients cl ON c.account_number = cl.client_id::text
        WHERE c.total_amount_due > 0  -- Has charges
          AND (c.paid_amount IS NULL OR c.paid_amount = 0)  -- No payments recorded
          AND c.cancelled = FALSE  -- Not cancelled
        ORDER BY c.charter_date DESC, c.reserve_number DESC
    """)
    
    unpaid_charters = cur.fetchall()
    
    print(f"\nTotal charters with charges but no payments (not cancelled): {len(unpaid_charters)}")
    print(f"Total amount unpaid: ${sum(ch['total_amount_due'] or 0 for ch in unpaid_charters):,.2f}\n")
    
    # Categorize by reason
    categories = {
        'promotional': [],
        'trade': [],
        'quoted': [],
        'cancelled': [],
        'bad_debt': [],
        'pending': [],
        'unknown': []
    }
    
    keywords = {
        'promotional': ['promo', 'promotional', 'complimentary', 'comp', 'free', 'donated', 'donation'],
        'trade': ['trade', 'barter', 'exchange', 'fibrenew'],
        'quoted': ['quote', 'quoted', 'estimate', 'proposal'],
        'cancelled': ['cancel', 'cancelled', 'canceled', 'no show', 'noshow'],
        'bad_debt': ['bad debt', 'write off', 'writeoff', 'uncollectable', 'uncollectible', 'collection']
    }
    
    for charter in unpaid_charters:
        # Combine all text fields for searching
        search_text = ' '.join([
            str(charter.get('notes') or ''),
            str(charter.get('booking_notes') or ''),
            str(charter.get('client_notes') or ''),
            str(charter.get('status') or ''),
            str(charter.get('booking_status') or ''),
            str(charter.get('payment_status') or '')
        ]).lower()
        
        categorized = False
        
        # Check each category
        for category, terms in keywords.items():
            if any(term in search_text for term in terms):
                categories[category].append(charter)
                categorized = True
                break
        
        # Check status fields
        if not categorized:
            if charter.get('cancelled'):
                categories['cancelled'].append(charter)
                categorized = True
            elif charter.get('booking_status') and 'quot' in charter['booking_status'].lower():
                categories['quoted'].append(charter)
                categorized = True
        
        if not categorized:
            # Check if recent (pending payment)
            charter_date = charter.get('charter_date')
            if charter_date and isinstance(charter_date, str):
                charter_date = datetime.strptime(charter_date[:10], '%Y-%m-%d').date()
            
            if charter_date and (datetime.now().date() - charter_date).days < 90:
                categories['pending'].append(charter)
            else:
                categories['unknown'].append(charter)
    
    # Print category summaries
    print("\nCATEGORY BREAKDOWN:")
    print("-" * 100)
    for category, charters in categories.items():
        if charters:
            total = sum(ch['total_amount_due'] or 0 for ch in charters)
            print(f"\n{category.upper()}: {len(charters)} charters, ${total:,.2f}")
            print("  Sample charters:")
            for ch in charters[:5]:  # Show first 5
                date_str = str(ch['charter_date'])[:10] if ch['charter_date'] else 'N/A'
                print(f"    {ch['reserve_number']}: ${ch['total_amount_due']:,.2f} - {date_str} - {ch['client_name']}")
                # Show reason
                notes_text = ' | '.join([
                    str(ch.get('notes') or ''),
                    str(ch.get('booking_notes') or ''),
                    str(ch.get('status') or '')
                ])[:100]
                if notes_text.strip():
                    print(f"      → {notes_text}")
    
    # Export detailed CSV
    print("\n" + "=" * 100)
    print("EXPORTING DETAILED REPORT...")
    
    with open('reports/unpaid_charters_analysis.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'reserve_number', 'charter_date', 'client_name', 'account_number',
            'total_amount_due', 'status', 'cancelled', 'booking_status', 'payment_status',
            'category', 'notes', 'booking_notes', 'client_notes'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for category, charters in categories.items():
            for charter in charters:
                writer.writerow({
                    'reserve_number': charter['reserve_number'],
                    'charter_date': charter['charter_date'],
                    'client_name': charter['client_name'],
                    'account_number': charter['account_number'],
                    'total_amount_due': charter['total_amount_due'],
                    'status': charter['status'],
                    'cancelled': charter['cancelled'],
                    'booking_status': charter['booking_status'],
                    'payment_status': charter['payment_status'],
                    'category': category,
                    'notes': charter['notes'],
                    'booking_notes': charter['booking_notes'],
                    'client_notes': charter['client_notes']
                })
    
    print(f"✓ Detailed report exported: reports/unpaid_charters_analysis.csv ({len(unpaid_charters)} rows)")
    
    # Now check cancelled charters separately
    print("\n" + "=" * 100)
    print("CHECKING CANCELLED CHARTERS WITH CHARGES...")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            cl.client_name,
            c.total_amount_due,
            c.paid_amount,
            c.status,
            c.cancelled,
            c.notes
        FROM charters c
        LEFT JOIN clients cl ON c.account_number = cl.client_id::text
        WHERE c.total_amount_due > 0
          AND (c.paid_amount IS NULL OR c.paid_amount = 0)
          AND c.cancelled = TRUE
        ORDER BY c.charter_date DESC
    """)
    
    cancelled_unpaid = cur.fetchall()
    
    print(f"\nCancelled charters with unpaid charges: {len(cancelled_unpaid)}")
    if cancelled_unpaid:
        total = sum(ch['total_amount_due'] or 0 for ch in cancelled_unpaid)
        print(f"Total amount: ${total:,.2f}")
        print("\nSample (first 10):")
        for ch in cancelled_unpaid[:10]:
            date_str = str(ch['charter_date'])[:10] if ch['charter_date'] else 'N/A'
            print(f"  {ch['reserve_number']}: ${ch['total_amount_due']:,.2f} - {date_str} - {ch['client_name']}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)

if __name__ == '__main__':
    analyze_unpaid_charters()
