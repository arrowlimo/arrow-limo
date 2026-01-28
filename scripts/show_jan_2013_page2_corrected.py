#!/usr/bin/env python3
"""
Display corrected Page 2 transactions with missing Jan 07 entries added.
"""

# Page 2 transactions from PDF screenshot - CORRECTED
PAGE2_TRANSACTIONS = [
    # Date, Description, Debit/Withdrawal, Credit/Deposit, Balance
    ('Jan 07', 'Balance forward', None, None, -340.67),
    ('Jan 07', 'CORRECTION 00339', None, 316.88, -23.79),
    ('Jan 07', 'NSF CHARGE 00339', 90.00, None, -113.79),
    ('Jan 08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None, -318.06),
    ('Jan 08', 'CORRECTION 00339', None, 202.27, -113.79),
    ('Jan 08', 'NSF CHARGE 00339', 45.00, None, -158.79),
    ('Jan 14', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -259.93),
    ('Jan 14', 'CORRECTION 00339', None, 101.14, -158.79),
    ('Jan 14', 'NSF CHARGE 00339', 45.00, None, -203.79),
    ('Jan 15', 'CREDIT MEMO GBL MERCH#4017775', None, 96.26, -107.53),
    ('Jan 15', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None, -512.07),
    ('Jan 15', 'CORRECTION 00339', None, 404.54, -107.53),
    ('Jan 15', 'NSF CHARGE 00339', 45.00, None, -152.53),
    ('Jan 21', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -253.67),
    ('Jan 21', 'CORRECTION 00339', None, 101.14, -152.53),
    ('Jan 21', 'NSF CHARGE 00339', 45.00, None, -197.53),
    ('Jan 22', 'CREDIT MEMO GBL PMC', None, 170.00, -27.53),
    ('Jan 24', 'INSURANCE #5 PREMIUM FIN INSURANCE Coaperation CSI', 2383.24, None, -2410.77),
    ('Jan 24', 'CORRECTION 00339', None, 105.15, -2515.92),
    ('Jan 24', 'CORRECTION 00339', None, 2383.24, -27.53),
    ('Jan 24', 'NSF CHARGE 00339', 90.00, None, 117.53),
    ('Jan 28', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None, -522.07),
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
print("JANUARY 2013 PAGE 2 TRANSACTIONS - CORRECTED WITH MISSING JAN 07 ENTRIES")
print("="*100)
print(f"{'Date':<8} {'Description':<55} {'Withdrawal':>12} {'Deposit':>12} {'Balance':>12}")
print("-"*100)

line_num = 8  # Start from line 8 (lines 1-7 were page 1)
for date, desc, withdrawal, deposit, balance in PAGE2_TRANSACTIONS:
    w_str = f"${withdrawal:,.2f}" if withdrawal else ""
    d_str = f"${deposit:,.2f}" if deposit else ""
    b_str = f"${balance:,.2f}" if balance else ""
    
    if withdrawal or deposit:  # Only number actual transaction lines
        print(f"{line_num:2d}. {date:<8} {desc:<50} {w_str:>12} {d_str:>12} {b_str:>12}")
        line_num += 1
    else:
        print(f"    {date:<8} {desc:<50} {w_str:>12} {d_str:>12} {b_str:>12}")

print("-"*100)

# Calculate totals
total_withdrawals = sum(t[2] for t in PAGE2_TRANSACTIONS if t[2])
total_deposits = sum(t[3] for t in PAGE2_TRANSACTIONS if t[3])

print(f"\n{'PAGE 2 TOTALS:':<13} {'':<50} ${total_withdrawals:>11,.2f} ${total_deposits:>11,.2f}")
print()
print("Lines 8-9 are NEW (missing from previous extraction)")
print("Can you confirm the exact descriptions for lines 8 and 9?")
print("="*100)
