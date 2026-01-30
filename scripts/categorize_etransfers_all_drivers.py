#!/usr/bin/env python3
"""
Categorize e-transfers as driver payments by matching to all drivers in database.

Searches banking descriptions for driver names and categorizes as driver_pay.

Usage:
    python categorize_etransfers_all_drivers.py --dry-run
    python categorize_etransfers_all_drivers.py --write
"""

import os
import sys
import psycopg2
from difflib import SequenceMatcher
import re

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REDACTED***')

DRY_RUN = '--write' not in sys.argv

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def normalize_name(name):
    """Normalize name for comparison."""
    if not name:
        return ""
    
    # Remove common prefixes/suffixes
    name = re.sub(r'\b(mr|mrs|ms|dr|miss|jr|sr|ii|iii)\b\.?', '', name, flags=re.IGNORECASE)
    
    # Remove punctuation and extra spaces
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name.upper()

def fuzzy_match(name1, name2, threshold=0.75):
    """Return True if names match with >= threshold similarity."""
    if not name1 or not name2:
        return False, 0.0
    
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)
    
    # Try full name match
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    if ratio >= threshold:
        return True, ratio
    
    # Try first/last name matches
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    # If any significant word matches (3+ chars)
    significant_words1 = {w for w in words1 if len(w) >= 3}
    significant_words2 = {w for w in words2 if len(w) >= 3}
    
    common_words = significant_words1 & significant_words2
    if common_words:
        # Calculate ratio based on word overlap
        word_ratio = len(common_words) / max(len(significant_words1), len(significant_words2))
        if word_ratio >= 0.5:  # At least 50% word overlap
            return True, word_ratio
    
    return False, 0.0

def extract_name_from_description(description):
    """Extract person name from banking description."""
    if not description:
        return None
    
    # Pattern 1: E-TRANSFER#... Name
    match = re.search(r'E-TRANSFER[#\s]+\d+\s+([A-Z][A-Za-z\s]+?)(?:\s+\d|$)', description, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Pattern 2: Internet Banking E-TRANSFER ... Name
    match = re.search(r'Internet Banking E-TRANSFER\s+\d+\s+([A-Z][A-Za-z\s]+?)(?:\s*$)', description, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Pattern 3: E-TRANSFER Name (simple)
    match = re.search(r'E-TRANSFER\s+([A-Z][A-Za-z\s]{3,})', description, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    return None

def main():
    print("\n" + "="*100)
    print("CATEGORIZE E-TRANSFERS AS DRIVER PAYMENTS")
    print("="*100)
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE'}")
    
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Get all drivers/employees from database
        print("\n1. Loading all drivers from database...")
        
        cur.execute("""
            SELECT DISTINCT
                employee_id,
                full_name,
                first_name,
                last_name
            FROM employees
            WHERE full_name IS NOT NULL
            ORDER BY full_name
        """)
        
        employees = cur.fetchall()
        print(f"   Found {len(employees):,} employees in database")
        
        # Build driver lookup with all name variations
        driver_lookup = {}
        for emp_id, full_name, first_name, last_name in employees:
            driver_lookup[emp_id] = {
                'full_name': full_name,
                'first_name': first_name,
                'last_name': last_name,
                'name_variants': []
            }
            
            # Add name variants
            if full_name:
                driver_lookup[emp_id]['name_variants'].append(full_name)
            if first_name and last_name:
                driver_lookup[emp_id]['name_variants'].append(f"{first_name} {last_name}")
                driver_lookup[emp_id]['name_variants'].append(f"{last_name} {first_name}")
            if first_name:
                driver_lookup[emp_id]['name_variants'].append(first_name)
            if last_name:
                driver_lookup[emp_id]['name_variants'].append(last_name)
        
        # Get uncategorized or wrongly categorized e-transfers with banking links
        print("\n2. Finding e-transfers to categorize...")
        
        cur.execute("""
            SELECT 
                et.etransfer_id,
                et.direction,
                et.transaction_date,
                et.amount,
                et.category,
                bt.description
            FROM etransfer_transactions et
            JOIN banking_transactions bt ON et.banking_transaction_id = bt.transaction_id
            WHERE bt.description IS NOT NULL
            AND (bt.description ILIKE '%e-transfer%' OR bt.description ILIKE '%interac%')
            ORDER BY et.amount DESC
        """)
        
        all_etransfers = cur.fetchall()
        print(f"   Found {len(all_etransfers):,} e-transfers with banking descriptions")
        
        # Match to drivers
        print("\n3. Matching e-transfers to drivers...")
        
        matches = []
        already_driver_pay = 0
        
        for etrans_id, direction, tdate, amount, current_cat, description in all_etransfers:
            # Skip if already categorized as driver_pay
            if current_cat == 'driver_pay':
                already_driver_pay += 1
                continue
            
            # Skip if already in specific business categories (not driver pay)
            if current_cat in ('loan_payment', 'auto_insurance', 'auto_lease_payment', 'rent_vehicle_repairs', 'employee_pay_reimbursement'):
                continue
            
            # Extract name from description
            extracted_name = extract_name_from_description(description)
            if not extracted_name:
                continue
            
            # Name disambiguation: Exclude specific non-driver names
            extracted_lower = extracted_name.lower()
            if 'vanessa thomas' in extracted_lower or 'vanessa' in extracted_lower:
                # Vanessa Thomas is NOT a driver (different from Chantal Thomas)
                continue
            if 'mike woodrow' in extracted_lower:
                # Mike Woodrow is rent/vehicle repairs, not driver
                continue
            if 'david richard' in extracted_lower or 'david w richard' in extracted_lower:
                # David Richard is loan payments, not driver
                continue
            
            # Try to match to a driver
            best_match = None
            best_ratio = 0.0
            best_employee_id = None
            
            for emp_id, driver_info in driver_lookup.items():
                for name_variant in driver_info['name_variants']:
                    is_match, ratio = fuzzy_match(extracted_name, name_variant, threshold=0.75)
                    
                    if is_match and ratio > best_ratio:
                        best_match = driver_info['full_name']
                        best_ratio = ratio
                        best_employee_id = emp_id
            
            if best_match:
                matches.append({
                    'etrans_id': etrans_id,
                    'direction': direction,
                    'date': tdate,
                    'amount': amount,
                    'current_category': current_cat,
                    'description': description,
                    'extracted_name': extracted_name,
                    'matched_driver': best_match,
                    'employee_id': best_employee_id,
                    'confidence': best_ratio
                })
        
        print(f"   Already categorized as driver_pay: {already_driver_pay:,}")
        print(f"   New matches found: {len(matches):,}")
        
        # Show results
        print("\n" + "="*100)
        print("DRIVER PAYMENT MATCHES")
        print("="*100)
        
        if matches:
            print(f"\n{'Dir':<4} | {'Date':<12} | {'Amount':>12} | {'Extracted Name':<25} | {'Matched Driver':<30} | {'Confidence':>10}")
            print("-" * 100)
            
            # Sort by amount descending
            matches.sort(key=lambda x: x['amount'], reverse=True)
            
            for match in matches[:50]:
                print(f"{match['direction']:<4} | {str(match['date']):<12} | ${match['amount']:>11,.2f} | "
                      f"{match['extracted_name'][:25]:<25} | {match['matched_driver'][:30]:<30} | {match['confidence']:>9.1%}")
            
            if len(matches) > 50:
                print(f"\n... and {len(matches) - 50} more matches")
            
            # Summary by driver
            print("\n" + "="*100)
            print("SUMMARY BY DRIVER")
            print("="*100)
            
            driver_summary = {}
            for match in matches:
                driver_name = match['matched_driver']
                if driver_name not in driver_summary:
                    driver_summary[driver_name] = {
                        'count': 0,
                        'total': 0,
                        'incoming': 0,
                        'outgoing': 0,
                        'in_count': 0,
                        'out_count': 0
                    }
                
                driver_summary[driver_name]['count'] += 1
                driver_summary[driver_name]['total'] += match['amount']
                
                if match['direction'] == 'IN':
                    driver_summary[driver_name]['incoming'] += match['amount']
                    driver_summary[driver_name]['in_count'] += 1
                else:
                    driver_summary[driver_name]['outgoing'] += match['amount']
                    driver_summary[driver_name]['out_count'] += 1
            
            print(f"\n{'Driver Name':<40} | {'Total':>12} | {'Count':>6} | {'IN':>6} | {'IN $':>12} | {'OUT':>6} | {'OUT $':>12}")
            print("-" * 100)
            
            for driver_name in sorted(driver_summary.keys(), key=lambda x: driver_summary[x]['total'], reverse=True):
                summary = driver_summary[driver_name]
                print(f"{driver_name[:40]:<40} | ${summary['total']:>11,.2f} | {summary['count']:>6,} | "
                      f"{summary['in_count']:>6,} | ${summary['incoming']:>11,.2f} | "
                      f"{summary['out_count']:>6,} | ${summary['outgoing']:>11,.2f}")
            
            # Update database
            if not DRY_RUN:
                print("\n4. Updating database...")
                
                updated = 0
                for match in matches:
                    cur.execute("""
                        UPDATE etransfer_transactions
                        SET category = 'driver_pay',
                            category_description = 'Driver pay',
                            notes = COALESCE(notes || '; ', '') || 
                                    'Matched to driver: ' || %s || 
                                    ' (confidence: ' || %s || 
                                    ', extracted name: ' || %s || ')'
                        WHERE etransfer_id = %s
                    """, (match['matched_driver'], 
                          f"{match['confidence']:.1%}", 
                          match['extracted_name'],
                          match['etrans_id']))
                    updated += 1
                
                conn.commit()
                print(f"   ✓ Updated {updated:,} e-transfers to driver_pay category")
                print("\n[SUCCESS] Categorization completed.")
            else:
                conn.rollback()
                print("\n[DRY RUN] No changes made to database.")
                print(f"Would update {len(matches):,} e-transfers to driver_pay category.")
                print("Run with --write to apply changes.")
        else:
            print("\nNo new driver payment matches found.")
            conn.rollback()
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()
    
    print("\n" + "="*100)

if __name__ == '__main__':
    main()
