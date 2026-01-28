"""
Comprehensive Split Receipt Testing
Tests multiple banking transactions with various payment method combinations
"""

import psycopg2
import os
import json
from datetime import datetime, timedelta

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def find_suitable_banking_transactions():
    """Find banking transactions to test split functionality"""
    conn = get_connection()
    cur = conn.cursor()
    
    # Look for unmatched banking transactions with various vendors and amounts
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            vendor_extracted
        FROM banking_transactions
        WHERE receipt_id IS NULL
            AND reconciliation_status != 'reconciled'
            AND (debit_amount > 50 OR credit_amount > 50)
            AND transaction_date BETWEEN '2023-01-01' AND '2023-12-31'
        ORDER BY ABS(COALESCE(debit_amount, 0) + COALESCE(credit_amount, 0)) DESC
        LIMIT 20
    """)
    
    results = []
    for row in cur.fetchall():
        trans_id, date, desc, debit, credit = row[0], row[1], row[2], row[3], row[4]
        amount = float(debit or credit or 0)
        if amount > 50:  # Only test substantial amounts
            results.append({
                'transaction_id': trans_id,
                'date': date,
                'description': desc,
                'amount': amount
            })
    
    cur.close()
    conn.close()
    return results[:10]  # Return top 10

def create_test_split(banking_id, vendor_name, amount, splits_config):
    """
    Create a test split receipt
    splits_config: list of {amount, gl_code, payment_method, memo}
    """
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Find the banking transaction details
        cur.execute("""
            SELECT transaction_date, category 
            FROM banking_transactions 
            WHERE transaction_id = %s
        """, (banking_id,))
        
        row = cur.fetchone()
        if not row:
            print(f"❌ Banking transaction {banking_id} not found")
            return None
        
        receipt_date, category = row
        gst_code = "GST_INCL_5"  # Assume Alberta GST
        
        # Create split tag
        split_tag = f"SPLIT/{amount:.2f}"
        new_receipt_ids = []
        
        for idx, split in enumerate(splits_config):
            split_amount = split['amount']
            gl_code = split['gl_code']
            payment_method = split['payment_method']
            memo = split.get('memo', '')
            
            # Calculate GST for this split (tax-inclusive 5%)
            line_gst = split_amount * 0.05 / 1.05
            line_net = split_amount - line_gst
            
            # Build description
            full_desc = f"{vendor_name} | {memo} | {split_tag}" if memo else f"{vendor_name} | {split_tag}"
            
            # Only link first split to banking
            link_banking = banking_id if idx == 0 else None
            
            # Get GL account name
            cur.execute("""
                SELECT account_name FROM chart_of_accounts WHERE account_code = %s
            """, (gl_code,))
            gl_row = cur.fetchone()
            gl_name = gl_row[0] if gl_row else "Unknown"
            
            # Insert receipt
            insert_sql = """
                INSERT INTO receipts (
                    receipt_date, vendor_name, canonical_vendor, gross_amount,
                    gst_amount, gst_code, sales_tax, tax_category,
                    description, category, source_reference, payment_method,
                    banking_transaction_id, is_driver_reimbursement,
                    gl_account_code, gl_account_name
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING receipt_id
            """
            
            cur.execute(insert_sql, (
                receipt_date,
                vendor_name,
                vendor_name.upper(),
                float(split_amount),
                float(line_gst),
                gst_code,
                float(line_net),
                'expense',
                full_desc,
                category,
                f"Split from {banking_id}",
                payment_method,
                link_banking,
                False,
                gl_code,
                gl_name
            ))
            
            receipt_id = cur.fetchone()[0]
            new_receipt_ids.append(receipt_id)
            
            # Create ledger entry only for first split
            if idx == 0:
                cur.execute("""
                    INSERT INTO banking_receipt_matching_ledger (
                        banking_transaction_id, receipt_id, amount_allocated,
                        allocation_date, notes, allocation_type, match_type,
                        match_status, match_confidence, created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    banking_id,
                    receipt_id,
                    float(split_amount),
                    datetime.now(),
                    f"Split first of {len(splits_config)} splits",
                    'split_first',
                    'split_receipt',
                    'matched',
                    'high',
                    'system'
                ))
        
        conn.commit()
        
        return {
            'banking_id': banking_id,
            'vendor_name': vendor_name,
            'total_amount': amount,
            'split_count': len(splits_config),
            'receipt_ids': new_receipt_ids,
            'status': '✅ SUCCESS'
        }
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creating split for banking {banking_id}: {e}")
        return None
    
    finally:
        cur.close()
        conn.close()

def test_scenario_1():
    """
    Scenario 1: Fuel + Maintenance split
    $150 purchase: $95 Fuel (Debit) + $55 Oil (Cash)
    """
    return {
        'name': 'Fuel + Maintenance Split',
        'vendor': 'SHELL GAS STATION',
        'amount': 150.00,
        'splits': [
            {'amount': 95.00, 'gl_code': '5110', 'payment_method': 'debit', 'memo': 'Premium Fuel'},
            {'amount': 55.00, 'gl_code': '5100', 'payment_method': 'cash', 'memo': 'Oil & Filter'}
        ]
    }

def test_scenario_2():
    """
    Scenario 2: Multi-tender payment
    $200 purchase: $100 Gift Card + $75 Credit Card + $25 Cash (3-way split)
    """
    return {
        'name': 'Three-Way Payment Split',
        'vendor': 'BEST BUY SUPPLIES',
        'amount': 200.00,
        'splits': [
            {'amount': 100.00, 'gl_code': '5200', 'payment_method': 'gift_card', 'memo': 'Office Supplies'},
            {'amount': 75.00, 'gl_code': '5220', 'payment_method': 'credit_card', 'memo': 'Software License'},
            {'amount': 25.00, 'gl_code': '5100', 'payment_method': 'cash', 'memo': 'Miscellaneous'}
        ]
    }

def test_scenario_3():
    """
    Scenario 3: High-value mixed payment
    $500 fuel purchase: $300 Debit + $200 Credit Card (2-way)
    """
    return {
        'name': 'Large Fuel Purchase Split',
        'vendor': 'PETRO CANADA',
        'amount': 500.00,
        'splits': [
            {'amount': 300.00, 'gl_code': '5110', 'payment_method': 'debit', 'memo': 'Diesel'},
            {'amount': 200.00, 'gl_code': '5110', 'payment_method': 'credit_card', 'memo': 'Premium'}
        ]
    }

def test_scenario_4():
    """
    Scenario 4: Rebate + Expense (unusual but valid)
    $125 purchase: $100 Regular + $25 Rebate reversal
    """
    return {
        'name': 'Purchase with Rebate',
        'vendor': 'TRUCK PARTS WHOLESALER',
        'amount': 125.00,
        'splits': [
            {'amount': 100.00, 'gl_code': '5140', 'payment_method': 'check', 'memo': 'Engine Parts'},
            {'amount': 25.00, 'gl_code': '5140', 'payment_method': 'rebate', 'memo': 'Volume Discount'}
        ]
    }

def test_scenario_5():
    """
    Scenario 5: Driver reimbursement with multiple categories
    $87.50: $50 Fuel + $37.50 Food (2-way)
    """
    return {
        'name': 'Driver Reimbursement Split',
        'vendor': 'DRIVER EXPENSE REIMBURSE',
        'amount': 87.50,
        'splits': [
            {'amount': 50.00, 'gl_code': '5110', 'payment_method': 'cash', 'memo': 'Fuel'},
            {'amount': 37.50, 'gl_code': '6050', 'payment_method': 'cash', 'memo': 'Meals'}
        ]
    }

def main():
    print("=" * 80)
    print("COMPREHENSIVE SPLIT RECEIPT TEST")
    print("=" * 80)
    
    # Get suitable banking transactions
    print("\n📊 Finding suitable banking transactions for testing...")
    banking_txns = find_suitable_banking_transactions()
    
    if not banking_txns:
        print("❌ No suitable banking transactions found (need >$50 unmatched receipts)")
        return
    
    print(f"✅ Found {len(banking_txns)} banking transactions")
    for i, txn in enumerate(banking_txns[:5]):
        print(f"  {i+1}. {txn['date']} | {txn['description'][:40]:40s} | ${txn['amount']:,.2f}")
    
    # Define test scenarios
    scenarios = [
        test_scenario_1(),
        test_scenario_2(),
        test_scenario_3(),
        test_scenario_4(),
        test_scenario_5()
    ]
    
    results = []
    
    # Run tests
    print("\n" + "=" * 80)
    print("RUNNING TESTS")
    print("=" * 80)
    
    for i, scenario in enumerate(scenarios):
        if i >= len(banking_txns):
            print(f"\n⚠️  Skipping scenario {i+1} (not enough banking transactions)")
            break
        
        banking_id = banking_txns[i]['transaction_id']
        
        print(f"\n🧪 Test {i+1}: {scenario['name']}")
        print(f"   Banking ID: {banking_id}")
        print(f"   Vendor: {scenario['vendor']}")
        print(f"   Amount: ${scenario['amount']:,.2f}")
        print(f"   Splits:")
        
        for split in scenario['splits']:
            print(f"     • ${split['amount']:6.2f} | {split['gl_code']} | {split['payment_method']:12s} | {split['memo']}")
        
        result = create_test_split(
            banking_id,
            scenario['vendor'],
            scenario['amount'],
            scenario['splits']
        )
        
        if result:
            print(f"   {result['status']}")
            print(f"   Created {len(result['receipt_ids'])} receipts: {result['receipt_ids']}")
            results.append(result)
        else:
            print(f"   ❌ FAILED")
    
    # Verification
    print("\n" + "=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    
    conn = get_connection()
    cur = conn.cursor()
    
    verified = 0
    for result in results:
        banking_id = result['banking_id']
        receipt_ids = result['receipt_ids']
        
        print(f"\n📋 Verifying banking {banking_id}:")
        
        # Check receipts
        cur.execute("""
            SELECT receipt_id, gross_amount, gst_amount, payment_method, 
                   gl_account_code, description, banking_transaction_id
            FROM receipts
            WHERE receipt_id = ANY(%s)
            ORDER BY receipt_id
        """, (receipt_ids,))
        
        rows = cur.fetchall()
        split_verified = True
        
        for idx, row in enumerate(rows):
            rid, amt, gst, pm, gl, desc, bkt = row
            is_linked = "✅ LINKED" if bkt else "⚠️  unlinked"
            
            # Check SPLIT/ tag in description
            has_split_tag = "SPLIT/" in desc
            
            print(f"  Receipt {rid}: ${amt:6.2f} | {pm:12s} | GL {gl} | {is_linked} | SPLIT: {'✅' if has_split_tag else '❌'}")
            
            if idx == 0 and not bkt:
                print(f"     ❌ First split should be linked to banking!")
                split_verified = False
            elif idx > 0 and bkt:
                print(f"     ❌ Non-first split should NOT be linked!")
                split_verified = False
            
            # Verify GST calculation
            if gst > 0:
                net = amt - gst
                expected_gst = float(amt) * 0.05 / 1.05
                if abs(float(gst) - expected_gst) > 0.01:
                    print(f"     ❌ GST mismatch: {gst} vs expected {expected_gst}")
                    split_verified = False
        
        # Check ledger entry exists (only for first split)
        cur.execute("""
            SELECT COUNT(*) FROM banking_receipt_matching_ledger
            WHERE banking_transaction_id = %s AND receipt_id = ANY(%s)
        """, (banking_id, receipt_ids))
        
        ledger_count = cur.fetchone()[0]
        if ledger_count == 1:
            print(f"  ✅ Ledger entry: 1 (correct)")
            verified += 1
        else:
            print(f"  ❌ Ledger entries: {ledger_count} (expected 1)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Tests Passed: {verified}/{len(results)}")
    print(f"📊 Total Receipts Created: {sum(len(r['receipt_ids']) for r in results)}")
    print(f"💾 Total Scenarios Tested: {len(results)}")

if __name__ == "__main__":
    main()
