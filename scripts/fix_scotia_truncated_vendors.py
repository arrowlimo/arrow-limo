"""
Fix remaining truncated Scotia vendor names based on 2012-2014 receipt data.

This uses actual vendor names from receipts to restore proper business names
that were truncated by previous cleanup operations.
"""
import psycopg2
import argparse
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

# Vendor name corrections based on receipt analysis
VENDOR_CORRECTIONS = {
    # Run'n On Empty locations
    'RUN\'N ON EMPTY RED D': 'Run\'n On Empty 50th Ave',
    'Run\'n On Empty': 'Run\'n On Empty 50th Ave',
    
    # Liquor stores
    '67TH ST. RED D': 'Liquor Barn 67th St',
    'Liquor Barn 67th Sir': 'Liquor Barn 67th St',
    'Liquor Barn 67th Str': 'Liquor Barn 67th St',
    
    # Gas stations
    'Centex (C-STOR': 'Centex Deerpark',
    'MOHAWK RED DEER': 'Mohawk',
    'Petro Canada': 'Petro-Canada',
    'PETRO-CANADA': 'Petro-Canada',
    
    # Tire stores
    'CANADIAN TIRE': 'Canadian Tire',
    'Canadian Tire.': 'Canadian Tire',
    
    # Financial/merchant services
    'Chase Paymentech': 'Merchant Services Fee',
    'Global Merchant Fees': 'Merchant Services Fee',
    
    # Liquor stores
    'Plaza Liquor Store': 'Plaza Liquor',
    'Liquor Depot': 'Liquor Depot',
    'Global Liquor Store': 'Global Liquor',
    'Liquor Town': 'Liquor Town',
    
    # Auto services
    'ERLES AUTO REPAIR': 'Erles Auto Repair',
    'ERLES AUTO REPAIR RED D': 'Erles Auto Repair',
    'MGM Ford': 'MGM Ford',
    
    # Insurance
    'Jevco Insurance': 'Jevco Insurance',
    'IFS Premium Finance': 'IFS Premium Finance',
    'Cooperators CSI': 'Cooperators Insurance',
    'Optimum West Insur': 'Optimum West Insurance',
    'Optimum West lnsu': 'Optimum West Insurance',
    
    # Registries
    'Red Deer Registries': 'Red Deer Registries',
    
    # Office supplies
    'Staples': 'Staples',
    'STAPLES#285': 'Staples',
    
    # Restaurants/hospitality
    'KUMA HOSPITALITY -': 'Kuma Hospitality',
    'Phil\'s Restaurant': 'Phil\'s Restaurant',
    'MCDONALD\'S': 'McDonald\'s',
    
    # Retail
    'WAL-MART': 'Walmart',
    'CANADA SAFEWAY': 'Safeway',
    'A Buck or Two': 'A Buck or Two',
    'BUCK OR TWO': 'A Buck or Two',
    'Future Shop Red Deer': 'Future Shop',
    'CINEPLEX QPS': 'Cineplex',
    'Mr Suds': 'Mr Suds',
    
    # Truck rental
    'Rent/Lease ACE TRUCK RENTALS LTD.': 'Ace Truck Rentals',
    'Ace Truck': 'Ace Truck Rentals',
    
    # Co-op locations
    'Co-op Deer Park Ce': 'Co-op Deer Park',
    'RED DEER CO-OP QPE': 'Co-op Red Deer',
    
    # Money services
    'Money Mart': 'Money Mart',
    'MONEY MART': 'Money Mart',
    'NATIONAL MONEYMART': 'Money Mart',
    
    # Esso/Essa typo
    'Essa': 'Esso',
    
    # Gas stations with store codes
    'FAS GAS EASTHILL SVC #': 'Fas Gas Easthill',
    'FAS GAS WESTPARK SVC #': 'Fas Gas Westpark',
    'CANADIAN TIRE GAS BAR': 'Canadian Tire Gas Bar',
    
    # Bank transaction descriptions
    'ATM Withdrawal BRANCH': 'ATM Withdrawal',
    'ATM Withdrawal & 67TH 1': 'ATM Withdrawal',
    'SHARED ABM WITHDRAWAL': 'ATM Withdrawal',
    'ABM WITHDRAWAL RED DEER BRANCH RED DEER AB': 'ATM Withdrawal',
    
    # QuickBooks tags to remove
    '[QB: Shareholder Loans] Paul Richard (v)': 'Paul Richard',
    '[QB: 215958149 4] Telus Communicatio': 'Telus Communications',
    '[DUPLICATE?] AUTO LEASE HEFFNER AUTO FC': 'Heffner Auto Finance Lease',
    
    # Lease descriptions
    'AUTO LEASE HEFFNER AUTO FC': 'Heffner Auto Finance Lease',
    'AUTO LEASE': 'Auto Lease Payment',
    'Rent/Lease HEFFNER AUTO FC': 'Heffner Auto Finance Lease',
    'LFG Business PAD': 'Lease Finance Group',
    
    # Credit card payments
    'AMEX BANK OF CANADA': 'American Express Payment',
    'AMEX': 'American Express Payment',
    'AMEX 9322877839': 'American Express Payment',
    
    # NSF and bank fees
    'RETURNED NSF CHEQUE': 'NSF Returned Cheque',
    'Returned Cheque - NSF': 'NSF Returned Cheque',
    'OVERDRAFT INTEREST CHG': 'Overdraft Interest',
    'Overdrawn Handling Chg.': 'Overdraft Fee',
    'OVERDRAWN HANDLING CHGS': 'Overdraft Fee',
    'SERVICE CHARGE': 'Bank Service Charge',
    'Service Charge': 'Bank Service Charge',
    'Bank Charges & Int': 'Bank Charges & Interest',
    'Bank Charges & Int. ..': 'Bank Charges & Interest',
    'Bank Charges & Int...': 'Bank Charges & Interest',
    
    # Draft transactions
    'DRAFT PURCHASE': 'Bank Draft',
    'OTHER CREDIT MEMO RETURN ITEM': 'Returned Item Credit',
    'VISA DEP DR': 'Visa Deposit',
    
    # Employee names standardization
    'Paul Richard (v)': 'Paul Richard',
    'Cheque w/d Paul Richard (v)': 'Paul Richard',
    'Paul Mansell': 'Paul Mansell',
    'Jack Carter': 'Jack Carter',
    'Angel Escobar': 'Angel Escobar',
    'Dale Mernard': 'Dale Mernard',
    'Jeannie Shillington': 'Jeannie Shillington',
    'Jesse Gordon': 'Jesse Gordon',
    'Dustan Townsend': 'Dustan Townsend',
    'Douglas Redmond': 'Douglas Redmond',
    'Heffner, Will': 'Will Heffner',
}

def main():
    parser = argparse.ArgumentParser(description='Fix truncated Scotia vendor names')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("FIXING SCOTIA TRUNCATED VENDOR NAMES")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print()
    
    # Count how many transactions will be updated
    total_updates = 0
    for old_name, new_name in VENDOR_CORRECTIONS.items():
        cur.execute("""
            SELECT COUNT(*) 
            FROM banking_transactions 
            WHERE account_number = '903990106011'
            AND description = %s
        """, (old_name,))
        count = cur.fetchone()[0]
        if count > 0:
            total_updates += count
            print(f"{count:4d} × '{old_name}' → '{new_name}'")
    
    print()
    print(f"Total transactions to update: {total_updates}")
    
    if not args.write:
        print("\n*** DRY-RUN MODE - No changes will be made ***")
        print("Run with --write to apply changes")
        cur.close()
        conn.close()
        return
    
    # Create backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'banking_transactions_vendor_fix_backup_{timestamp}'
    
    print(f"\nCreating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM banking_transactions 
        WHERE account_number = '903990106011'
        AND description IN ({','.join(['%s'] * len(VENDOR_CORRECTIONS))})
    """, tuple(VENDOR_CORRECTIONS.keys()))
    
    backup_count = cur.rowcount
    print(f"✓ Backed up {backup_count} rows")
    
    # Apply updates
    print("\nApplying updates...")
    updated_count = 0
    
    for old_name, new_name in VENDOR_CORRECTIONS.items():
        cur.execute("""
            UPDATE banking_transactions 
            SET description = %s
            WHERE account_number = '903990106011'
            AND description = %s
        """, (new_name, old_name))
        
        count = cur.rowcount
        if count > 0:
            updated_count += count
    
    conn.commit()
    print(f"✓ Updated {updated_count} transaction descriptions")
    print(f"✓ Backup table: {backup_table}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    main()
