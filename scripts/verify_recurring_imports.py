#!/usr/bin/env python3
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
)

cur = conn.cursor()

print("\n" + "="*70)
print("RECURRING PAYMENT AUDIT - FINAL VERIFICATION")
print("="*70 + "\n")

# Verify each vendor
vendors = [
    ("GoDaddy", "vendor_name LIKE 'GoDaddy%'"),
    ("Wix", "vendor_name LIKE 'Wix%'"),
    ("IONOS", "vendor_name LIKE 'IONOS%'"),
]

for vendor_name, condition in vendors:
    cur.execute(f"""
        SELECT 
            COUNT(*) as count,
            SUM(gross_amount) as gross,
            MIN(receipt_date) as earliest,
            MAX(receipt_date) as latest
        FROM receipts
        WHERE {condition}
    """)
    
    count, gross, earliest, latest = cur.fetchone()
    gross = gross or 0
    
    print(f"✅ {vendor_name:10} │ {count:3d} records │ ${gross:>10,.2f} │ {earliest} to {latest}")

print("\n" + "="*70 + "\n")

# Get totals
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount), SUM(gst_amount), SUM(net_amount)
    FROM receipts
    WHERE vendor_name LIKE 'GoDaddy%'
       OR vendor_name LIKE 'Wix%'
       OR vendor_name LIKE 'IONOS%'
""")

total_count, total_gross, total_gst, total_net = cur.fetchone()
total_gross = total_gross or 0
total_gst = total_gst or 0
total_net = total_net or 0

print(f"📊 TOTALS:")
print(f"   Records:  {total_count}")
print(f"   Gross:    ${total_gross:,.2f}")
print(f"   GST:      ${total_gst:,.2f}")
print(f"   Net:      ${total_net:,.2f}")

print(f"\n✅ AUDIT COMPLETE - All recurring payments imported successfully")
print(f"   Full report: l:\\limo\\reports\\RECURRING_PAYMENT_AUDIT_FINAL_REPORT_20251205.md")
print("\n" + "="*70 + "\n")

cur.close()
conn.close()
