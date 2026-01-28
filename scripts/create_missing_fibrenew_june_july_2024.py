"""
Create the 2 missing Fibrenew receipts for June and July 2024.
Invoice #12304 (June 2024) and #12363 (July 2024) - both $1,102.50 rent.
"""
import psycopg2
import hashlib
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Missing invoices from fibrenew invoices2.pdf
missing_invoices = [
    {
        'invoice_number': '12304',
        'date': '2024-06-01',
        'amount': 1102.50,
        'description': 'Fibrenew Office Rent - Invoice #12304'
    },
    {
        'invoice_number': '12363',
        'date': '2024-07-01',
        'amount': 1102.50,
        'description': 'Fibrenew Office Rent - Invoice #12363'
    }
]

print("\n=== Creating 2 missing Fibrenew receipts ===\n")

for inv in missing_invoices:
    # Calculate GST (5% included in amount)
    gross_amount = inv['amount']
    gst_amount = round(gross_amount * 0.05 / 1.05, 2)
    net_amount = round(gross_amount - gst_amount, 2)
    
    # Generate source hash for deduplication
    hash_input = f"{inv['date']}|{inv['description']}|{gross_amount:.2f}".encode('utf-8')
    source_hash = hashlib.sha256(hash_input).hexdigest()
    
    # Check if already exists
    cur.execute("SELECT receipt_id FROM receipts WHERE source_hash = %s", (source_hash,))
    existing = cur.fetchone()
    
    if existing:
        print(f"⚠️  Invoice #{inv['invoice_number']} already exists (receipt_id {existing[0]})")
        continue
    
    # Insert receipt
    cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            description, category, source_hash
        ) VALUES (
            %s, 'Fibrenew Central Alberta', %s, %s, %s,
            %s, 'rent', %s
        ) RETURNING receipt_id
    """, (inv['date'], gross_amount, gst_amount, net_amount, inv['description'], source_hash))
    
    receipt_id = cur.fetchone()[0]
    print(f"✅ Created receipt {receipt_id}: Invoice #{inv['invoice_number']} | {inv['date']} | ${gross_amount:,.2f}")
    print(f"   GST: ${gst_amount:.2f}, Net: ${net_amount:.2f}")

conn.commit()

# Final verification
print("\n=== Final Fibrenew Reconciliation ===\n")

cur.execute("""
    SELECT COUNT(*), SUM(gross_amount)
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%'
    AND description LIKE '%Invoice #%'
""")
count, total = cur.fetchone()
print(f"Total Fibrenew receipts with invoice numbers: {count}")
print(f"Total amount: ${total:,.2f}")

# Check all 2024 invoices
cur.execute("""
    SELECT receipt_date, gross_amount, description
    FROM receipts
    WHERE vendor_name ILIKE '%fibrenew%'
    AND receipt_date >= '2024-01-01'
    AND receipt_date <= '2024-12-31'
    AND description LIKE '%Invoice #%'
    ORDER BY receipt_date
""")

all_2024 = cur.fetchall()
print(f"\n2024 Fibrenew invoices with invoice numbers: {len(all_2024)}")
for r in all_2024:
    print(f"  {r[0]} | ${r[1]:>10,.2f} | {r[2]}")

cur.close()
conn.close()

print("\n✅ Fibrenew reconciliation complete!")
print("All invoices from PDFs and statement now have receipt records.")
