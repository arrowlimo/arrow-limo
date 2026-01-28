#!/usr/bin/env python3
"""
Complete verification summary: chargesummary.xls vs database
"""

import pandas as pd
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def main():
    print("=" * 100)
    print("CHARGESUMMARY.XLS VERIFICATION - FINAL REPORT")
    print("=" * 100)
    print()
    
    xls_path = r'L:\limo\chargesummary.xls'
    
    # Read Excel
    df = pd.read_excel(xls_path, sheet_name='Sheet1', header=11)
    df.columns = [str(col).strip().replace('\n', ' ') for col in df.columns]
    df = df.dropna(how='all')
    
    # Exclude total/subtotal rows
    first_col = df.columns[0]
    df[first_col] = df[first_col].astype(str)
    df = df[~df[first_col].str.contains('Sub-Total|Total|TOTAL|Grand', case=False, na=False)].copy()
    
    # Filter to valid data
    reserve_num_col = 'Reserve  Number'
    total_col = 'Total'
    
    df['reserve_numeric'] = pd.to_numeric(df[reserve_num_col], errors='coerce')
    df = df[df['reserve_numeric'].notna()].copy()
    df['total_numeric'] = pd.to_numeric(df[total_col], errors='coerce')
    df = df[df['total_numeric'].notna()].copy()
    df = df[df['total_numeric'] < 100000].copy()
    
    excel_total = df['total_numeric'].sum()
    excel_count = len(df)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Aggregate charter_charges by reserve
    cur.execute("""
        SELECT 
            reserve_number,
            COUNT(*) as charge_count,
            SUM(COALESCE(amount, 0)) as total_amount
        FROM charter_charges
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
        ORDER BY reserve_number
    """)
    
    db_aggregated = {row[0]: (row[1], float(row[2])) for row in cur.fetchall()}
    
    print("EXCEL CHARGESUMMARY.XLS (Aggregated by Reserve):")
    print(f"  Total reserves: {excel_count:,}")
    print(f"  Total charges: ${excel_total:,.2f}")
    print(f"  Average per reserve: ${excel_total/excel_count:,.2f}")
    print()
    
    print("DATABASE CHARTER_CHARGES (Aggregated by Reserve):")
    print(f"  Total reserves: {len(db_aggregated):,}")
    db_total_aggregated = sum(amt for _, amt in db_aggregated.values())
    db_charge_lines = sum(cnt for cnt, _ in db_aggregated.values())
    print(f"  Total charge line items: {db_charge_lines:,}")
    print(f"  Total amount: ${db_total_aggregated:,.2f}")
    print(f"  Average per reserve: ${db_total_aggregated/len(db_aggregated):,.2f}")
    print()
    
    # Compare reserve by reserve
    print("=" * 100)
    print("RESERVE-LEVEL COMPARISON:")
    print("=" * 100)
    print()
    
    exact_matches = 0
    close_matches = 0
    differences = []
    only_in_excel = []
    only_in_db = []
    
    for _, row in df.iterrows():
        reserve_num = str(int(row['reserve_numeric'])).zfill(6)
        excel_amt = row['total_numeric']
        
        if reserve_num in db_aggregated:
            db_charge_cnt, db_amt = db_aggregated[reserve_num]
            diff = abs(excel_amt - db_amt)
            
            if diff < 0.01:
                exact_matches += 1
            elif diff < 1.00:
                close_matches += 1
            else:
                differences.append((reserve_num, excel_amt, db_amt, diff))
        else:
            only_in_excel.append((reserve_num, excel_amt))
    
    # Reserves only in DB
    excel_reserves = {str(int(r)).zfill(6) for r in df['reserve_numeric']}
    for reserve_num in db_aggregated:
        if reserve_num not in excel_reserves:
            charge_cnt, amt = db_aggregated[reserve_num]
            only_in_db.append((reserve_num, amt))
    
    print(f"Exact matches (diff < $0.01): {exact_matches:,} reserves ({100*exact_matches/excel_count:.1f}%)")
    print(f"Close matches (diff < $1.00): {close_matches:,} reserves ({100*close_matches/excel_count:.1f}%)")
    print(f"Differences (diff >= $1.00): {len(differences):,} reserves ({100*len(differences)/excel_count:.1f}%)")
    print(f"Only in Excel: {len(only_in_excel):,} reserves")
    print(f"Only in Database: {len(only_in_db):,} reserves")
    print()
    
    if differences:
        print("Top 20 differences:")
        differences.sort(key=lambda x: x[3], reverse=True)
        for reserve, excel_amt, db_amt, diff in differences[:20]:
            print(f"  Reserve {reserve}: Excel=${excel_amt:,.2f}, DB=${db_amt:,.2f}, Diff=${diff:,.2f}")
        print()
    
    if only_in_excel:
        print(f"Reserves only in Excel ({len(only_in_excel)} total):")
        for reserve, amt in only_in_excel[:20]:
            print(f"  Reserve {reserve}: Excel=${amt:,.2f}")
        print()
    
    if only_in_db:
        print(f"Reserves only in Database ({len(only_in_db)} total):")
        for reserve, amt in only_in_db[:20]:
            print(f"  Reserve {reserve}: DB=${amt:,.2f}")
        print()
    
    print("=" * 100)
    print("SUMMARY:")
    print("=" * 100)
    print()
    
    accuracy = 100 * (exact_matches + close_matches) / excel_count
    print(f"[OK] Data Quality: {accuracy:.2f}% of reserves match exactly or very closely")
    print()
    print(f"Excel report total: ${excel_total:,.2f}")
    print(f"Database aggregated total: ${db_total_aggregated:,.2f}")
    diff_amt = db_total_aggregated - excel_total
    print(f"Difference: ${diff_amt:,.2f} ({100*diff_amt/excel_total:+.1f}%)")
    print()
    
    if accuracy > 95:
        print("[OK] EXCELLENT DATA INTEGRITY - Excel report matches database")
    elif accuracy > 90:
        print("[WARN] GOOD - Minor discrepancies need investigation")
    else:
        print("[FAIL] NEEDS INVESTIGATION - Significant differences found")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
