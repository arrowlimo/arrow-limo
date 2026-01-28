#!/usr/bin/env python3
"""
Test script to verify split receipt UI on all split receipts in database
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def test_split_receipts():
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Find all receipts with split_status or linked banking
        print("=" * 80)
        print("SPLIT RECEIPTS IN DATABASE - TESTING UI COMPATIBILITY")
        print("=" * 80)
        
        cur.execute("""
            SELECT DISTINCT r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount,
                   r.split_status, COUNT(rs.split_id) as split_parts, 
                   COUNT(rbl.link_id) as banking_links,
                   COUNT(rcl.link_id) as cash_links
            FROM receipts r
            LEFT JOIN receipt_splits rs ON rs.receipt_id = r.receipt_id
            LEFT JOIN receipt_banking_links rbl ON rbl.receipt_id = r.receipt_id
            LEFT JOIN receipt_cashbox_links rcl ON rcl.receipt_id = r.receipt_id
            WHERE r.split_status IS NOT NULL OR 
                  rs.split_id IS NOT NULL OR 
                  rbl.link_id IS NOT NULL OR
                  rcl.link_id IS NOT NULL
            GROUP BY r.receipt_id, r.receipt_date, r.vendor_name, r.gross_amount, r.split_status
            ORDER BY r.receipt_id DESC
        """)
        
        splits = cur.fetchall()
        
        if not splits:
            print("\n⚠️  NO SPLIT RECEIPTS FOUND IN DATABASE\n")
            print("To test the split receipt UI, you need to:")
            print("1. Create a test split using [✂️ Create Split] button in app")
            print("2. Or create test data manually\n")
            cur.close()
            conn.close()
            return False
        
        print(f"\n✅ FOUND {len(splits)} RECEIPTS WITH SPLITS/CASH/BANKING LINKS\n")
        
        # Test each split receipt
        test_results = []
        for r in splits:
            receipt_id, date, vendor, amount, status, split_parts, bank_links, cash_links = r
            
            result = {
                'receipt_id': receipt_id,
                'date': date,
                'vendor': vendor,
                'amount': amount,
                'status': status,
                'split_parts': split_parts,
                'banking_links': bank_links,
                'cash_links': cash_links,
                'passed': True,
                'errors': []
            }
            
            # Test 1: Check if split_parts > 0 or banking_links > 0
            if split_parts == 0 and bank_links == 0 and cash_links == 0:
                result['errors'].append("No split parts, banking links, or cash links found")
                result['passed'] = False
            
            # Test 2: Verify split parts if they exist
            if split_parts > 0:
                cur.execute("""
                    SELECT split_id, split_order, gl_code, amount, payment_method
                    FROM receipt_splits WHERE receipt_id = %s ORDER BY split_order
                """, (receipt_id,))
                parts = cur.fetchall()
                
                if len(parts) != split_parts:
                    result['errors'].append(f"Split count mismatch: DB says {split_parts}, found {len(parts)}")
                    result['passed'] = False
                
                # Check amounts sum to receipt total
                total_split_amount = sum(float(p[3]) for p in parts)
                if abs(total_split_amount - amount) > 0.01:
                    result['errors'].append(f"Split amounts don't sum to total: ${total_split_amount:.2f} vs ${amount:.2f}")
                    result['passed'] = False
            
            # Test 3: Verify banking links if they exist
            if bank_links > 0:
                cur.execute("""
                    SELECT link_id, transaction_id, linked_amount, link_status
                    FROM receipt_banking_links WHERE receipt_id = %s
                """, (receipt_id,))
                banks = cur.fetchall()
                
                if len(banks) != bank_links:
                    result['errors'].append(f"Banking link count mismatch: DB says {bank_links}, found {len(banks)}")
                    result['passed'] = False
            
            # Test 4: Verify cash links if they exist
            if cash_links > 0:
                cur.execute("""
                    SELECT link_id, cashbox_amount, float_reimbursement_type, driver_id
                    FROM receipt_cashbox_links WHERE receipt_id = %s
                """, (receipt_id,))
                cashes = cur.fetchall()
                
                if len(cashes) != cash_links:
                    result['errors'].append(f"Cash link count mismatch: DB says {cash_links}, found {len(cashes)}")
                    result['passed'] = False
            
            test_results.append(result)
        
        # Print test results
        print("\n" + "=" * 80)
        print("TEST RESULTS")
        print("=" * 80 + "\n")
        
        passed_count = 0
        failed_count = 0
        
        for result in test_results:
            status_icon = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"{status_icon} | Receipt #{result['receipt_id']}")
            print(f"       Date: {result['date']} | Vendor: {result['vendor']} | Amount: ${result['amount']:,.2f}")
            print(f"       Status: {result['status'] or 'N/A'} | Parts: {result['split_parts']} | Banking: {result['banking_links']} | Cash: {result['cash_links']}")
            
            if result['errors']:
                for error in result['errors']:
                    print(f"       ❌ ERROR: {error}")
            
            print()
            
            if result['passed']:
                passed_count += 1
            else:
                failed_count += 1
        
        # Summary
        print("=" * 80)
        print(f"SUMMARY: {passed_count} PASSED, {failed_count} FAILED out of {len(test_results)}")
        print("=" * 80 + "\n")
        
        if failed_count == 0:
            print("✅ ALL SPLIT RECEIPTS ARE VALID FOR UI TESTING\n")
            print("To test the UI:")
            print("1. Set environment variable: RECEIPT_WIDGET_WRITE_ENABLED=true")
            print("2. Launch desktop app: python -X utf8 desktop_app/main.py")
            print("3. Go to Receipts tab")
            print("4. Use receipt ID filter to load each split receipt")
            print("5. Verify split detection banner + side-by-side panels appear")
            print(f"\nTest receipts to load: {', '.join(str(r['receipt_id']) for r in test_results[:5])}")
            return True
        else:
            print(f"⚠️  {failed_count} SPLIT(S) HAVE VALIDATION ERRORS\n")
            print("Please fix database integrity issues before testing UI")
            return False
        
        cur.close()
        conn.close()
    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_split_receipts()
    exit(0 if success else 1)
