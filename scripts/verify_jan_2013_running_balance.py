#!/usr/bin/env python3
"""
Display January 2013 transactions with PDF balances and calculated running balance.
"""

# All transactions from Pages 1 & 2
ALL_TRANSACTIONS = [
    # (Line, Date, Description, Withdrawal, Deposit, PDF_Balance)
    (1, 'Jan 01', 'Opening balance', None, None, 21.21),
    (2, 'Jan 02', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 316.88, None, -295.67),
    (3, 'Jan 02', 'CORRECTION 00339', None, 316.88, 21.21),
    (4, 'Jan 02', 'NSF CHARGE 00339', 45.00, None, -23.79),
    (5, 'Jan 07', 'M M BEBRESENTED DR GBL MERCH FEES', 316.88, None, -340.67),
    (6, 'Jan 07', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -441.81),
    (7, 'Jan 07', 'CORRECTION 00339', None, 101.14, -340.67),
    # Page 2 starts
    (8, 'Jan 07', 'CORRECTION 00339', None, 316.88, -23.79),
    (9, 'Jan 07', 'NSF CHARGE 00339', 90.00, None, -113.79),
    (10, 'Jan 08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None, -316.06),
    (11, 'Jan 08', 'CORRECTION 00339', None, 202.27, -113.79),
    (12, 'Jan 08', 'NSF CHARGE 00339', 45.00, None, -158.79),
    (13, 'Jan 14', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -259.93),
    (14, 'Jan 14', 'CORRECTION 00339', None, 101.14, -158.79),
    (15, 'Jan 14', 'NSF CHARGE 00339', 45.00, None, -203.79),
    (16, 'Jan 15', 'CREDIT MEMO GBL MERCH#4017775', None, 96.26, -107.53),
    (17, 'Jan 15', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None, -512.07),
    (18, 'Jan 15', 'CORRECTION 00339', None, 404.54, -107.53),
    (19, 'Jan 15', 'NSF CHARGE 00339', 45.00, None, -152.53),
    (20, 'Jan 21', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -253.67),
    (21, 'Jan 21', 'CORRECTION 00339', None, 101.14, -152.53),
    (22, 'Jan 21', 'NSF CHARGE 00339', 45.00, None, -197.53),
    (23, 'Jan 22', 'CREDIT MEMO GBL PMC', None, 170.00, -27.53),
    (24, 'Jan 24', 'INSURANCE #5 PREMIUM FIN', 2383.24, None, -2410.77),
    (25, 'Jan 24', 'INSURANCE Coaperation CSI', 105.15, None, -2515.92),
    (26, 'Jan 24', 'CORRECTION 00339', None, 105.15, -2410.77),
    (27, 'Jan 24', 'CORRECTION 00339', None, 2383.24, -27.53),
    (28, 'Jan 24', 'NSF CHARGE 00339', 90.00, None, -117.53),
    (29, 'Jan 28', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None, -522.07),
    (30, 'Jan 28', 'CORRECTION 00339', None, 404.54, -117.53),
    (31, 'Jan 28', 'NSF CHARGE 00339', 45.00, None, -162.53),
    (32, 'Jan 31', 'INSURANCE Coaperation CSI', 105.15, None, -267.68),
    (33, 'Jan 31', 'CORRECTION 00339', None, 105.15, -162.53),
    (34, 'Jan 31', 'NSF CHARGE 00339', 45.00, None, -207.53),
    (35, 'Jan 31', 'ACCOUNT FEE', 35.00, None, -242.53),
    (36, 'Jan 31', 'OVERDRAFT INTEREST', 2.12, None, -244.65),
]

print("\n" + "="*120)
print("JANUARY 2013 BALANCE VERIFICATION - PDF vs CALCULATED")
print("="*120)
print(f"{'Ln':<4} {'Date':<8} {'Description':<45} {'Withdrawal':>12} {'Deposit':>12} {'PDF Bal':>12} {'Calc Bal':>12} {'Diff':>8}")
print("-"*120)

running_balance = 21.21  # Opening balance
discrepancies = []

for line, date, desc, withdrawal, deposit, pdf_balance in ALL_TRANSACTIONS:
    w_str = f"${withdrawal:,.2f}" if withdrawal else ""
    d_str = f"${deposit:,.2f}" if deposit else ""
    
    # Calculate running balance
    if line > 1:  # Skip opening balance calculation
        if withdrawal:
            running_balance -= withdrawal
        if deposit:
            running_balance += deposit
    
    pdf_str = f"${pdf_balance:,.2f}" if pdf_balance else ""
    calc_str = f"${running_balance:,.2f}"
    
    # Check for discrepancy
    if pdf_balance:
        diff = abs(running_balance - pdf_balance)
        diff_str = f"${diff:.2f}" if diff > 0.01 else "OK"
        
        if diff > 0.01:
            discrepancies.append((line, date, diff))
            marker = " ⚠️"
        else:
            marker = " ✓"
    else:
        diff_str = ""
        marker = ""
    
    print(f"{line:<4} {date:<8} {desc:<45} {w_str:>12} {d_str:>12} {pdf_str:>12} {calc_str:>12} {diff_str:>8}{marker}")

print("-"*120)

# Calculate totals
total_withdrawals = sum(t[3] for t in ALL_TRANSACTIONS if t[3])
total_deposits = sum(t[4] for t in ALL_TRANSACTIONS if t[4])

print(f"\n{'TOTALS:':<4} {'':<8} {'':<45} ${total_withdrawals:>11,.2f} ${total_deposits:>11,.2f}")
print(f"\nOpening Balance: ${21.21:,.2f}")
print(f"Net Change: ${total_deposits - total_withdrawals:+,.2f}")
print(f"Closing Balance: ${running_balance:,.2f}")

if discrepancies:
    print("\n" + "="*120)
    print("⚠️  DISCREPANCIES FOUND:")
    print("="*120)
    for line, date, diff in discrepancies:
        print(f"Line {line} ({date}): ${diff:.2f} difference")
else:
    print("\n" + "="*120)
    print("✓ ALL BALANCES MATCH PERFECTLY!")
    print("="*120)

print()
