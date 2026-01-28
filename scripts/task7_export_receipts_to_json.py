#!/usr/bin/env python3
"""
TASK #7: Export all receipts to JSON for easy querying and deduplication
"""
import psycopg2
import json
from datetime import date, datetime
from decimal import Decimal

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

def decimal_default(obj):
    """JSON serializer for Decimal and date objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("="*100)
    print("TASK #7: EXPORT RECEIPTS TO JSON")
    print("="*100)
    
    # Export receipts with banking links
    print("\n📦 Exporting receipts...")
    
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.receipt_date,
            r.vendor_name,
            r.gross_amount,
            r.gst_amount,
            r.net_amount,
            r.category,
            r.description,
            r.business_personal,
            r.payment_method,
            r.source_hash,
            r.source_file,
            r.source_system,
            r.created_from_banking,
            r.mapped_bank_account_id,
            r.validation_status,
            -- Banking links
            COALESCE(
                json_agg(
                    json_build_object(
                        'banking_transaction_id', bml.banking_transaction_id,
                        'transaction_uid', bt.transaction_uid,
                        'match_type', bml.match_type,
                        'match_confidence', bml.match_confidence,
                        'match_status', bml.match_status
                    ) ORDER BY bml.match_date
                ) FILTER (WHERE bml.banking_transaction_id IS NOT NULL),
                '[]'::json
            ) as banking_links
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger bml ON bml.receipt_id = r.receipt_id
        LEFT JOIN banking_transactions bt ON bt.transaction_id = bml.banking_transaction_id
        GROUP BY r.receipt_id
        ORDER BY r.receipt_date DESC, r.receipt_id
    """)
    
    receipts = []
    for row in cur.fetchall():
        receipt = {
            'receipt_id': row[0],
            'receipt_date': row[1],
            'vendor_name': row[2],
            'gross_amount': row[3],
            'gst_amount': row[4],
            'net_amount': row[5],
            'category': row[6],
            'description': row[7],
            'business_personal': row[8],
            'payment_method': row[9],
            'source_hash': row[10],
            'source_file': row[11],
            'source_system': row[12],
            'created_from_banking': row[13],
            'mapped_bank_account_id': row[14],
            'validation_status': row[15],
            'banking_links': row[16] if row[16] else []
        }
        receipts.append(receipt)
    
    print(f"   ✅ Loaded {len(receipts):,} receipts")
    
    # Calculate statistics
    print("\n📊 Statistics:")
    
    with_banking = sum(1 for r in receipts if r['banking_links'])
    without_banking = len(receipts) - with_banking
    
    created_from_banking = sum(1 for r in receipts if r['created_from_banking'])
    
    by_category = {}
    for r in receipts:
        cat = r['category'] or 'Unknown'
        by_category[cat] = by_category.get(cat, 0) + 1
    
    print(f"   Total receipts: {len(receipts):,}")
    print(f"   With banking links: {with_banking:,} ({with_banking/len(receipts)*100:.1f}%)")
    print(f"   Without banking links: {without_banking:,} ({without_banking/len(receipts)*100:.1f}%)")
    print(f"   Auto-created from banking: {created_from_banking:,}")
    
    print(f"\n   Top 10 categories:")
    for cat, count in sorted(by_category.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"      {cat}: {count:,}")
    
    # Save to JSON
    output_file = 'l:\\limo\\data\\receipts_export.json'
    print(f"\n💾 Saving to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'export_date': datetime.now().isoformat(),
            'total_receipts': len(receipts),
            'statistics': {
                'with_banking_links': with_banking,
                'without_banking_links': without_banking,
                'created_from_banking': created_from_banking
            },
            'receipts': receipts
        }, f, indent=2, default=decimal_default)
    
    print(f"   ✅ Saved {len(receipts):,} receipts to JSON")
    
    # Create deduplication lookup file
    dedup_file = 'l:\\limo\\data\\receipts_dedup_lookup.json'
    print(f"\n🔍 Creating deduplication lookup file...")
    
    # Group by date + amount + vendor for easy duplicate detection
    dedup_index = {}
    for r in receipts:
        if r['receipt_date'] and r['gross_amount'] and r['vendor_name']:
            key = f"{r['receipt_date']}|{float(r['gross_amount']):.2f}|{r['vendor_name'].lower()}"
            if key not in dedup_index:
                dedup_index[key] = []
            dedup_index[key].append({
                'receipt_id': r['receipt_id'],
                'category': r['category'],
                'source_hash': r['source_hash'],
                'banking_links': len(r['banking_links'])
            })
    
    # Find potential duplicates
    potential_duplicates = {k: v for k, v in dedup_index.items() if len(v) > 1}
    
    print(f"   Found {len(potential_duplicates):,} potential duplicate groups")
    
    with open(dedup_file, 'w', encoding='utf-8') as f:
        json.dump({
            'export_date': datetime.now().isoformat(),
            'total_unique_keys': len(dedup_index),
            'potential_duplicate_groups': len(potential_duplicates),
            'duplicates': potential_duplicates
        }, f, indent=2, default=decimal_default)
    
    print(f"   ✅ Saved deduplication lookup")
    
    # Summary
    print("\n" + "="*100)
    print("✅ TASK #7 COMPLETE")
    print("="*100)
    
    print(f"\n📁 Output files:")
    print(f"   • {output_file}")
    print(f"     Full export: {len(receipts):,} receipts with all fields")
    print(f"   • {dedup_file}")
    print(f"     Dedup lookup: {len(potential_duplicates):,} potential duplicate groups")
    
    print(f"\n💡 Next steps:")
    print(f"   1. Review potential duplicates in dedup_lookup.json")
    print(f"   2. Verify receipts without banking links ({without_banking:,} receipts)")
    print(f"   3. Check Unknown category receipts ({by_category.get('Unknown', 0):,} receipts)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
