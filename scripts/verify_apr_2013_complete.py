#!/usr/bin/env python3
"""
Verify April 2013 CIBC banking transactions from PDF reconciliation report.
Opening balance: -$251.26 (from Mar 31 closing)
Closing balance: -$899.63 (from PDF)
"""

# All transactions from April 2013 PDF screenshots
transactions = [
    # Line, Date, Description, Withdrawal, Deposit, PDF Balance
    (1, 'Apr 01', 'Opening balance', None, None, -251.26),
    (2, 'Apr 01', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 172.68, None, -423.94),
    (3, 'Apr 01', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 606.81, None, -1030.75),
    (4, 'Apr 01', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 303.42, None, -1334.17),
    (5, 'Apr 01', 'CORRECTION 00339', None, 172.68, -1161.49),
    (6, 'Apr 01', 'CORRECTION 00339', None, 303.42, -858.07),
    (7, 'Apr 01', 'CORRECTION 00339', None, 606.81, -251.26),
    (8, 'Apr 01', 'NSF CHARGE 00339', 135.00, None, -386.26),
    (9, 'Apr 04', 'DEBIT MEMO REPRESENTED DR GBL MERCH FEES', 172.68, None, -558.94),
    (10, 'Apr 04', 'CORRECTION 00339', None, 172.68, -386.26),
    (11, 'Apr 08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -487.40),
    
    # Page 2
    (12, 'Apr 08', 'Balance forward', None, None, -487.40),
    (13, 'Apr 08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None, -689.67),
    (14, 'Apr 08', 'CORRECTION 00339', None, 202.27, -487.40),
    (15, 'Apr 08', 'CORRECTION 00339', None, 101.14, -386.26),
    (16, 'Apr 08', 'NSF CHARGE 00339', 90.00, None, -476.26),
    (17, 'Apr 09', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 606.81, None, -1083.07),
    (18, 'Apr 09', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 303.42, None, -1386.49),
    (19, 'Apr 09', 'CORRECTION 00339', None, 303.42, -1083.07),
    (20, 'Apr 09', 'CORRECTION 00339', None, 606.81, -476.26),
    (21, 'Apr 09', 'NSF CHARGE 00339', 90.00, None, -566.26),
    (22, 'Apr 15', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -667.40),
    (23, 'Apr 15', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None, -869.67),
    (24, 'Apr 15', 'CORRECTION 00339', None, 101.14, -768.53),
    (25, 'Apr 15', 'CORRECTION 00339', None, 202.27, -566.26),
    (26, 'Apr 15', 'NSF CHARGE 00339', 90.00, None, -656.26),
    (27, 'Apr 24', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 809.08, None, -1465.34),
    (28, 'Apr 24', 'INSURANCE IFS PREMIUM FIN', 2383.24, None, -3848.58),
    (29, 'Apr 24', 'INSURANCE Cooperators CSI', 104.03, None, -3952.61),
    (30, 'Apr 24', 'CORRECTION 00339', None, 104.03, -3848.58),
    (31, 'Apr 24', 'CORRECTION 00339', None, 809.08, -3039.50),
    (32, 'Apr 24', 'CORRECTION 00339', None, 2383.24, -656.26),
    (33, 'Apr 24', 'NSF CHARGE 00339', 135.00, None, -791.26),
    (34, 'Apr 30', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 404.56, None, -1195.82),
    (35, 'Apr 30', 'CORRECTION 00339', None, 404.56, -791.26),
    (36, 'Apr 30', 'NSF CHARGE 00339', 45.00, None, -836.26),
    (37, 'Apr 30', 'ACCOUNT FEE', 50.00, None, -886.26),
    (38, 'Apr 30', 'OVERDRAFT INTEREST', 10.37, None, -896.63),
    (39, 'Apr 30', 'PAPER STMT/MT FEE', 3.00, None, -899.63),
    (40, 'Apr 30', 'Closing balance', None, None, -899.63),
]

def main():
    print("\n" + "="*100)
    print("APRIL 2013 CIBC BANKING VERIFICATION")
    print("="*100)
    print(f"{'Ln':<4} {'Date':<8} {'Description':<50} {'Withdrawal':>12} {'Deposit':>12} {'PDF Bal':>12} {'Calc Bal':>12} {'Status'}")
    print("-"*100)
    
    running_balance = -251.26  # Opening from Mar 31 closing
    total_withdrawals = 0.0
    total_deposits = 0.0
    all_match = True
    
    for ln, date, desc, withdrawal, deposit, pdf_balance in transactions:
        # Skip opening/closing balance markers
        if 'Opening balance' in desc or 'Closing balance' in desc or 'Balance forward' in desc:
            status = '—'
            print(f"{ln:<4} {date:<8} {desc:<50} {'':>12} {'':>12} {pdf_balance:>12.2f} {'':>12} {status}")
            continue
        
        # Update running balance
        if withdrawal:
            running_balance -= withdrawal
            total_withdrawals += withdrawal
        if deposit:
            running_balance += deposit
            total_deposits += deposit
        
        # Compare with PDF balance
        diff = abs(running_balance - pdf_balance)
        if diff < 0.01:  # Penny-perfect match
            status = '✓'
        else:
            status = f'⚠️ DIFF ${diff:.2f}'
            all_match = False
        
        w_str = f'${withdrawal:.2f}' if withdrawal else ''
        d_str = f'${deposit:.2f}' if deposit else ''
        
        print(f"{ln:<4} {date:<8} {desc:<50} {w_str:>12} {d_str:>12} {pdf_balance:>12.2f} {running_balance:>12.2f} {status}")
    
    print("-"*100)
    print(f"{'Total Withdrawals:':<63} ${total_withdrawals:>12,.2f}")
    print(f"{'Total Deposits:':<63} ${total_deposits:>12,.2f}")
    print(f"{'Net Change:':<63} ${total_deposits - total_withdrawals:>12,.2f}")
    print()
    print(f"Opening: ${-251.26:.2f} | Net Change: ${total_deposits - total_withdrawals:+.2f} | Closing: ${running_balance:.2f}")
    print(f"Expected Closing (PDF): ${-899.63:.2f}")
    print()
    
    if all_match:
        print("✓ PERFECT MATCH! All April transactions verified")
    else:
        print("⚠️ DISCREPANCIES FOUND - Review needed")
    
    print("="*100 + "\n")

if __name__ == '__main__':
    main()
