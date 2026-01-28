"""
Import Fibrenew statement data (2019-2025) into rent_debt_ledger table.
Creates CHARGE and PAYMENT entries with running balance calculation.
"""
import psycopg2
import re
from datetime import datetime
from decimal import Decimal
import argparse
import os

os.environ['DB_HOST'] = 'localhost'
os.environ['DB_NAME'] = 'almsdata'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = '***REMOVED***'

# Complete statement data from PDF
STATEMENT_DATA = """
01/02/2019 Invoice #8696: Due 301.48 193.84
01/03/2019 Invoice #8693: Due 682.50 682.50
01/03/2019 Invoice #8697: Due 345.88 345.88
01/04/2019 Invoice #8695: Due 682.50 682.50
07/05/2019 Invoice #8690: Due 295.69 295.69
07/05/2019 Invoice #8691: Due 682.50 682.50
31/05/2019 Invoice #8743: Due 682.50 682.50
31/05/2019 Invoice #8744: Due 254.32 254.32
01/07/2019 Invoice #8832: Due 682.50 682.50
11/07/2019 Invoice #8833: Due 153.13 153.13
06/08/2019 Invoice #8894: Due 144.89 144.89
06/08/2019 Invoice #8895: Due 682.50 682.50
04/09/2019 Invoice #8942: Due 682.50 682.50
04/09/2019 Invoice #8943: Due 183.91 183.91
01/10/2019 Invoice #8979: Due 682.50 682.50
01/10/2019 Invoice #8980: Due 152.62 152.62
01/11/2019 Invoice #9025: Due 163.46 163.46
06/11/2019 Invoice #9066: Due 682.50 682.50
06/11/2019 Invoice #9067: Due 157.88 157.88
04/12/2019 Invoice #9103: Due 126.60 126.60
01/01/2020 Invoice #9135: Due 682.50 682.50
08/01/2020 Invoice #9139: Due 190.20 190.20
01/02/2020 Invoice #9172: Due 682.50 682.50
14/02/2020 Invoice #9201: Due 228.12 228.12
02/03/2020 Invoice #9239: Due 682.50 682.50
30/03/2020 Invoice #9288: Due 304.47 304.47
01/04/2020 Invoice #9287: Due 682.50 682.50
14/05/2020 Invoice #9325: Due 199.26 199.26
23/06/2020 Invoice #9392: Due 156.64 156.64
02/07/2020 Invoice #9407: Due 840.00 840.00
22/07/2020 Invoice #9436: Due 134.81 134.81
05/08/2020 Invoice #9490: Due 840.00 840.00
01/09/2020 Invoice #9542: Due 840.00 840.00
10/09/2020 Invoice #9561: Due 142.63 142.63
01/10/2020 Invoice #9609: Due 840.00 840.00
08/10/2020 Invoice #9623: Due 145.20 145.20
01/11/2020 Invoice #9670: Due 840.00 840.00
18/11/2020 Invoice #9694: Due 162.21 162.21
01/12/2020 Invoice #9727: Due 840.00 840.00
07/12/2020 Invoice #9742: Due 191.25 191.25
01/01/2021 Invoice #9767: Due 840.00 840.00
18/01/2021 Invoice #9772: Due 201.35 201.35
01/02/2021 Invoice #9800: Due 840.00 840.00
05/02/2021 Invoice #9815: Due 169.44 169.44
01/03/2021 Invoice #9866: Due 840.00 840.00
08/03/2021 Invoice #9885: Due 220.34 220.34
06/04/2021 Invoice #9956: Due 840.00 840.00
31/07/2023 Journal Entry #21: -3508.25 -1458.58
31/07/2023 Journal Entry #22: -2767.50 -746.42
22/09/2023 Payment -500.00 -380.64
12/10/2023 Payment -500.00 -500.00
26/10/2023 Payment -500.00 -500.00
01/11/2023 Payment -500.00 -500.00
01/12/2023 Payment -500.00 -500.00
31/12/2023 Payment -400.00 -400.00
02/01/2024 Invoice #12131: 1102.50 1102.50
01/02/2024 Invoice #12132: 1102.50 1102.50
20/02/2024 Payment -300.00 -300.00
01/03/2024 Invoice #12133: 1102.50 1102.50
13/03/2024 Payment -500.00 -500.00
01/04/2024 Invoice #12177: 1102.50 1102.50
18/04/2024 Payment -400.00 -400.00
18/04/2024 Payment -500.00 -500.00
01/05/2024 Invoice #12226: 1102.50 1102.50
13/05/2024 Payment -1200.00 -1200.00
02/07/2024 Payment -1102.50 -1102.50
01/08/2024 Invoice #12419: 1102.50 167.06
01/09/2024 Invoice #12494: 1102.50 1102.50
04/09/2024 Payment -2100.00 -2100.00
11/09/2024 Payment -500.00 -500.00
26/09/2024 Payment -500.00 -500.00
01/10/2024 Invoice #12540: 1102.50 1102.50
15/10/2024 Payment -1000.00 -1000.00
01/11/2024 Invoice #12601: 1102.50 1102.50
04/11/2024 Payment -1102.50 -1102.50
02/12/2024 Invoice #12664: 1102.50 1102.50
05/12/2024 Payment -1500.00 -1500.00
01/01/2025 Invoice #12714: 1102.50 1102.50
07/01/2025 Payment -1200.00 -1200.00
03/02/2025 Invoice #12775: 1102.50 1102.50
04/02/2025 Payment -1102.50 -1102.50
03/03/2025 Invoice #12835: 1102.50 1102.50
10/03/2025 Payment -1102.50 -1102.50
01/04/2025 Invoice #12909: 1102.50 1102.50
08/04/2025 Payment -1102.50 -1102.50
01/05/2025 Invoice #12973: 1102.50 1102.50
14/05/2025 Payment -1102.50 -1102.50
01/06/2025 Invoice #13041: 1102.50 1102.50
10/06/2025 Payment -1102.50 -1102.50
01/07/2025 Invoice #13103: 1102.50 1102.50
04/07/2025 Payment -800.00 -800.00
04/07/2025 Payment -400.00 -400.00
31/07/2025 Payment -2500.00 -2500.00
01/08/2025 Invoice #13180: 1260.00 1260.00
15/08/2025 Payment -300.00 -300.00
01/09/2025 Invoice #13248: 1260.00 1260.00
16/09/2025 Payment -500.00 -500.00
01/10/2025 Invoice #13310: 1260.00 1260.00
02/10/2025 Payment -2000.00 -2000.00
01/11/2025 Invoice #13379: 1260.00 1260.00
10/11/2025 Payment -900.00 -900.00
17/11/2025 Payment -200.00 -200.00
"""

def parse_statement():
    """Parse statement text into structured entries."""
    entries = []
    
    for line in STATEMENT_DATA.strip().split('\n'):
        if not line.strip():
            continue
        
        # Parse date
        date_match = re.match(r'(\d{2}/\d{2}/\d{4})', line)
        if not date_match:
            continue
        
        date_str = date_match.group(1)
        date_obj = datetime.strptime(date_str, '%d/%m/%Y')
        
        # Parse invoice
        invoice_match = re.search(r'Invoice #(\d+):.+?([\d.]+)\s+([\d.]+)$', line)
        if invoice_match:
            entries.append({
                'date': date_obj,
                'type': 'CHARGE',
                'invoice_number': invoice_match.group(1),
                'charge_amount': Decimal(invoice_match.group(2)),
                'payment_amount': Decimal('0'),
                'description': f'Fibrenew Invoice #{invoice_match.group(1)} - Office Rent'
            })
            continue
        
        # Parse journal entry
        journal_match = re.search(r'Journal Entry #(\d+):\s+(-[\d.]+)', line)
        if journal_match:
            entries.append({
                'date': date_obj,
                'type': 'PAYMENT',
                'invoice_number': f'JE{journal_match.group(1)}',
                'charge_amount': Decimal('0'),
                'payment_amount': abs(Decimal(journal_match.group(2))),
                'description': f'Trade of Services - Journal Entry #{journal_match.group(1)}'
            })
            continue
        
        # Parse payment
        payment_match = re.search(r'Payment(?:\s+[#\d/]+)?\s+(-[\d.]+)', line)
        if payment_match:
            entries.append({
                'date': date_obj,
                'type': 'PAYMENT',
                'invoice_number': None,
                'charge_amount': Decimal('0'),
                'payment_amount': abs(Decimal(payment_match.group(1))),
                'description': 'Rent Payment'
            })
            continue
    
    return entries

def main():
    parser = argparse.ArgumentParser(description='Import Fibrenew statement to rent_debt_ledger')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    args = parser.parse_args()
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("FIBRENEW STATEMENT IMPORT TO RENT_DEBT_LEDGER")
    print("=" * 80)
    print()
    
    # Parse statement
    entries = parse_statement()
    print(f"Parsed {len(entries)} entries from statement")
    print()
    
    # Check for existing Fibrenew entries
    cur.execute("""
        SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
        FROM rent_debt_ledger
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
    """)
    existing = cur.fetchone()
    print(f"Existing Fibrenew entries in rent_debt_ledger: {existing[0]}")
    if existing[0] > 0:
        print(f"  Date range: {existing[1]} to {existing[2]}")
    print()
    
    # Summarize entries
    charges = sum(1 for e in entries if e['type'] == 'CHARGE')
    payments = sum(1 for e in entries if e['type'] == 'PAYMENT')
    charge_total = sum(e['charge_amount'] for e in entries)
    payment_total = sum(e['payment_amount'] for e in entries)
    
    print(f"Statement Summary:")
    print(f"  Charges: {charges} ({charge_total:,.2f})")
    print(f"  Payments: {payments} ({payment_total:,.2f})")
    print(f"  Net: {charge_total - payment_total:,.2f}")
    print()
    
    # Show first 10 entries
    print("Sample entries (first 10):")
    print("-" * 80)
    for i, e in enumerate(entries[:10], 1):
        if e['type'] == 'CHARGE':
            print(f"{i:3}. {e['date'].strftime('%Y-%m-%d')} CHARGE  ${e['charge_amount']:>8,.2f} | {e['description']}")
        else:
            print(f"{i:3}. {e['date'].strftime('%Y-%m-%d')} PAYMENT ${e['payment_amount']:>8,.2f} | {e['description']}")
    print()
    
    if not args.write:
        print("=" * 80)
        print("DRY RUN - Use --write to apply changes")
        print("=" * 80)
        cur.close()
        conn.close()
        return
    
    # Import entries with running balance calculation
    print("Importing entries...")
    
    # Get starting balance (if any existing entries)
    cur.execute("""
        SELECT COALESCE(running_balance, 0)
        FROM rent_debt_ledger
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
        ORDER BY transaction_date DESC, id DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    running_balance = row[0] if row else Decimal('0')
    
    print(f"Starting balance: ${running_balance:,.2f}")
    
    imported = 0
    for entry in entries:
        # Check if entry already exists (by date, type, and amount)
        cur.execute("""
            SELECT id FROM rent_debt_ledger
            WHERE vendor_name = 'Fibrenew Central Alberta'
            AND transaction_date = %s
            AND transaction_type = %s
            AND charge_amount = %s
            AND payment_amount = %s
        """, (entry['date'], entry['type'], entry['charge_amount'], entry['payment_amount']))
        
        if cur.fetchone():
            continue  # Skip duplicate
        
        # Calculate new running balance
        if entry['type'] == 'CHARGE':
            running_balance += entry['charge_amount']
        else:
            running_balance -= entry['payment_amount']
        
        # Insert entry
        cur.execute("""
            INSERT INTO rent_debt_ledger (
                transaction_date, transaction_type, vendor_name,
                description, charge_amount, payment_amount,
                running_balance, created_at
            ) VALUES (
                %s, %s, 'Fibrenew Central Alberta',
                %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
        """, (
            entry['date'], entry['type'], entry['description'],
            entry['charge_amount'], entry['payment_amount'],
            running_balance
        ))
        imported += 1
    
    conn.commit()
    
    print(f"Imported {imported} new entries")
    print(f"Final balance: ${running_balance:,.2f}")
    print()
    
    # Verify
    cur.execute("""
        SELECT 
            COUNT(*),
            SUM(charge_amount),
            SUM(payment_amount),
            MAX(running_balance)
        FROM rent_debt_ledger
        WHERE LOWER(vendor_name) LIKE '%fibrenew%'
    """)
    row = cur.fetchone()
    
    print("=" * 80)
    print("VERIFICATION:")
    print(f"  Total entries: {row[0]}")
    print(f"  Total charges: ${row[1]:,.2f}")
    print(f"  Total payments: ${row[2]:,.2f}")
    print(f"  Current balance: ${row[3]:,.2f}")
    print("=" * 80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
