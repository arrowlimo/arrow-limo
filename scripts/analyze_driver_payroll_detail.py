#!/usr/bin/env python3
"""Analyze individual driver payroll entries to identify discrepancies.
Shows per-driver breakdown comparing driver_payroll table vs what should be in PD7A.
"""
import os, psycopg2, argparse

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

def table_has_column(cur, table, column):
    cur.execute("SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s", (table, column))
    return cur.fetchone() is not None

def get_drivers_for_year(cur, year):
    """Get list of all drivers with payroll entries for the year"""
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    
    base = f"""
    SELECT DISTINCT 
        driver_id,
        COUNT(*) as entry_count,
        ROUND(SUM(gross_pay)::numeric,2) as total_gross,
        ROUND(SUM(cpp)::numeric,2) as total_cpp,
        ROUND(SUM(ei)::numeric,2) as total_ei,
        ROUND(SUM(tax)::numeric,2) as total_tax
    FROM driver_payroll
    WHERE {date_col} >= %s AND {date_col} < %s
    """
    
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        base += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
    
    base += " GROUP BY driver_id ORDER BY total_gross DESC"
    
    start = f"{year}-01-01"
    end = f"{year+1}-01-01"
    cur.execute(base, (start, end))
    
    drivers = []
    for row in cur.fetchall():
        drivers.append({
            'driver_id': row[0],
            'entry_count': int(row[1]),
            'total_gross': float(row[2] or 0),
            'total_cpp': float(row[3] or 0),
            'total_ei': float(row[4] or 0),
            'total_tax': float(row[5] or 0)
        })
    return drivers

def get_driver_entries(cur, driver_id, year):
    """Get all payroll entries for a specific driver"""
    has_pay_date = table_has_column(cur, 'driver_payroll', 'pay_date')
    date_col = 'pay_date' if has_pay_date else 'imported_at'
    
    fields = ['id', date_col, 'gross_pay', 'cpp', 'ei', 'tax', 'charter_id', 'reserve_number']
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        fields.append('payroll_class')
    if table_has_column(cur, 'driver_payroll', 'source'):
        fields.append('source')
    
    base = f"""
    SELECT {', '.join(fields)}
    FROM driver_payroll
    WHERE driver_id = %s 
      AND {date_col} >= %s AND {date_col} < %s
    """
    
    if table_has_column(cur, 'driver_payroll', 'payroll_class'):
        base += " AND (payroll_class <> 'ADJUSTMENT' OR payroll_class IS NULL)"
    
    base += f" ORDER BY {date_col}"
    
    start = f"{year}-01-01"
    end = f"{year+1}-01-01"
    cur.execute(base, (driver_id, start, end))
    
    entries = []
    for row in cur.fetchall():
        entry = {
            'id': row[0],
            'date': row[1],
            'gross_pay': float(row[2] or 0),
            'cpp': float(row[3] or 0),
            'ei': float(row[4] or 0),
            'tax': float(row[5] or 0),
            'charter_id': row[6],
            'reserve_number': row[7]
        }
        if len(row) > 8:
            entry['payroll_class'] = row[8]
        if len(row) > 9:
            entry['source'] = row[9]
        entries.append(entry)
    return entries

def check_duplicates(entries):
    """Check for potential duplicate entries"""
    seen = {}
    duplicates = []
    
    for entry in entries:
        key = (entry['date'], entry['gross_pay'], entry['charter_id'])
        if key in seen:
            duplicates.append({
                'original_id': seen[key]['id'],
                'duplicate_id': entry['id'],
                'date': entry['date'],
                'amount': entry['gross_pay']
            })
        else:
            seen[key] = entry
    
    return duplicates

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, required=True, help='Year to analyze')
    parser.add_argument('--driver', help='Specific driver_id to analyze (or omit for summary)')
    parser.add_argument('--limit', type=int, default=10, help='Limit number of drivers shown in summary')
    args = parser.parse_args()
    
    conn = get_conn()
    cur = conn.cursor()
    
    if args.driver:
        # Single driver drill-down
        print(f"\n{'='*90}")
        print(f"DRIVER PAYROLL DETAIL: {args.driver} ({args.year})")
        print(f"{'='*90}\n")
        
        entries = get_driver_entries(cur, args.driver, args.year)
        
        if not entries:
            print(f"No payroll entries found for driver {args.driver} in {args.year}")
            return
        
        print(f"Total Entries: {len(entries)}")
        print(f"Total Gross:   ${sum(e['gross_pay'] for e in entries):,.2f}")
        print(f"Total CPP:     ${sum(e['cpp'] for e in entries):,.2f}")
        print(f"Total EI:      ${sum(e['ei'] for e in entries):,.2f}")
        print(f"Total Tax:     ${sum(e['tax'] for e in entries):,.2f}")
        
        # Check for duplicates
        duplicates = check_duplicates(entries)
        if duplicates:
            print(f"\n[WARN]  POTENTIAL DUPLICATES FOUND: {len(duplicates)}")
            for dup in duplicates[:5]:  # Show first 5
                print(f"   IDs {dup['original_id']} & {dup['duplicate_id']}: {dup['date']} ${dup['amount']:,.2f}")
        
        print(f"\n{'Date':<12} {'Gross Pay':>12} {'CPP':>10} {'EI':>10} {'Tax':>10} {'Charter':>10} {'Reserve':>10}")
        print(f"{'-'*90}")
        
        for entry in entries:
            charter = entry.get('charter_id') or ''
            reserve = entry.get('reserve_number') or ''
            print(f"{str(entry['date']):<12} ${entry['gross_pay']:>11,.2f} ${entry['cpp']:>9,.2f} ${entry['ei']:>9,.2f} ${entry['tax']:>9,.2f} {str(charter):>10} {str(reserve):>10}")
        
    else:
        # Summary of all drivers
        print(f"\n{'='*90}")
        print(f"DRIVER PAYROLL SUMMARY ({args.year})")
        print(f"{'='*90}\n")
        
        drivers = get_drivers_for_year(cur, args.year)
        
        if not drivers:
            print(f"No payroll entries found for {args.year}")
            return
        
        print(f"Total Drivers: {len(drivers)}")
        print(f"Total Gross:   ${sum(d['total_gross'] for d in drivers):,.2f}")
        print(f"Total CPP:     ${sum(d['total_cpp'] for d in drivers):,.2f}")
        print(f"Total EI:      ${sum(d['total_ei'] for d in drivers):,.2f}")
        print(f"Total Tax:     ${sum(d['total_tax'] for d in drivers):,.2f}")
        
        print(f"\nTop {args.limit} Drivers by Gross Pay:")
        print(f"{'Driver ID':<20} {'Entries':>8} {'Gross Pay':>15} {'CPP':>12} {'EI':>12} {'Tax':>12}")
        print(f"{'-'*90}")
        
        for driver in drivers[:args.limit]:
            print(f"{driver['driver_id']:<20} {driver['entry_count']:>8} ${driver['total_gross']:>14,.2f} ${driver['total_cpp']:>11,.2f} ${driver['total_ei']:>11,.2f} ${driver['total_tax']:>11,.2f}")
        
        print(f"\nUse --driver <driver_id> to see detailed entries for a specific driver")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
