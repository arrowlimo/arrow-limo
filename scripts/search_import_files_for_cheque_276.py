"""
Search CSV import files for cheque 276 transaction
Looking for: Jul 10, 2012, $1,050.00, reference 000000017545393
"""
import csv
import os
from datetime import datetime

# Files to search
files_to_search = [
    r"L:\limo\data\2012_cibc_ocr_data.csv",
    r"L:\limo\exports\banking\imported_2012_cibc_transactions.csv",
    r"L:\limo\staging\2012_parsed_cibc_statements.csv"
]

print("Searching for cheque 276 transaction...")
print("Target: Jul 10, 2012, $1,050.00, reference 000000017545393")
print("=" * 80)

for filepath in files_to_search:
    if not os.path.exists(filepath):
        print(f"\n[FAIL] File not found: {filepath}")
        continue
    
    print(f"\n📄 Checking: {filepath}")
    print(f"   Size: {os.path.getsize(filepath):,} bytes")
    
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            print(f"   Columns: {headers}")
            
            row_count = 0
            july_rows = []
            cheque_276_candidates = []
            
            for row in reader:
                row_count += 1
                
                # Check for July 2012 data
                date_str = None
                for col in ['date', 'transaction_date', 'Date', 'Transaction Date', 'txn_date']:
                    if col in row:
                        date_str = row[col]
                        break
                
                if date_str and ('2012-07' in date_str or 'Jul' in date_str or '7/10/2012' in date_str):
                    july_rows.append(row)
                    
                    # Check for $1,050.00 amount
                    amount_found = False
                    for col in ['amount', 'debit_amount', 'Amount', 'withdrawal', 'Debit']:
                        if col in row:
                            try:
                                amt = row[col].replace('$', '').replace(',', '').strip()
                                if amt and float(amt) == 1050.00:
                                    amount_found = True
                                    break
                            except:
                                pass
                    
                    # Check for reference number
                    ref_found = False
                    for col in ['reference', 'ref_number', 'check_number', 'cheque_number', 'description']:
                        if col in row and row[col]:
                            if '17545393' in str(row[col]) or '276' in str(row[col]):
                                ref_found = True
                                break
                    
                    if amount_found or ref_found:
                        cheque_276_candidates.append(row)
            
            print(f"   Total rows: {row_count}")
            print(f"   July 2012 rows: {len(july_rows)}")
            print(f"   Cheque 276 candidates: {len(cheque_276_candidates)}")
            
            if cheque_276_candidates:
                print("\n   🎯 POTENTIAL MATCHES FOUND:")
                for idx, row in enumerate(cheque_276_candidates, 1):
                    print(f"\n   Match {idx}:")
                    for key, value in row.items():
                        if value:
                            print(f"      {key}: {value}")
            
            # Show sample of July data
            if july_rows and not cheque_276_candidates:
                print(f"\n   Sample July transactions (first 3):")
                for idx, row in enumerate(july_rows[:3], 1):
                    print(f"\n   Row {idx}:")
                    for key, value in list(row.items())[:5]:  # First 5 columns
                        print(f"      {key}: {value}")
    
    except Exception as e:
        print(f"   [FAIL] Error reading file: {e}")

print("\n" + "=" * 80)
print("Search complete.")
