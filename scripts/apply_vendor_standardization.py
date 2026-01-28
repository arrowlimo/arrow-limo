#!/usr/bin/env python3
"""
Apply comprehensive vendor name standardization to banking and receipts
Uses patterns from verified 2012-2014 banking data
"""
import psycopg2
import re
import sys

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

receipts_only = '--receipts-only' in sys.argv or '--skip-banking' in sys.argv

def standardize_vendor_name(vendor):
    """Apply standardization rules to vendor name"""
    if not vendor:
        return None
    
    # Convert to uppercase and clean
    vendor = vendor.upper().strip()
    
    # Remove masked card numbers and collapse whitespace early
    vendor = re.sub(r"\d{4}\*+\d{3}", "", vendor)
    vendor = re.sub(r"\s+", " ", vendor).strip()

    # Normalize common placeholders from QB/GL cheque stubs
    if vendor.startswith("UNKNOWN PAYEE"):
        return "UNKNOWN PAYEE"

    # Bill Payment (Cheque) - PAYEE -> BILL PAYMENT - PAYEE
    bill_cheque_match = re.match(r"BILL PAYMENT\s*\(CHEQUE\)\s*-\s*(.+)", vendor)
    if bill_cheque_match:
        return f"BILL PAYMENT - {bill_cheque_match.group(1).strip()}"

    # Generic cheque placeholder with payee text
    cheque_payee_match = re.match(r"CHEQUE[#\s-]*(.+)", vendor)
    if cheque_payee_match:
        normalized_payee = cheque_payee_match.group(1).strip()
        # Special case: FAS GAS is just FAS GAS (no PLUS, no CHEQUE prefix)
        if 'FAS GAS' in normalized_payee or 'FASGAS' in normalized_payee:
            return "FAS GAS"
        return f"CHEQUE {normalized_payee}" if normalized_payee else "CHEQUE"

    # Remove extra spaces
    vendor = re.sub(r'\s+', ' ', vendor)
    
    # Pattern-based standardizations
    
    # Gas stations with numbers
    if 'FAS GAS' in vendor or 'FASGAS' in vendor:
        # Remove PLUS, location/transaction numbers
        return "FAS GAS"
    
    if 'SHELL' in vendor:
        return "SHELL"
    
    if 'CO-OP' in vendor or 'COOP' in vendor:
        if 'INSURANCE' in vendor:
            return "CO-OP INSURANCE"
        return "CO-OP"
    
    if 'PETRO' in vendor and 'CANADA' in vendor:
        return "PETRO CANADA"
    
    if 'HUSKY' in vendor:
        match = re.search(r'(\d+)', vendor)
        if match:
            return f"HUSKY {match.group(1)}"
        return "HUSKY"
    
    if 'ESSO' in vendor:
        return "ESSO"
    
    # Card transactions - keep as MCARD/VCARD/ACARD/DCARD, just capitalize
    # MCARD = MasterCard, VCARD = Visa, ACARD = Amex, DCARD = Debit
    if re.search(r'\b(M|V|A|D)CARD\b', vendor, re.IGNORECASE):
        # Already uppercase from earlier processing, just return as-is
        return vendor
    
    # Capital One
    if 'CAPITAL ONE' in vendor:
        if 'MASTERCARD' in vendor or 'MCARD' in vendor or 'MC' in vendor:
            return "CAPITAL ONE MASTERCARD"
        return "CAPITAL ONE"
    
    # Credit memos - standardize and remove GBL patterns
    if 'CREDIT MEMO' in vendor:
        # Extract the account number (e.g., 4017775)
        account_match = re.search(r'(\d{7})', vendor)
        if account_match:
            account = account_match.group(1)
            # Determine card type
            if 'VISA' in vendor or 'VI' in vendor:
                return f"CREDIT MEMO {account} VISA"
            elif 'MC' in vendor or 'MASTERCARD' in vendor:
                return f"CREDIT MEMO {account} MC"
            elif 'IDP' in vendor:
                return f"CREDIT MEMO {account} IDP"
            elif 'ID#' in vendor:
                return f"CREDIT MEMO {account} ID"
            else:
                return f"CREDIT MEMO {account}"
        return "CREDIT MEMO"
    
    # Email transfers - preserve names, but standardize MIKE RICHARD → MICHAEL RICHARD (same person)
    if 'EMAIL TRANSFER' in vendor or 'E-TRANSFER' in vendor:
        if 'FEE' in vendor and 'EMAIL TRANSFER' not in vendor:
            return "EMAIL TRANSFER FEE"
        # Standardize MIKE RICHARD to MICHAEL RICHARD (same family member)
        if 'MIKE RICHARD' in vendor:
            vendor = vendor.replace('MIKE RICHARD', 'MICHAEL RICHARD')
        # Keep all other names intact (IMAGE LIMO, FIRE ALERT, DAVID RICHARD, MATTHEW RICHARD are all different vendors)
        return vendor
    
    # Bank fees and charges
    if 'INTERAC' in vendor and 'FEE' in vendor:
        return "INTERAC FEE"
    
    if 'ATM' in vendor and 'FEE' in vendor:
        return "ATM FEE"
    
    if 'OVERDRAFT' in vendor or 'OD INTEREST' in vendor:
        return "OVERDRAFT INTEREST"
    
    if 'SERVICE CHARGE' in vendor or 'SVC CHARGE' in vendor:
        return "SERVICE CHARGE"
    
    if 'BANK FEE' in vendor or 'BANK CHARGES' in vendor:
        return "BANK FEE"
    
    # NSF charges (word boundary to avoid matching "S" at end of words)
    if re.search(r'\bNSF\b', vendor):
        if 'FEE' in vendor:
            return "NSF FEE"
        if 'RETURNED' in vendor or 'RETURN' in vendor:
            return "NSF RETURNED ITEM"
        return "NSF CHARGE"
    
    # Cash withdrawals (includes ATM withdrawals, automated banking machines, branch withdrawals - all go to cashbox)
    if any(keyword in vendor for keyword in ['CASH WITHDRAWAL', 'CASH W/D', 'ATM WITHDRAWAL', 'AUTOMATED BANKING MACHINE', 'INSTANTTELLER', 'BRANCH WITHDRAWAL', 'MCARD WITHDRAWAL', 'VCARD WITHDRAWAL']):
        # Don't preserve numbers for cash withdrawals - just return generic
        return "CASH WITHDRAWAL"
    
    # Generic WITHDRAWAL (but not EMAIL, SQUARE, or other transfers)
    if vendor == 'WITHDRAWAL' or re.match(r'^WITHDRAWAL\s*\d*$', vendor):
        return "CASH WITHDRAWAL"
    
    # Checks
    if 'CHQ' in vendor or 'CHEQUE' in vendor or 'CHECK' in vendor:
        match = re.search(r'(\d+)', vendor)
        if match:
            return f"CHQ {match.group(1)}"
        return "CHQ"
    
    # Square deposits (net amount after card processing fees)
    if 'SQUARE' in vendor and 'DEPOSIT' in vendor:
        return "SQUARE DEPOSIT"
    
    # Transfers (exclude email transfers and Square)
    if 'TRANSFER' in vendor and 'EMAIL' not in vendor and 'SQUARE' not in vendor:
        if 'BILL' in vendor:
            return "BILL PAYMENT"
        return "TRANSFER"
    
    # Insurance companies
    if 'EQUITY PREMIUM FINANCE' in vendor:
        return "EQUITY PREMIUM FINANCE"
    
    if 'IFS PREMIUM FINANCE' in vendor:
        return "IFS PREMIUM FINANCE"
    
    if 'JEVCO' in vendor:
        return "JEVCO INSURANCE"
    
    if 'OPTIMUM' in vendor and 'INSURANCE' in vendor:
        return "OPTIMUM INSURANCE"
    
    # Common vendors
    if 'CO-OP' in vendor or 'COOP' in vendor:
        if 'INSURANCE' in vendor:
            return "CO-OP INSURANCE"
        # Check for U-HAUL (not CO-OP)
        if 'U-HAUL' in vendor or 'UHAUL' in vendor:
            return "UHAUL RENTAL"
        # CO-OP gas bar locations (TAYLOR, GAETZ, SYLVAN, DOWNTOWN, BLKFLDS, RED DEE, EASTVIE)
        if any(loc in vendor for loc in ['TAYLOR', 'GAETZ', 'SYLVAN', 'DOWNTOWN', 'BLKFLDS', 'RED DEE', 'EASTVIE', 'GAETZ G']):
            return "CO-OP GAS BAR"
        # Check for HGC (Home and Garden Centre)
        if 'HGC' in vendor or 'HOME' in vendor or 'GARDEN' in vendor:
            return "CO-OP HGC"
        # Check for liquor
        if 'LIQUOR' in vendor or 'WINE' in vendor or 'BEER' in vendor:
            return "CO-OP LIQUOR"
        return "CO-OP"
    
    if 'CANADIAN TIRE' in vendor or 'CANADAINA TIRE' in vendor:
        return "CANADIAN TIRE"
    
    if 'TIM HORTONS' in vendor or 'TIM HORTON' in vendor:
        return "TIM HORTONS"
    
    if 'COSTCO' in vendor:
        return "COSTCO"
    
    if 'SAFEWAY' in vendor:
        return "SAFEWAY"
    
    if 'SOBEYS' in vendor or "SOBEY'S" in vendor:
        return "SOBEYS"
    
    if 'MONEY MART' in vendor or 'MONEYMART' in vendor:
        return "MONEY MART"
    
    if 'STAPLES' in vendor:
        return "STAPLES"
    
    # Liquor stores - match abbreviations
    if 'WINE AND BEYOND' in vendor or re.match(r'^WB\b', vendor) or re.search(r'\bWB\b', vendor):
        return "WINE AND BEYOND"
    
    if 'LIQUOR BARN' in vendor or 'LIQUOR MARKET' in vendor or 'LIQUOR BARON' in vendor or re.match(r'^LB\b', vendor) or re.search(r'\bLB\b', vendor):
        return "LIQUOR BARN"
    
    if 'LIQUOR DEPOT' in vendor or re.match(r'^LD\b', vendor) or re.search(r'\bLD\b', vendor):
        return "LIQUOR DEPOT"
    
    # Lease/Finance
    if 'LEASE FINANCE' in vendor:
        return "LEASE FINANCE"
    
    if 'HEFFNER' in vendor:
        if 'AUTO' in vendor or 'FINANCE' in vendor:
            return "HEFFNER AUTO FINANCE"
        return "HEFFNER"
    
    # Specific vendor cleanups
    if 'FRESHCO' in vendor:
        # Remove # and location codes
        return "FRESHCO"
    
    if 'SAVE ON FOODS' in vendor:
        # Remove # and location codes
        vendor = re.sub(r'#\s*\d*', '', vendor)
        vendor = re.sub(r'\s+', ' ', vendor).strip()
        return vendor
    
    if "RUN'N ON EMPTY" in vendor or "RUN'N ON EMPTY" in vendor:
        return "RUN'N ON EMPTY"
    
    # General cleanup
    # Remove common prefixes/suffixes
    vendor = re.sub(r'\s*\(.*?\)\s*', ' ', vendor)  # Remove parentheses
    vendor = re.sub(r'\s+', ' ', vendor).strip()
    
    return vendor

# Test standardization
print("="*100)
print("VENDOR NAME STANDARDIZATION - DRY RUN")
print("="*100)

dry_run = '--dry-run' in sys.argv or len(sys.argv) == 1

# Get sample vendors
if receipts_only:
    cur.execute("""
        SELECT DISTINCT
            vendor_name,
            COUNT(*) as frequency
        FROM receipts
        WHERE vendor_name IS NOT NULL
        AND vendor_name != ''
        GROUP BY vendor_name
        ORDER BY frequency DESC
        LIMIT 50
    """)
    sample_label = "receipts"
else:
    cur.execute("""
        SELECT DISTINCT
            vendor_extracted,
            COUNT(*) as frequency
        FROM banking_transactions
        WHERE vendor_extracted IS NOT NULL
        AND vendor_extracted != ''
        GROUP BY vendor_extracted
        ORDER BY frequency DESC
        LIMIT 50
    """)
    sample_label = "banking"

print(f"\nSample standardizations (top 50 by frequency) from {sample_label}:")
print(f"\n{'Original':<50} {'Standardized':<50}")
print("-"*100)

standardizations = {}
for vendor, freq in cur.fetchall():
    standardized = standardize_vendor_name(vendor)
    standardizations[vendor] = standardized
    if vendor != standardized:
        print(f"{vendor[:48]:<50} → {standardized[:48]}")

# Count impact
cur.execute("""
    SELECT COUNT(*) FROM receipts
    WHERE vendor_name IS NOT NULL
""")
total_receipts = cur.fetchone()[0]

if receipts_only:
    total_banking = 0
else:
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE vendor_extracted IS NOT NULL
    """)
    total_banking = cur.fetchone()[0]

print(f"\n\n📊 Impact:")
if not receipts_only:
    print(f"   Banking transactions with vendors: {total_banking:,}")
print(f"   Receipts with vendors: {total_receipts:,}")
print(f"   Total records to standardize: {total_banking + total_receipts:,}")

if dry_run:
    print("\n✅ DRY RUN COMPLETE")
    print("Run with --execute to apply standardization")
else:
    print("\n⚠️  EXECUTION MODE")
    response = input("\nType 'STANDARDIZE' to proceed: ")
    
    if response != 'STANDARDIZE':
        print("❌ Cancelled")
        cur.close()
        conn.close()
        sys.exit(0)
    
    trigger_disabled = False
    try:
        if not receipts_only:
            print("\n🔓 Checking for banking lock trigger...")
            try:
                cur.execute("ALTER TABLE banking_transactions DISABLE TRIGGER trg_banking_transactions_lock")
                conn.commit()
                trigger_disabled = True
            except Exception as trigger_err:
                conn.rollback()
                print("   (Trigger does not exist, skipping)")
                trigger_disabled = False

        # Update banking transactions (optional)
        updated_count = 0
        if not receipts_only:
            print("\n📝 Standardizing banking_transactions vendor names...")
            cur.execute("""
                SELECT transaction_id, vendor_extracted
                FROM banking_transactions
                WHERE vendor_extracted IS NOT NULL
            """)
            for trans_id, vendor in cur.fetchall():
                standardized = standardize_vendor_name(vendor)
                if standardized != vendor:
                    cur.execute("""
                        UPDATE banking_transactions
                        SET vendor_extracted = %s
                        WHERE transaction_id = %s
                    """, (standardized, trans_id))
                    updated_count += 1
            print(f"   ✅ Updated {updated_count:,} banking transaction vendors")

        # Update receipts
        print("\n📝 Standardizing receipts vendor names...")
        updated_receipts = 0
        cur.execute("""
            SELECT receipt_id, vendor_name
            FROM receipts
            WHERE vendor_name IS NOT NULL
        """)
        for receipt_id, vendor in cur.fetchall():
            standardized = standardize_vendor_name(vendor)
            if standardized != vendor:
                cur.execute("""
                    UPDATE receipts
                    SET vendor_name = %s
                    WHERE receipt_id = %s
                """, (standardized, receipt_id))
                updated_receipts += 1
        print(f"   ✅ Updated {updated_receipts:,} receipt vendors")
        
        if trigger_disabled:
            print("\n🔒 Re-enabling banking lock trigger...")
            try:
                cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
                conn.commit()
            except Exception:
                conn.rollback()
        
        # Start fresh transaction for updates
        conn.commit()
        
        total_updates = updated_count + updated_receipts
        print(f"\n✅ STANDARDIZATION COMPLETE")
        print(f"   Total updates: {total_updates:,}")
        print(f"   Format: ALL UPPERCASE")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        if trigger_disabled:
            print("🔒 Re-enabling banking lock trigger...")
            try:
                cur.execute("ALTER TABLE banking_transactions ENABLE TRIGGER trg_banking_transactions_lock")
            except Exception:
                pass
        conn.rollback()
        raise

cur.close()
conn.close()
