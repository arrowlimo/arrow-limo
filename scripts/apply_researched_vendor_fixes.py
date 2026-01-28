#!/usr/bin/env python3
"""
Apply vendor fixes based on banking research and user comments.
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("=" * 80)
print("APPLYING VENDOR FIXES BASED ON RESEARCH")
print("=" * 80)

# Based on the research findings, here are the corrections
fixes = [
    # Spelling corrections
    ('ACARD DEPOSITT', 'ACARD DEPOSIT'),
    ('ACE LIQUORT', 'ACE LIQUOR'),
    ('ALBERTA SKYDIVET', 'ALBERTA SKYDIVE'),
    ('BIRD RIDEST', 'BIRD RIDES'),
    ('BOURBON STREETT', 'BOURBON STREET'),
    ('BRANCH WITHDRAWALT', 'BRANCH WITHDRAWAL'),
    ('BUKWILDZ BART', 'BUKWILDZ BAR'),
    ('CORONATION RESTAURAN', 'CORONATION RESTAURANT'),
    ('FILLCAN LIQUORST', 'FILLCAN LIQUORS'),
    ('LIQUOR DEPO', 'LIQUOR DEPOT'),
    ('VCARD DEPOSITT', 'VCARD DEPOSIT'),
    
    # Truncated names
    ('ACTION EQUIPMEN', 'ACTION EQUIPMENT'),
    ('ANDREW SHERET L', 'ANDREW SHERET LIMITED'),
    ('BAMBOO HUT SOUT', 'BAMBOO HUT'),
    ('BLUE DRAGON FIN', 'BLUE DRAGON FINANCIAL'),
    ('BLUE GRASS SOD', 'BLUE GRASS SOD FARM'),
    ('CHINA BEN RESTA', 'CHINA BEN RESTAURANT'),
    ('ERLES AUTO REPA', 'ERLES AUTO REPAIR'),
    ('GAETZ FRESH MAR', 'GAETZ FRESH MARKET'),
    ('GROWER DIRECT S', 'GROWER DIRECT'),
    ('THE LIQUOR HUTC', 'THE LIQUOR HUTCH'),
    
    # From comments - Facebook advertising
    ('FACEBK *SZYJXJA', 'FACEBOOK ADVERTISING'),
    ('FACEBK SZTKJKWD', 'FACEBOOK ADVERTISING'),
    ('FACEBK', 'FACEBOOK ADVERTISING'),
    
    # From banking research - Air Canada
    ('AIR CAN*', 'AIR CANADA'),
    
    # From banking research - BE rewards
    ('BE* C-REWARDS', 'BE REWARDS'),
    
    # From banking research - CLEARVIEW is actually CLEARVIEW MARKET
    ('CLEARVIEW', 'CLEARVIEW MARKET'),
    
    # From banking research - CRYSTAL VIB is SQ *CRYSTAL VIB (Square payment)
    ('CRYSTAL VIB', 'SQUARE - CRYSTAL VIBES'),
    
    # From banking research - AUTOMOTIVE PART (truncated)
    ('AUTOMOTIVE PART', 'AUTOMOTIVE PARTS'),
    
    # From banking research - D+H (appears in CIBC statements)
    ('D+H', 'D+H (BANK SYSTEM)'),
    
    # Cash transfers internal
    ('ARROW LIMOUSINE', 'ARROW LIMOUSINE (INTERNAL TRANSFER)'),
    ('ARROW LIMOUSINE CASH', 'ARROW LIMOUSINE (INTERNAL TRANSFER)'),
    
    # Generic categories that need context
    ('BUSINESS EXPENSE', 'BUSINESS EXPENSE (CIBC AUTO-GEN)'),
    ('CUSTOMER', 'CUSTOMER DEPOSIT'),
    ('DEPOSIT', 'DEPOSIT (UNSPECIFIED)'),
    ('CASH', 'CASH PAYMENT'),
    ('BANK', 'BANK FEE'),
    ('CREDIT_CARD', 'CREDIT CARD PAYMENT'),
    
    # Check payments (missing detail)
    ('CHQ', 'CHECK PAYMENT'),
    
    # Truncated locations
    ('GAETZ AVE CENTE', 'GAETZ AVENUE CENTER'),
    ('GAETZ AVENUE PH', 'GAETZ AVENUE PHARMACY'),
    
    # WIX and other USD point of sale
    ('WIX', 'WIX.COM'),
    ('HTS', 'HTS (USD PURCHASE)'),
    
    # Internal transfers
    ('DEPOSIT $500 FROM CIBC', 'CIBC TRANSFER (INTERNAL)'),
    
    # Missing vendor for GASOLINE ALLEY
    ('GASOLINE ALLEY', 'GASOLINE ALLEY (VENDOR UNKNOWN)'),
    
    # City services
    ('CITY OF EDMONTON', 'CITY OF EDMONTON'),  # Keep as is, not police
    
    # Shell with PST/GST
    ('C05410 FISHER ST STATI NORTH', 'SHELL'),
    
    # Test/placeholder
    ('ANOTHER VENDOR', 'TEST RECEIPT (PLACEHOLDER)'),
    ('ER@FIFL@¢% ION RECORD', 'TRANSACTION RECORD (CORRUPTED)'),
    ('EUROPEAN LINGER', 'EUROPEAN LINGERIE'),
    ('EAD INC', 'EAD INC'),
]

print("\nApplying fixes:")
updated_total = 0

for old_name, new_name in fixes:
    cur.execute("""
        UPDATE receipts
        SET vendor_name = %s
        WHERE vendor_name = %s
    """, (new_name, old_name))
    
    count = cur.rowcount
    if count > 0:
        updated_total += count
        print(f"  ✅ {count:4} receipts: '{old_name[:35]}' → '{new_name[:35]}'")

conn.commit()

print(f"\n✅ COMMITTED: {updated_total} receipts updated")

# Also fix the FIRST INSURANCE FUNDING-C issue mentioned
print("\n" + "=" * 80)
print("FIXING ADDITIONAL TRUNCATIONS")
print("=" * 80)

additional_fixes = [
    ('FIRST INSURANCE FUNDING-C', 'FIRST INSURANCE FUNDING'),
    ('LEASE FINANCE GROUP', 'LEASE FINANCE GROUP (FULL NAME UNKNOWN)'),
]

for old_name, new_name in additional_fixes:
    cur.execute("""
        UPDATE receipts
        SET vendor_name = %s
        WHERE vendor_name = %s
    """, (new_name, old_name))
    
    count = cur.rowcount
    if count > 0:
        updated_total += count
        print(f"  ✅ {count:4} receipts: '{old_name}' → '{new_name}'")

conn.commit()

print(f"\n✅ TOTAL UPDATED: {updated_total} receipts")

cur.close()
conn.close()

print("\n✅ COMPLETE")
