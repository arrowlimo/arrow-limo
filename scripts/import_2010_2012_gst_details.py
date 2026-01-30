"""
Import 2010-2012 Charge Summary GST details into almsdata

This spreadsheet contains detailed GST calculations, charge breakdowns,
and reconciliation data that's missing from the current charter records.

Columns from spreadsheet:
- Reserve Date, Reserve Number, Service Fee, Travel Time, Extra Stops
- Gratuity, Fuel Surcharge, Beverage Charge, Other Charge, Other Charge 2  
- Extra Charge, GST, Total
- REDUCED Revenue, ADJUSTE Deliv., GST (multiple columns)
- RECONCIL E to Total, Difference columns
- GST Taxable, GST, Total Bill
"""
import pandas as pd
import psycopg2
import hashlib
import argparse
from datetime import datetime
from pathlib import Path

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def normalize_column_names(df):
    """Normalize column names for easier processing"""
    # Strip whitespace and standardize (handles "Reserve  " with extra spaces)
    df.columns = df.columns.str.strip().str.replace(r'\s+', ' ', regex=True)
    
    # Create mapping for known columns
    column_map = {
        'Reserve Date': 'reserve_date',
        'Reserve': 'reserve_date',  # 2012 sheet uses just "Reserve" for date column
        'Reserve Number': 'reserve_number',
        'Service Fee': 'service_fee',
        'Travel Time': 'travel_time',
        'Extra Stops': 'extra_stops',
        'Gratuity': 'gratuity',
        'Fuel Surcharge': 'fuel_surcharge',
        'Beverage Charge': 'beverage_charge',
        'Other Charge': 'other_charge',
        'Other Charge 2': 'other_charge_2',
        'Extra Charge': 'extra_charge',
        'GST': 'gst',
        'Total': 'total',
        'G.S.T.': 'gst_alt',
        'REDUCED Revenue': 'reduced_revenue',
        'ADJUSTE Deliv.': 'adjusted_delivery',
        'GST Taxable': 'gst_taxable',
        'Total Bill': 'total_bill',
        'Diff - Total': 'diff_total',
        'Diff - GST': 'diff_gst',
        'RECONCIL E to Total': 'reconcil_e_to_total',
        'Difference E to Total': 'difference_e_to_total'
    }
    
    # Apply mapping where columns match
    for old_name, new_name in column_map.items():
        if old_name in df.columns:
            df.rename(columns={old_name: new_name}, inplace=True)
    
    return df

def parse_excel_file(file_path):
    """Parse the 2010-2012 Charge Summary Excel file"""
    print(f"Reading Excel file: {file_path}")
    
    # Try to read each sheet
    xls = pd.ExcelFile(file_path)
    print(f"Found sheets: {xls.sheet_names}")
    
    all_data = []
    
    for sheet_name in xls.sheet_names:
        print(f"\nProcessing sheet: {sheet_name}")
        
        # Read sheet with flexible header detection
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        
        # Find header row (look for "Reserve Number" or "Reserve Date" or "Reserve")
        header_row = None
        for idx, row in df.iterrows():
            if idx > 10:  # Don't search beyond row 10
                break
            row_str = ' '.join([str(x).strip() for x in row.values if pd.notna(x)])
            # Check for various header patterns
            if any(pattern in row_str for pattern in ['Reserve Number', 'Reserve Date', 'Service Fee', 'GST Taxable']):
                header_row = idx
                print(f"  Found header at row {idx}")
                break
        
        if header_row is None:
            print(f"  ⚠ No header found in sheet {sheet_name}, skipping")
            continue
        
        # Re-read with proper header
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
        
        # Normalize column names
        df = normalize_column_names(df)
        
        # Filter out rows without reserve numbers
        if 'reserve_number' in df.columns:
            df = df[pd.notna(df['reserve_number'])]
            df = df[df['reserve_number'] != '']
            
            # Convert reserve_number to string and clean
            df['reserve_number'] = df['reserve_number'].astype(str).str.strip()
            df['reserve_number'] = df['reserve_number'].str.replace('.0', '', regex=False)
            
            # Filter out non-numeric reserve numbers
            df = df[df['reserve_number'].str.match(r'^\d+$', na=False)]
            
            print(f"  Found {len(df)} valid records")
            
            # Add sheet identifier
            df['source_sheet'] = sheet_name
            all_data.append(df)
        else:
            print(f"  ⚠ No 'reserve_number' column found in sheet {sheet_name}")
    
    if not all_data:
        raise ValueError("No valid data found in any sheet")
    
    # Combine all sheets
    combined_df = pd.concat(all_data, ignore_index=True)
    print(f"\nTotal records across all sheets: {len(combined_df)}")
    
    return combined_df

def create_gst_details_table(conn):
    """Create table to store GST details from spreadsheet"""
    cur = conn.cursor()
    
    # Check if table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'charter_gst_details_2010_2012'
        )
    """)
    
    if cur.fetchone()[0]:
        print("\n✓ charter_gst_details_2010_2012 table already exists")
        cur.close()
        return
    
    print("\nCreating charter_gst_details_2010_2012 table...")
    
    cur.execute("""
        CREATE TABLE charter_gst_details_2010_2012 (
            id SERIAL PRIMARY KEY,
            charter_id INTEGER REFERENCES charters(charter_id),
            reserve_number VARCHAR(50) NOT NULL,
            reserve_date DATE,
            
            -- Charge breakdown
            service_fee DECIMAL(12,2),
            travel_time DECIMAL(12,2),
            extra_stops DECIMAL(12,2),
            gratuity DECIMAL(12,2),
            fuel_surcharge DECIMAL(12,2),
            beverage_charge DECIMAL(12,2),
            other_charge DECIMAL(12,2),
            other_charge_2 DECIMAL(12,2),
            extra_charge DECIMAL(12,2),
            
            -- GST calculations
            gst_amount DECIMAL(12,2),
            gst_taxable DECIMAL(12,2),
            total_amount DECIMAL(12,2),
            total_bill DECIMAL(12,2),
            
            -- Adjustments and reconciliation
            reduced_revenue DECIMAL(12,2),
            adjusted_delivery DECIMAL(12,2),
            reconcil_e_to_total DECIMAL(12,2),
            difference_e_to_total DECIMAL(12,2),
            diff_total DECIMAL(12,2),
            diff_gst DECIMAL(12,2),
            
            -- Metadata
            source_sheet VARCHAR(100),
            source_file VARCHAR(500),
            source_hash VARCHAR(64) UNIQUE,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            CONSTRAINT unique_reserve_source UNIQUE (reserve_number, source_sheet)
        )
    """)
    
    # Create indexes
    cur.execute("""
        CREATE INDEX idx_gst_details_reserve ON charter_gst_details_2010_2012(reserve_number);
        CREATE INDEX idx_gst_details_charter ON charter_gst_details_2010_2012(charter_id);
        CREATE INDEX idx_gst_details_date ON charter_gst_details_2010_2012(reserve_date);
    """)
    
    conn.commit()
    cur.close()
    print("✓ Table created successfully")

def calculate_source_hash(row):
    """Calculate unique hash for deduplication"""
    key_fields = [
        str(row.get('reserve_number', '')),
        str(row.get('reserve_date', '')),
        str(row.get('service_fee', '')),
        str(row.get('gst_amount', '')),
        str(row.get('total_amount', '')),
        str(row.get('source_sheet', ''))
    ]
    hash_input = '|'.join(key_fields)
    return hashlib.sha256(hash_input.encode()).hexdigest()

def link_to_charter(cur, reserve_number):
    """Find charter_id for a given reserve number"""
    # Normalize reserve number to 6 digits
    reserve_padded = reserve_number.zfill(6)
    
    cur.execute("""
        SELECT charter_id 
        FROM charters 
        WHERE reserve_number = %s
        LIMIT 1
    """, (reserve_padded,))
    
    result = cur.fetchone()
    return result[0] if result else None

def import_data(df, file_path, dry_run=True):
    """Import GST details into database"""
    conn = get_db_connection()
    
    # Create table if needed
    create_gst_details_table(conn)
    
    cur = conn.cursor()
    
    print(f"\n{'=' * 80}")
    print(f"IMPORT SUMMARY - {'DRY RUN' if dry_run else 'LIVE IMPORT'}")
    print(f"{'=' * 80}")
    
    inserted = 0
    updated = 0
    skipped = 0
    no_charter = 0
    
    for idx, row in df.iterrows():
        reserve_number = str(row['reserve_number']).zfill(6)
        
        # Link to charter
        charter_id = link_to_charter(cur, reserve_number)
        if not charter_id:
            no_charter += 1
            if idx < 5:  # Show first few
                print(f"⚠ No charter found for reserve {reserve_number}")
            continue
        
        # Calculate hash
        source_hash = calculate_source_hash(row)
        
        # Check if already exists
        cur.execute("""
            SELECT id FROM charter_gst_details_2010_2012 
            WHERE source_hash = %s
        """, (source_hash,))
        
        if cur.fetchone():
            skipped += 1
            continue
        
        # Prepare values
        values = {
            'charter_id': charter_id,
            'reserve_number': reserve_number,
            'reserve_date': None,  # Will parse below
            'service_fee': float(row['service_fee']) if pd.notna(row.get('service_fee')) else None,
            'travel_time': float(row['travel_time']) if pd.notna(row.get('travel_time')) else None,
            'extra_stops': float(row['extra_stops']) if pd.notna(row.get('extra_stops')) else None,
            'gratuity': float(row['gratuity']) if pd.notna(row.get('gratuity')) else None,
            'fuel_surcharge': float(row['fuel_surcharge']) if pd.notna(row.get('fuel_surcharge')) else None,
            'beverage_charge': float(row['beverage_charge']) if pd.notna(row.get('beverage_charge')) else None,
            'other_charge': float(row['other_charge']) if pd.notna(row.get('other_charge')) else None,
            'other_charge_2': float(row['other_charge_2']) if pd.notna(row.get('other_charge_2')) else None,
            'extra_charge': float(row['extra_charge']) if pd.notna(row.get('extra_charge')) else None,
            'gst_amount': float(row['gst']) if pd.notna(row.get('gst')) else None,
            'gst_taxable': float(row['gst_taxable']) if pd.notna(row.get('gst_taxable')) else None,
            'total_amount': float(row['total']) if pd.notna(row.get('total')) else None,
            'total_bill': float(row['total_bill']) if pd.notna(row.get('total_bill')) else None,
            'reduced_revenue': float(row['reduced_revenue']) if pd.notna(row.get('reduced_revenue')) else None,
            'adjusted_delivery': float(row['adjusted_delivery']) if pd.notna(row.get('adjusted_delivery')) else None,
            'reconcil_e_to_total': float(row['reconcil_e_to_total']) if pd.notna(row.get('reconcil_e_to_total')) else None,
            'difference_e_to_total': float(row['difference_e_to_total']) if pd.notna(row.get('difference_e_to_total')) else None,
            'diff_total': float(row['diff_total']) if pd.notna(row.get('diff_total')) else None,
            'diff_gst': float(row['diff_gst']) if pd.notna(row.get('diff_gst')) else None,
            'source_sheet': row.get('source_sheet', ''),
            'source_file': str(file_path),
            'source_hash': source_hash
        }
        
        # Parse reserve_date carefully (handle datetime objects vs strings)
        try:
            reserve_date_raw = row.get('reserve_date')
            if pd.notna(reserve_date_raw):
                if isinstance(reserve_date_raw, (pd.Timestamp, datetime)):
                    values['reserve_date'] = reserve_date_raw
                else:
                    values['reserve_date'] = pd.to_datetime(reserve_date_raw)
        except (ValueError, TypeError) as e:
            # Skip date if can't parse
            if idx < 5:
                print(f"  ⚠ Could not parse date for reserve {reserve_number}: {reserve_date_raw}")
        
        if not dry_run:
            cur.execute("""
                INSERT INTO charter_gst_details_2010_2012 (
                    charter_id, reserve_number, reserve_date,
                    service_fee, travel_time, extra_stops, gratuity,
                    fuel_surcharge, beverage_charge, other_charge, other_charge_2,
                    extra_charge, gst_amount, gst_taxable, total_amount, total_bill,
                    reduced_revenue, adjusted_delivery, reconcil_e_to_total,
                    difference_e_to_total, diff_total, diff_gst,
                    source_sheet, source_file, source_hash
                ) VALUES (
                    %(charter_id)s, %(reserve_number)s, %(reserve_date)s,
                    %(service_fee)s, %(travel_time)s, %(extra_stops)s, %(gratuity)s,
                    %(fuel_surcharge)s, %(beverage_charge)s, %(other_charge)s, %(other_charge_2)s,
                    %(extra_charge)s, %(gst_amount)s, %(gst_taxable)s, %(total_amount)s, %(total_bill)s,
                    %(reduced_revenue)s, %(adjusted_delivery)s, %(reconcil_e_to_total)s,
                    %(difference_e_to_total)s, %(diff_total)s, %(diff_gst)s,
                    %(source_sheet)s, %(source_file)s, %(source_hash)s
                )
            """, values)
        
        inserted += 1
        
        # Progress indicator
        if (idx + 1) % 100 == 0:
            print(f"Processed {idx + 1} rows...")
    
    if not dry_run:
        conn.commit()
    
    cur.close()
    conn.close()
    
    print(f"\nResults:")
    print(f"  ✓ Would insert: {inserted}")
    print(f"  ⊘ Would skip (duplicate): {skipped}")
    print(f"  ⚠ No matching charter: {no_charter}")
    
    return inserted, skipped, no_charter

def generate_gst_summary():
    """Generate summary of imported GST data"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print(f"\n{'=' * 80}")
    print("GST DATA SUMMARY (2010-2012)")
    print(f"{'=' * 80}")
    
    # Check if table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'charter_gst_details_2010_2012'
        )
    """)
    
    if not cur.fetchone()[0]:
        print("No GST details imported yet")
        cur.close()
        conn.close()
        return
    
    # Summary by year
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM reserve_date) as year,
            COUNT(*) as records,
            SUM(gst_taxable) as total_taxable,
            SUM(gst_amount) as total_gst,
            SUM(total_amount) as total_revenue,
            SUM(gratuity) as total_gratuity,
            SUM(fuel_surcharge) as total_fuel_surcharge,
            SUM(beverage_charge) as total_beverage
        FROM charter_gst_details_2010_2012
        GROUP BY EXTRACT(YEAR FROM reserve_date)
        ORDER BY year
    """)
    
    print("\nGST Summary by Year:")
    print(f"{'Year':<6} {'Records':<10} {'GST Taxable':<15} {'GST Amount':<15} {'Total Revenue':<15}")
    print("-" * 70)
    
    grand_taxable = 0
    grand_gst = 0
    grand_revenue = 0
    
    for row in cur.fetchall():
        year = int(row[0]) if row[0] else 0
        records = row[1]
        taxable = row[2] or 0
        gst = row[3] or 0
        revenue = row[4] or 0
        
        print(f"{year:<6} {records:<10,} ${taxable:<14,.2f} ${gst:<14,.2f} ${revenue:<14,.2f}")
        
        grand_taxable += taxable
        grand_gst += gst
        grand_revenue += revenue
    
    print("-" * 70)
    print(f"{'TOTAL':<6} {'':<10} ${grand_taxable:<14,.2f} ${grand_gst:<14,.2f} ${grand_revenue:<14,.2f}")
    
    # Additional charges summary
    cur.execute("""
        SELECT 
            SUM(gratuity) as gratuity,
            SUM(fuel_surcharge) as fuel,
            SUM(beverage_charge) as beverage,
            SUM(service_fee) as service,
            SUM(travel_time) as travel,
            SUM(extra_stops) as extra_stops
        FROM charter_gst_details_2010_2012
    """)
    
    row = cur.fetchone()
    print("\nCharge Breakdown:")
    print(f"  Gratuity: ${row[0] or 0:,.2f}")
    print(f"  Fuel Surcharge: ${row[1] or 0:,.2f}")
    print(f"  Beverage: ${row[2] or 0:,.2f}")
    print(f"  Service Fee: ${row[3] or 0:,.2f}")
    print(f"  Travel Time: ${row[4] or 0:,.2f}")
    print(f"  Extra Stops: ${row[5] or 0:,.2f}")
    
    cur.close()
    conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='Import 2010-2012 Charge Summary GST details into almsdata'
    )
    parser.add_argument('--file', '-f', 
                       default=r'l:\limo\2010-2012 Charge Sum..xlsx',
                       help='Path to Excel file')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview import without writing to database')
    parser.add_argument('--summary', action='store_true',
                       help='Show summary of already imported data')
    
    args = parser.parse_args()
    
    if args.summary:
        generate_gst_summary()
        return
    
    file_path = Path(args.file)
    
    if not file_path.exists():
        print(f"[FAIL] File not found: {file_path}")
        return
    
    try:
        # Parse Excel
        df = parse_excel_file(file_path)
        
        print(f"\nParsed {len(df)} records from Excel")
        print(f"Columns found: {', '.join(df.columns)}")
        
        # Show sample
        print(f"\nSample data (first 3 rows):")
        print(df.head(3).to_string())
        
        # Import
        inserted, skipped, no_charter = import_data(df, file_path, dry_run=args.dry_run)
        
        if args.dry_run:
            print(f"\n{'=' * 80}")
            print("This was a DRY RUN - no data was written")
            print("Run without --dry-run to perform actual import")
            print(f"{'=' * 80}")
        else:
            print(f"\n{'=' * 80}")
            print("✓ IMPORT COMPLETE")
            print(f"{'=' * 80}")
            generate_gst_summary()
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
