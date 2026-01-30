#!/usr/bin/env python3
"""
Connect to Square API and lookup refund details to find associated order/payment
"""
import psycopg2
from square import Square
from square.client import SquareEnvironment
import os

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

# Square API credentials
SQUARE_ACCESS_TOKEN = "EAAAl0IkBWKAvgZiwfzKfbUxwxaWIbmKgYV0pTmL-5wNdxDZSd6XqnR_9Kq8il22"
client = Square(
    token=SQUARE_ACCESS_TOKEN,
    environment=SquareEnvironment.PRODUCTION
)

conn = get_db_connection()
cur = conn.cursor()

print("="*100)
print("SQUARE API: Lookup Refund Details and Link to Charters")
print("="*100)

# Get unlinked Square refunds
cur.execute("""
    SELECT id, refund_date, amount, square_payment_id, description, reference
    FROM charter_refunds
    WHERE charter_id IS NULL
    AND source_file LIKE 'items-%'
    AND square_payment_id IS NOT NULL
    AND square_payment_id != ''
    ORDER BY amount DESC
""")

refunds = cur.fetchall()
print(f"\nFound {len(refunds)} unlinked Square refunds with payment IDs\n")

linked_count = 0

for refund_id, refund_date, amount, square_payment_id, description, reference in refunds:
    print(f"\n{'='*100}")
    print(f"Refund #{refund_id}: ${amount:,.2f} on {refund_date}")
    print(f"Square Payment ID: {square_payment_id}")
    print(f"Description: {description}")
    
    try:
        # Get payment details from Square
        result = client.payments.get(payment_id=square_payment_id)
        
        if result.errors is None and result.payment:
            payment = result.payment
            
            print(f"\n[OK] Found payment in Square:")
            print(f"  Payment Status: {payment.status}")
            print(f"  Amount: ${payment.amount_money.amount / 100:,.2f}" if payment.amount_money else "N/A")
            print(f"  Created: {payment.created_at}")
            
            # Get customer info
            customer_id = payment.customer_id
            if customer_id:
                customer_result = client.customers.get(customer_id=customer_id)
                if customer_result.errors is None and customer_result.customer:
                    customer = customer_result.customer
                    customer_name = f"{customer.given_name or ''} {customer.family_name or ''}".strip()
                    customer_email = customer.email_address or ''
                    customer_phone = customer.phone_number or ''
                    
                    print(f"  Customer: {customer_name}")
                    print(f"  Email: {customer_email}")
                    print(f"  Phone: {customer_phone}")
                    
                    # Try to find charter by customer name
                    if customer_name:
                        cur.execute("""
                            SELECT c.charter_id, c.reserve_number, c.charter_date, c.rate, cl.client_name
                            FROM charters c
                            LEFT JOIN clients cl ON c.client_id = cl.client_id
                            WHERE (
                                LOWER(cl.client_name) LIKE LOWER(%s)
                                OR LOWER(cl.email) = LOWER(%s)
                            )
                            AND c.charter_date BETWEEN %s::date - INTERVAL '60 days' 
                                                   AND %s::date + INTERVAL '60 days'
                            ORDER BY ABS(c.rate - %s) ASC
                            LIMIT 5
                        """, (f'%{customer_name}%', customer_email, refund_date, refund_date, amount))
                        
                        matches = cur.fetchall()
                        if matches:
                            print(f"\n  Found {len(matches)} potential charter matches:")
                            for charter_id, reserve, charter_date, rate, client_name in matches:
                                print(f"    {reserve}: {charter_date}, ${rate:,.2f} - {client_name}")
                            
                            if len(matches) == 1:
                                charter_id, reserve, charter_date, rate, client_name = matches[0]
                                print(f"\n  [OK] SINGLE MATCH - Linking to charter {reserve}")
                                
                                cur.execute("""
                                    UPDATE charter_refunds
                                    SET charter_id = %s, 
                                        reserve_number = %s,
                                        customer = %s
                                    WHERE id = %s
                                """, (charter_id, reserve, customer_name, refund_id))
                                linked_count += 1
                                print(f"  [OK] Linked!")
            
            # Get order info if available
            order_id = payment.order_id if hasattr(payment, 'order_id') else None
            if order_id:
                print(f"  Order ID: {order_id}")
                
                order_result = client.orders.get(order_id=order_id)
                if order_result.errors is None and order_result.order:
                    order = order_result.order
                    
                    # Check for reference number in order
                    reference_id = order.reference_id if hasattr(order, 'reference_id') else None
                    if reference_id:
                        print(f"  Reference ID: {reference_id}")
                        
                        # Try to extract reserve number from reference
                        import re
                        reserve_match = re.search(r'\b(\d{6})\b', reference_id)
                        if reserve_match:
                            reserve_number = reserve_match.group(1)
                            print(f"  📋 Found reserve number in reference: {reserve_number}")
                            
                            # Find charter
                            cur.execute("""
                                SELECT charter_id FROM charters WHERE reserve_number = %s
                            """, (reserve_number,))
                            
                            charter = cur.fetchone()
                            if charter:
                                charter_id = charter[0]
                                print(f"  [OK] FOUND CHARTER {reserve_number} - Linking!")
                                
                                cur.execute("""
                                    UPDATE charter_refunds
                                    SET charter_id = %s, reserve_number = %s
                                    WHERE id = %s
                                """, (charter_id, reserve_number, refund_id))
                                linked_count += 1
                                print(f"  [OK] Linked!")
            
            # Check receipt notes
            note = payment.note if hasattr(payment, 'note') and payment.note else ''
            if note:
                print(f"  Note: {note}")
                
                # Try to extract reserve number from note
                import re
                reserve_match = re.search(r'\b(\d{6})\b', note)
                if reserve_match:
                    reserve_number = reserve_match.group(1)
                    print(f"  📋 Found reserve number in note: {reserve_number}")
                    
                    cur.execute("""
                        SELECT charter_id FROM charters WHERE reserve_number = %s
                    """, (reserve_number,))
                    
                    charter = cur.fetchone()
                    if charter:
                        charter_id = charter[0]
                        print(f"  [OK] FOUND CHARTER {reserve_number} - Linking!")
                        
                        cur.execute("""
                            UPDATE charter_refunds
                            SET charter_id = %s, reserve_number = %s
                            WHERE id = %s
                        """, (charter_id, reserve_number, refund_id))
                        linked_count += 1
                        print(f"  [OK] Linked!")
        
        else:
            print(f"  [FAIL] Error from Square API: {result.errors}")
    
    except Exception as e:
        print(f"  [FAIL] Exception: {e}")

if linked_count > 0:
    conn.commit()
    print(f"\n\n[OK] COMMITTED: Linked {linked_count} refunds via Square API")

# Final status
cur.execute("""
    SELECT COUNT(*) 
    FROM charter_refunds 
    WHERE charter_id IS NULL 
    AND source_file LIKE 'items-%'
""")
remaining = cur.fetchone()[0]

print("\n" + "="*100)
print("FINAL RESULTS")
print("="*100)
print(f"Square refunds still unlinked: {remaining}")
print(f"Successfully linked via Square API: {linked_count}")

cur.close()
conn.close()
