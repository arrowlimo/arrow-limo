#!/usr/bin/env python
"""
Explore LMS Reserve table structure to find the correct total charges column.
"""
import pyodbc

LMS_PATH = r'L:\limo\backups\lms.mdb'
lms_conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
lms_conn = pyodbc.connect(lms_conn_str)
lms_cur = lms_conn.cursor()

print('='*100)
print('LMS Reserve Table Structure')
print('='*100)

# Get all column names
lms_cur.execute("SELECT * FROM Reserve WHERE Reserve_No = '009854'")
columns = [column[0] for column in lms_cur.description]

print(f'\nAll columns ({len(columns)}):')
for i, col in enumerate(columns, 1):
    print(f'  {i:2}. {col}')

# Get sample data to see which fields have values
lms_cur.execute("SELECT * FROM Reserve WHERE Reserve_No = '009854'")
sample = lms_cur.fetchone()

print(f'\nSample data for 009854:')
for col, val in zip(columns, sample):
    if val is not None and val != 0 and val != '':
        print(f'  {col}: {val}')

# Check Est_Charge vs Rate for sample records
print('\n\nComparing Rate vs Est_Charge for sample records:')
lms_cur.execute("""
    SELECT TOP 10 Reserve_No, Rate, Est_Charge, Deposit, Balance
    FROM Reserve 
    WHERE Rate > 0 AND Est_Charge IS NOT NULL
    ORDER BY PU_Date DESC
""")

print('\nRecent records (Reserve_No, Rate, Est_Charge, Deposit, Balance):')
for row in lms_cur.fetchall():
    print(f'  {row}')

lms_cur.close()
lms_conn.close()
print('\nDone.')
