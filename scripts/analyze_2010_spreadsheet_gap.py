"""
Analyze what data from the 2010-2012 Charge Summary spreadsheet 
might be missing from the almsdata database.

Based on visible columns in the spreadsheet:
- Reserve Date, Reserve Number, Service Fee, Travel Time, Extra Stops
- Gratuity, Fuel Surcharge, Beverage Charge, Other Charge, Other Charge 2
- Extra Charge, GST, Total
- REDUCED Revenue, ADJUSTE Delivery, GST columns, RECONCIL columns
- Difference E to Total, GST Taxable, GST, Total Bill, Diff - Total, Diff - GST
"""
import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def check_charter_columns():
    """Check what columns exist in charters table"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'charters' 
        ORDER BY ordinal_position
    """)
    
    columns = {row[0]: row[1] for row in cur.fetchall()}
    
    print("=" * 80)
    print("CHARTERS TABLE COLUMNS")
    print("=" * 80)
    
    # Check for financial detail columns
    financial_columns = [
        'rate', 'balance', 'deposit', 'retainer_amount', 'total_amount_due',
        'paid_amount', 'gratuity', 'fuel_surcharge', 'beverage_charge',
        'extra_charges', 'gst_amount', 'service_fee', 'travel_time_charge'
    ]
    
    print("\nFinancial columns present:")
    for col in financial_columns:
        if col in columns:
            print(f"  ✓ {col} ({columns[col]})")
        else:
            print(f"  ✗ {col} - MISSING")
    
    cur.close()
    conn.close()
    
    return columns

def sample_2010_charters():
    """Sample some 2010 charters to see what data is populated"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("SAMPLE 2010 CHARTER RECORDS")
    print("=" * 80)
    
    cur.execute("""
        SELECT 
            reserve_number,
            charter_date,
            rate,
            balance,
            deposit,
            retainer_amount,
            total_amount_due,
            paid_amount
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2010
        ORDER BY reserve_number
        LIMIT 10
    """)
    
    print("\nFirst 10 records from 2010:")
    print(f"{'Reserve':<10} {'Date':<12} {'Rate':<10} {'Balance':<10} {'Deposit':<10} {'Retainer':<10} {'Total Due':<10} {'Paid':<10}")
    print("-" * 90)
    
    for row in cur.fetchall():
        print(f"{row[0]:<10} {str(row[1]):<12} {row[2] or 0:<10.2f} {row[3] or 0:<10.2f} {row[4] or 0:<10.2f} {row[5] or 0:<10.2f} {row[6] or 0:<10.2f} {row[7] or 0:<10.2f}")
    
    # Check how many have NULL values
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(rate) as has_rate,
            COUNT(balance) as has_balance,
            COUNT(deposit) as has_deposit,
            COUNT(retainer_amount) as has_retainer,
            COUNT(total_amount_due) as has_total_due,
            COUNT(paid_amount) as has_paid
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) = 2010
    """)
    
    row = cur.fetchone()
    print(f"\n2010 Data Completeness:")
    print(f"  Total records: {row[0]}")
    print(f"  Has rate: {row[1]} ({row[1]/row[0]*100:.1f}%)")
    print(f"  Has balance: {row[2]} ({row[2]/row[0]*100:.1f}%)")
    print(f"  Has deposit: {row[3]} ({row[3]/row[0]*100:.1f}%)")
    print(f"  Has retainer: {row[4]} ({row[4]/row[0]*100:.1f}%)")
    print(f"  Has total_due: {row[5]} ({row[5]/row[0]*100:.1f}%)")
    print(f"  Has paid_amount: {row[6]} ({row[6]/row[0]*100:.1f}%)")
    
    cur.close()
    conn.close()

def check_gst_tracking():
    """Check if GST is tracked separately for charters"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("GST TRACKING FOR 2010-2012")
    print("=" * 80)
    
    # Check if charter_charges table exists (might have GST breakdown)
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'charter_charges'
        )
    """)
    
    if cur.fetchone()[0]:
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM c.charter_date) as yr,
                COUNT(DISTINCT cc.charter_id) as charters_with_charges,
                COUNT(*) as total_charge_entries,
                SUM(CASE WHEN cc.charge_type ILIKE '%gst%' THEN 1 ELSE 0 END) as gst_entries
            FROM charter_charges cc
            JOIN charters c ON c.charter_id = cc.charter_id
            WHERE EXTRACT(YEAR FROM c.charter_date) BETWEEN 2010 AND 2012
            GROUP BY EXTRACT(YEAR FROM c.charter_date)
            ORDER BY yr
        """)
        
        print("\ncharter_charges table exists:")
        rows = cur.fetchall()
        if rows:
            for row in rows:
                print(f"  {int(row[0])}: {row[1]} charters with charges | {row[2]} entries | {row[3]} GST entries")
        else:
            print("  No charge entries for 2010-2012")
    else:
        print("\n✗ charter_charges table does NOT exist")
        print("  GST details from spreadsheet cannot be stored granularly")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    try:
        columns = check_charter_columns()
        sample_2010_charters()
        check_gst_tracking()
        
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        print("""
The 2010-2012 Charge Summary spreadsheet contains detailed financial breakdowns:
1. GST calculations and reconciliation columns
2. Beverage charges, fuel surcharges, gratuities
3. Reduced revenue and adjusted delivery tracking
4. Difference/variance tracking

If your current charter records only have basic rate/balance fields,
you may want to:
1. Create a detailed charges import script
2. Extract GST-specific calculations for CRA compliance
3. Import variance/reconciliation data for audit trail
        """)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
