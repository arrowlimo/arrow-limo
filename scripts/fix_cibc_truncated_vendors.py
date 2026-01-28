"""
Fix truncated CIBC vendor names based on receipt data analysis.

This uses actual vendor names from receipts to restore proper business names
that were truncated by previous cleanup operations or OCR imports.
"""
import psycopg2
import argparse
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

# Vendor name corrections based on receipt analysis
VENDOR_CORRECTIONS = {
    # ATM/ABM withdrawals - remove location codes and standardize
    'Automated Banking Machine ATM WITHDRAWAL GAETZ AVE + 67TH ST 2D54': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL GAETZ AVE + 67TH ST 1E0U': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL GAETZ AVE + 22ND ST 1A66': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL GAETZ AVE + 22ND ST 1F2X': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL GAETZ AVE + 22ND ST 2C92': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL GAETZ AVE and 67TH ST 2D54': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL GAETZ AVE and 67TH ST 1E0U': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL GAETZ AVE and 22ND ST 2C92': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL INTERAC/RBC SCD 0003': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL INTERAC/TNS SCD 1127': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL INTERAC/CCCS SCD 0869': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL CLEARVIEW BKNG CTR 1A0N': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL CLEARVIEW BKNG CTR 2B90': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL INTERAC/BNS SCD 0002': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL INTERAC/TD SCD 0004': 'ATM Withdrawal',
    'Automated Banking Machine ATM WITHDRAWAL NORTHLAND BANKING CENTRE 1B2D': 'ATM Withdrawal',
    'ABM WITHDRAWAL 2CQQ 7-ELEVEN 99512': 'ATM Withdrawal',
    'ABM WITHDRAWAL 2D54 GAETZ AVE + 67TH ST': 'ATM Withdrawal',
    'ABM WITHDRAWAL 2D54 GAETZ AVE + 67TH ST 00339 4506*********359': 'ATM Withdrawal',
    '[QB: Shareholder Loans] ABM WITHDRAWAL 2CQ0 7-ELEVEN 99512': 'ATM Withdrawal',
    '[QB: Shareholder Loans] ABM WITHDRAWAL 2CQ0 7-ELEVEN 99512 4506*********359': 'ATM Withdrawal',
    '[QB: Shareholder Loans] ABM WITHDRAWAL 2D54 GAETZ AVE + 67TH ST': 'ATM Withdrawal',
    '[QB: Shareholder Loans] ABM WITHDRAWAL 1A66 GAETZ AVE + 22ND ST': 'ATM Withdrawal',
    '[QB: Shareholder Loans] ABM WITHDRAWAL 1A95 7-ELEVEN 33502': 'ATM Withdrawal',
    '[QB: Shareholder Loans] ABM WITHDRAWAL 2C02 7-ELEVEN 99512': 'ATM Withdrawal',
    'ABM WITHDRAWAL 1A95 GAETZ AVE + 22ND': 'ATM Withdrawal',
    'Automated Banking Machine ATM TRANSFER GAETZ AVE + 67TH ST 2D54': 'ATM Transfer',
    
    # Instant Teller withdrawals
    'Automated Banking Machine INSTANT TELLER WITHDRAWAL GAETZ AVE + 67TH ST 2D54': 'ATM Withdrawal',
    'Automated Banking Machine INSTANT TELLER WITHDRAWAL GAETZ AVE + 67TH ST 1E0U': 'ATM Withdrawal',
    'Automated Banking Machine INSTANT TELLER WITHDRAWAL INTERAC/RBC SCD 0003': 'ATM Withdrawal',
    'Automated Banking Machine INSTANT TELLER WITHDRAWAL INTERAC/BNS SCD 0002': 'ATM Withdrawal',
    
    # Branch withdrawals
    'Branch Transaction WITHDRAWAL IBB GAETZ AVE & 67TH ST BANKING CE': 'Branch Withdrawal',
    'Branch Transaction WITHDRAWAL': 'Branch Withdrawal',
    '[QB: Shareholder Loans] WITHDRAWAL': 'Branch Withdrawal',
    '[QB: Shareholder Loans] WITHDRAWAL TRANSFER TO: 00339/02-28362': 'Branch Transfer',
    
    # Bank fees
    'Branch Transaction NON-SUFFICIENT FUNDS CHARGE': 'NSF Fee',
    'NSF CHARGE 00339': 'NSF Fee',
    'Branch Transaction SERVICE CHARGE': 'Bank Service Charge',
    'Branch Transaction OVERDRAFT INTEREST CHARGE': 'Overdraft Interest',
    'Branch Transaction OVERDRAFT FEE': 'Overdraft Fee',
    'OVERDRAFT INTEREST': 'Overdraft Interest',
    'OVERDRAFT S/C': 'Overdraft Service Charge',
    'ACCOUNT FEE': 'Account Fee',
    'PAPER STMT/MT FEE': 'Statement Fee',
    
    # E-Transfer fees
    'Branch Transaction E-TRANSFER NETWORK FEE': 'E-Transfer Fee',
    'E-TRANSFER NWK FEE': 'E-Transfer Fee',
    'Electronic Funds Transfer NETWORK TRANSACTION FEE ATM-CANADA/GAB-CANADA': 'ATM Network Fee',
    'Electronic Funds Transfer NETWORK TRANSACTION FEE ABM-CANADA/GAB-CANADA': 'ATM Network Fee',
    
    # Heffner Auto Finance leases/payments
    'Electronic Funds Transfer PREAUTHORIZED DEBIT HEFFNER AUTO': 'Heffner Auto Finance',
    'Electronic Funds Transfer PREAUTHORIZED DEBIT HEFFNER AUTO FC': 'Heffner Auto Finance',
    'RENT/LEASE 000000000000000 LEASE FINANCE GR': 'Lease Finance Group',
    'RENT/LEASE Heffner Auto FC': 'Heffner Auto Finance',
    'RENT/LEASE HEFFNER AUTO FC': 'Heffner Auto Finance',
    'RENT/LEASE HEFFNER AUTO FC (NSF)': 'Heffner Auto Finance (NSF)',
    'RENT/LEASE Dec11 PMT Heffner Auto FC': 'Heffner Auto Finance',
    'PRE-AUTH DEBIT 80652200000004 LFG': 'Lease Finance Group',
    'PRE-AUTH DEBIT 68483200000004 LFG': 'Lease Finance Group',
    'PRE-AUTH DEBIT 8065220000000035 LFG': 'Lease Finance Group',
    'PRE-AUTH DEBIT 80652200000035 LFG': 'Lease Finance Group',
    'PRE-AUTH DEBIT 80652200000109 LFG': 'Lease Finance Group',
    'PRE-AUTH DEBIT LFG BUSINESS PAD': 'Lease Finance Group',
    'RENT/LEASE L08136 JACK CARTER': 'Jack Carter',
    'RENT/LEASE L08136 JACK CARTER (NSF)': 'Jack Carter (NSF)',
    
    # Insurance companies
    'Electronic Funds Transfer PREAUTHORIZED DEBIT FIRST INSURANCE': 'First Insurance',
    'INSURANCE Cooperators CSI': 'Cooperators Insurance',
    'INSURANCE Coaperation CSI': 'Cooperators Insurance',
    'INSURANCE IFS PREMIUM FIN': 'IFS Premium Finance',
    'INSURANCE JEVCO INSURANCE COMPANY': 'Jevco Insurance',
    'INSURANCE OPTIMUM WEST INSURANCE COMPANY': 'Optimum West Insurance',
    'INSURANCE OPTIMUM WEST INSURANCE CO': 'Optimum West Insurance',
    'INSURANCE CO-OPERATORS': 'Cooperators Insurance',
    'Cheque #Auto Optimum West Insur. .. -91.86': 'Optimum West Insurance',
    'Cheque #Auto IFS Premium Finance -1,654.94': 'IFS Premium Finance',
    
    # Merchant services
    'DEBIT MEMO MERCH#4017775 GBL MERCH FEES': 'Merchant Services Fee',
    'DEBIT MEMO REPRESENTED DR GBL MERCH FEES': 'Merchant Services Fee',
    'DEBIT MEMO 4017775 VISA': 'Visa Merchant Fee',
    'DEBIT MEMO 4017775 MC': 'MasterCard Merchant Fee',
    '[QB: Shareholder Loans] DEBIT MEMO': 'Merchant Services Fee',
    
    # Other financial institutions
    'Electronic Funds Transfer PREAUTHORIZED DEBIT WOODRIDGE FORD': 'Woodridge Ford',
    'Electronic Funds Transfer PREAUTHORIZED DEBIT National Money Mart Com': 'Money Mart',
    'Electronic Funds Transfer PREAUTHORIZED DEBIT SQUARE, INC. SQUARE INC': 'Square Payment Processing',
    'Electronic Funds Transfer PREAUTHORIZED DEBIT ASI FINANCE': 'ASI Finance',
    'Electronic Funds Transfer PREAUTHORIZED DEBIT MORTGAGEPROTECT': 'Mortgage Protection',
    
    # Gas stations and fuel
    'PURCHASE Centex Petroleu': 'Centex',
    'PURCHASE CENTEX DEERPARK': 'Centex Deerpark',
    'Cheque #DD Centex': 'Centex',
    'Cheque #DD Centex X': 'Centex',
    'Cheque #dd Centex X': 'Centex',
    'Cheque #Centex X': 'Centex',
    'PURCHASE MOHAWK RED DEER': 'Mohawk',
    'Cheque #DD Fas Gas Plus': 'Fas Gas Plus',
    'Cheque #dd Fas Gas Plus X': 'Fas Gas Plus',
    '[QB: -SPLIT-] Cheque #DD Fas Gas Plus': 'Fas Gas Plus',
    'Cheque #DD Husky': 'Husky',
    'Cheque #DD Husky X': 'Husky',
    'PURCHASE Hertz': 'Hertz',
    '[QB: -SPLIT-] PURCHASE#000001001167 VICTORIA ESSO #': 'Esso',
    
    # Liquor stores
    'PURCHASE 604 - LB 67TH S': 'Liquor Barn 67th St',
    'Cheque #DD 67th Street Liquor': '67th Street Liquor',
    'Cheque #DD 67th Street Liquor X': '67th Street Liquor',
    'Cheque #dd 67th Street Liquor X': '67th Street Liquor',
    '[QB: -SPLIT-] Cheque #DD 67th Street Liquor': '67th Street Liquor',
    '[QB: -SPLIT-] Cheque #dd 67th Street Liquor X': '67th Street Liquor',
    'Cheque #dd Liquor Barn 67th Sir ... X': 'Liquor Barn 67th St',
    'Cheque #dd Liquor Barn 67th Str. .. X': 'Liquor Barn 67th St',
    'Point of Sale - Interac RETAIL PURCHASE 000001078131 PLENTY OF LIQUO': 'Plenty of Liquor',
    'Point of Sale - Interac RETAIL PURCHASE 000001078129 PLENTY OF LIQUO': 'Plenty of Liquor',
    'Point of Sale - Interac RETAIL PURCHASE 000001078134 PLENTY OF LIQUO': 'Plenty of Liquor',
    'Point of Sale - Interac RETAIL PURCHASE 000001078253 PLENTY OF LIQUO': 'Plenty of Liquor',
    'Point of Sale - Interac RETAIL PURCHASE 000001078389 PLENTY OF LIQUO': 'Plenty of Liquor',
    'Point of Sale - Interac RETAIL PURCHASE 000001078492 PLENTY OF LIQUOR': 'Plenty of Liquor',
    'Point of Sale - Interac RETAIL PURCHASE 000001078493 PLENTY OF LIQUOR': 'Plenty of Liquor',
    'Point of Sale - Interac RETAIL PURCHASE 000001078494 PLENTY OF LIQUOR': 'Plenty of Liquor',
    'Point of Sale - Interac RETAIL PURCHASE 000001155487 PLENTY OF LIQUO': 'Plenty of Liquor',
    'Point of Sale - Interac RETAIL PURCHASE 000001155789 PLENTY OF LIQUO': 'Plenty of Liquor',
    
    # Retail stores
    'PURCHASE Erles Auto Repa': 'Erles Auto Repair',
    '[QB: -SPLIT-] PURCHASE#000001351001 ERLES AUTO REPA': 'Erles Auto Repair',
    'PURCHASE STAPLES# 72': 'Staples',
    '[QB: -SPLIT-] PURCHASE#000001001142 STAPLES#285': 'Staples',
    '[QB: -SPLIT-] PURCHASE#000001001799 CANADIAN TIRE #': 'Canadian Tire',
    'Cheque #DD Canadian Tire. -53.16': 'Canadian Tire',
    'Cheque #DD Warehouse One -128.59': 'Warehouse One',
    '[QB: -SPLIT-] PURCHASE#000001001009 PRINCESS AUTO': 'Princess Auto',
    '[QB: -SPLIT-] PURCHASE#000001266001 PARR AUTOMOTIVE': 'Parr Automotive',
    'PURCHASE The Phone Exper': 'The Phone Expert',
    
    # Restaurants
    '[QB: -SPLIT-] PURCHASE#000001192005 GEORGE\'S PIZZA': 'George\'s Pizza',
    '[QB: -SPLIT-] PURCHASE#000001248004 MONGOLIA GRILL': 'Mongolia Grill',
    '[QB: -SPLIT-] Cheque #DD Ranch House': 'Ranch House',
    '[QB: -SPLIT-] Cheque #dd Ranch House X': 'Ranch House',
    
    # Gas stations with QuickBooks tags
    '[QB: -SPLIT-] PURCHASE#000001155160 RUN\'N ON EMPTY': 'Run\'n On Empty',
    '[QB: -SPLIT-] PURCHASE#000001157068 RUN\'N ON EMPTY': 'Run\'n On Empty',
    
    # Utilities/Communications
    '[QB: 215958149 4] INTERNET BILL PMT TELUS COMMUNICATIONS': 'Telus',
    
    # Credit card payments
    'MISC PAYMENT AMEX 9320382063': 'American Express Payment',
    'MISC PAYMENT AMEX 9320382063 AMEX BANK': 'American Express Payment',
    
    # Co-op locations
    'Cheque #dd Co-op Deer Park Ce. .. X': 'Co-op Deer Park',
    
    # Bank charges cleanup
    'Cheque #dd Bank Charges & Int... X': 'Bank Charges & Interest',
    'Cheque #dd Bank Charges & Int.. . X': 'Bank Charges & Interest',
    
    # Employee names - remove QuickBooks tags
    '[QB: Shareholder Loans] Cheque #TSF': 'Employee Transfer',
    '[QB: Shareholder Loans] Cheque #Tsf Paul Richard (v) X': 'Paul Richard',
    '[QB: Shareholder Loans] Cheque #TSF X': 'Employee Transfer',
    '[QB: Shareholder Loans] Cheque #w/d Paul Richard (v) X': 'Paul Richard',
    '[QB: Shareholder Loans] Cheque #WD': 'Employee Withdrawal',
    'Cheque #249 Mark Linton X': 'Mark Linton',
    'Cheque #Heffner Lexus Toyota': 'Heffner Lexus Toyota',
    
    # Generic cheques
    'Cheque #-110.51': 'Cheque Payment',
    'Cheque #-61.15': 'Cheque Payment',
    '[QB: -SPLIT-] Cheque #-1,585.33': 'Cheque Payment',
    '[QB: -SPLIT-] Cheque #-412.32': 'Cheque Payment',
    
    # Generic purchases
    'PURCHASE': 'Purchase',
    '[QB: Shareholder Loans] PURCHASE': 'Purchase',
    
    # Business expenses
    'Business Expense - CIBC (from ledger staging)': 'Business Expense',
}

def main():
    parser = argparse.ArgumentParser(description='Fix truncated CIBC vendor names')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 80)
    print("FIXING CIBC TRUNCATED VENDOR NAMES")
    print("=" * 80)
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print()
    
    # Count how many transactions will be updated
    total_updates = 0
    updates_by_category = {}
    
    for old_name, new_name in VENDOR_CORRECTIONS.items():
        cur.execute("""
            SELECT COUNT(*) 
            FROM banking_transactions 
            WHERE account_number = '0228362'
            AND description = %s
        """, (old_name,))
        count = cur.fetchone()[0]
        if count > 0:
            total_updates += count
            # Group by category for better reporting
            category = new_name.split()[0] if ' ' in new_name else new_name
            updates_by_category[category] = updates_by_category.get(category, 0) + count
            print(f"{count:4d} × '{old_name[:60]}...' → '{new_name}'")
    
    print()
    print(f"Total transactions to update: {total_updates}")
    print("\nBreakdown by category:")
    for category, count in sorted(updates_by_category.items(), key=lambda x: -x[1]):
        print(f"  {count:4d} × {category}")
    
    if not args.write:
        print("\n*** DRY-RUN MODE - No changes will be made ***")
        print("Run with --write to apply changes")
        cur.close()
        conn.close()
        return
    
    # Create backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'banking_transactions_cibc_vendor_fix_backup_{timestamp}'
    
    print(f"\nCreating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS 
        SELECT * FROM banking_transactions 
        WHERE account_number = '0228362'
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
            WHERE account_number = '0228362'
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
