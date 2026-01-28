#!/usr/bin/env python3
"""
Verify March 2013 CIBC banking transactions from PDF reconciliation report.
Opening balance: -$377.77 (from Feb 28 closing)
Closing balance: -$251.26 (from PDF)
"""

# All transactions from March 2013 PDF screenshots
transactions = [
    # Line, Date, Description, Withdrawal, Deposit, PDF Balance
    (1, 'Mar 01', 'Opening balance', None, None, -377.77),
    (2, 'Mar 01', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 116.53, None, -494.30),
    (3, 'Mar 01', 'CORRECTION 00339', None, 116.53, -377.77),
    (4, 'Mar 01', 'NSF CHARGE 00339', 45.00, None, -422.77),
    (5, 'Mar 04', 'INSURANCE Cooperators CSI', 50.00, None, -472.77),
    (6, 'Mar 04', 'CORRECTION 00339', None, 50.00, -422.77),
    (7, 'Mar 04', 'NSF CHARGE 00339', 45.00, None, -467.77),
    (8, 'Mar 05', 'CREDIT MEMO 4017775 MC GBL MC 4017775', None, 615.55, 147.78),
    (9, 'Mar 05', 'CREDIT MEMO 4017775 IDP GBL IDP4017775', None, 847.50, 995.28),
    (10, 'Mar 05', 'ABM WITHDRAWAL 2D54 GAETZ AVE + 67TH ST 00339 4506*********359', 800.00, None, 195.28),
    (11, 'Mar 05', 'ABM WITHDRAWAL 2D54 GAETZ AVE + 67TH ST 00339 4506*********359', 180.00, None, 15.28),
    (12, 'Mar 07', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 101.14, None, -85.86),
    (13, 'Mar 07', 'CORRECTION 00339', None, 101.14, 15.28),
    (14, 'Mar 07', 'CORRECTION 00339', None, 116.53, 131.81),
    (15, 'Mar 07', 'NSF CHARGE 00339', 45.00, None, 86.81),
    
    # Mar 08 section with missing DEBIT MEMO
    (16, 'Mar 08', 'DEBIT MEMO MERCH#4017775 GBL MERCH FEES', 161.53, None, -74.72),
    (17, 'Mar 08', 'CORRECTION 00339', None, 116.53, 41.81),
    (18, 'Mar 08', 'NSF CHARGE 00339', 45.00, None, -3.19),
    (19, 'Mar 08', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 400.00, 396.81),
    (20, 'Mar 08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 202.27, None, 194.54),
    (21, 'Mar 08', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 606.81, None, -412.27),
    (22, 'Mar 08', 'CORRECTION 00339', None, 606.81, 194.54),
    (23, 'Mar 08', 'NSF CHARGE 00339', 45.00, None, 149.54),
    
    (24, 'Mar 11', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 315.00, 464.54),
    (25, 'Mar 12', 'ABM WITHDRAWAL 1E0U GAETZ AVE + 67TH ST 00339 4506*********359', 380.00, None, 84.54),
    (26, 'Mar 14', 'Cheque 285 0000000443Z4877', 200.00, None, -115.46),
    (27, 'Mar 14', 'REVERSAL 443Z4877', None, 200.00, 84.54),
    (28, 'Mar 14', 'NSF CHARGE 00339', 45.00, None, 39.54),
    (29, 'Mar 15', 'CREDIT MEMO 4017775 VISA GBL VI 4017775', None, 205.00, 244.54),
    (30, 'Mar 18', 'DEPOSIT', None, 2835.00, 3079.54),
    (31, 'Mar 18', 'INTERNET BILL PMT0000000674Z4J IFS FINANCIAL SERVICES IN 4506*********359', 2474.74, None, 604.80),
    (32, 'Mar 18', 'ABM WITHDRAWAL 2D54 GAETZ AVE + 67TH ST 00339 4506*********359', 500.00, None, 104.80),
    (33, 'Mar 20', 'RENT/LEASE 000000000000000 LEASE FINANCE GR', 606.81, None, -502.01),
    (34, 'Mar 20', 'CORRECTION 00339', None, 606.81, 104.80),
    (35, 'Mar 20', 'NSF CHARGE 00339', 45.00, None, 59.80),
    
    # Page 4
    (36, 'Mar 20', 'Balance forward', None, None, 59.80),
    (37, 'Mar 25', 'INSURANCE IFS PREMIUM FIN', 2383.24, None, -2323.44),
    (38, 'Mar 25', 'INSURANCE Cooperators CSI', 152.53, None, -2475.97),
    (39, 'Mar 25', 'CORRECTION 00339', None, 2383.24, -92.73),
    (40, 'Mar 25', 'NSF CHARGE 00339', 45.00, None, -137.73),
    (41, 'Mar 28', 'OVERDRAFT S/C', 5.00, None, -142.73),
    (42, 'Mar 28', 'ACCOUNT FEE', 35.00, None, -177.73),
    (43, 'Mar 28', 'OVERDRAFT INTEREST', 2.00, None, -179.73),
    (44, 'Mar 31', 'Closing balance', None, None, -179.73),
]

def main():
    print("\n" + "="*100)
    print("MARCH 2013 CIBC BANKING VERIFICATION")
    print("="*100)
    print(f"{'Ln':<4} {'Date':<8} {'Description':<50} {'Withdrawal':>12} {'Deposit':>12} {'PDF Bal':>12} {'Calc Bal':>12} {'Status'}")
    print("-"*100)
    
    running_balance = -377.77  # Opening from Feb 28 closing
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
    print(f"Opening: ${-377.77:.2f} | Net Change: ${total_deposits - total_withdrawals:+.2f} | Closing: ${running_balance:.2f}")
    print(f"Expected Closing (PDF): ${-179.73:.2f}")
    print()
    
    if all_match:
        print("✓ PERFECT MATCH! All March transactions verified")
    else:
        print("⚠️ DISCREPANCIES FOUND - Review needed")
    
    print("="*100 + "\n")

if __name__ == '__main__':
    main()
