#!/usr/bin/env python3
"""Quick list of all Fibrenew invoices with invoice numbers."""

import pandas as pd
from datetime import datetime
from decimal import Decimal

EXCEL_FILE = r'L:\limo\pdf\2012\fibrenew.xlsx'

def parse_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d']:
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except:
                continue
    return None

def parse_amount(val):
    if pd.isna(val):
        return None
    try:
        return Decimal(str(val))
    except:
        return None

# Read Excel
df = pd.read_excel(EXCEL_FILE, header=None)

excel_invoices = []
seen = {}

for idx, row in df.iterrows():
    col0 = str(row[0]).strip()
    if col0 and col0 not in ['inv', 'pmt', 'statement', 'nan'] and not 'balance' in str(row[1]).lower():
        inv_date = parse_date(row[1])
        inv_amt = parse_amount(row[2])
        
        if inv_date and col0 not in seen:
            amount = inv_amt if inv_amt else Decimal('0')
            if amount > 0:
                excel_invoices.append((col0, inv_date, amount))
                seen[col0] = True

# Statement invoices with numbers
statement = [
    ('8696', datetime(2019, 2, 1).date(), Decimal('301.48')),
    ('8693', datetime(2019, 3, 1).date(), Decimal('682.50')),
    ('8697', datetime(2019, 3, 1).date(), Decimal('345.88')),
    ('8695', datetime(2019, 4, 1).date(), Decimal('682.50')),
    ('8690', datetime(2019, 5, 7).date(), Decimal('295.69')),
    ('8691', datetime(2019, 5, 7).date(), Decimal('682.50')),
    ('8743', datetime(2019, 5, 31).date(), Decimal('682.50')),
    ('8744', datetime(2019, 5, 31).date(), Decimal('254.32')),
    ('8832', datetime(2019, 7, 1).date(), Decimal('682.50')),
    ('8833', datetime(2019, 7, 11).date(), Decimal('153.13')),
    ('8894', datetime(2019, 8, 6).date(), Decimal('144.89')),
    ('8895', datetime(2019, 8, 6).date(), Decimal('682.50')),
    ('8942', datetime(2019, 9, 4).date(), Decimal('682.50')),
    ('8943', datetime(2019, 9, 4).date(), Decimal('183.91')),
    ('8979', datetime(2019, 10, 1).date(), Decimal('682.50')),
    ('8980', datetime(2019, 10, 1).date(), Decimal('152.62')),
    ('9025', datetime(2019, 11, 1).date(), Decimal('163.46')),
    ('9066', datetime(2019, 11, 6).date(), Decimal('682.50')),
    ('9067', datetime(2019, 11, 6).date(), Decimal('157.88')),
    ('9103', datetime(2019, 12, 4).date(), Decimal('126.60')),
    ('9135', datetime(2020, 1, 1).date(), Decimal('682.50')),
    ('9139', datetime(2020, 1, 8).date(), Decimal('190.20')),
    ('9172', datetime(2020, 2, 1).date(), Decimal('682.50')),
    ('9201', datetime(2020, 2, 14).date(), Decimal('228.12')),
    ('9239', datetime(2020, 3, 2).date(), Decimal('682.50')),
    ('9288', datetime(2020, 3, 30).date(), Decimal('304.47')),
    ('9287', datetime(2020, 4, 1).date(), Decimal('682.50')),
    ('9325', datetime(2020, 5, 14).date(), Decimal('199.26')),
    ('9392', datetime(2020, 6, 23).date(), Decimal('156.64')),
    ('9407', datetime(2020, 7, 2).date(), Decimal('840.00')),
    ('9436', datetime(2020, 7, 22).date(), Decimal('134.81')),
    ('9490', datetime(2020, 8, 5).date(), Decimal('840.00')),
    ('9542', datetime(2020, 9, 1).date(), Decimal('840.00')),
    ('9561', datetime(2020, 9, 10).date(), Decimal('142.63')),
    ('9609', datetime(2020, 10, 1).date(), Decimal('840.00')),
    ('9623', datetime(2020, 10, 8).date(), Decimal('145.20')),
    ('9670', datetime(2020, 11, 1).date(), Decimal('840.00')),
    ('9694', datetime(2020, 11, 18).date(), Decimal('162.21')),
    ('9727', datetime(2020, 12, 1).date(), Decimal('840.00')),
    ('9742', datetime(2020, 12, 7).date(), Decimal('191.25')),
    ('9767', datetime(2021, 1, 1).date(), Decimal('840.00')),
    ('9772', datetime(2021, 1, 18).date(), Decimal('201.35')),
    ('9800', datetime(2021, 2, 1).date(), Decimal('840.00')),
    ('9815', datetime(2021, 2, 5).date(), Decimal('169.44')),
    ('9866', datetime(2021, 3, 1).date(), Decimal('840.00')),
    ('9885', datetime(2021, 3, 8).date(), Decimal('220.34')),
    ('9956', datetime(2021, 4, 6).date(), Decimal('840.00')),
    ('12131', datetime(2024, 1, 2).date(), Decimal('1102.50')),
    ('12132', datetime(2024, 2, 1).date(), Decimal('1102.50')),
    ('12133', datetime(2024, 3, 1).date(), Decimal('1102.50')),
    ('12177', datetime(2024, 4, 1).date(), Decimal('1102.50')),
    ('12226', datetime(2024, 5, 1).date(), Decimal('1102.50')),
    ('12419', datetime(2024, 8, 1).date(), Decimal('1102.50')),
    ('12494', datetime(2024, 9, 1).date(), Decimal('1102.50')),
    ('12540', datetime(2024, 10, 1).date(), Decimal('1102.50')),
    ('12601', datetime(2024, 11, 1).date(), Decimal('1102.50')),
    ('12664', datetime(2024, 12, 2).date(), Decimal('1102.50')),
    ('12714', datetime(2025, 1, 1).date(), Decimal('1102.50')),
    ('12775', datetime(2025, 2, 3).date(), Decimal('1102.50')),
    ('12835', datetime(2025, 3, 3).date(), Decimal('1102.50')),
    ('12909', datetime(2025, 4, 1).date(), Decimal('1102.50')),
    ('12973', datetime(2025, 5, 1).date(), Decimal('1102.50')),
    ('13041', datetime(2025, 6, 1).date(), Decimal('1102.50')),
    ('13103', datetime(2025, 7, 1).date(), Decimal('1102.50')),
    ('13180', datetime(2025, 8, 1).date(), Decimal('1260.00')),
    ('13248', datetime(2025, 9, 1).date(), Decimal('1260.00')),
    ('13310', datetime(2025, 10, 1).date(), Decimal('1260.00')),
    ('13379', datetime(2025, 11, 1).date(), Decimal('1260.00')),
]

all_invoices = excel_invoices + statement

print(f"Total invoices: {len(all_invoices)}")
print(f"\nAll invoices with numbers:\n")
for inv_num, inv_date, amount in sorted(all_invoices, key=lambda x: x[1]):
    print(f"{inv_num:6} | {inv_date} | ${amount:>9,.2f}")
