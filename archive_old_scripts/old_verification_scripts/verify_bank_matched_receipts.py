#!/usr/bin/env python3
"""Mark receipts as verified if they have banking match - using existing field."""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    user='postgres',
    password='ArrowLimousine',
    dbname='almsdata'
)
cur = conn.cursor()

print("\n" + "="*100)
print("MARK BANK-MATCHED RECEIPTS AS VERIFIED")
print("="*100)

# Check current status
print("\n1. Current Status")
print("-"*100)

cur.execute("""
    SELECT 
        COUNT(*) as total_receipts,
        SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 ELSE 0 END) as bank_matched,
        SUM(CASE WHEN is_verified_banking = TRUE THEN 1 ELSE 0 END) as verified_banking,
        SUM(CASE WHEN banking_transaction_id IS NOT NULL AND (is_verified_banking IS NULL OR is_verified_banking = FALSE) THEN 1 ELSE 0 END) as need_verify
    FROM receipts
""")

total, bank_matched, verified, need_verify = cur.fetchone()

print(f"Total receipts: {total:,}")
print(f"Bank-matched receipts: {bank_matched:,}")
print(f"Already verified (is_verified_banking): {verified:,}")
print(f"Need to verify: {need_verify:,}")

# Update
if need_verify > 0:
    print(f"\n2. Marking {need_verify:,} bank-matched receipts as verified...")
    print("-"*100)
    
    cur.execute("""
        UPDATE receipts
        SET is_verified_banking = TRUE,
            verified_source = 'Banking Transaction Match',
            verified_at = CURRENT_TIMESTAMP
        WHERE banking_transaction_id IS NOT NULL
        AND (is_verified_banking IS NULL OR is_verified_banking = FALSE)
    """)
    
    updated = cur.rowcount
    conn.commit()
    print(f"✓ Updated {updated:,} receipts")
    
    # Show final status
    print("\n3. Final Status")
    print("-"*100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as verified_count,
            SUM(gross_amount) as verified_amount
        FROM receipts
        WHERE is_verified_banking = TRUE
    """)
    
    verified_count, verified_amount = cur.fetchone()
    print(f"Total verified receipts: {verified_count:,}")
    print(f"Total verified amount: ${verified_amount:,.2f}" if verified_amount else "Total verified amount: $0.00")
    
    # Show by GL code
    print("\n4. Verified Receipts by GL Code (Top 20)")
    print("-"*100)
    
    cur.execute("""
        SELECT 
            gl_account_code,
            gl_account_name,
            COUNT(*) as count,
            SUM(gross_amount) as amount
        FROM receipts
        WHERE is_verified_banking = TRUE
        GROUP BY gl_account_code, gl_account_name
        ORDER BY count DESC
        LIMIT 20
    """)
    
    print(f"{'GL Code':<10} {'GL Name':<45} {'Count':<10} {'Amount'}")
    print("-"*100)
    
    for gl_code, gl_name, count, amount in cur.fetchall():
        gl_name_display = (gl_name or "NO NAME")[:45]
        amount_str = f"${amount:,.2f}" if amount else "$0.00"
        print(f"{gl_code or 'NONE':<10} {gl_name_display:<45} {count:<10} {amount_str}")
    
else:
    print("\n✓ All bank-matched receipts are already verified")

print("\n" + "="*100)
print("COMPLETE")
print("="*100)
print(f"""
✓ {bank_matched:,} receipts matched to banking transactions
✓ All marked as verified (is_verified_banking = TRUE)
✓ Bank verification confirms these transactions cleared the bank
✓ ${verified_amount:,.2f} in verified banking transactions
""")

conn.close()
