"""
Final cleanup for remaining vendors:
- DRAFT PURCHASE/DEBIT VIA DRAFT → GL 6900 (Unknown bill payment)
- BILL PAYMENT → GL 6900 (Unknown bill payment)
- BUSINESS EXPENSE → GL 6900 (Unknown)
- CREDIT MEMO → GL 1010 (Bank Deposit)
- LFG BUSINESS PAD → GL 6900 (Unknown pre-authorized debit)
- DCARD DEPOSIT → GL 1010 (Bank Deposit - debit card)
- BANK FEE → GL 6500 (Bank Fees)
- CITY OF RED DEER → GL 6900 (Unknown - likely taxes/utilities)
- EMAIL TRANSFER → GL 6900 (Unknown e-transfer)
- RECEIVER GENERAL (typo) → GL 6900 (CRA tax)
- ROYNAT LEASE FINANCE → GL 2100 (Vehicle finance)
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

updates = [
    # Unknown bill payments
    ("DRAFT PURCHASE", "6900", "Unknown", "Draft purchase payment"),
    ("DEBIT VIA DRAFT", "6900", "Unknown", "Debit via draft payment"),
    ("BILL PAYMENT", "6900", "Unknown", "Bill payment"),
    ("BUSINESS EXPENSE", "6900", "Unknown", "Business expense"),
    ("LFG BUSINESS PAD", "6900", "Unknown", "Pre-authorized debit"),
    
    # Bank deposits
    ("CREDIT MEMO", "1010", "Bank Deposit", "Credit memo"),
    ("DCARD DEPOSIT", "1010", "Bank Deposit", "Debit card deposit"),
    
    # Bank fees
    ("BANK FEE", "6500", "Bank Fees", "Bank fee"),
    
    # Tax/Municipality
    ("CITY OF RED DEER", "6900", "Unknown", "City of Red Deer payment"),
    ("RECEIVER GENERAL", "6900", "CRA Tax Payment", "Revenue Canada tax"),
    
    # Vehicle finance
    ("ROYNAT LEASE FINANCE", "2100", "Vehicle Lease/Finance", "Vehicle lease finance"),
    
    # Unknown transfers
    ("EMAIL TRANSFER", "6900", "Unknown", "Email transfer payment"),
]

print("=== FINAL GL CLEANUP ===\n")

total_updated = 0
for vendor, gl_code, category, notes in updates:
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE vendor_name = %s
        AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    """, (vendor,))
    
    count, total = cur.fetchone()
    if count > 0:
        cur.execute("""
            UPDATE receipts
            SET gl_account_code = %s,
                gl_account_name = %s,
                category = %s,
                auto_categorized = true
            WHERE vendor_name = %s
            AND (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
        """, (gl_code, f"GL {gl_code}", category, vendor))
        
        total_updated += count
        print(f"✅ {vendor:<35} {count:>4} receipts  ${total:>13,.0f}  → GL {gl_code}")

conn.commit()

print(f"\n✅ Total updated: {total_updated} receipts")

# Show any remaining NULL GL vendors
print("\n" + "=" * 80)
print("Remaining NULL GL vendors (should be very few):")
print("=" * 80 + "\n")

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        COALESCE(SUM(gross_amount), 0) as total
    FROM receipts
    WHERE gl_account_code IS NULL OR gl_account_code = ''
    GROUP BY vendor_name
    ORDER BY total DESC
    LIMIT 20
""")

print(f"{'Vendor':<50} {'Count':>7} {'Total':>14}")
print("-" * 75)

for vendor, count, total in cur.fetchall():
    vendor_display = vendor[:47] + '...' if len(vendor) > 50 else vendor
    print(f"{vendor_display:<50} {count:>7} {total:>13,.0f}")

cur.close()
conn.close()
