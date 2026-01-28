"""
Deep dive into the 4 "needs review" duplicate groups.
Payment IDs: 26758/26759, 26170/26171, 26955/26956, 27906/27907
"""

import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)

# IDs to investigate
review_groups = [
    ([26758, 26759], "2016-01-14", 150.00),
    ([26170, 26171], "2016-10-11", 150.00),
    ([26955, 26956], "2017-10-26", 415.42),
    ([27906, 27907], "2018-07-20", 205.89)
]

print("="*80)
print("DETAILED INVESTIGATION: 4 'NEEDS REVIEW' GROUPS")
print("="*80)

for payment_ids, date, amount in review_groups:
    print(f"\nGroup: {date} ${amount:.2f} - Payment IDs: {payment_ids}")
    print("-" * 60)
    
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_method,
            reserve_number,
            charter_id,
            client_id,
            notes,
            square_transaction_id,
            square_payment_id,
            created_at,
            last_updated
        FROM payments
        WHERE payment_id = ANY(%s)
        ORDER BY payment_id
    """, (payment_ids,))
    
    payments = cur.fetchall()
    
    for p in payments:
        print(f"\n  Payment {p['payment_id']}:")
        print(f"    Date: {p['payment_date']}")
        print(f"    Amount: ${p['amount']:.2f}")
        print(f"    Method: {p['payment_method']}")
        print(f"    Reserve #: {p['reserve_number']}")
        print(f"    Charter ID: {p['charter_id']}")
        print(f"    Client ID: {p['client_id']}")
        print(f"    Square Txn ID: {p['square_transaction_id']}")
        print(f"    Square Pay ID: {p['square_payment_id']}")
        print(f"    Created: {p['created_at']}")
        print(f"    Updated: {p['last_updated']}")
        print(f"    Notes: {p['notes'][:200] if p['notes'] else 'None'}...")
    
    # Check if linked to charters
    charter_ids = [p['charter_id'] for p in payments if p['charter_id']]
    if charter_ids:
        cur.execute("""
            SELECT 
                charter_id,
                reserve_number,
                client_id,
                charter_date,
                total_amount_due,
                paid_amount,
                balance,
                status,
                cancelled
            FROM charters
            WHERE charter_id = ANY(%s)
        """, (charter_ids,))
        
        charters = cur.fetchall()
        
        print(f"\n  Linked Charters:")
        for c in charters:
            print(f"    Charter {c['charter_id']} (Reserve: {c['reserve_number']})")
            print(f"      Date: {c['charter_date']}, Total: ${c['total_amount_due']:.2f}, Paid: ${c['paid_amount']:.2f}")
            print(f"      Status: {c['status']}, Cancelled: {c['cancelled']}")
    
    # Check Square transaction details if exists
    square_ids = [p['square_transaction_id'] for p in payments if p['square_transaction_id']]
    if square_ids:
        print(f"\n  Square Transaction Analysis:")
        print(f"    Unique Square IDs: {len(set(square_ids))}")
        if len(set(square_ids)) == 1:
            print(f"    ⚠️ SAME Square transaction used for multiple payments!")
        else:
            print(f"    ✅ Different Square transactions")
    
    # Check if notes indicate refund or correction
    notes_text = ' '.join([p['notes'] or '' for p in payments])
    if 'refund' in notes_text.lower():
        print(f"\n  ⚠️ Contains 'refund' in notes")
    if 'correction' in notes_text.lower():
        print(f"\n  ⚠️ Contains 'correction' in notes")
    
    # Determine likely classification
    print(f"\n  ANALYSIS:")
    if not any(p['reserve_number'] for p in payments):
        print(f"    • No reserve numbers = unlinked to charters")
    if not any(p['charter_id'] for p in payments):
        print(f"    • No charter IDs = not linked to charters")
    if len(set(p['square_transaction_id'] for p in payments if p['square_transaction_id'])) == 1:
        print(f"    • Same Square ID = likely TRUE DUPLICATE")
    if all(p['payment_method'] == 'cash' for p in payments):
        print(f"    • Both marked as 'cash'")
    
    print()

print("="*80)
print("RECOMMENDATIONS")
print("="*80)
print("""
1. Groups 26758/26759, 26170/26171:
   - Both cash payments, no reserve numbers, no charter links
   - Likely manual entry duplicates or uncategorized payments
   - ACTION: Review source documents, mark one as duplicate if confirmed

2. Group 26955/26956:
   - One has 'Square refund transaction' note
   - Different purposes: original payment + refund
   - ACTION: Verify refund is properly linked, no action needed if legitimate

3. Group 27906/27907:
   - One has 'Square refund transaction' note
   - Different purposes: original payment + refund
   - ACTION: Verify refund is properly linked, no action needed if legitimate
""")

cur.close()
conn.close()
