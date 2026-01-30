#!/usr/bin/env python3
"""Identify problematic payroll entries: duplicates, zero deductions, missing data."""
import os, psycopg2

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

def table_has_column(cur, table, column):
    cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (table, column))
    return cur.fetchone() is not None

def find_zero_deduction_entries(cur, year):
    """Find entries with gross pay but zero CPP/EI/Tax"""
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    
    fields = ['id', 'driver_id', date_col, 'gross_pay', 'cpp', 'ei', 'tax']
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        fields.append('payroll_class')
    if table_has_column(cur, 'driver_payroll', 'source'):
        fields.append('source')
    
    base = f"""
    SELECT {', '.join(fields)}
    FROM driver_payroll
    WHERE {date_col} >= %s AND {date_col} < %s
      AND gross_pay > 0
      AND COALESCE(cpp, 0) = 0
      AND COALESCE(ei, 0) = 0
      AND COALESCE(tax, 0) = 0
    """
    
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        base += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
    
    base += f" ORDER BY gross_pay DESC"
    
    start = f"{year}-01-01"
    end = f"{year+1}-01-01"
    cur.execute(base, (start, end))
    
    entries = []
    for row in cur.fetchall():
        entry = {
            'id': row[0],
            'driver_id': row[1],
            'date': row[2],
            'gross_pay': float(row[3] or 0),
            'cpp': float(row[4] or 0),
            'ei': float(row[5] or 0),
            'tax': float(row[6] or 0)
        }
        if len(row) > 7:
            entry['payroll_class'] = row[7]
        if len(row) > 8:
            entry['source'] = row[8]
        entries.append(entry)
    
    return entries

def find_duplicate_entries(cur, year):
    """Find duplicate entries (same driver, date, amount)"""
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    
    base = f"""
    SELECT 
        driver_id,
        {date_col} as pay_date,
        gross_pay,
        COUNT(*) as dup_count,
        ARRAY_AGG(id ORDER BY id) as ids,
        SUM(gross_pay) as total_gross
    FROM driver_payroll
    WHERE {date_col} >= %s AND {date_col} < %s
    """
    
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        base += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
    
    base += f"""
    GROUP BY driver_id, {date_col}, gross_pay
    HAVING COUNT(*) > 1
    ORDER BY total_gross DESC
    """
    
    start = f"{year}-01-01"
    end = f"{year+1}-01-01"
    cur.execute(base, (start, end))
    
    duplicates = []
    for row in cur.fetchall():
        duplicates.append({
            'driver_id': row[0],
            'date': row[1],
            'gross_pay': float(row[2] or 0),
            'dup_count': int(row[3]),
            'ids': row[4],
            'total_gross': float(row[5] or 0)
        })
    
    return duplicates

def find_high_value_entries(cur, year, threshold=10000):
    """Find unusually high individual payroll entries"""
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    
    fields = ['id', 'driver_id', date_col, 'gross_pay', 'cpp', 'ei', 'tax']
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        fields.append('payroll_class')
    
    base = f"""
    SELECT {', '.join(fields)}
    FROM driver_payroll
    WHERE {date_col} >= %s AND {date_col} < %s
      AND gross_pay > %s
    """
    
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        base += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
    
    base += " ORDER BY gross_pay DESC"
    
    start = f"{year}-01-01"
    end = f"{year+1}-01-01"
    cur.execute(base, (start, end, threshold))
    
    entries = []
    for row in cur.fetchall():
        entry = {
            'id': row[0],
            'driver_id': row[1],
            'date': row[2],
            'gross_pay': float(row[3] or 0),
            'cpp': float(row[4] or 0),
            'ei': float(row[5] or 0),
            'tax': float(row[6] or 0)
        }
        if len(row) > 7:
            entry['payroll_class'] = row[7]
        entries.append(entry)
    
    return entries

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, required=True)
    args = parser.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    print(f"\n{'='*100}")
    print(f"PROBLEMATIC PAYROLL ANALYSIS ({args.year})")
    print(f"{'='*100}\n")
    
    # 1. Zero deduction entries
    zero_ded = find_zero_deduction_entries(cur, args.year)
    total_zero = sum(e['gross_pay'] for e in zero_ded)
    
    print(f"1. ZERO DEDUCTIONS (Gross pay with $0 CPP/EI/Tax)")
    print(f"   Entries: {len(zero_ded)}")
    print(f"   Total Gross: ${total_zero:,.2f}")
    
    if zero_ded:
        print(f"\n   {'ID':<8} {'Driver':<12} {'Date':<12} {'Gross Pay':>15} {'Class':<15} {'Source':<20}")
        print(f"   {'-'*95}")
        for entry in zero_ded[:20]:  # Top 20
            pclass = entry.get('payroll_class', '')
            source = entry.get('source', '')
            print(f"   {entry['id']:<8} {entry['driver_id']:<12} {str(entry['date']):<12} ${entry['gross_pay']:>14,.2f} {str(pclass):<15} {str(source):<20}")
        if len(zero_ded) > 20:
            print(f"   ... and {len(zero_ded)-20} more")
    
    # 2. Duplicates
    duplicates = find_duplicate_entries(cur, args.year)
    total_dup_impact = sum(d['total_gross'] - d['gross_pay'] for d in duplicates)  # Extra amount from dupes
    
    print(f"\n2. DUPLICATE ENTRIES (Same driver, date, amount)")
    print(f"   Duplicate Groups: {len(duplicates)}")
    print(f"   Extra Amount: ${total_dup_impact:,.2f}")
    
    if duplicates:
        print(f"\n   {'Driver':<12} {'Date':<12} {'Amount':>12} {'Count':>6} {'Total':>15} {'IDs':<30}")
        print(f"   {'-'*95}")
        for dup in duplicates[:15]:  # Top 15
            ids_str = ', '.join(str(i) for i in dup['ids'][:5])
            if len(dup['ids']) > 5:
                ids_str += '...'
            print(f"   {dup['driver_id']:<12} {str(dup['date']):<12} ${dup['gross_pay']:>11,.2f} {dup['dup_count']:>6} ${dup['total_gross']:>14,.2f} {ids_str:<30}")
        if len(duplicates) > 15:
            print(f"   ... and {len(duplicates)-15} more")
    
    # 3. High value entries
    high_value = find_high_value_entries(cur, args.year, threshold=10000)
    total_high = sum(e['gross_pay'] for e in high_value)
    
    print(f"\n3. HIGH VALUE ENTRIES (>$10,000 single entry)")
    print(f"   Entries: {len(high_value)}")
    print(f"   Total Gross: ${total_high:,.2f}")
    
    if high_value:
        print(f"\n   {'ID':<8} {'Driver':<12} {'Date':<12} {'Gross Pay':>15} {'CPP':>10} {'EI':>10} {'Tax':>10}")
        print(f"   {'-'*95}")
        for entry in high_value:
            print(f"   {entry['id']:<8} {entry['driver_id']:<12} {str(entry['date']):<12} ${entry['gross_pay']:>14,.2f} ${entry['cpp']:>9,.2f} ${entry['ei']:>9,.2f} ${entry['tax']:>9,.2f}")
    
    # Summary
    print(f"\n{'='*100}")
    print(f"SUMMARY OF ISSUES")
    print(f"{'='*100}")
    print(f"Zero Deduction Impact:   ${total_zero:>14,.2f}  ({len(zero_ded)} entries)")
    print(f"Duplicate Impact:        ${total_dup_impact:>14,.2f}  ({len(duplicates)} groups)")
    print(f"High Value Total:        ${total_high:>14,.2f}  ({len(high_value)} entries)")
    print(f"{'-'*100}")
    print(f"Total Problematic:       ${total_zero + total_dup_impact:>14,.2f}")
    print(f"\n[WARN]  These amounts should likely be excluded from PD7A calculations")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
