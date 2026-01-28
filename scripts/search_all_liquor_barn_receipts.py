#!/usr/bin/env python3
"""
Search All Three Liquor Barn Receipts - December 2012
=====================================================

Check for all three Liquor Barn receipts from accountant records:
1. Dec 6, 2012: $41.18 ($1.93 GST)
2. Dec 7, 2012: $44.90 ($2.10 GST)  
3. Dec 31, 2012: $60.32 ($2.75 GST)

Author: AI Agent
Date: October 2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from decimal import Decimal
from datetime import datetime

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def search_all_liquor_barn_receipts(conn):
    """Search for all three Liquor Barn receipts."""
    cur = conn.cursor()
    
    # Target receipts from accountant records
    target_receipts = [
        ('2012-12-06', Decimal('41.18'), Decimal('1.93')),
        ('2012-12-07', Decimal('44.90'), Decimal('2.10')),
        ('2012-12-31', Decimal('60.32'), Decimal('2.75'))
    ]
    
    print("🍷 LIQUOR BARN RECEIPTS SEARCH - December 2012")
    print("=" * 50)
    print("Checking for 3 accountant receipts:")
    print("1. Dec 6:  $41.18 ($1.93 GST)")
    print("2. Dec 7:  $44.90 ($2.10 GST)")
    print("3. Dec 31: $60.32 ($2.75 GST)")
    print("Combined:  $146.40 ($6.78 GST, $139.62 net)")
    print()
    
    # Search for existing liquor receipts in December
    cur.execute("""
        SELECT receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
               description, category, source_system
        FROM receipts 
        WHERE receipt_date >= '2012-12-01' AND receipt_date <= '2012-12-31'
          AND (vendor_name ILIKE %s 
               OR description ILIKE %s
               OR vendor_name ILIKE %s
               OR vendor_name ILIKE %s)
        ORDER BY receipt_date, gross_amount
    """, ('%liquor%', '%liquor%', '%wine%', '%beer%'))
    
    existing_liquor = cur.fetchall()
    
    print("📋 EXISTING LIQUOR RECEIPTS (December 2012)")
    print("=" * 45)
    if existing_liquor:
        print(f"Found {len(existing_liquor)} existing liquor receipts:")
        print(f"{'Date':<12} {'Vendor':<18} {'Gross':<8} {'GST':<6} {'Net':<8} {'Source':<12}")
        print("-" * 70)
        
        total_existing_gross = Decimal('0')
        total_existing_gst = Decimal('0')
        
        for date, vendor, gross, gst, net, desc, cat, source in existing_liquor:
            total_existing_gross += Decimal(str(gross or 0))
            total_existing_gst += Decimal(str(gst or 0))
            print(f"{date} {(vendor or 'Unknown')[:16]:<18} ${gross or 0:>6.2f} ${gst or 0:>4.2f} ${net or 0:>6.2f} {(source or 'N/A')[:10]}")
        
        print("-" * 70)
        print(f"{'EXISTING TOTAL':<30} ${total_existing_gross:>6.2f} ${total_existing_gst:>4.2f}")
    else:
        print("[FAIL] No existing liquor receipts found in December 2012")
        total_existing_gross = Decimal('0')
        total_existing_gst = Decimal('0')
    
    print()
    
    # Check each target receipt
    print("🎯 TARGET RECEIPT VERIFICATION")
    print("=" * 30)
    
    found_receipts = 0
    missing_receipts = []
    
    for i, (date, target_gross, target_gst) in enumerate(target_receipts, 1):
        cur.execute("""
            SELECT vendor_name, gross_amount, gst_amount, net_amount, source_system
            FROM receipts 
            WHERE receipt_date = %s
              AND (ABS(gross_amount - %s) < 0.50 OR ABS(gst_amount - %s) < 0.10)
            ORDER BY ABS(gross_amount - %s)
        """, (date, target_gross, target_gst, target_gross))
        
        matches = cur.fetchall()
        
        if matches:
            found_receipts += 1
            print(f"[OK] Receipt {i} ({date}): Found {len(matches)} matches near ${target_gross:.2f}")
            for vendor, gross, gst, net, source in matches:
                gross_diff = abs(float(gross) - float(target_gross))
                gst_diff = abs(float(gst) - float(target_gst))
                print(f"   {vendor}: ${gross:.2f} (±${gross_diff:.2f}) GST ${gst:.2f} (±${gst_diff:.2f})")
        else:
            print(f"[FAIL] Receipt {i} ({date}): NOT FOUND - ${target_gross:.2f} (${target_gst:.2f} GST)")
            missing_receipts.append((date, target_gross, target_gst))
    
    print()
    
    # GST calculation verification
    print("🧮 GST CALCULATION VERIFICATION")
    print("=" * 32)
    gst_rate = Decimal('0.05')  # Alberta 2012: 5% GST
    
    all_correct = True
    for i, (date, gross, expected_gst) in enumerate(target_receipts, 1):
        calculated_gst = gross * gst_rate / (1 + gst_rate)
        calculated_net = gross - calculated_gst
        diff = abs(expected_gst - calculated_gst)
        is_correct = diff < Decimal('0.05')
        all_correct &= is_correct
        
        status = "[OK]" if is_correct else "[FAIL]"
        print(f"Receipt {i}: ${gross:.2f} → Expected ${expected_gst:.2f}, Calculated ${calculated_gst:.2f} {status}")
        print(f"         Net: ${calculated_net:.2f} (difference: ${diff:.4f})")
    
    print(f"\nOverall GST Accuracy: {'[OK] ALL CORRECT' if all_correct else '[FAIL] SOME ERRORS'}")
    print()
    
    # Summary of missing receipts
    if missing_receipts:
        total_missing_gross = sum(gross for _, gross, _ in missing_receipts)
        total_missing_gst = sum(gst for _, _, gst in missing_receipts)
        total_missing_net = total_missing_gross - total_missing_gst
        
        print("[FAIL] MISSING RECEIPTS SUMMARY")
        print("=" * 28)
        print(f"Missing Receipts: {len(missing_receipts)} of {len(target_receipts)}")
        print(f"Missing Gross Amount: ${total_missing_gross:.2f}")
        print(f"Missing GST Amount: ${total_missing_gst:.2f}")
        print(f"Missing Net Expense: ${total_missing_net:.2f}")
        print()
        
        print("💡 BUSINESS IMPACT")
        print("==================")
        print(f"• Additional expense deductions available: ${total_missing_net:.2f}")
        print(f"• GST/HST input tax credits available: ${total_missing_gst:.2f}")
        print(f"• Total tax benefit potential: ~${total_missing_net * Decimal('0.14') + total_missing_gst:.2f}")
        print("• These appear to be legitimate business expenses from accountant records")
    else:
        print("[OK] ALL RECEIPTS FOUND IN SYSTEM")
    
    print()
    print("📊 COMPREHENSIVE SUMMARY")
    print("=" * 24)
    print(f"Target Receipts: {len(target_receipts)}")
    print(f"Found in System: {found_receipts}")
    print(f"Missing from System: {len(missing_receipts)}")
    print(f"Existing Liquor Receipts: {len(existing_liquor)}")
    print(f"Existing Liquor Total: ${total_existing_gross:.2f}")
    
    if len(missing_receipts) > 0:
        print()
        print("🔧 RECOMMENDED ACTIONS")
        print("=====================")
        print("1. Add missing receipts to system as legitimate business expenses")
        print("2. Verify vendor names and categorization")
        print("3. Update 2012 tax calculations with additional deductions")
        print("4. Check for other missing accountant cash receipts")
        print("5. Reconcile against cash payment records we identified earlier")
    
    cur.close()

def main():
    conn = get_db_connection()
    
    try:
        search_all_liquor_barn_receipts(conn)
    except Exception as e:
        print(f"[FAIL] Error searching for receipts: {e}")
        return 1
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())