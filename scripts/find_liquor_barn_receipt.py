#!/usr/bin/env python3
"""
Find Specific Receipt - Liquor Barn December 6, 2012
====================================================

Search for specific receipt: Liquor Barn 12/6/2012 $41.18 (GST $1.93)
to verify receipt recording accuracy and GST calculation correctness.

Author: AI Agent
Date: October 2025
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from decimal import Decimal
from datetime import datetime, date

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def search_liquor_barn_receipt(conn):
    """Search for the specific Liquor Barn receipt."""
    cur = conn.cursor()
    
    # Search by vendor name and date
    cur.execute("""
        SELECT 
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            description, category, source_system, source_reference, id
        FROM receipts 
        WHERE receipt_date = '2012-12-06'
          AND (vendor_name ILIKE '%liquor%barn%' 
               OR vendor_name ILIKE '%liquor%'
               OR description ILIKE '%liquor%barn%'
               OR description ILIKE '%liquor%')
        ORDER BY ABS(gross_amount - 41.18)
    """)
    
    exact_matches = cur.fetchall()
    
    # Search by amount and date (in case vendor name is different)
    cur.execute("""
        SELECT 
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            description, category, source_system, source_reference, id
        FROM receipts 
        WHERE receipt_date = '2012-12-06'
          AND ABS(gross_amount - 41.18) < 1.00
        ORDER BY ABS(gross_amount - 41.18)
    """)
    
    amount_matches = cur.fetchall()
    
    # Search broader date range for Liquor Barn
    cur.execute("""
        SELECT 
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            description, category, source_system, source_reference, id
        FROM receipts 
        WHERE receipt_date BETWEEN '2012-12-01' AND '2012-12-10'
          AND (vendor_name ILIKE '%liquor%barn%' 
               OR vendor_name ILIKE '%liquor%'
               OR description ILIKE '%liquor%barn%'
               OR description ILIKE '%liquor%')
        ORDER BY receipt_date, gross_amount
    """)
    
    date_range_matches = cur.fetchall()
    
    # Search for GST amount match
    cur.execute("""
        SELECT 
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            description, category, source_system, source_reference, id
        FROM receipts 
        WHERE receipt_date = '2012-12-06'
          AND ABS(gst_amount - 1.93) < 0.10
        ORDER BY ABS(gst_amount - 1.93)
    """)
    
    gst_matches = cur.fetchall()
    
    cur.close()
    return exact_matches, amount_matches, date_range_matches, gst_matches

def verify_gst_calculation():
    """Verify GST calculation for Alberta 2012."""
    gross_amount = Decimal('41.18')
    expected_gst = Decimal('1.93')
    
    # Alberta 2012: 5% GST included in price
    gst_rate = Decimal('0.05')
    calculated_gst = gross_amount * gst_rate / (1 + gst_rate)
    calculated_net = gross_amount - calculated_gst
    
    return {
        'gross': gross_amount,
        'expected_gst': expected_gst,
        'calculated_gst': calculated_gst,
        'calculated_net': calculated_net,
        'gst_difference': abs(expected_gst - calculated_gst),
        'is_correct': abs(expected_gst - calculated_gst) < Decimal('0.05')
    }

def search_all_december_6_receipts(conn):
    """Get all receipts from December 6, 2012 for context."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
            description, category, source_system, source_reference, id
        FROM receipts 
        WHERE receipt_date = '2012-12-06'
        ORDER BY gross_amount DESC
    """)
    
    all_receipts = cur.fetchall()
    cur.close()
    return all_receipts

def main():
    conn = get_db_connection()
    
    try:
        print("🍷 LIQUOR BARN RECEIPT SEARCH - December 6, 2012")
        print("=" * 55)
        print("Target: Liquor Barn, $41.18 gross, $1.93 GST")
        print(f"Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Verify GST calculation first
        gst_check = verify_gst_calculation()
        
        print("🧮 GST CALCULATION VERIFICATION")
        print("==============================")
        print(f"Gross Amount: ${gst_check['gross']:.2f}")
        print(f"Expected GST: ${gst_check['expected_gst']:.2f}")
        print(f"Calculated GST (5% included): ${gst_check['calculated_gst']:.2f}")
        print(f"Calculated Net: ${gst_check['calculated_net']:.2f}")
        print(f"GST Difference: ${gst_check['gst_difference']:.4f}")
        print(f"Calculation Correct: {'[OK] YES' if gst_check['is_correct'] else '[FAIL] NO'}")
        print()
        
        # Search for the receipt
        exact_matches, amount_matches, date_range_matches, gst_matches = search_liquor_barn_receipt(conn)
        
        print("🔍 EXACT VENDOR & DATE MATCHES")
        print("=============================")
        if exact_matches:
            print(f"Found {len(exact_matches)} exact matches:")
            print(f"{'Date':<12} {'Vendor':<20} {'Gross':<10} {'GST':<8} {'Net':<10} {'Source':<15}")
            print("-" * 75)
            
            for date, vendor, gross, gst, net, desc, cat, source, ref, rec_id in exact_matches:
                print(f"{date} {(vendor or 'N/A')[:18]:<20} ${gross or 0:>7.2f} ${gst or 0:>6.2f} ${net or 0:>8.2f} {(source or 'N/A')[:13]}")
        else:
            print("[FAIL] No exact vendor name matches found")
        print()
        
        print("💰 AMOUNT MATCHES (±$1.00)")
        print("=========================")
        if amount_matches:
            print(f"Found {len(amount_matches)} amount matches:")
            print(f"{'Date':<12} {'Vendor':<20} {'Gross':<10} {'GST':<8} {'Net':<10} {'Source':<15}")
            print("-" * 75)
            
            for date, vendor, gross, gst, net, desc, cat, source, ref, rec_id in amount_matches:
                gross_diff = abs(float(gross or 0) - 41.18)
                print(f"{date} {(vendor or 'N/A')[:18]:<20} ${gross or 0:>7.2f} ${gst or 0:>6.2f} ${net or 0:>8.2f} {(source or 'N/A')[:13]} (±${gross_diff:.2f})")
        else:
            print("[FAIL] No amount matches found")
        print()
        
        print("🧾 GST AMOUNT MATCHES (±$0.10)")
        print("=============================")
        if gst_matches:
            print(f"Found {len(gst_matches)} GST matches:")
            print(f"{'Date':<12} {'Vendor':<20} {'Gross':<10} {'GST':<8} {'Net':<10} {'Source':<15}")
            print("-" * 75)
            
            for date, vendor, gross, gst, net, desc, cat, source, ref, rec_id in gst_matches:
                gst_diff = abs(float(gst or 0) - 1.93)
                print(f"{date} {(vendor or 'N/A')[:18]:<20} ${gross or 0:>7.2f} ${gst or 0:>6.2f} ${net or 0:>8.2f} {(source or 'N/A')[:13]} (±${gst_diff:.2f})")
        else:
            print("[FAIL] No GST amount matches found")
        print()
        
        print("📅 LIQUOR BARN - DATE RANGE (Dec 1-10)")
        print("=====================================")
        if date_range_matches:
            print(f"Found {len(date_range_matches)} liquor-related receipts:")
            print(f"{'Date':<12} {'Vendor':<20} {'Gross':<10} {'GST':<8} {'Net':<10} {'Source':<15}")
            print("-" * 75)
            
            for date, vendor, gross, gst, net, desc, cat, source, ref, rec_id in date_range_matches:
                print(f"{date} {(vendor or 'N/A')[:18]:<20} ${gross or 0:>7.2f} ${gst or 0:>6.2f} ${net or 0:>8.2f} {(source or 'N/A')[:13]}")
        else:
            print("[FAIL] No liquor-related receipts in date range")
        print()
        
        # Show all December 6 receipts for context
        all_receipts = search_all_december_6_receipts(conn)
        
        print("📋 ALL RECEIPTS - December 6, 2012")
        print("=================================")
        if all_receipts:
            print(f"Found {len(all_receipts)} total receipts on Dec 6, 2012:")
            print(f"{'Vendor':<25} {'Gross':<10} {'GST':<8} {'Net':<10} {'Category':<15}")
            print("-" * 75)
            
            total_gross = Decimal('0')
            total_gst = Decimal('0')
            
            for date, vendor, gross, gst, net, desc, cat, source, ref, rec_id in all_receipts:
                total_gross += Decimal(str(gross or 0))
                total_gst += Decimal(str(gst or 0))
                print(f"{(vendor or 'Unknown')[:23]:<25} ${gross or 0:>7.2f} ${gst or 0:>6.2f} ${net or 0:>8.2f} {(cat or 'N/A')[:13]}")
            
            print("-" * 75)
            print(f"{'TOTAL':<25} ${total_gross:>7.2f} ${total_gst:>6.2f}")
            
            # Check if our target amount is close to any receipt
            target_found = False
            for date, vendor, gross, gst, net, desc, cat, source, ref, rec_id in all_receipts:
                if abs(float(gross or 0) - 41.18) < 0.50:  # Within 50 cents
                    print(f"\n🎯 POTENTIAL MATCH: {vendor} ${gross:.2f} (difference: ${abs(float(gross or 0) - 41.18):.2f})")
                    target_found = True
            
            if not target_found:
                print(f"\n[WARN] Target amount $41.18 not found within 50¢ of any Dec 6 receipt")
        else:
            print("[FAIL] No receipts found for December 6, 2012")
        
        print()
        print("📊 SEARCH SUMMARY")
        print("================")
        print(f"[OK] GST Calculation: {'Correct' if gst_check['is_correct'] else 'Incorrect'}")
        print(f"📍 Exact Matches: {len(exact_matches)}")
        print(f"💰 Amount Matches: {len(amount_matches)}")
        print(f"🧾 GST Matches: {len(gst_matches)}")
        print(f"📅 Date Range Matches: {len(date_range_matches)}")
        print(f"📋 Total Dec 6 Receipts: {len(all_receipts)}")
        
        if exact_matches or amount_matches or gst_matches:
            print("\n[OK] RECEIPT LIKELY FOUND IN SYSTEM")
        else:
            print("\n[FAIL] RECEIPT NOT FOUND - May need to be added")
            print("💡 Consider checking:")
            print("   • Different vendor name spelling")
            print("   • Different date format")
            print("   • Different source system")
            print("   • Manual entry required")
    
    except Exception as e:
        print(f"[FAIL] Error searching for receipt: {e}")
        return 1
    
    finally:
        conn.close()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())