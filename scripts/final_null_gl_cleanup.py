"""
Handle final NULL GL vendors:
- NSF FEE, NSF RETURN CHECK → GL 6500 (Bank Fees)
- MORTGAGE PROTECT, MCAP variants → GL 9999 (Personal Draws)
- ALL SERVICE INS variants → GL 5150 (Vehicle Insurance)
- THE TIRE GARAGE, NOTHLAND RADIATOR → GL 5100 (Vehicle Maintenance)
- COPIES NOW, STAPLES → GL 6100 (Supplies)
- E-TRANSFERS (drivers) → GL 6900 (Driver payments)
- KNW DIESEL → GL 5306 (Fuel)
- PAYMENT VISA ROYAL BANK → GL 9999 (Personal draws)
- PROV COURT → GL 6900 (Unknown)
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
    # Bank fees
    ("NSF FEE", "6500", "Bank Fees", "Non-sufficient funds fee"),
    ("NSF RETURN CHECK", "6500", "Bank Fees", "Non-sufficient funds return"),
    
    # Personal/Mortgage
    ("MORTGAGE PROTECT", "9999", "Personal Draws", "Mortgage protection insurance"),
    ("MCAP SERVICE CORP MORTGAGE", "9999", "Personal Draws", "Personal mortgage payment"),
    ("MCAP SERVICE", "9999", "Personal Draws", "Personal mortgage/finance"),
    
    # Vehicle Insurance
    ("ALL SERVICE INS", "5150", "Vehicle Insurance", "Vehicle insurance"),
    ("MONEY ORDER TO ALL SERVICE INSURANCE", "5150", "Vehicle Insurance", "Vehicle insurance payment"),
    
    # Vehicle Maintenance
    ("THE TIRE GARAGE", "5100", "Vehicle Maintenance & Repair", "Tire service"),
    ("NOTHLAND RADIATOR", "5100", "Vehicle Maintenance & Repair", "Radiator service"),
    
    # Fuel
    ("KNW DIESEL IN", "5306", "Fuel", "Diesel fuel"),
    
    # Supplies
    ("COPIES NOW", "6100", "Supplies", "Copy service"),
    ("STAPLES", "6100", "Supplies", "Office supplies"),
    
    # Payments/Draws
    ("PAYMENT VISA ROYAL BANK", "9999", "Personal Draws", "Credit card payment"),
    
    # Driver e-transfers
    ("ETRANSFER JESSE GORDON", "6900", "Driver Payment", "Driver payment - Jesse Gordon"),
    ("ETRANSFER JEANNIE SHILLINGTON", "6900", "Driver Payment", "Driver payment - Jeannie Shillington"),
    ("ETRANSFER HEFFNER AUTO FINANCING", "2100", "Vehicle Lease/Finance", "Vehicle finance"),
    ("ETRANSFER HEFFNER", "6900", "Personal Draws", "Personal transfer"),
    ("ETRANFER HEFFNER", "6900", "Personal Draws", "Personal transfer (typo)"),
    ("ETRANSER HEFFNER", "6900", "Personal Draws", "Personal transfer (typo)"),
    
    # Government/Legal
    ("PROV COURT RED DEER", "6900", "Unknown", "Provincial court payment"),
]

print("=== FINAL NULL GL CLEANUP ===\n")

total_updated = 0
for vendor, gl_code, category, notes in updates:
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
        FROM receipts
        WHERE vendor_name = %s
        AND (gl_account_code IS NULL OR gl_account_code = '')
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
            AND (gl_account_code IS NULL OR gl_account_code = '')
        """, (gl_code, f"GL {gl_code}", category, vendor))
        
        total_updated += count
        print(f"✅ {vendor:<45} {count:>4} receipts  ${total:>13,.0f}  → GL {gl_code}")

conn.commit()

print(f"\n✅ Total updated: {total_updated} receipts")

# Show truly remaining edge cases
print("\n" + "=" * 80)
print("Remaining edge cases (should be minimal):")
print("=" * 80 + "\n")

cur.execute("""
    SELECT 
        vendor_name,
        COUNT(*) as count,
        COALESCE(SUM(gross_amount), 0) as total,
        STRING_AGG(DISTINCT COALESCE(gl_account_code, 'NULL'), ', ') as gl_codes
    FROM receipts
    WHERE gl_account_code IS NULL OR gl_account_code = ''
    GROUP BY vendor_name
    ORDER BY total DESC
""")

results = cur.fetchall()
print(f"Total remaining uncategorized vendors: {len(results)}\n")
print(f"{'Vendor':<50} {'Count':>7} {'Total':>14} {'GL'}")
print("-" * 80)

for vendor, count, total, gl_codes in results:
    vendor_display = vendor[:47] + '...' if len(vendor) > 50 else vendor
    print(f"{vendor_display:<50} {count:>7} {total:>13,.0f} {gl_codes}")

cur.close()
conn.close()
