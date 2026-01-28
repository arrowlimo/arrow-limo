#!/usr/bin/env python3
"""
Quick Vendor Standardization - Apply common patterns automatically

This script applies pre-defined standardization rules for common vendor patterns.
Run this BEFORE using the interactive tool to handle the easy cases automatically.
"""

import psycopg2
import os

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': os.environ.get('DB_PASSWORD', '***REMOVED***')
}

# Pre-defined standardization rules
STANDARDIZATION_RULES = {
    # Card deposits (Global Payments)
    'GLOBAL VISA DEPOSIT': ['VCARD DEPOSIT', 'VCARD DEPOSIT 2', 'GBL VI', 'GLOBAL VI'],
    'GLOBAL MASTERCARD DEPOSIT': ['MCARD DEPOSIT', 'GBL MC', 'GLOBAL MC'],
    'GLOBAL AMEX DEPOSIT': ['ACARD DEPOSIT', 'GBL AX', 'GLOBAL AX'],
    'DEBIT CARD DEPOSIT': ['DCARD DEPOSIT'],
    
    # Card payments (chargebacks/fees)
    'GLOBAL VISA PAYMENT': ['VCARD PAYMENT'],
    'GLOBAL MASTERCARD PAYMENT': ['MCARD PAYMENT'],
    'GLOBAL AMEX PAYMENT': ['ACARD PAYMENT'],
    'DEBIT CARD PAYMENT': ['DCARD PAYMENT'],
    
    # Banking fees
    'BANKING FEE': ['SERVICE CHARGE', 'MONTHLY FEE', 'ACCOUNT FEE'],
    'EMAIL TRANSFER FEE': ['EMAIL MONEY TRANSFER FEE', 'EMAIL MONEY TRANSFER FEE 2', 'EMAIL MONEY TRANSFER FEE 3', 'E-TRANSFER FEE'],
    'ATM FEE': ['ABM FEE', 'ATM WITHDRAWAL FEE'],
    'NSF FEE': ['NSF CHARGE', 'NSF'],
    'OVERDRAFT INTEREST': ['OVERDRAFT CHARGE'],
    
    # Gas stations
    'FAS GAS': ['FASGAS', 'FAS GAS PLUS', 'FAS GAS & WASH'],
    'CENTEX': ['CENTEX GAS', 'CENTEX PETROLEUM'],
    'CO-OP': ['CO-OP GAS', 'CO OP', 'COOP'],
    'SHELL': ['SHELL CANADA', 'SHELL GAS'],
    'ESSO': ['ESSO CANADA', 'IMPERIAL OIL'],
    'HUSKY': ['HUSKY CANADA'],
    'PETRO-CANADA': ['PETRO CANADA', 'PETROCANADA'],
    
    # Restaurants
    'TIM HORTONS': ['TIM HORTON', 'TIMS', 'TIM HORTONS #'],
    'MCDONALDS': ['MCDONALD\'S', 'MC DONALDS', 'MCDONALDS #'],
    'SUBWAY': ['SUBWAY SANDWICHES'],
    'A&W': ['A & W', 'A AND W'],
    'DAIRY QUEEN': ['DAIRY QUEEN #26', 'DAIRY QUEEN #27', 'DQ'],
    
    # Retail
    'WALMART': ['WAL-MART', 'WAL MART'],
    'REAL CANADIAN SUPERSTORE': ['REAL CANADIAN SUPER STORE', 'RCSS'],
    'COSTCO': ['COSTCO WHOLESALE'],
    'SAFEWAY': ['SAFEWAY CANADA'],
    'SOBEYS': ['SOBEYS CANADA'],
    'STAPLES': ['STAPLES BUSINESS DEPOT'],
    
    # Liquor stores
    'LIQUOR BARN': ['THE LIQUOR BARN'],
    'LIQUOR DEPOT': ['THE LIQUOR DEPOT'],
    'ACE LIQUOR': ['ACE LIQUOR STORE', 'ACE LIQUOR STORES'],
    
    # Financial
    'HEFFNER TOYOTA': ['HEFFNER AUTO FINANCE', 'HEFFNER TOYOTA SCION', 'HEFFNER FINANCE'],
    'LEASE FINANCE GROUP': ['LFG', 'LEASE FINANCE', 'ROYNAT LEASE FINANCE'],
    
    # Government
    'WCB': ['WCB ALBERTA', 'WORKERS COMPENSATION BOARD'],
    'CITY OF RED DEER': ['CITY OF RED DEER UTILITIES'],
    'REVENUE CANADA': ['CRA', 'CANADA REVENUE AGENCY'],
    
    # Utilities
    'TELUS': ['TELUS COMMUNICATIONS'],
    'SHAW': ['SHAW CABLE', 'SHAW COMMUNICATIONS'],
    'ENMAX': ['ENMAX ENERGY'],
    'ATCO': ['ATCO GAS', 'ATCO ELECTRIC'],
    
    # Professional services
    'ACCOUNTING FOR SUCCESS': ['ACCOUNTING SUCCESS', 'ACCOUNTING 4 SUCCESS'],
    
    # Generic transfers
    'CASH WITHDRAWAL': ['CASH', 'CASH OUT', 'ATM CASH WITHDRAWAL'],
    'INTERNAL TRANSFER': ['TRANSFER', 'E-TRANSFER', 'FUNDS TRANSFER'],
    'EMAIL TRANSFER': ['INTERAC E-TRANSFER'],
    'SQUARE DEPOSIT': ['SQUARE', 'SQUARE INC'],
    'CHEQUE DEPOSIT': ['CHEQUE', 'CHECK DEPOSIT'],
    'UNKNOWN': ['UNKNOWN PAYEE', 'PAYEE UNKNOWN', 'NO PAYEE'],
}


def apply_quick_standardizations(dry_run=True):
    """Apply pre-defined standardization rules"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("=" * 100)
    print("QUICK VENDOR STANDARDIZATION")
    print("=" * 100)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'APPLYING CHANGES'}")
    print()
    
    total_updated = 0
    
    for canonical, variations in sorted(STANDARDIZATION_RULES.items()):
        print(f"\n📌 {canonical}")
        print(f"   Variations: {', '.join(variations)}")
        
        updated_count = 0
        
        for variation in variations:
            # Update receipts where vendor_name matches
            cur.execute("""
                SELECT COUNT(*)
                FROM receipts
                WHERE vendor_name ILIKE %s
                  AND (canonical_vendor IS NULL OR canonical_vendor != %s)
            """, (variation, canonical))
            count = cur.fetchone()[0]
            
            if count > 0:
                print(f"   → {variation}: {count} receipts")
                
                if not dry_run:
                    cur.execute("""
                        UPDATE receipts
                        SET canonical_vendor = %s
                        WHERE vendor_name ILIKE %s
                          AND (canonical_vendor IS NULL OR canonical_vendor != %s)
                    """, (canonical, variation, canonical))
                
                updated_count += count
        
        if updated_count > 0:
            print(f"   ✓ Total for {canonical}: {updated_count} receipts")
            total_updated += updated_count
    
    if dry_run:
        print("\n" + "=" * 100)
        print(f"DRY RUN COMPLETE - Would update {total_updated} receipts")
        print("Run with --apply to actually make these changes")
        print("=" * 100)
        conn.rollback()
    else:
        conn.commit()
        print("\n" + "=" * 100)
        print(f"SUCCESS - Updated {total_updated} receipts")
        print("=" * 100)
    
    conn.close()


def main():
    import sys
    
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        dry_run = False
    
    apply_quick_standardizations(dry_run)


if __name__ == '__main__':
    main()
