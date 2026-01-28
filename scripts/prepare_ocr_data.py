#!/usr/bin/env python3
"""
Helper script to format Excel OCR data for import.

INSTRUCTIONS:
1. Copy all the transaction rows from Excel
2. Paste them below between the triple quotes
3. Run this script to generate formatted TRANSACTIONS list
4. Copy the output into import_scotia_dec2012_jan2013_from_ocr.py
"""

# PASTE YOUR EXCEL DATA HERE (TAB-SEPARATED)
EXCEL_DATA = """
BALANCE FORWARD DEPOSIT	597384700019 00001		01|07	1650|
MCARD DEP CR CHASE		1	|	
PAYMENTTECH			
DEPOSIT 097384700019		1610	
00001 MCARD DEP CR		
CHASE PAYMENTTECH DEPOSIT		
097384700019 00001		
VISA DEP CR CHASE		7306170	
PAYMENTTECH		
PAYMENTTECH		"
BBQ 121 3700210463		/J 9 m N tD !	
RETURNED NSF CHEQUE		500!00	!
DEPOSIT		! !	77100	!
		164!B9
097384700019 00001		
VISA DEP CR CHASE		
PAYMENTTECH		/8ll:75	V	!sll_s
DEPOSIT 097384700019		:	v	I	bl:08
00001 MCARD DEP CR		42150.'v	1522!48	!
CHASE PAYMENTTECH MISC		. blic9
PAYMENT		5440
AMEX 5329877835 AMEX BANK		_ 3B5!oo
OF CANADA		
DMQ 122 3700294555		293:67 "'v
		4751 ./
RETURNED NSF CHEQUE NSF		"
SERVICE CHARGE SERVICE		960!00- I
CHARGE !YBRD$IT		0
OVERDRAWN		63!01
CHQ 123 3700357915		
POINT OF SALE PURCHASE		hilD	
CINEPLEX #3132 GPS RED		I	
DEER ABCD		
DEPOSIT 007384700015		
00001 VISA DEP CR		
CHASE PAYMENTTECH DEPOSIT		
"""

def parse_excel_rows():
    """Parse tab-separated Excel data into transactions."""
    lines = EXCEL_DATA.strip().split('\n')
    transactions = []
    current_desc = []
    current_withdrawal = None
    current_deposit = None
    current_date = None
    current_balance = None
    
    for line in lines:
        parts = [p.strip() for p in line.split('\t')]
        
        # Look for date pattern (contains |)
        for part in parts:
            if '|' in part and len(part) <= 10:
                current_date = part
        
        # Look for amounts (contains digits and decimals)
        for part in parts:
            if not part:
                continue
            # Check if it's a number-like string
            clean = part.replace('|', '').replace('!', '').replace('o', '0').replace('.', '').replace("'", '').replace(' ', '')
            if clean.isdigit() and len(clean) >= 2:
                # Could be amount or balance
                if not current_withdrawal and not current_deposit:
                    if '!' in part or 'o' in part:
                        # Likely an amount with OCR errors
                        current_withdrawal = part
                    else:
                        current_deposit = part
                else:
                    current_balance = part
        
        # Accumulate description
        if parts[0] and not (parts[0].replace('|', '').replace('.', '').replace("'", '').replace(' ', '').isdigit()):
            current_desc.append(parts[0])
        
        # When we hit a date, we likely have a complete transaction
        if current_date and current_desc:
            desc_text = ' '.join(current_desc)
            
            # Emit transaction
            if current_withdrawal or current_deposit:
                withdrawal_str = f"'{current_withdrawal}'" if current_withdrawal else 'None'
                deposit_str = f"{current_deposit}" if current_deposit else 'None'
                
                print(f"    ('{current_date}', '{desc_text}', {withdrawal_str}, {deposit_str}),")
                transactions.append((current_date, desc_text, current_withdrawal, current_deposit))
            
            # Reset
            current_desc = []
            current_withdrawal = None
            current_deposit = None
            current_date = None
            current_balance = None
    
    return transactions

if __name__ == '__main__':
    print("# Formatted TRANSACTIONS for import_scotia_dec2012_jan2013_from_ocr.py")
    print("# Copy this into the TRANSACTIONS list in that file\n")
    print("TRANSACTIONS = [")
    transactions = parse_excel_rows()
    print("]")
    print(f"\n# Total transactions: {len(transactions)}")
