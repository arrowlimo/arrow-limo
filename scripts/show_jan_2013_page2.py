#!/usr/bin/env python3
"""
Display Page 2 transactions for user verification (Jan 07 balance forward through Jan 31).
"""

# Page 2 transactions from PDF screenshot
PAGE2_TRANSACTIONS = [
    # Date, Description, Debit/Withdrawal, Credit/Deposit, Balance
    ('Jan 07', 'Balance forward', None, None, -340.67),
    ('Jan 08', 'NSF CHARGE 00339', 90.00, None, -413.79),  # Reading from PDF
    ('Jan 08', 'RENT/LEASE 000000000000000', 202.27, None, -318.06),  # Reading from PDF
    ('Jan 08', 'LEASE FINANCE GR', None, None, None),  # Part of description above
    ('Jan 08', 'CORRECTION 00339', None, 202.27, -113.79),
    ('Jan 14', 'NSF CHARGE 00339', 45.00, None, -158.79),
    ('Jan 14', 'RENT/LEASE 000000000000000', 101.14, None, -259.93),
    ('Jan 14', 'LEASE FINANCE GR', None, None, None),  # Part of description above
    ('Jan 14', 'CORRECTION 00339', None, 101.14, -158.79),
    ('Jan 14', 'NSF CHARGE 00339', 45.00, None, -203.79),
    ('Jan 15', 'CREDIT MEMO GBL MERCH#4017775', None, 96.26, -107.53),
    ('Jan 15', 'RENT/LEASE 000000000000000', 404.54, None, -512.07),
    ('Jan 15', 'LEASE FINANCE GR', None, None, None),  # Part of description above
    ('Jan 15', 'CORRECTION 00339', None, 404.54, -107.53),
    ('Jan 15', 'NSF CHARGE 00339', 45.00, None, -152.53),
    ('Jan 21', 'RENT/LEASE 000000000000000', 101.14, None, -253.67),
    ('Jan 21', 'LEASE FINANCE GR', None, None, None),  # Part of description above
    ('Jan 21', 'CORRECTION 00339', None, 101.14, -152.53),
    ('Jan 21', 'NSF CHARGE 00339', 45.00, None, -197.53),
    ('Jan 22', 'CREDIT MEMO GBL PMC', None, 170.00, -27.53),
    ('Jan 24', 'INSURANCE #5 PREMIUM FIN', 2383.24, None, -2410.77),
    ('Jan 24', 'INSURANCE Coaperation CSI', None, None, None),  # Part of description above
    ('Jan 24', 'CORRECTION 00339', None, 105.15, -2515.92),  # Reading from PDF
    ('Jan 24', 'CORRECTION 00339', None, 2383.24, -27.53),
    ('Jan 24', 'NSF CHARGE 00339', 90.00, None, 117.53),
    ('Jan 28', 'RENT/LEASE 000000000000000', 404.54, None, -522.07),
    ('Jan 28', 'LEASE FINANCE GR', None, None, None),  # Part of description above
    ('Jan 28', 'CORRECTION 00339', None, 404.54, -117.53),
    ('Jan 28', 'NSF CHARGE 00339', 45.00, None, -162.53),
    ('Jan 31', 'INSURANCE Coaperation CSI', None, 105.15, -267.68),
    ('Jan 31', 'CORRECTION 00339', None, 105.15, -162.53),
    ('Jan 31', 'NSF CHARGE 00339', 45.00, None, -207.53),
    ('Jan 31', 'ACCOUNT FEE', 35.00, None, -242.53),
    ('Jan 31', 'OVERDRAFT INTEREST', 2.12, None, -244.65),
    ('Jan 31', 'Closing balance', None, None, -244.65),
]

print("\n" + "="*100)
print("JANUARY 2013 PAGE 2 TRANSACTIONS - FOR VERIFICATION")
print("="*100)
print(f"{'Date':<8} {'Description':<55} {'Withdrawal':>12} {'Deposit':>12} {'Balance':>12}")
print("-"*100)

for date, desc, withdrawal, deposit, balance in PAGE2_TRANSACTIONS:
    w_str = f"${withdrawal:,.2f}" if withdrawal else ""
    d_str = f"${deposit:,.2f}" if deposit else ""
    b_str = f"${balance:,.2f}" if balance else ""
    
    print(f"{date:<8} {desc:<55} {w_str:>12} {d_str:>12} {b_str:>12}")

print("-"*100)

# Calculate totals (excluding balance forward and non-transaction lines)
total_withdrawals = sum(t[2] for t in PAGE2_TRANSACTIONS if t[2])
total_deposits = sum(t[3] for t in PAGE2_TRANSACTIONS if t[3])

print(f"\n{'PAGE 2 TOTALS:':<8} {'':<55} ${total_withdrawals:>11,.2f} ${total_deposits:>11,.2f}")
print()
print("="*100)
print("\nPlease verify each line 8-35:")
print("- Are all amounts correct?")
print("- Are all balances correct?")
print("- Any missing transactions?")
print("="*100)
