#!/usr/bin/env python3
"""
Display all extracted January 2013 transactions for user verification.
"""

# All transactions extracted from PDF screenshots
TRANSACTIONS = [
    # Date, Description, Debit/Withdrawal, Credit/Deposit
    
    # Page 1 - Jan 01 to Jan 07
    ('Jan 01', 'Opening balance', None, None, 21.21),
    ('Jan 02', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 316.88, None, -295.67),
    ('Jan 02', 'CORRECTION 00339', None, 316.88, 21.21),
    ('Jan 02', 'NSF CHARGE 00339', 45.00, None, -23.79),
    ('Jan 07', 'M M BEBRESENTED DR GBL MERCH FEES', 316.88, None, -340.67),
    ('Jan 07', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -441.81),
    ('Jan 07', 'CORRECTION 00339', None, 101.14, -340.67),
    
    # Page 2 - Jan 07 to Jan 31
    ('Jan 07', 'Balance forward', None, None, -340.67),
    ('Jan 08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None, None),
    ('Jan 08', 'CORRECTION 00339', None, 202.27, -113.79),
    ('Jan 08', 'NSF CHARGE 00339', 45.00, None, -158.79),
    ('Jan 14', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -259.93),
    ('Jan 14', 'CORRECTION 00339', None, 101.14, None),
    ('Jan 14', 'NSF CHARGE 00339', 45.00, None, -203.79),
    ('Jan 15', 'CREDIT MEMO GBL MERCH#4017775', None, 96.26, -107.53),
    ('Jan 15', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None, -512.07),
    ('Jan 15', 'CORRECTION 00339', None, 404.54, -107.53),
    ('Jan 15', 'NSF CHARGE 00339', 45.00, None, -152.53),
    ('Jan 21', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -253.67),
    ('Jan 21', 'CORRECTION 00339', None, 101.14, None),
    ('Jan 21', 'NSF CHARGE 00339', 45.00, None, -197.53),
    ('Jan 22', 'CREDIT MEMO GBL PMC', None, 170.00, -27.53),
    ('Jan 24', 'INSURANCE #5 PREMIUM FIN INSURANCE Coaperation CSI', 2383.24, None, -2410.77),
    ('Jan 24', 'CORRECTION 00339', None, 105.15, None),
    ('Jan 24', 'CORRECTION 00339', None, 2383.24, -27.53),
    ('Jan 24', 'NSF CHARGE 00339', 90.00, None, 117.53),
    ('Jan 28', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None, -522.07),
    ('Jan 28', 'CORRECTION 00339', None, 404.54, -117.53),
    ('Jan 28', 'NSF CHARGE 00339', 45.00, None, -162.53),
    ('Jan 31', 'INSURANCE Coaperation CSI', None, 105.15, None),
    ('Jan 31', 'CORRECTION 00339', None, 105.15, -267.68),
    ('Jan 31', 'NSF CHARGE 00339', 45.00, None, 207.53),
    ('Jan 31', 'ACCOUNT FEE', 35.00, None, 242.53),
    ('Jan 31', 'OVERDRAFT INTEREST', 2.12, None, None),
    ('Jan 31', 'Closing balance', None, None, -244.65),
]

print("\n" + "="*100)
print("JANUARY 2013 CIBC TRANSACTIONS - EXTRACTED FROM PDF")
print("="*100)
print(f"{'Date':<8} {'Description':<55} {'Withdrawal':>12} {'Deposit':>12} {'Balance':>12}")
print("-"*100)

running_total = 0
for date, desc, withdrawal, deposit, balance in TRANSACTIONS:
    w_str = f"${withdrawal:,.2f}" if withdrawal else ""
    d_str = f"${deposit:,.2f}" if deposit else ""
    b_str = f"${balance:,.2f}" if balance else ""
    
    print(f"{date:<8} {desc:<55} {w_str:>12} {d_str:>12} {b_str:>12}")

print("-"*100)

# Calculate totals
total_withdrawals = sum(t[2] for t in TRANSACTIONS if t[2])
total_deposits = sum(t[3] for t in TRANSACTIONS if t[3])
opening = 21.21
closing = -244.65

print(f"\n{'TOTALS:':<8} {'':<55} ${total_withdrawals:>11,.2f} ${total_deposits:>11,.2f}")
print()
print(f"Opening Balance (Jan 01): ${opening:>11,.2f}")
print(f"Total Withdrawals:        ${total_withdrawals:>11,.2f}")
print(f"Total Deposits:           ${total_deposits:>11,.2f}")
print(f"Net Change:               ${total_deposits - total_withdrawals:>+11,.2f}")
print(f"Closing Balance (Jan 31): ${closing:>11,.2f}")
print()
print(f"Calculated vs PDF: ${opening + (total_deposits - total_withdrawals):>11,.2f} vs ${closing:,.2f}")
print(f"Difference: ${(opening + (total_deposits - total_withdrawals)) - closing:>+11,.2f}")
print()
print("="*100)
print("\nPlease verify:")
print("1. All transaction amounts are correct")
print("2. All balances match the PDF")
print("3. Opening balance: $21.21")
print("4. Closing balance: -$244.65")
print("="*100)
