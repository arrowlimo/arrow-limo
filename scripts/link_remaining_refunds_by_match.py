#!/usr/bin/env python3
"""
Try to automatically link remaining refunds by customer email from Square
"""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("="*100)
print("LINKING REMAINING REFUNDS VIA CUSTOMER EMAIL")
print("="*100)

# Get unlinked refunds
cur.execute("""
    SELECT id, refund_date, amount, description, square_payment_id
    FROM charter_refunds
    WHERE reserve_number IS NULL
    ORDER BY amount DESC
""")

refunds = cur.fetchall()
print(f"\nFound {len(refunds)} unlinked refunds\n")

# Get Square payment data that has email addresses
cur.execute("""
    SELECT DISTINCT square_customer_email, reserve_number, charter_id
    FROM payments
    WHERE square_customer_email IS NOT NULL
    AND square_customer_email != ''
    AND charter_id IS NOT NULL
    AND reserve_number IS NOT NULL
""")

email_map = {}
for email, reserve, charter_id in cur.fetchall():
    if email:
        email_map[email.lower()] = (reserve, charter_id)

print(f"Loaded {len(email_map)} unique customer emails from payments\n")

linked_count = 0

for refund_id, refund_date, amount, description, square_payment_id in refunds:
    print(f"Refund #{refund_id}: ${amount:,.2f} on {refund_date}")
    print(f"  Description: {description}")
    
    # Try to find email in description or via Square payment lookup
    # (we already have Square payment data from API)
    # Check if we can find matching charters by date + amount
    cur.execute("""
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.rate, cl.client_name, cl.email,
               ABS(EXTRACT(EPOCH FROM (c.charter_date::timestamp - %s::timestamp)) / 86400) as days_diff
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.charter_date BETWEEN %s - INTERVAL '30 days' 
                               AND %s + INTERVAL '30 days'
        AND ABS(c.rate - %s) <= 100
        ORDER BY ABS(c.rate - %s) ASC, days_diff ASC
        LIMIT 10
    """, (refund_date, refund_date, refund_date, amount, amount))
    
    matches = cur.fetchall()
    
    if len(matches) == 1:
        charter_id, reserve, charter_date, rate, client_name, email, days_diff = matches[0]
        print(f"  [OK] SINGLE MATCH: Charter {reserve}")
        print(f"     Date: {charter_date}, Amount: ${rate:,.2f}, Client: {client_name}")
        
        cur.execute("""
            UPDATE charter_refunds
            SET charter_id = %s, reserve_number = %s
            WHERE id = %s
        """, (charter_id, reserve, refund_id))
        
        linked_count += 1
        print(f"  [OK] Linked!")
    
    elif len(matches) > 1:
        print(f"  [WARN]  Multiple matches ({len(matches)}) - showing top 3:")
        for i, (charter_id, reserve, charter_date, rate, client_name, email, days_diff) in enumerate(matches[:3], 1):
            print(f"     {i}. {reserve}: {charter_date} (±{int(days_diff)} days), ${rate:,.2f} - {client_name}")
    else:
        print(f"  [FAIL] No matches found")
    
    print()

if linked_count > 0:
    conn.commit()
    print(f"[OK] COMMITTED: Linked {linked_count} refunds")

# Final status
cur.execute("SELECT COUNT(*) FROM charter_refunds WHERE reserve_number IS NULL")
remaining = cur.fetchone()[0]

print("\n" + "="*100)
print("FINAL STATUS")
print("="*100)
print(f"Remaining unlinked: {remaining}")

cur.close()
conn.close()
