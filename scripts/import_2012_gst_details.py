"""
Import 2012 CS sheet from 2010-2012 Charge Summary
This sheet has a different structure than 2010/2011 sheets
"""
import pandas as pd
import psycopg2
import hashlib
from datetime import datetime
from pathlib import Path

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def parse_2012_sheet(file_path):
    """Parse the 2012 CS sheet with its unique structure"""
    print(f"Reading 2012 CS sheet from: {file_path}")
    
    # Read the 2012 CS sheet starting at row 3 (header row)
    df = pd.read_excel(file_path, sheet_name='2012 CS', header=3)
    
    print(f"Initial shape: {df.shape}")
    print(f"Columns: {list(df.columns)[:10]}")  # First 10 columns
    
    # The 2012 sheet structure based on position:
    # Column 0: Reserve Date (datetime)
    # Column 1: Reserve Number (string)
    # Column 2: Service Fee
    # Column 3: Concert Special
    # ... etc
    
    # Simply rename by position to avoid duplicate issues
    new_columns = []
    for i, col in enumerate(df.columns):
        if i == 0:
            new_columns.append('reserve_date')
        elif i == 1:
            new_columns.append('reserve_number')
        elif i == 2:
            new_columns.append('service_fee')
        elif i == 3:
            new_columns.append('concert_special')
        elif i == 4:
            new_columns.append('travel_time')
        elif i == 5:
            new_columns.append('extra_stops')
        elif i == 6:
            new_columns.append('gratuity')
        elif i == 7:
            new_columns.append('fuel_surcharge')
        elif i == 8:
            new_columns.append('beverage_charge')
        elif i == 9:
            new_columns.append('other_charge')
        elif i == 10:
            new_columns.append('other_charge_2')
        elif i == 11:
            new_columns.append('extra_charge')
        elif i == 12:
            new_columns.append('gst')  # This is the actual GST column (G.S.T.)
        elif i == 13:
            new_columns.append('col_13')  # Unknown/empty
        elif i == 14:
            new_columns.append('col_14')  # Unknown/empty
        elif i == 15:
            new_columns.append('total')  # Total column
        elif i == 16:
            new_columns.append('reduced_revenue')
        elif i == 17:
            new_columns.append('adjusted_service')
        elif i == 18:
            new_columns.append('gst_calculate_to')
        elif i == 19:
            new_columns.append('reconcil_e_to_total')  # This is actually GST taxable from looking at data
        elif i == 20:
            new_columns.append('difference')
        elif i == 21:
            new_columns.append('col_21')  # Unknown
        elif i == 22:
            new_columns.append('gst_taxable')
        elif i == 23:
            new_columns.append('gst_calculated')  # Calculated GST
        elif i == 24:
            new_columns.append('total_bill')
        elif i == 22:
            new_columns.append('gst_taxable')
        elif i == 23:
            new_columns.append('gst_calculated')  # Calculated GST
        elif i == 24:
            new_columns.append('total_bill')
        elif i == 25:
            new_columns.append('diff_total')
        elif i == 26:
            new_columns.append('diff_gst')
        else:
            new_columns.append(f'col_{i}')
    
    df.columns = new_columns
    
    print(f"\nMapped columns: {new_columns[:24]}")
    
    # Filter to valid reserve numbers
    if 'reserve_number' not in df.columns:
        raise ValueError("Could not identify reserve_number column in 2012 sheet")
    
    df = df[pd.notna(df['reserve_number'])]
    df = df[df['reserve_number'] != '']
    
    # Clean reserve numbers
    df['reserve_number'] = df['reserve_number'].astype(str).str.strip()
    df['reserve_number'] = df['reserve_number'].str.replace('.0', '', regex=False)
    df = df[df['reserve_number'].str.match(r'^\d+$', na=False)]
    
    print(f"Found {len(df)} valid 2012 records")
    
    return df

def calculate_source_hash(row):
    """Calculate unique hash for deduplication"""
    key_fields = [
        str(row.get('reserve_number', '')),
        str(row.get('reserve_date', '')),
        str(row.get('service_fee', '')),
        str(row.get('gst', '')),
        str(row.get('total', '')),
        '2012 CS'
    ]
    hash_input = '|'.join(key_fields)
    return hashlib.sha256(hash_input.encode()).hexdigest()

def link_to_charter(cur, reserve_number):
    """Find charter_id for a given reserve number"""
    reserve_padded = reserve_number.zfill(6)
    
    cur.execute("""
        SELECT charter_id 
        FROM charters 
        WHERE reserve_number = %s
        LIMIT 1
    """, (reserve_padded,))
    
    result = cur.fetchone()
    return result[0] if result else None

def import_2012_data(df, file_path):
    """Import 2012 GST details into database"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print(f"\n{'=' * 80}")
    print("IMPORTING 2012 GST DETAILS")
    print(f"{'=' * 80}")
    
    inserted = 0
    skipped = 0
    no_charter = 0
    
    for idx, row in df.iterrows():
        reserve_number = str(row['reserve_number']).zfill(6)
        
        # Link to charter
        charter_id = link_to_charter(cur, reserve_number)
        if not charter_id:
            no_charter += 1
            if idx < 5:
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
        
        # Parse date
        reserve_date = None
        try:
            reserve_date_raw = row.get('reserve_date')
            if pd.notna(reserve_date_raw):
                if isinstance(reserve_date_raw, (pd.Timestamp, datetime)):
                    reserve_date = reserve_date_raw
                else:
                    reserve_date = pd.to_datetime(reserve_date_raw)
        except (ValueError, TypeError):
            pass
        
        # Prepare values
        values = {
            'charter_id': charter_id,
            'reserve_number': reserve_number,
            'reserve_date': reserve_date,
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
            'adjusted_delivery': float(row['adjusted_service']) if pd.notna(row.get('adjusted_service')) else None,
            'reconcil_e_to_total': float(row['reconcil_e_to_total']) if pd.notna(row.get('reconcil_e_to_total')) else None,
            'difference_e_to_total': float(row['difference']) if pd.notna(row.get('difference')) else None,
            'diff_total': float(row['diff_total']) if pd.notna(row.get('diff_total')) else None,
            'diff_gst': float(row['diff_gst']) if pd.notna(row.get('diff_gst')) else None,
            'source_sheet': '2012 CS',
            'source_file': str(file_path),
            'source_hash': source_hash
        }
        
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
        
        if (idx + 1) % 100 == 0:
            print(f"Processed {idx + 1} rows...")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\nResults:")
    print(f"  ✓ Inserted: {inserted}")
    print(f"  ⊘ Skipped (duplicate): {skipped}")
    print(f"  ⚠ No matching charter: {no_charter}")
    
    return inserted, skipped, no_charter

def main():
    file_path = Path(r'l:\limo\2010-2012 Charge Sum..xlsx')
    
    if not file_path.exists():
        print(f"[FAIL] File not found: {file_path}")
        return
    
    try:
        # Parse 2012 sheet
        df = parse_2012_sheet(file_path)
        
        print(f"\nSample data (first 3 rows):")
        sample_cols = ['reserve_number', 'reserve_date', 'service_fee', 'gst_taxable', 'gst', 'total']
        available_cols = [c for c in sample_cols if c in df.columns]
        print(df[available_cols].head(3).to_string())
        
        # Import
        inserted, skipped, no_charter = import_2012_data(df, file_path)
        
        print(f"\n{'=' * 80}")
        print("✓ 2012 IMPORT COMPLETE")
        print(f"{'=' * 80}")
        
        # Show updated summary
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM reserve_date) as yr,
                COUNT(*) as records,
                SUM(gst_taxable) as total_taxable,
                SUM(gst_amount) as total_gst
            FROM charter_gst_details_2010_2012
            WHERE source_sheet = '2012 CS'
            GROUP BY EXTRACT(YEAR FROM reserve_date)
            ORDER BY yr
        """)
        
        print("\n2012 GST Summary:")
        for row in cur.fetchall():
            year = int(row[0]) if row[0] else 'NULL'
            print(f"  {year}: {row[1]} records | Taxable: ${row[2] or 0:,.2f} | GST: ${row[3] or 0:,.2f}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
