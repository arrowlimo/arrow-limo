import psycopg2
from datetime import date

conn = psycopg2.connect(host='localhost', user='postgres', password='ArrowLimousine', dbname='almsdata')
cur = conn.cursor()

print("\n" + "="*80)
print("CREATE MONEY MART PREPAID VISA CARD LOADS - Sept 12, 2012")
print("="*80 + "\n")

# Step 1: Check if GL 1135 exists, create if not
print("Step 1: Checking GL 1135 (Prepaid Visa Cards)...")
cur.execute("SELECT account_code, account_name, is_active FROM chart_of_accounts WHERE account_code = '1135'")
gl_1135 = cur.fetchone()

if gl_1135:
    print(f"✓ GL 1135 already exists: {gl_1135[1]}")
    print(f"  Active: {gl_1135[2]}")
else:
    print("✗ GL 1135 does not exist - creating it now...")
    cur.execute("""
        INSERT INTO chart_of_accounts 
        (account_code, account_name, account_type, parent_account, is_active, is_system)
        VALUES ('1135', 'Prepaid Visa Cards', 'Asset', '1100', TRUE, FALSE)
    """)
    print("✓ Created GL 1135 - Prepaid Visa Cards")

# Step 2: Check for existing Money Mart transactions on 09/12/2012
print("\nStep 2: Checking for existing Money Mart transactions on 09/12/2012...")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, gl_account_code, 
           payment_method, description
    FROM receipts
    WHERE vendor_name ILIKE '%money%mart%'
    AND receipt_date = '2012-09-12'
    ORDER BY gross_amount DESC
""")

existing = cur.fetchall()

if existing:
    print(f"Found {len(existing)} existing Money Mart transaction(s) on 09/12/2012:")
    for rec in existing:
        print(f"  Receipt {rec[0]}: ${rec[3]:,.2f} - Currently coded to GL {rec[4] or 'NONE'}")
    
    # Update them to GL 1135
    print("\nUpdating existing transactions to GL 1135...")
    for rec in existing:
        cur.execute("""
            UPDATE receipts 
            SET gl_account_code = '1135',
                gl_account_name = 'Prepaid Visa Cards',
                description = COALESCE(description || ' - ', '') || 'Prepaid Visa card load (asset transfer)'
            WHERE receipt_id = %s
        """, (rec[0],))
        print(f"✓ Updated Receipt {rec[0]} (${rec[3]:,.2f}) to GL 1135")
else:
    print("No existing Money Mart transactions found on 09/12/2012")
    print("\nStep 3: Creating two new prepaid Visa card load transactions...")
    
    # Create first transaction: $900
    cur.execute("""
        INSERT INTO receipts 
        (receipt_date, vendor_name, gross_amount, gl_account_code, gl_account_name,
         payment_method, description, receipt_category)
        VALUES 
        ('2012-09-12', 'Money Mart', 900.00, '1135', 'Prepaid Visa Cards',
         'Cash', 'Prepaid Visa card load #1 - $900 (asset transfer)', 'Banking')
        RETURNING receipt_id
    """)
    receipt_id_1 = cur.fetchone()[0]
    print(f"✓ Created Receipt {receipt_id_1}: $900.00 - Money Mart prepaid Visa load")
    
    # Create second transaction: $750
    cur.execute("""
        INSERT INTO receipts 
        (receipt_date, vendor_name, gross_amount, gl_account_code, gl_account_name,
         payment_method, description, receipt_category)
        VALUES 
        ('2012-09-12', 'Money Mart', 750.00, '1135', 'Prepaid Visa Cards',
         'Cash', 'Prepaid Visa card load #2 - $750 (asset transfer)', 'Banking')
        RETURNING receipt_id
    """)
    receipt_id_2 = cur.fetchone()[0]
    print(f"✓ Created Receipt {receipt_id_2}: $750.00 - Money Mart prepaid Visa load")

conn.commit()

# Step 4: Verify the result
print("\n" + "="*80)
print("VERIFICATION")
print("="*80)

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
           gl_account_code, gl_account_name, description
    FROM receipts
    WHERE vendor_name ILIKE '%money%mart%'
    AND receipt_date = '2012-09-12'
    ORDER BY gross_amount DESC
""")

final = cur.fetchall()

print(f"\nMoney Mart transactions on 09/12/2012: {len(final)}")
total_loaded = sum(r[3] for r in final)

for rec in final:
    print(f"\nReceipt ID: {rec[0]}")
    print(f"Date: {rec[1]}")
    print(f"Vendor: {rec[2]}")
    print(f"Amount: ${rec[3]:,.2f}")
    print(f"GL Code: {rec[4]} - {rec[5]}")
    print(f"Description: {rec[6]}")

print(f"\n{'='*80}")
print(f"TOTAL PREPAID VISA CARD LOADS: ${total_loaded:,.2f}")
print(f"{'='*80}")

print("""
ACCOUNTING TREATMENT:
────────────────────────────
Journal Entry for prepaid card loads:
  Debit:  GL 1135 Prepaid Visa Cards (Asset ↑)    $1,650.00
  Credit: GL 1010 Cash & Bank Accounts (Asset ↓)  $1,650.00

Effect: No impact on Profit & Loss - this is an asset transfer.
The expense will be recorded later when money is spent from the prepaid card.
""")

conn.close()

print("\n✓ All changes committed to database")
print("="*80 + "\n")
