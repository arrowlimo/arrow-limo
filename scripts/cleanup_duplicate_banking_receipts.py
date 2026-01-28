#!/usr/bin/env python3
"""
Clean up duplicate receipts - Delete true duplicates, keep legitimate splits
"""
import psycopg2
import pandas as pd
from datetime import datetime

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    # Load the audit CSV
    import glob
    csv_files = glob.glob("l:/limo/reports/duplicate_banking_receipts_*.csv")
    if not csv_files:
        print("ERROR: No duplicate banking receipts audit CSV found")
        print("Run audit_duplicate_banking_receipts.py first")
        return
    
    latest_csv = max(csv_files)
    print(f"Loading audit data from: {latest_csv}")
    
    df = pd.read_csv(latest_csv)
    
    print("="*100)
    print("DUPLICATE RECEIPTS CLEANUP ANALYSIS")
    print("="*100)
    
    # Group by banking_tx_id
    grouped = df.groupby('banking_tx_id')
    
    true_duplicates = []
    potential_splits = []
    need_review = []
    
    for tx_id, group in grouped:
        bank_amount = group['bank_amount'].iloc[0]
        amounts = group['receipt_amount'].tolist()
        vendors = group['receipt_vendor'].tolist()
        receipt_ids = group['receipt_id'].tolist()
        dates = group['receipt_date'].tolist()
        
        # Check if all amounts are the same
        if len(set(amounts)) == 1:
            # All same amount - likely true duplicate
            if len(set(vendors)) == 1 or all(pd.isna(v) or v == vendors[0] for v in vendors):
                # Same vendor too - definite duplicate
                true_duplicates.append({
                    'tx_id': tx_id,
                    'receipt_ids': receipt_ids,
                    'amount': amounts[0],
                    'vendor': vendors[0],
                    'count': len(receipt_ids),
                    'action': 'DELETE_DUPLICATES_KEEP_OLDEST'
                })
            else:
                # Same amount, different vendors - unusual
                need_review.append({
                    'tx_id': tx_id,
                    'receipt_ids': receipt_ids,
                    'amounts': amounts,
                    'vendors': vendors,
                    'reason': 'Same amount, different vendors'
                })
        else:
            # Different amounts - might be split or error
            total_receipts = sum(amounts)
            diff = abs(total_receipts - bank_amount)
            
            if diff < 0.10:  # Within 10 cents - likely legitimate split
                potential_splits.append({
                    'tx_id': tx_id,
                    'receipt_ids': receipt_ids,
                    'amounts': amounts,
                    'vendors': vendors,
                    'bank_amount': bank_amount,
                    'action': 'MARK_AS_SPLIT_GROUP'
                })
            else:
                need_review.append({
                    'tx_id': tx_id,
                    'receipt_ids': receipt_ids,
                    'amounts': amounts,
                    'vendors': vendors,
                    'reason': f'Amounts dont sum to bank amount (${diff:.2f} difference)'
                })
    
    print(f"\n{'='*100}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*100}")
    print(f"True duplicates (same amount, same/no vendor): {len(true_duplicates)}")
    print(f"  Total duplicate receipts to delete: {sum(d['count'] - 1 for d in true_duplicates)}")
    print(f"\nPotential legitimate splits: {len(potential_splits)}")
    print(f"  (Amounts sum to banking amount)")
    print(f"\nNeed manual review: {len(need_review)}")
    
    # Show examples of true duplicates
    if true_duplicates:
        print(f"\n{'='*100}")
        print("TRUE DUPLICATES - WILL DELETE ALL BUT OLDEST (10 examples)")
        print(f"{'='*100}")
        
        for dup in true_duplicates[:10]:
            print(f"\nBanking TX #{dup['tx_id']} | ${dup['amount']:.2f} | {dup['vendor'] or 'NO VENDOR'}")
            print(f"  {dup['count']} duplicate receipts: {dup['receipt_ids']}")
            print(f"  → KEEP: Receipt #{min(dup['receipt_ids'])} (oldest)")
            print(f"  → DELETE: {[r for r in dup['receipt_ids'] if r != min(dup['receipt_ids'])]}")
    
    # Show examples of splits
    if potential_splits:
        print(f"\n{'='*100}")
        print("POTENTIAL LEGITIMATE SPLITS - WILL MARK AS SPLIT GROUP (5 examples)")
        print(f"{'='*100}")
        
        for split in potential_splits[:5]:
            print(f"\nBanking TX #{split['tx_id']} | Bank: ${split['bank_amount']:.2f}")
            print(f"  Split into {len(split['receipt_ids'])} receipts:")
            for rec_id, amt, vendor in zip(split['receipt_ids'], split['amounts'], split['vendors']):
                print(f"    Receipt #{rec_id}: ${amt:.2f} - {vendor or 'NO VENDOR'}")
            print(f"  Total: ${sum(split['amounts']):.2f}")
    
    # Show need review
    if need_review:
        print(f"\n{'='*100}")
        print("NEED MANUAL REVIEW (10 examples)")
        print(f"{'='*100}")
        
        for item in need_review[:10]:
            print(f"\nBanking TX #{item['tx_id']}")
            print(f"  Reason: {item['reason']}")
            print(f"  Receipts:")
            for rec_id, amt, vendor in zip(item['receipt_ids'], item['amounts'], item['vendors']):
                print(f"    #{rec_id}: ${amt:.2f} - {vendor or 'NO VENDOR'}")
    
    # Ask for confirmation
    print(f"\n{'='*100}")
    print("PROPOSED ACTIONS")
    print(f"{'='*100}")
    print(f"\n1. Delete {sum(d['count'] - 1 for d in true_duplicates)} duplicate receipts")
    print(f"   (Keep oldest receipt for each banking transaction)")
    print(f"\n2. Mark {len(potential_splits)} sets as legitimate splits")
    print(f"   (Assign split_key to group them)")
    print(f"\n3. Export {len(need_review)} cases for manual review")
    
    response = input("\nProceed with cleanup? (yes/no): ")
    
    if response.lower() != 'yes':
        print("\n❌ Cleanup cancelled")
        return
    
    # Execute cleanup
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    deleted_count = 0
    split_groups_marked = 0
    
    # Delete true duplicates
    print(f"\n{'='*100}")
    print("DELETING TRUE DUPLICATES...")
    print(f"{'='*100}")
    
    for dup in true_duplicates:
        keep_id = min(dup['receipt_ids'])
        delete_ids = [r for r in dup['receipt_ids'] if r != keep_id]
        
        if delete_ids:
            print(f"  Banking TX #{dup['tx_id']}: Keeping #{keep_id}, deleting {delete_ids}")
            
            # First, update any banking_transactions references to point to the kept receipt
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = %s
                WHERE receipt_id = ANY(%s)
            """, (keep_id, delete_ids))
            
            # Now safe to delete the duplicate receipts
            cur.execute("""
                DELETE FROM receipts
                WHERE receipt_id = ANY(%s)
            """, (delete_ids,))
            deleted_count += len(delete_ids)
    
    # Mark splits
    print(f"\n{'='*100}")
    print("MARKING LEGITIMATE SPLITS...")
    print(f"{'='*100}")
    
    for split in potential_splits:
        split_key = f"BANK_TX_{split['tx_id']}"
        
        print(f"  Banking TX #{split['tx_id']}: Marking {len(split['receipt_ids'])} receipts as split group")
        cur.execute("""
            UPDATE receipts
            SET split_key = %s,
                is_split_receipt = TRUE
            WHERE receipt_id = ANY(%s)
        """, (split_key, split['receipt_ids']))
        split_groups_marked += 1
    
    # Export manual review cases
    if need_review:
        review_df = pd.DataFrame([{
            'banking_tx_id': item['tx_id'],
            'reason': item['reason'],
            'receipt_ids': str(item['receipt_ids']),
            'amounts': str(item['amounts']),
            'vendors': str(item['vendors'])
        } for item in need_review])
        
        review_file = f"l:/limo/reports/duplicate_receipts_manual_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        review_df.to_csv(review_file, index=False)
        print(f"\n📋 Manual review cases exported to: {review_file}")
    
    # Commit
    conn.commit()
    
    print(f"\n{'='*100}")
    print("CLEANUP COMPLETE")
    print(f"{'='*100}")
    print(f"✅ Deleted {deleted_count} duplicate receipts")
    print(f"✅ Marked {split_groups_marked} split groups")
    print(f"📋 {len(need_review)} cases need manual review")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
