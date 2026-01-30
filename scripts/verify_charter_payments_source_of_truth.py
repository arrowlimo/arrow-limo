#!/usr/bin/env python
"""
Verify: Is charter_payments the actual source of truth, not payments table?
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
    print("ANALYZING PAYMENTS vs CHARTER_PAYMENTS RELATIONSHIP")
    print("=" * 100)
    
    # Check how many payments have NULL amounts
    print("\n1. PAYMENTS TABLE AMOUNT ANALYSIS:")
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(payment_amount) as non_null_amount,
            SUM(CASE WHEN payment_amount IS NULL THEN 1 ELSE 0 END) as null_amount,
            SUM(CASE WHEN payment_amount = 0 THEN 1 ELSE 0 END) as zero_amount,
            SUM(CASE WHEN payment_amount > 0 THEN 1 ELSE 0 END) as positive_amount,
            COALESCE(SUM(payment_amount), 0) as total_amount
        FROM payments
    """)
    row = cur.fetchone()
    print(f"   Total records: {row[0]:,}")
    print(f"   Non-NULL amounts: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
    print(f"   NULL amounts: {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
    print(f"   Zero amounts: {row[3]:,}")
    print(f"   Positive amounts: {row[4]:,}")
    print(f"   Total amount: ${row[5]:,.2f}")
    
    # Check charter-linked payments specifically
    print("\n2. CHARTER-LINKED PAYMENTS (charter_id IS NOT NULL):")
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(payment_amount) as non_null_amount,
            SUM(CASE WHEN payment_amount IS NULL THEN 1 ELSE 0 END) as null_amount,
            SUM(CASE WHEN payment_amount > 0 THEN 1 ELSE 0 END) as positive_amount,
            COALESCE(SUM(payment_amount), 0) as total_amount
        FROM payments
        WHERE reserve_number IS NOT NULL
    """)
    row = cur.fetchone()
    print(f"   Total records: {row[0]:,}")
    print(f"   Non-NULL amounts: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
    print(f"   NULL amounts: {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
    print(f"   Positive amounts: {row[3]:,}")
    print(f"   Total amount: ${row[4]:,.2f}")
    
    # Check charter_payments coverage
    print("\n3. CHARTER_PAYMENTS TABLE:")
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT charter_id) as distinct_charters,
            COALESCE(SUM(amount), 0) as total_amount
        FROM charter_payments
    """)
    row = cur.fetchone()
    print(f"   Total records: {row[0]:,}")
    print(f"   Distinct charters: {row[1]:,}")
    print(f"   Total amount: ${row[2]:,.2f}")
    
    # Check overlap: how many charter_payments payment_ids exist in payments table?
    print("\n4. CHARTER_PAYMENTS ↔ PAYMENTS LINKAGE:")
    cur.execute("""
        SELECT 
            COUNT(*) as charter_payments_count,
            COUNT(DISTINCT cp.payment_id) as distinct_payment_ids,
            SUM(CASE WHEN p.payment_id IS NOT NULL THEN 1 ELSE 0 END) as linked_to_payments,
            SUM(CASE WHEN p.payment_id IS NULL THEN 1 ELSE 0 END) as not_linked_to_payments
        FROM charter_payments cp
        LEFT JOIN payments p ON cp.payment_id = p.payment_id
    """)
    row = cur.fetchone()
    print(f"   charter_payments records: {row[0]:,}")
    print(f"   Distinct payment_ids: {row[1]:,}")
    print(f"   Linked to payments table: {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
    print(f"   NOT linked to payments: {row[3]:,} ({row[3]/row[0]*100:.1f}%)")
    
    # Check: For charter_payments linked to payments, what are the amounts?
    print("\n5. AMOUNT COMPARISON (charter_payments vs payments where linked):")
    cur.execute("""
        SELECT 
            COUNT(*) as linked_count,
            SUM(CASE WHEN p.payment_amount IS NOT NULL THEN 1 ELSE 0 END) as payments_has_amount,
            SUM(CASE WHEN p.payment_amount IS NULL THEN 1 ELSE 0 END) as payments_null_amount,
            SUM(CASE WHEN cp.amount = p.payment_amount THEN 1 ELSE 0 END) as amounts_match,
            SUM(CASE WHEN cp.amount != COALESCE(p.payment_amount, 0) AND p.payment_amount IS NOT NULL THEN 1 ELSE 0 END) as amounts_differ
        FROM charter_payments cp
        INNER JOIN payments p ON cp.payment_id = p.payment_id
    """)
    row = cur.fetchone()
    print(f"   Linked records: {row[0]:,}")
    print(f"   Payments has amount: {row[1]:,}")
    print(f"   Payments has NULL amount: {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
    print(f"   Amounts match exactly: {row[3]:,}")
    print(f"   Amounts differ: {row[4]:,}")
    
    # Conclusion
    print("\n" + "="*100)
    print("CONCLUSION:")
    print("="*100)
    
    if row[2] > row[1]:  # More NULL than non-NULL
        print("\n✓ charter_payments is the SOURCE OF TRUTH for payment amounts")
        print("✓ payments table is a reference/metadata table (mostly NULL amounts)")
        print("✓ Strategy should be: Sync charter.paid_amount FROM charter_payments")
        print("\n⚠ MIGRATION IS NOT NEEDED - charter_payments already has the data!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
