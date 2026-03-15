"""
Add missing GL codes that are being used in receipts but don't exist in chart_of_accounts
"""
import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
conn.autocommit = False
cur = conn.cursor()

# GL codes to add based on usage and the assign_gl_codes_to_categories.py mapping
gl_codes_to_add = [
    ('6000', '5000', 'Advertising & Marketing', 'Expense', 'Marketing and advertising expenses', True),
    ('6100', '5000', 'Meals & Entertainment', 'Expense', 'Business meals and entertainment (50% deductible)', True),
    ('6200', '5000', 'Client Hospitality', 'Expense', 'Client beverages and hospitality supplies', True),
    ('6300', '5000', 'Government Fees & Licenses', 'Expense', 'Licenses, permits, registrations, and government fees', True),
    ('6400', '5000', 'General Business Expenses', 'Expense', 'General business and administrative expenses', True),
    ('5750', '5000', 'Utilities', 'Expense', 'Electricity, water, gas, and other utilities', True),
    ('6900', '5000', 'Uncategorized/Unknown', 'Expense', 'Temporary holding account - requires review and reclassification', True),
    ('6950', '5000', 'WCB Premiums', 'Expense', 'Workers Compensation Board premiums', True),
]

print("="*80)
print("ADDING MISSING GL CODES TO CHART_OF_ACCOUNTS")
print("="*80)

try:
    for code, parent, name, acct_type, desc, is_active in gl_codes_to_add:
        # Check if it already exists
        cur.execute("SELECT account_code FROM chart_of_accounts WHERE account_code = %s", (code,))
        exists = cur.fetchone()
        
        if exists:
            print(f"✓ {code} - {name} (already exists)")
        else:
            cur.execute("""
                INSERT INTO chart_of_accounts 
                (account_code, parent_account, account_name, account_type, description, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (code, parent, name, acct_type, desc, is_active))
            print(f"+ {code} - {name} (ADDED)")
    
    conn.commit()
    print("\n✅ All missing GL codes have been added to chart_of_accounts")
    
    # Verify the fix
    print("\n" + "="*80)
    print("VERIFICATION - Checking for remaining invalid GL codes")
    print("="*80)
    
    cur.execute("""
        SELECT COUNT(*) as invalid_count
        FROM receipts r
        LEFT JOIN chart_of_accounts coa ON r.gl_account_code = coa.account_code
        WHERE r.gl_account_code IS NOT NULL 
          AND r.gl_account_code != ''
          AND coa.account_code IS NULL
    """)
    
    remaining_invalid = cur.fetchone()[0]
    
    if remaining_invalid == 0:
        print("\n✅ SUCCESS! All GL codes in receipts now exist in chart_of_accounts")
    else:
        print(f"\n⚠️  {remaining_invalid} receipts still have invalid GL codes")
        
        cur.execute("""
            SELECT DISTINCT r.gl_account_code, COUNT(*) as count
            FROM receipts r
            LEFT JOIN chart_of_accounts coa ON r.gl_account_code = coa.account_code
            WHERE r.gl_account_code IS NOT NULL 
              AND r.gl_account_code != ''
              AND coa.account_code IS NULL
            GROUP BY r.gl_account_code
            ORDER BY COUNT(*) DESC
        """)
        
        print(f"\n{'GL Code':<12} {'Receipt Count':<15}")
        print("-"*30)
        for code, count in cur.fetchall():
            print(f"{code:<12} {count:<15,}")

except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()

print("\n" + "="*80)
