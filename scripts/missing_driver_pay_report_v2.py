import psycopg2
import os
from collections import defaultdict
from datetime import datetime, timedelta

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def normalize_driver_name(name):
    """Normalize driver names for fuzzy matching"""
    if not name:
        return ""
    # Remove extra whitespace, convert to lowercase
    name = ' '.join(name.lower().split())
    # Remove common prefixes/suffixes
    name = name.replace('driver', '').strip()
    # Remove driver code prefixes like "dr" from "dr100"
    if name.startswith('dr') and len(name) > 2:
        name = name[2:]
    return name

def get_charter_activity(conn):
    """Get all charter activity with driver assignments"""
    cur = conn.cursor()
    
    # Query the charters table with correct column names
    cur.execute("""
        SELECT 
            charter_date,
            driver_name,
            driver,
            charter_id,
            reserve_number,
            client_id,
            driver_total,
            driver_paid,
            status,
            rate,
            calculated_hours,
            driver_base_pay,
            driver_gratuity
        FROM charters
        WHERE charter_date IS NOT NULL
          AND cancelled = FALSE
          AND (driver IS NOT NULL OR driver_name IS NOT NULL)
        ORDER BY charter_date, charter_id
    """)
    
    results = cur.fetchall()
    print(f"Found {len(results)} charter records with drivers assigned")
    cur.close()
    return results

def get_driver_pay(conn):
    """Get all driver pay records from staging"""
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            txn_date,
            driver_name,
            amount,
            source_file,
            memo
        FROM staging_driver_pay
        WHERE driver_name IS NOT NULL
          AND txn_date IS NOT NULL
        ORDER BY driver_name, txn_date
    """)
    results = cur.fetchall()
    cur.close()
    return results

def analyze_missing_pay(charters, pay_records):
    """Analyze which charters have no corresponding pay records"""
    
    # Build pay lookup: (normalized_driver, date) -> amount
    pay_lookup = defaultdict(list)
    for txn_date, driver_name, amount, source_file, memo in pay_records:
        norm_name = normalize_driver_name(driver_name)
        pay_lookup[(norm_name, txn_date)].append({
            'amount': amount,
            'source': source_file,
            'memo': memo
        })
    
    print(f"\nTotal pay records: {len(pay_records)}")
    print(f"Unique driver-date combinations: {len(pay_lookup)}")
    
    # Check each charter for matching pay
    missing = []
    found = []
    name_mismatches = defaultdict(list)
    
    for charter in charters:
        charter_date = charter[0]
        driver_name_col = charter[1]  # driver_name column
        driver_code = charter[2]  # driver column (Dr100, Dr06, etc.)
        charter_id = charter[3]
        reserve_number = charter[4]
        client_id = charter[5]
        driver_total = charter[6]
        driver_paid = charter[7]
        status = charter[8]
        rate = charter[9]
        calculated_hours = charter[10]
        driver_base_pay = charter[11]
        driver_gratuity = charter[12]
        
        # Try both driver name fields
        driver_names = [d for d in [driver_name_col, driver_code] if d]
        
        if not driver_names or not charter_date:
            continue
        
        matched = False
        matched_driver = None
        
        for driver_name in driver_names:
            norm_name = normalize_driver_name(driver_name)
            
            # Check exact date match
            if (norm_name, charter_date) in pay_lookup:
                matched = True
                matched_driver = driver_name
                found.append({
                    'charter_date': charter_date,
                    'driver': driver_name,
                    'charter_id': charter_id,
                    'client_id': client_id,
                    'charter_total': driver_total,
                    'driver_paid': driver_paid,
                    'pay_records': pay_lookup[(norm_name, charter_date)]
                })
                break
            
            # Check within 7 days window (pay might be batched)
            for days_offset in range(-7, 8):
                if days_offset == 0:
                    continue
                check_date = charter_date + timedelta(days=days_offset)
                if (norm_name, check_date) in pay_lookup:
                    matched = True
                    matched_driver = driver_name
                    found.append({
                        'charter_date': charter_date,
                        'driver': driver_name,
                        'charter_id': charter_id,
                        'client_id': client_id,
                        'charter_total': driver_total,
                        'driver_paid': driver_paid,
                        'pay_date': check_date,
                        'date_offset': days_offset,
                        'pay_records': pay_lookup[(norm_name, check_date)]
                    })
                    break
            
            if matched:
                break
        
        if not matched:
            missing.append({
                'charter_date': charter_date,
                'driver_names': driver_names,
                'charter_id': charter_id,
                'reserve_number': reserve_number,
                'client_id': client_id,
                'driver_total': driver_total,
                'driver_paid': driver_paid,
                'status': status,
                'rate': rate,
                'calculated_hours': calculated_hours,
                'driver_base_pay': driver_base_pay,
                'driver_gratuity': driver_gratuity
            })
            
            # Track name variations for this date
            for driver_name in driver_names:
                norm_name = normalize_driver_name(driver_name)
                # Check if there's ANY pay on this date (different driver name)
                for (pay_norm_name, pay_date), records in pay_lookup.items():
                    if pay_date == charter_date and pay_norm_name != norm_name:
                        name_mismatches[charter_date].append({
                            'charter_driver': driver_name,
                            'pay_driver': pay_norm_name,
                            'charter_id': charter_id,
                            'pay_records': records
                        })
    
    return missing, found, name_mismatches

def generate_report(missing, found, name_mismatches):
    """Generate detailed report"""
    
    output = []
    output.append("=" * 100)
    output.append("DRIVER PAY vs CHARTER ACTIVITY ANALYSIS")
    output.append("=" * 100)
    output.append(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append("")
    
    output.append("SUMMARY:")
    output.append("-" * 100)
    output.append(f"Charters with matching pay: {len(found)}")
    output.append(f"Charters with MISSING pay: {len(missing)}")
    output.append(f"Dates with potential name mismatches: {len(name_mismatches)}")
    output.append("")
    
    if missing:
        output.append("=" * 100)
        output.append("CHARTERS WITH MISSING PAY RECORDS")
        output.append("=" * 100)
        output.append("")
        
        # Group by driver
        by_driver = defaultdict(list)
        for item in missing:
            driver_key = ', '.join(item['driver_names'])
            by_driver[driver_key].append(item)
        
        for driver, items in sorted(by_driver.items()):
            output.append(f"\nDriver: {driver}")
            output.append(f"Missing pay records: {len(items)}")
            output.append("-" * 100)
            
            # Group by year-month
            by_month = defaultdict(list)
            for item in items:
                month_key = item['charter_date'].strftime('%Y-%m')
                by_month[month_key].append(item)
            
            for month, month_items in sorted(by_month.items()):
                output.append(f"\n  {month}: {len(month_items)} charters")
                for item in sorted(month_items, key=lambda x: x['charter_date']):
                    amt = float(item['driver_total']) if item['driver_total'] is not None else 0.0
                    output.append(f"    {item['charter_date']} | Reserve #{item['reserve_number']} | Client ID: {item['client_id']} | Driver Total: ${amt:.2f} | Paid: {item['driver_paid']}")
    
    if name_mismatches:
        output.append("\n" + "=" * 100)
        output.append("POTENTIAL DRIVER NAME MISMATCHES")
        output.append("=" * 100)
        output.append("(These dates have pay records but under different driver names)")
        output.append("")
        
        for date, mismatches in sorted(name_mismatches.items()):
            output.append(f"\nDate: {date}")
            output.append("-" * 100)
            for m in mismatches:
                output.append(f"  Charter Driver: {m['charter_driver']}")
                output.append(f"  Pay Driver(s): {m['pay_driver']}")
                output.append(f"  Charter ID: {m['charter_id']}")
                output.append(f"  Pay Records: {len(m['pay_records'])}")
                for pr in m['pay_records']:
                    amt = float(pr['amount']) if pr['amount'] is not None else 0.0
                    output.append(f"    - ${amt:.2f} from {pr['source']}")
                output.append("")
    
    # Write to file
    report_text = "\n".join(output)
    report_path = "missing_driver_pay_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    print(report_text)
    print(f"\n\nReport saved to: {report_path}")
    
    return report_path

def main():
    print("Connecting to database...")
    conn = connect_db()
    
    print("\nFetching charter activity...")
    charters = get_charter_activity(conn)
    
    if not charters:
        print("ERROR: Could not retrieve charter data. Please check table structure.")
        conn.close()
        return
    
    print("\nFetching driver pay records...")
    pay_records = get_driver_pay(conn)
    
    print("\nAnalyzing missing pay...")
    missing, found, name_mismatches = analyze_missing_pay(charters, pay_records)
    
    print("\nGenerating report...")
    generate_report(missing, found, name_mismatches)
    
    conn.close()
    print("\nAnalysis complete!")

if __name__ == '__main__':
    main()
