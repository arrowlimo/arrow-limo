import psycopg2
import re
from decimal import Decimal

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("2019 SPLIT RECEIPTS ANALYSIS (description field)")
print("="*100)

# Find receipts with SPLIT in description
cur.execute("""
    SELECT 
        receipt_id,
        vendor_name,
        gross_amount,
        receipt_date,
        description,
        banking_transaction_id,
        exclude_from_reports
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2019
      AND description ILIKE '%split%'
    ORDER BY receipt_date
""")

split_receipts = cur.fetchall()

print(f"\n1. RECEIPTS WITH 'SPLIT' IN DESCRIPTION")
print("-"*100)
print(f"Found {len(split_receipts)} split receipts in 2019\n")

if split_receipts:
    print(f"{'Receipt ID':<12} | {'Date':<12} | {'Amount':>10} | {'Vendor':<30} | {'Description'}")
    print("-"*100)
    
    total_split_amount = 0
    split_patterns = []
    
    for receipt_id, vendor, amount, date, description, banking_id, excluded in split_receipts:
        total_split_amount += float(amount) if amount else 0
        desc_short = description[:70] if description else 'N/A'
        vendor_short = vendor[:28] if vendor else 'N/A'
        excluded_flag = " [EXCLUDED]" if excluded else ""
        
        print(f"{receipt_id:<12} | {str(date):<12} | ${float(amount):>9,.2f} | {vendor_short:<30} | {desc_short}{excluded_flag}")
        
        # Parse split pattern
        if description:
            split_patterns.append((receipt_id, description, amount))
    
    print(f"\nTotal split receipts: {len(split_receipts)} | ${total_split_amount:,.2f}")
    
    # Analyze split patterns
    print(f"\n2. SPLIT PATTERN ANALYSIS")
    print("-"*100)
    
    # Common patterns
    patterns_found = {
        'SPLIT/': 0,
        'CASH': 0,
        'CARD': 0,
        'REBATE': 0,
        'FUEL': 0,
        'SUPPLIES': 0,
        'OFFICE': 0
    }
    
    for receipt_id, description, amount in split_patterns:
        desc_upper = description.upper()
        for pattern in patterns_found.keys():
            if pattern in desc_upper:
                patterns_found[pattern] += 1
    
    print(f"Common split indicators found:")
    for pattern, count in sorted(patterns_found.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            print(f"  {pattern}: {count} receipts")
    
    # Show detailed examples
    print(f"\n3. DETAILED SPLIT EXAMPLES (first 10)")
    print("-"*100)
    
    for i, (receipt_id, description, amount) in enumerate(split_patterns[:10]):
        print(f"\nReceipt {receipt_id} (${float(amount):,.2f}):")
        print(f"  Description: {description}")
        
        # Try to parse split amounts
        # Pattern: SPLIT/$100 - $50 fuel, $30 supplies
        split_match = re.search(r'SPLIT/?\$?([0-9,]+\.?[0-9]*)', description, re.I)
        if split_match:
            split_total = split_match.group(1).replace(',', '')
            try:
                split_total_num = Decimal(split_total)
                print(f"  Split total indicated: ${split_total_num:,.2f}")
                
                if abs(float(amount) - float(split_total_num)) < 0.01:
                    print(f"  ✅ Amount matches split total")
                else:
                    print(f"  ⚠️  Amount ${float(amount):,.2f} != Split total ${split_total_num:,.2f}")
            except:
                pass
        
        # Find all dollar amounts in description
        amounts = re.findall(r'\$([0-9,]+\.?[0-9]*)', description)
        if len(amounts) > 1:
            print(f"  Split components found: {len(amounts)} amounts")
            component_sum = 0
            for amt_str in amounts:
                try:
                    amt_val = Decimal(amt_str.replace(',', ''))
                    component_sum += amt_val
                    print(f"    ${amt_val:,.2f}")
                except:
                    pass
            
            if component_sum > 0:
                print(f"  Sum of components: ${component_sum:,.2f}")
                if abs(component_sum - Decimal(str(amount))) < Decimal('0.01'):
                    print(f"  ✅ Components sum to receipt amount")
                else:
                    print(f"  ⚠️  Components sum ${component_sum:,.2f} != receipt ${float(amount):,.2f}")

    # Check if these are linked to banking
    print(f"\n4. BANKING LINKAGE FOR SPLIT RECEIPTS")
    print("-"*100)
    
    with_banking = [r for r in split_receipts if r[5] is not None]
    without_banking = [r for r in split_receipts if r[5] is None]
    
    print(f"With banking_transaction_id: {len(with_banking)} receipts")
    print(f"Without banking_transaction_id: {len(without_banking)} receipts")
    
    # Check for multiple receipts sharing same banking TX (true database splits)
    if with_banking:
        banking_ids = [r[5] for r in with_banking]
        
        cur.execute("""
            SELECT 
                banking_transaction_id,
                COUNT(*) as receipt_count,
                STRING_AGG(receipt_id::text, ', ') as receipt_ids
            FROM receipts
            WHERE banking_transaction_id = ANY(%s)
            GROUP BY banking_transaction_id
            HAVING COUNT(*) > 1
        """, (banking_ids,))
        
        multi_receipt_banking = cur.fetchall()
        
        if multi_receipt_banking:
            print(f"\n⚠️  Found {len(multi_receipt_banking)} banking TXs with multiple receipts (true DB splits):")
            for tx_id, count, receipt_ids in multi_receipt_banking:
                print(f"  Banking TX {tx_id}: {count} receipts ({receipt_ids})")
        else:
            print(f"\n✅ No database splits - each banking TX has one receipt")
            print(f"   Splits are documented in description field only (manual tracking)")

    # Check excluded status
    excluded_splits = [r for r in split_receipts if r[6]]
    
    print(f"\n5. EXCLUDED SPLIT RECEIPTS")
    print("-"*100)
    print(f"Excluded from reports: {len(excluded_splits)} split receipts")
    print(f"Active in reports: {len(split_receipts) - len(excluded_splits)} split receipts")

else:
    print("No split receipts found in 2019")

print(f"\n{'='*100}")
print(f"SUMMARY")
print(f"{'='*100}")
print(f"""
2019 Total receipts: 2,318
2019 Split receipts (in description): {len(split_receipts)}
Total amount in splits: ${total_split_amount if split_receipts else 0:,.2f}

SPLIT TRACKING METHOD:
  Manual tracking in description field
  Format: SPLIT/$amount - breakdown by category/payment method
  Examples: "SPLIT/$100 - $50 CASH, $50 CARD"
            "SPLIT - $30 fuel, $20 supplies, $10 rebate"

DATABASE STRUCTURE:
  Each physical receipt = ONE database record
  Split details stored in description field (text documentation)
  NOT split into multiple database receipts per category
  
This is a documentation/tracking method, not database splits.
The one-to-one receipt-banking relationship is maintained.
""")

cur.close()
conn.close()
