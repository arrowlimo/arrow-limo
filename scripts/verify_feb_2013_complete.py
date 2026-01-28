#!/usr/bin/env python3
"""
Complete February 2013 CIBC transactions - all pages combined.
"""

# Complete February 2013 transactions
FEB_TRANSACTIONS = [
    # (Date, Description, Withdrawal, Deposit, Balance)
    ('Feb 01', 'Opening balance', None, None, -244.65),
    ('Feb 01', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 145.39, None, -390.04),
    ('Feb 01', 'CORRECTION 00339', None, 145.39, -244.65),
    ('Feb 01', 'NSF CHARGE 00339', 45.00, None, -289.65),
    ('Feb 05', 'DEPOSIT', None, 1500.00, 1210.35),
    ('Feb 05', 'WITHDRAWAL', 1000.00, None, 210.35),
    ('Feb 05', 'ABM WITHDRAWAL 1E0U GAETZ AVE + 67TH ST 00339', 200.00, None, 10.35),
    ('Feb 06', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.54, None, -394.19),
    ('Feb 06', 'DEBIT MEMO REPRESENTED DR GBL MERCH FEES', 145.39, None, -539.58),
    ('Feb 06', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -640.72),
    ('Feb 06', 'CORRECTION 00339', None, 101.14, -539.58),
    ('Feb 06', 'CORRECTION 00339', None, 145.39, -394.19),
    # From zoomed page - between Feb 06 and Feb 20
    ('Feb 06', 'CORRECTION 00339', None, 404.54, 10.35),
    ('Feb 06', 'NSF CHARGE 00339', 135.00, None, -124.65),
    ('Feb 06', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None, -326.92),
    ('Feb 06', 'CORRECTION 00339', None, 202.27, -124.65),
    ('Feb 06', 'NSF CHARGE 00339', 45.00, None, -169.65),
    ('Feb 15', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 606.81, None, -776.46),
    ('Feb 15', 'CORRECTION 00339', None, 606.81, -169.65),
    ('Feb 15', 'NSF CHARGE 00339', 45.00, None, -214.65),
    ('Feb 19', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.28, None, -416.93),
    ('Feb 19', 'CORRECTION 00339', None, 202.28, -214.65),
    ('Feb 19', 'NSF CHARGE 00339', 45.00, None, -259.65),
    ('Feb 20', 'CREDIT MEMO 4017775 IDP GBL IDP4017775', None, 100.00, -159.65),
    ('Feb 25', 'INSURANCE Cooperators CSI', 50.00, None, -209.65),
    ('Feb 25', 'CORRECTION 00339', None, 50.00, -159.65),
    ('Feb 25', 'NSF CHARGE 00339', 45.00, None, -204.65),
    ('Feb 27', 'INSURANCE IF5 PREMIUM FIN', 2383.24, None, -2587.89),
    ('Feb 27', 'CORRECTION 00339', None, 2383.24, -204.65),
    ('Feb 27', 'NSF CHARGE 00339', 45.00, None, -249.65),
    ('Feb 28', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 606.81, None, -856.46),
    ('Feb 28', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.28, None, -1058.74),
    ('Feb 28', 'CORRECTION 00339', None, 202.28, -856.46),
    ('Feb 28', 'CORRECTION 00339', None, 606.81, -249.65),
    ('Feb 28', 'NSF CHARGE 00339', 90.00, None, -339.65),
    ('Feb 28', 'ACCOUNT FEE', 35.00, None, -374.65),
    ('Feb 28', 'OVERDRAFT INTEREST', 3.12, None, -377.77),
    ('Feb 28', 'Closing balance', None, None, -377.77),
]

print("\n" + "="*120)
print("FEBRUARY 2013 COMPLETE TRANSACTIONS - FOR VERIFICATION")
print("="*120)
print(f"{'Ln':<4} {'Date':<8} {'Description':<50} {'Withdrawal':>12} {'Deposit':>12} {'PDF Bal':>12} {'Calc Bal':>12} {'Status':>8}")
print("-"*120)

running_balance = -244.65  # Opening from Jan 31
line_num = 1

for date, desc, withdrawal, deposit, balance in FEB_TRANSACTIONS:
    w_str = f"${withdrawal:,.2f}" if withdrawal else ""
    d_str = f"${deposit:,.2f}" if deposit else ""
    
    # Calculate running balance
    if line_num > 1 and (withdrawal or deposit):
        if withdrawal:
            running_balance -= withdrawal
        if deposit:
            running_balance += deposit
    
    b_str = f"${balance:,.2f}" if balance else ""
    calc_str = f"${running_balance:,.2f}"
    
    # Check discrepancy
    if balance and line_num > 1:
        diff = abs(running_balance - balance)
        if diff > 0.01:
            status = f"⚠️ ${diff:.2f}"
        else:
            status = "✓"
    else:
        status = ""
    
    print(f"{line_num:<4} {date:<8} {desc:<50} {w_str:>12} {d_str:>12} {b_str:>12} {calc_str:>12} {status:>8}")
    line_num += 1

print("-"*120)

total_w = sum(t[2] for t in FEB_TRANSACTIONS if t[2])
total_d = sum(t[3] for t in FEB_TRANSACTIONS if t[3])

print(f"\nTotal Withdrawals: ${total_w:,.2f}")
print(f"Total Deposits: ${total_d:,.2f}")
print(f"Net Change: ${total_d - total_w:+,.2f}")
print(f"Opening: -$244.65 | Closing: -$377.77")
print(f"Calculated closing: ${running_balance:,.2f}")

if abs(running_balance - (-377.77)) < 0.01:
    print("\n✓ PERFECT MATCH!")
else:
    print(f"\n⚠️ Discrepancy: ${abs(running_balance - (-377.77)):.2f}")
    print("Please verify transactions and provide corrections.")

print("="*120)
