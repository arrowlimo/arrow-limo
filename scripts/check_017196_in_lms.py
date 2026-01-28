#!/usr/bin/env python3
"""
Check LMS Reserve table for reserve 017196 to get the actual charge amount.
"""

import pyodbc

LMS_PATH = r'L:\limo\lms.mdb'
conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(conn_str)
cur = lms_conn.cursor()

print('='*100)
print('LMS RESERVE 017196 DATA')
print('='*100)

cur.execute('''
    SELECT Reserve_No, Account_No, PU_Date, Rate, Est_Charge, Balance, Deposit, Pymt_Type, Name
    FROM Reserve
    WHERE Reserve_No = '017196'
''')

reserve = cur.fetchone()
if reserve:
    print(f'\nReserve Number: {reserve[0]}')
    print(f'Account Number: {reserve[1]}')
    print(f'Pickup Date: {reserve[2]}')
    print(f'Rate: ${reserve[3]:,.2f}' if reserve[3] else 'Rate: None')
    print(f'Est_Charge (TOTAL AMOUNT): ${reserve[4]:,.2f}' if reserve[4] else 'Est_Charge: None')
    print(f'Balance: ${reserve[5]:,.2f}' if reserve[5] else 'Balance: None')
    print(f'Deposit (Total Paid): ${reserve[6]:,.2f}' if reserve[6] else 'Deposit: None')
    print(f'Payment Type: {reserve[7]}')
    print(f'Customer Name: {reserve[8]}')
    
    print('\n\nRECONCILIATION:')
    print('-'*100)
    if reserve[4] and reserve[6]:
        print(f'LMS Est_Charge (amount due): ${reserve[4]:,.2f}')
        print(f'LMS Deposit (amount paid): ${reserve[6]:,.2f}')
        print(f'LMS Balance (calculated): ${reserve[4] - reserve[6]:,.2f}')
        print(f'LMS Balance (field): ${reserve[5]:,.2f}' if reserve[5] else 'LMS Balance (field): None')
        
        if reserve[5] is not None and abs((reserve[4] - reserve[6]) - reserve[5]) < 0.01:
            print('\nLMS Balance Calculation: CORRECT')
        else:
            print(f'\nLMS Balance Calculation: Uses Balance field = ${reserve[5]:,.2f}')
else:
    print('\nReserve 017196 NOT FOUND in LMS')

# Check LMS Payment table
print('\n\n' + '='*100)
print('LMS PAYMENTS FOR RESERVE 017196')
print('='*100)

cur.execute('''
    SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated, LastUpdatedBy
    FROM Payment
    WHERE Reserve_No = '017196'
    ORDER BY LastUpdated
''')

payments = cur.fetchall()
print(f'\n{len(payments)} payments found:')
for p in payments:
    print(f'\nPayment ID: {p[0]}')
    print(f'  Amount: ${p[3]:,.2f}')
    print(f'  Key: {p[4]}')
    print(f'  Date: {p[5]}')
    print(f'  By: {p[6]}')

cur.close()
lms_conn.close()
