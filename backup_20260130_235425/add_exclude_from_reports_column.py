#!/usr/bin/env python3
"""
Add exclude_from_reports column and mark NSF pairs and voided checks
Preserves audit trail while excluding from financial reports
"""
import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("="*100)
    print("ADD exclude_from_reports COLUMN TO RECEIPTS")
    print("="*100)
    
    # Check if column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        AND column_name = 'exclude_from_reports'
    """)
    
    exists = cur.fetchone()
    
    if not exists:
        print("\nAdding exclude_from_reports column...")
        cur.execute("""
            ALTER TABLE receipts 
            ADD COLUMN exclude_from_reports BOOLEAN DEFAULT FALSE
        """)
        print("✓ Column added")
    else:
        print("\n✓ Column already exists")
    
    conn.commit()
    
    # NSF pairs that net to $0
    nsf_pairs = [140232]  # Karen Richard $2,000 NSF with reversal
    
    # Voided checks (not in banking) - all the 2025-10-17 "CHECK PAYMENT" entries
    voided_checks = [
        71774,   # 2021 Canada Games
        118548, 118571, 118573, 118558, 118621, 118626, 118627, 118628, 118630,
        118631, 118635, 118643, 118499, 118677, 118400, 118414, 118434, 118440,
        118442, 118455, 118471, 118473, 118494, 118496, 118502, 118503, 118510,
        118514, 118516, 118520, 118521, 118522, 118534, 118531
    ]
    
    all_excluded = nsf_pairs + voided_checks
    
    print(f"\n{'='*100}")
    print("MARKING RECEIPTS AS EXCLUDED FROM REPORTS")
    print(f"{'='*100}")
    
    print(f"\nNSF pairs (net $0): {len(nsf_pairs)} receipts")
    print(f"Voided checks (not in banking): {len(voided_checks)} receipts")
    print(f"Total to exclude: {len(all_excluded)} receipts")
    
    # Show what we're excluding
    print(f"\n{'='*100}")
    print("RECEIPTS TO EXCLUDE")
    print(f"{'='*100}")
    
    placeholders = ','.join(['%s'] * len(all_excluded))
    cur.execute(f"""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount,
               description, is_nsf, banking_transaction_id
        FROM receipts
        WHERE receipt_id IN ({placeholders})
        ORDER BY receipt_date
    """, all_excluded)
    
    receipts = cur.fetchall()
    
    total_amount = 0
    for rec_id, date, vendor, amount, desc, is_nsf, bank_tx in receipts:
        if amount:
            total_amount += float(amount)
        nsf_flag = "🚨 NSF" if is_nsf else ""
        bank_flag = "❌ NOT IN BANKING" if not bank_tx else f"✓ Banking TX {bank_tx}"
        
        print(f"\n  Receipt #{rec_id} | {date} | ${amount:,.2f} | {vendor or 'NO VENDOR'} {nsf_flag}")
        print(f"  {bank_flag}")
        print(f"  {desc[:80] if desc else 'No description'}")
    
    print(f"\n{'='*100}")
    print(f"Total amount to exclude: ${total_amount:,.2f}")
    print("(Amounts preserved for audit trail, just excluded from reports)")
    print(f"{'='*100}")
    
    # Mark them as excluded
    print("\nMarking receipts as exclude_from_reports = TRUE...")
    
    cur.execute(f"""
        UPDATE receipts
        SET exclude_from_reports = TRUE
        WHERE receipt_id IN ({placeholders})
    """, all_excluded)
    
    updated_count = cur.rowcount
    print(f"✓ Updated {updated_count} receipts")
    
    conn.commit()
    print("\n✅ COMMITTED")
    
    # Verify
    print(f"\n{'='*100}")
    print("VERIFICATION")
    print(f"{'='*100}")
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE exclude_from_reports = TRUE
    """)
    
    count, total = cur.fetchone()
    print(f"\nTotal receipts excluded: {count}")
    print(f"Total amount excluded: ${total:,.2f}")
    
    print(f"\n{'='*100}")
    print("USAGE IN QUERIES")
    print(f"{'='*100}")
    
    print("""
To get accurate financial reports, use:

SELECT vendor_name, SUM(gross_amount) as total
FROM receipts
WHERE exclude_from_reports = FALSE  -- ← Exclude NSF pairs and voided checks
GROUP BY vendor_name;

Total receipts for reporting:
""")
    
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE exclude_from_reports = FALSE
        AND gross_amount IS NOT NULL
    """)
    
    active_count, active_total = cur.fetchone()
    print(f"  Active receipts: {active_count:,}")
    print(f"  Total amount: ${active_total:,.2f}")
    
    print(f"\nExcluded receipts (audit only):")
    print(f"  Excluded count: {count}")
    print(f"  Excluded amount: ${total:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
