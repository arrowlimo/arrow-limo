#!/usr/bin/env python3
"""Check if there are actual split receipts with data to test"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("\n" + "=" * 80)
print("SPLIT RECEIPT DATA ANALYSIS")
print("=" * 80)

# Check receipt_splits
cur.execute("SELECT COUNT(*) FROM receipt_splits")
split_count = cur.fetchone()[0]
print(f"\n📊 receipt_splits table: {split_count} rows")

# Check receipt_banking_links
cur.execute("SELECT COUNT(*) FROM receipt_banking_links")
banking_count = cur.fetchone()[0]
print(f"📊 receipt_banking_links table: {banking_count} rows")

# Check receipt_cashbox_links
cur.execute("SELECT COUNT(*) FROM receipt_cashbox_links")
cash_count = cur.fetchone()[0]
print(f"📊 receipt_cashbox_links table: {cash_count} rows")

# Check audit_log
cur.execute("SELECT COUNT(*) FROM audit_log")
audit_count = cur.fetchone()[0]
print(f"📊 audit_log table: {audit_count} rows")

# Check for receipts with split_status
cur.execute("SELECT COUNT(*) FROM receipts WHERE split_status IS NOT NULL")
split_status_count = cur.fetchone()[0]
print(f"📊 receipts with split_status: {split_status_count}")

print("\n" + "=" * 80)
print("TEST DATA STATUS")
print("=" * 80)

if split_count + banking_count + cash_count + audit_count == 0:
    print("\n❌ NO SPLIT DATA IN DATABASE")
    print("\nTo test the split receipt UI, you need to create test data.")
    print("\nOptions:")
    print("1. Use the UI to create a split:")
    print("   - Launch app: python -X utf8 desktop_app/main.py")
    print("   - Search for a receipt")
    print("   - Click [✂️ Create Split] button")
    print("   - Enter split amounts")
    print("   - Click [✅ Save Split]")
    print("\n2. Run this test again after creating splits via UI")
else:
    print(f"\n✅ SPLIT DATA FOUND!")
    print(f"   Total data rows: {split_count + banking_count + cash_count + audit_count}")
    
    if split_count > 0:
        # Get first few split receipts
        cur.execute("""
            SELECT DISTINCT receipt_id FROM receipt_splits 
            ORDER BY receipt_id DESC LIMIT 10
        """)
        receipt_ids = [r[0] for r in cur.fetchall()]
        print(f"\n📦 SPLIT RECEIPT IDS TO TEST: {', '.join(str(r) for r in receipt_ids)}")
        
        # Show details
        print("\n" + "=" * 80)
        print("SPLIT RECEIPT DETAILS")
        print("=" * 80)
        
        for receipt_id in receipt_ids[:5]:  # Show first 5
            cur.execute("""
                SELECT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount, r.split_status
                FROM receipts r WHERE r.receipt_id = %s
            """, (receipt_id,))
            r = cur.fetchone()
            if r:
                print(f"\n Receipt #{r[0]}")
                print(f"  Date: {r[1]} | Vendor: {r[2]} | Amount: ${r[3]:,.2f}")
                print(f"  Status: {r[4]}")
                
                # Get split parts
                cur.execute("""
                    SELECT split_order, gl_code, amount FROM receipt_splits 
                    WHERE receipt_id = %s ORDER BY split_order
                """, (receipt_id,))
                parts = cur.fetchall()
                if parts:
                    print(f"  Parts ({len(parts)}):")
                    for part in parts:
                        print(f"    Part {part[0]}: GL={part[1]} Amount=${part[2]:,.2f}")
                
                # Get banking links
                cur.execute("""
                    SELECT COUNT(*) FROM receipt_banking_links WHERE receipt_id = %s
                """, (receipt_id,))
                bank_count = cur.fetchone()[0]
                if bank_count > 0:
                    print(f"  Banking Links: {bank_count}")
                
                # Get cash links
                cur.execute("""
                    SELECT cashbox_amount, float_reimbursement_type FROM receipt_cashbox_links 
                    WHERE receipt_id = %s
                """, (receipt_id,))
                cash = cur.fetchone()
                if cash:
                    print(f"  Cash Portion: ${cash[0]:,.2f} ({cash[1]})")
        
        print("\n" + "=" * 80)
        print("✅ UI TESTING INSTRUCTIONS")
        print("=" * 80)
        print("""
1. Set environment variable:
   $env:RECEIPT_WIDGET_WRITE_ENABLED = "true"

2. Launch desktop app:
   python -X utf8 desktop_app/main.py

3. Go to Receipts tab

4. Test split detection on each receipt ID above:
   - Use Receipt ID filter or search by ID
   - Verify red banner appears: "📦 Split into X receipt(s)..."
   - Verify side-by-side panels show below search table
   - Click [👁️ View Split Details] for summary dialog
   - Click [🔗 Open] to navigate to linked receipt
   - Try [💰 Add Cash Portion] button
   - Try [✂️ Create Split] on non-split receipts

5. Document any issues or unexpected behavior
""")

cur.close()
conn.close()
