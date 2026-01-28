import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("FIXING CHARTER 17061 NOTES - Remove write-off, mark as PAID IN FULL:\n")
print("=" * 100)

# Get current charter state
cur.execute("""
    SELECT charter_id, reserve_number, total_amount_due, paid_amount, status, notes
    FROM charters
    WHERE charter_id = 17061
""")

charter = cur.fetchone()
if charter:
    cid, reserve, total, paid, status, old_notes = charter
    
    print("CURRENT STATE:")
    print(f"  Charter: {cid} | Reserve: {reserve}")
    print(f"  Total: ${total:.2f} | Paid: ${paid:.2f}")
    print(f"  Status: {status}")
    print(f"  Old Notes: {old_notes}\n")
    
    # Build new notes
    new_notes = f"[{datetime.now().strftime('%Y-%m-%d')} CORRECTION] Payment verified: E-transfer $630.00 received Oct 10, 2023. Charter PAID IN FULL and CLOSED. Previous write-off marking was in error."
    
    print("NEW NOTES:")
    print(f"  {new_notes}\n")
    
    # Update the charter
    cur.execute("""
        UPDATE charters
        SET notes = %s,
            status = 'Closed',
            updated_at = NOW()
        WHERE charter_id = 17061
    """, (new_notes,))
    
    conn.commit()
    
    # Verify the update
    cur.execute("""
        SELECT charter_id, reserve_number, total_amount_due, paid_amount, status, notes
        FROM charters
        WHERE charter_id = 17061
    """)
    
    updated = cur.fetchone()
    if updated:
        cid, reserve, total, paid, status, notes = updated
        print("✅ UPDATED STATE:")
        print(f"  Charter: {cid} | Reserve: {reserve}")
        print(f"  Total: ${total:.2f} | Paid: ${paid:.2f}")
        print(f"  Status: {status}")
        print(f"  New Notes: {notes}\n")
        
        print("=" * 100)
        print("✅ CHARTER FIXED!")
        print("   - Removed incorrect write-off notation")
        print("   - Marked as PAID IN FULL")
        print("   - Status updated to 'Closed'")
        print("   - Added correction note with payment verification")

cur.close()
conn.close()
