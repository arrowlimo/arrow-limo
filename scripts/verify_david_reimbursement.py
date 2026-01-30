#!/usr/bin/env python3
import os, psycopg2
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

print("\n" + "="*70)
print("RECURRING PAYMENT CURRENCY AUDIT - FINAL SUMMARY")
print("="*70 + "\n")

# Total USD-tagged receipts
cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE currency = 'USD'
    AND (vendor_name ILIKE 'godaddy%' OR vendor_name ILIKE 'wix%' OR vendor_name ILIKE 'ionos%')
""")
usd_count, usd_total = cur.fetchone()
print(f"✅ Total receipts tagged as USD: {usd_count}")
print(f"   Total amount (CAD posted): ${usd_total:,.2f}\n")

# David-paid breakdown
cur.execute("""
    SELECT 
        CASE 
            WHEN vendor_name ILIKE 'godaddy%' THEN 'GoDaddy'
            WHEN vendor_name ILIKE 'wix%' THEN 'Wix'
            WHEN vendor_name ILIKE 'ionos%' THEN 'IONOS'
        END as vendor,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE description ILIKE '%David paid%'
    GROUP BY vendor
    ORDER BY vendor
""")

print("💰 David-Paid Summary (Reimbursement/Loan Owed):")
print("-"*70)
print(f"{'Vendor':<10} │ {'Count':>6} │ {'Amount (CAD)':>15}")
print("-"*70)

david_total = 0
david_count = 0
for vendor, count, total in cur.fetchall():
    total = total or 0
    david_total += total
    david_count += count
    print(f"{vendor:<10} │ {count:>6} │ ${total:>14,.2f}")

print("-"*70)
print(f"{'TOTAL':<10} │ {david_count:>6} │ ${david_total:>14,.2f}")

# Business account payments
business_total = usd_total - david_total
business_count = usd_count - david_count

print(f"\n📊 Payment Source Summary:")
print(f"   David Paid:      {david_count:3} receipts = ${david_total:>10,.2f} ({david_count/usd_count*100:.1f}%)")
print(f"   Business Bank:   {business_count:3} receipts = ${business_total:>10,.2f} ({business_count/usd_count*100:.1f}%)")
print(f"   ────────────────────────────────────────────────")
print(f"   TOTAL:          {usd_count:3} receipts = ${usd_total:>10,.2f}")

print(f"\n✅ AUDIT COMPLETE")
print(f"   Report: l:\\limo\\reports\\RECURRING_PAYMENT_CURRENCY_AUDIT_FINAL_20251205.md")
print("="*70 + "\n")

cur.close()
conn.close()
