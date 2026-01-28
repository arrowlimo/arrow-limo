#!/usr/bin/env python3
"""
Extract February 2013 CIBC transactions for verification.
"""

# February 2013 transactions from PDF screenshots
FEB_TRANSACTIONS = [
    # (Line, Date, Description, Withdrawal, Deposit, Balance)
    (1, 'Feb 01', 'Opening balance', None, None, -244.65),
    (2, 'Feb 01', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 145.39, None, -390.04),
    (3, 'Feb 01', 'CORRECTION 00339', None, 145.39, -244.65),
    (4, 'Feb 01', 'NSF CHARGE 00339', 45.00, None, -289.65),
    (5, 'Feb 05', 'DEPOSIT', None, 1500.00, 1210.35),
    (6, 'Feb 05', 'WITHDRAWAL', 1000.00, None, 210.35),
    (7, 'Feb 05', 'ABM WITHDRAWAL 1E0U', 200.00, None, 10.35),
    (8, 'Feb 05', 'GAETZ AVE + 67TH ST 00339 4506*********359', None, None, None),  # Part of line 7
    (9, 'Feb 06', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None, -394.19),
    (10, 'Feb 06', 'DEBIT MEMO REPRESENTED DR GBL MERCH FEES', 145.39, None, -539.58),
    (11, 'Feb 06', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -640.72),
    (12, 'Feb 06', 'CORRECTION 00339', None, 101.14, -539.58),
    (13, 'Feb 06', 'CORRECTION 00339', None, 145.39, -394.19),
    
    # From second screenshot (continuing Feb transactions)
    (14, 'Feb 06', 'CORRECTION 00339', None, 202.28, -214.65),  # Need to verify balance
    (15, 'Feb 06', 'NSF CHARGE 00339', 45.00, None, -259.65),  # Need to verify balance
    (16, 'Feb 20', 'CREDIT MEMO 4017775 IDP GBL IDP4017775', None, 100.00, -159.65),
    (17, 'Feb 25', 'INSURANCE Cooperators CSI', 50.00, None, -209.65),
    (18, 'Feb 25', 'CORRECTION 00339', None, 50.00, -159.65),
    (19, 'Feb 25', 'NSF CHARGE 00339', 45.00, None, -204.65),
    (20, 'Feb 27', 'INSURANCE IF5 PREMIUM FIN', 2383.24, None, -2587.89),
    (21, 'Feb 27', 'CORRECTION 00339', None, 2383.24, -204.65),
    (22, 'Feb 27', 'NSF CHARGE 00339', 45.00, None, -249.65),
    (23, 'Feb 28', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 606.81, None, -856.46),
    (24, 'Feb 28', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.28, None, -1058.74),
    (25, 'Feb 28', 'CORRECTION 00339', None, 202.28, -856.46),
    (26, 'Feb 28', 'CORRECTION 00339', None, 606.81, -249.65),
    (27, 'Feb 28', 'NSF CHARGE 00339', 90.00, None, -339.65),
    (28, 'Feb 28', 'ACCOUNT FEE', 35.00, None, -374.65),
    (29, 'Feb 28', 'OVERDRAFT INTEREST', 3.12, None, -377.77),
    (30, 'Feb 28', 'Closing balance', None, None, -377.77),
]

print("\n" + "="*120)
print("FEBRUARY 2013 TRANSACTIONS - EXTRACTED FROM PDF")
print("="*120)
print(f"{'Ln':<4} {'Date':<8} {'Description':<50} {'Withdrawal':>12} {'Deposit':>12} {'Balance':>12}")
print("-"*120)

running_balance = -244.65  # Opening from Jan 31
for line, date, desc, withdrawal, deposit, balance in FEB_TRANSACTIONS:
    w_str = f"${withdrawal:,.2f}" if withdrawal else ""
    d_str = f"${deposit:,.2f}" if deposit else ""
    
    # Calculate running balance
    if line > 1 and (withdrawal or deposit):
        if withdrawal:
            running_balance -= withdrawal
        if deposit:
            running_balance += deposit
    
    b_str = f"${balance:,.2f}" if balance else ""
    calc_str = f"${running_balance:,.2f}"
    
    # Check discrepancy
    if balance and line > 1:
        diff = abs(running_balance - balance)
        if diff > 0.01:
            marker = f" ⚠️ DIFF ${diff:.2f}"
        else:
            marker = " ✓"
    else:
        marker = ""
    
    print(f"{line:<4} {date:<8} {desc:<50} {w_str:>12} {d_str:>12} {b_str:>12} | {calc_str:>12}{marker}")

print("-"*120)
print("\nPlease verify each line and provide corrections for any discrepancies.")
print("Opening balance Feb 01: -$244.65 (matches Jan 31 closing)")
print("Closing balance Feb 28: -$377.77")
print("="*120)
