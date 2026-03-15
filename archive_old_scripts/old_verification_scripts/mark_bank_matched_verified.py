#!/usr/bin/env python3
"""Mark receipts as verified if they have a direct banking match."""

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

# 1. Check receipts table for verification fields
print("\n1. Checking receipts table structure for verification fields...")
print("-"*100)

cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    AND (
        column_name LIKE '%verif%' 
        OR column_name LIKE '%confirm%'
        OR column_name LIKE '%bank%match%'
        OR column_name LIKE '%reconcil%'
    )
    ORDER BY column_name
""")

verify_cols = cur.fetchall()
if verify_cols:
    print("Verification-related columns found:")
    for col in verify_cols:
        print(f"  - {col[0]}")
else:
    print("No verification columns found. Will check for banking_transaction_id linkage.")

# 2. Count receipts with banking matches
print("\n2. Receipts with Banking Transaction Matches")
print("-"*100)

cur.execute("""
    SELECT 
        COUNT(*) as total_matched,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE banking_transaction_id IS NOT NULL
""")

matched_count, matched_amount = cur.fetchone()
print(f"Receipts linked to banking transactions: {matched_count:,}")
print(f"Total amount: ${matched_amount:,.2f}" if matched_amount else "Total amount: $0.00")

# 3. Check if we have a verification status field
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    AND column_name IN ('verified', 'is_verified', 'bank_verified', 'verification_status')
""")

verify_field = cur.fetchone()

if verify_field:
    verify_column = verify_field[0]
    print(f"\nFound verification column: {verify_column}")
    
    # Check current verification status
    cur.execute(f"""
        SELECT 
            COUNT(*) as already_verified
        FROM receipts
        WHERE banking_transaction_id IS NOT NULL
        AND {verify_column} = TRUE
    """)
    
    already_verified = cur.fetchone()[0]
    print(f"Already verified: {already_verified:,}")
    print(f"Need to verify: {matched_count - already_verified:,}")
    
    # Update unverified bank-matched receipts
    if matched_count - already_verified > 0:
        print(f"\n3. Marking {matched_count - already_verified:,} bank-matched receipts as verified...")
        print("-"*100)
        
        cur.execute(f"""
            UPDATE receipts
            SET {verify_column} = TRUE
            WHERE banking_transaction_id IS NOT NULL
            AND ({verify_column} IS NULL OR {verify_column} = FALSE)
        """)
        
        updated = cur.rowcount
        conn.commit()
        print(f"✓ Updated {updated:,} receipts to verified status")
        
        # Show summary
        cur.execute(f"""
            SELECT 
                COUNT(*) as verified_count,
                SUM(gross_amount) as verified_amount
            FROM receipts
            WHERE {verify_column} = TRUE
        """)
        
        verified_count, verified_amount = cur.fetchone()
        print(f"\nTotal verified receipts: {verified_count:,}")
        print(f"Total verified amount: ${verified_amount:,.2f}" if verified_amount else "Total verified amount: $0.00")
    else:
        print("\n✓ All bank-matched receipts are already verified")

else:
    # No verification column exists, create one
    print("\n3. Creating verification column...")
    print("-"*100)
    
    cur.execute("""
        ALTER TABLE receipts 
        ADD COLUMN IF NOT EXISTS bank_verified BOOLEAN DEFAULT FALSE
    """)
    
    cur.execute("""
        COMMENT ON COLUMN receipts.bank_verified IS 
        'TRUE if receipt has been matched to a banking transaction and verified'
    """)
    
    conn.commit()
    print("✓ Added 'bank_verified' column to receipts table")
    
    # Now mark bank-matched receipts as verified
    print(f"\n4. Marking {matched_count:,} bank-matched receipts as verified...")
    print("-"*100)
    
    cur.execute("""
        UPDATE receipts
        SET bank_verified = TRUE
        WHERE banking_transaction_id IS NOT NULL
    """)
    
    updated = cur.rowcount
    conn.commit()
    print(f"✓ Updated {updated:,} receipts to verified status")
    
    # Show summary
    cur.execute("""
        SELECT 
            COUNT(*) as verified_count,
            SUM(gross_amount) as verified_amount
        FROM receipts
        WHERE bank_verified = TRUE
    """)
    
    verified_count, verified_amount = cur.fetchone()
    print(f"\nTotal verified receipts: {verified_count:,}")
    print(f"Total verified amount: ${verified_amount:,.2f}" if verified_amount else "Total verified amount: $0.00")

# 4. Show breakdown by GL code
print("\n" + "="*100)
print("VERIFIED RECEIPTS BY GL CODE (Top 20)")
print("="*100)

verify_col = verify_field[0] if verify_field else 'bank_verified'

cur.execute(f"""
    SELECT 
        gl_account_code,
        gl_account_name,
        COUNT(*) as verified_count,
        SUM(gross_amount) as verified_amount
    FROM receipts
    WHERE {verify_col} = TRUE
    GROUP BY gl_account_code, gl_account_name
    ORDER BY verified_count DESC
    LIMIT 20
""")

print(f"{'GL Code':<10} {'GL Name':<45} {'Count':<10} {'Amount'}")
print("-"*100)

for gl_code, gl_name, count, amount in cur.fetchall():
    gl_name_display = (gl_name or "NO NAME")[:45]
    amount_str = f"${amount:,.2f}" if amount else "$0.00"
    print(f"{gl_code or 'NONE':<10} {gl_name_display:<45} {count:<10} {amount_str}")

print("\n" + "="*100)
print("SUMMARY")
print("="*100)
print("""
✓ Receipts matched to banking transactions are now marked as VERIFIED
✓ Bank verification confirms these transactions cleared the bank
✓ Verified receipts have higher confidence for accounting accuracy

This helps distinguish between:
- Verified (bank-matched) receipts -> Confirmed by bank statements
- Unverified receipts -> Manual entry, no bank confirmation yet
""")

conn.close()
