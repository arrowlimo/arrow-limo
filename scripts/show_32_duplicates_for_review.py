#!/usr/bin/env python3
"""
Display the 32 duplicate receipt groups in batches of 10 for manual review
"""
import psycopg2
import json

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Load deduplication report
with open('l:\\limo\\data\\receipts_dedup_lookup.json', 'r') as f:
    dedup_data = json.load(f)
    duplicates_dict = dedup_data.get('duplicates', {})

print("="*120)
print("32 DUPLICATE RECEIPT GROUPS - DETAILED REVIEW")
print("="*120)

# Sort by date and amount
sorted_groups = sorted(duplicates_dict.items(), key=lambda x: (x[0].split('|')[0], float(x[0].split('|')[1])), reverse=True)

batch_size = 10
total_batches = (len(sorted_groups) + batch_size - 1) // batch_size

for batch_num in range(total_batches):
    start_idx = batch_num * batch_size
    end_idx = min(start_idx + batch_size, len(sorted_groups))
    
    print(f"\n{'='*120}")
    print(f"BATCH {batch_num + 1} of {total_batches} (Groups {start_idx + 1}-{end_idx})")
    print(f"{'='*120}\n")
    
    for idx in range(start_idx, end_idx):
        key, group = sorted_groups[idx]
        parts = key.split('|')
        date = parts[0]
        amount = float(parts[1])
        vendor = parts[2]
        
        print(f"Group {idx + 1}: {date} | ${amount:,.2f} | {vendor}")
        print("-" * 120)
        
        # Get detailed info for each receipt in this group
        receipt_ids = [item['receipt_id'] for item in group]
        
        cur.execute(f"""
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                gross_amount,
                gst_amount,
                category,
                description,
                source_system,
                created_from_banking,
                (SELECT COUNT(*) FROM banking_receipt_matching_ledger WHERE receipt_id = r.receipt_id) as banking_links
            FROM receipts r
            WHERE receipt_id IN ({','.join(map(str, receipt_ids))})
            ORDER BY receipt_id
        """)
        
        receipts = cur.fetchall()
        
        for rec_id, rec_date, vname, gross, gst, cat, desc, source_sys, from_banking, bank_links in receipts:
            source_flag = 'BANKING' if from_banking else (source_sys or 'MANUAL')
            desc_str = (desc or '')[:50]
            cat_str = (cat or 'Unknown')[:20]
            
            print(f"   Receipt #{rec_id:<7} | ${gross:>10.2f} (GST: ${gst or 0:>6.2f}) | {source_flag:<15} | {bank_links} links | {cat_str:<20}")
            if desc_str:
                print(f"              Description: {desc_str}")
        
        # Recommendation
        print(f"\n   💡 RECOMMENDATION: ", end='')
        if len(group) == 2:
            # Check if they're from same source
            sources = set(item.get('created_from_banking', False) for item in group)
            if len(sources) == 1:
                print("Likely TRUE duplicate (same source) - DELETE ONE")
            else:
                print("Mixed sources - review carefully")
        else:
            print(f"{len(group)} receipts with same date/amount - likely TRUE duplicates - DELETE EXTRAS")
        
        print()
    
    if batch_num < total_batches - 1:
        input("\nPress Enter to see next batch...")

print("\n" + "="*120)
print("SUMMARY")
print("="*120)
print(f"\nTotal duplicate groups: {len(sorted_groups)}")
print(f"Total receipts involved: {sum(len(group) for _, group in sorted_groups)}")

# Count by duplicate size
dup_counts = {}
for _, group in sorted_groups:
    count = len(group)
    dup_counts[count] = dup_counts.get(count, 0) + 1

print(f"\nDuplicate group sizes:")
for size in sorted(dup_counts.keys(), reverse=True):
    print(f"   {size} receipts: {dup_counts[size]} groups")

cur.close()
conn.close()
