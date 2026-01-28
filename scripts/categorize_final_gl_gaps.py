"""
Categorize remaining vendors:
- CORRECTION 00339 → GL 6900 (Unknown - corrections/adjustments)
- [UNKNOWN POINT OF SALE] → GL 6900 (Unknown - retail purchases)
- TRANSFER → GL 9999 (Personal Draws - internal transfers)
- JOURNAL ENTRY → GL 6900 (Unknown - accounting entries)
- Other uncategorized → GL 6900 (Unknown)
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

updates = [
    # Corrections and adjustments
    ("CORRECTION 00339", "6900", "Unknown", "Bank correction/adjustment"),
    
    # Unknown POS transactions
    ("[UNKNOWN POINT OF SALE]", "6900", "Unknown", "Retail POS purchase"),
    
    # Internal transfers
    ("TRANSFER", "9999", "Personal Draws", "Internal transfer"),
    
    # Accounting entries
    ("JOURNAL ENTRY - JOURNAL ENTRY", "6900", "Unknown", "Journal entry adjustment"),
    
    # Insurance (if no GL)
    ("ALL SERVICE INSURANCE", "5150", "Vehicle Insurance", "Vehicle insurance"),
    ("FIRST INSURANCE", "5150", "Vehicle Insurance", "Vehicle insurance"),
    ("FIRST INSURANCE FUNDING", "5150", "Vehicle Insurance", "Vehicle insurance"),
    
    # Driver payments/reimbursements
    ("PAUL RICHARD", "6900", "Unknown", "Driver payment"),
    ("JEANNIE SHILLINGTON", "6900", "Unknown", "Driver payment"),
    ("JACK CARTER", "6900", "Unknown", "Driver payment"),
    ("PAUL MANSELL", "6900", "Unknown", "Driver payment"),
    ("MICHAEL RICHARD", "6900", "Unknown", "Driver payment"),
    ("MARK LINTON", "6900", "Unknown", "Driver payment"),
    
    # Card payments
    ("AMERICAN EXPRESS PAYMENT", "9999", "Personal Draws", "Credit card payment"),
    ("CAPITAL ONE MASTERCARD", "9999", "Personal Draws", "Credit card payment"),
    
    # Miscellaneous
    ("DRAFT PURCHASE", "6900", "Unknown", "Draft/check purchase"),
    ("BILL PAYMENT", "6900", "Unknown", "Bill payment"),
    ("RED DEER REGISTRIES", "5180", "Vehicle Registration", "Vehicle registration"),
    ("KAREN. RICHARD", "6900", "Unknown", "Unknown payment"),
    ("RUN'N ON EMPTY", "5306", "Fuel", "Fuel purchase"),
    ("RECEIVER GENERAL - 861556827 RT0001", "6900", "Unknown", "Government payment"),
    ("G-49416-90399 ATTACHMENT ORDER", "6900", "Unknown", "Attachment/garnishment"),
    ("MCAP SERVICES-RMG MORTGAGES", "6900", "Unknown", "Mortgage/finance"),
]

print("=== CATEGORIZING REMAINING VENDORS ===\n")

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
        print(f"✅ {vendor:<45} {count:>4} receipts  ${total:>13,.0f}  → GL {gl_code}")

conn.commit()
print(f"\n✅ Total receipts updated: {total_updated}")

# Show remaining gaps
print("\n" + "=" * 80)
print("REMAINING GL GAPS (still need categorization):")
print("=" * 80 + "\n")

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        COALESCE(SUM(gross_amount), 0) as total,
        STRING_AGG(DISTINCT COALESCE(gl_account_code, 'NULL'), ', ' ORDER BY COALESCE(gl_account_code, 'NULL')) as gl_codes
    FROM receipts
    WHERE (gl_account_code IS NULL OR gl_account_code = '' OR gl_account_code = '6900')
    AND receipt_date >= '2012-01-01'
    GROUP BY vendor_name
    ORDER BY total DESC
    LIMIT 20
""")

print(f"{'Vendor':<50} {'Count':>7} {'Total':>14} {'GL Codes'}")
print("-" * 100)

for vendor, count, total, gl_codes in cur.fetchall():
    vendor_display = vendor[:47] + '...' if len(vendor) > 50 else vendor
    print(f"{vendor_display:<50} {count:>7} {total:>13,.0f} {gl_codes}")

cur.close()
conn.close()
