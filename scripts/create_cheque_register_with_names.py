"""
Create comprehensive cheque register with cheque numbers, names, and validation
"""
import psycopg2
import pandas as pd
import re
from datetime import datetime

def extract_cheque_info(description, vendor_name, payment_method):
    """Extract cheque number from description"""
    if not description:
        return None
    
    # Pattern: CHQ, CHECK, CHEQUE, etc. followed by optional # and numbers
    patterns = [
        r'(?:CHQ|CHECK|CHEQUE|CHQUE)\s*#?(\d{4,6})',
        r'#(\d{4,6})',
        r'(\d{4,6})\s*(?:CHQ|CHECK|CHEQUE)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, str(description).upper())
        if match:
            return match.group(1)
    
    return None

def main():
    print("=" * 80)
    print("CREATING CHEQUE REGISTER WITH VALIDATION")
    print("=" * 80)
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    
    try:
        # Query all potential cheque payments
        query = """
            SELECT 
                receipt_id,
                receipt_date,
                vendor_name,
                description,
                gross_amount,
                net_amount,
                gst_amount,
                category,
                payment_method,
                mapped_bank_account_id,
                banking_transaction_id
            FROM receipts
            WHERE payment_method ILIKE '%cheque%'
            OR payment_method ILIKE '%check%'
            OR payment_method ILIKE '%chq%'
            OR description ILIKE '%cheque%'
            OR description ILIKE '%check%'
            OR description ILIKE '%chq%'
            ORDER BY receipt_date DESC, vendor_name
        """
        
        df = pd.read_sql_query(query, conn)
        print(f"\nLoaded {len(df):,} potential cheque payments")
        
        # Extract cheque numbers
        df['cheque_number'] = df.apply(
            lambda row: extract_cheque_info(row['description'], row['vendor_name'], row['payment_method']),
            axis=1
        )
        
        # Separate into two groups: with and without cheque numbers
        with_chq = df[df['cheque_number'].notna()].copy()
        without_chq = df[df['cheque_number'].isna()].copy()
        
        print(f"  With cheque numbers: {len(with_chq):,}")
        print(f"  Without cheque numbers: {len(without_chq):,}")
        
        # Clean and standardize cheque numbers
        with_chq['cheque_number'] = with_chq['cheque_number'].astype(str).str.zfill(6)
        with_chq['cheque_check'] = with_chq['cheque_number']  # for validation
        
        # Standardize vendor names (UPPERCASE, clean)
        with_chq['issuing_name'] = with_chq['vendor_name'].fillna('').str.upper().str.strip()
        without_chq['issuing_name'] = without_chq['vendor_name'].fillna('').str.upper().str.strip()
        
        # Create full cheque description
        with_chq['cheque_description'] = 'CHQ #' + with_chq['cheque_number'] + ' - ' + with_chq['issuing_name']
        without_chq['cheque_description'] = 'CHQ (NO #) - ' + without_chq['issuing_name']
        
        # Output to Excel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_file = f'l:/limo/reports/cheque_register_with_validation_{timestamp}.xlsx'
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            # Sheet 1: Cheques WITH numbers
            with_chq[[
                'receipt_date',
                'cheque_number',
                'cheque_check',
                'issuing_name',
                'cheque_description',
                'gross_amount',
                'gst_amount',
                'net_amount',
                'category',
                'payment_method',
                'mapped_bank_account_id',
                'banking_transaction_id',
                'description'
            ]].to_excel(writer, sheet_name='Cheques_With_Numbers', index=False)
            
            # Sheet 2: Cheques WITHOUT numbers (for manual assignment)
            without_chq[[
                'receipt_date',
                'issuing_name',
                'cheque_description',
                'gross_amount',
                'gst_amount',
                'net_amount',
                'category',
                'payment_method',
                'mapped_bank_account_id',
                'banking_transaction_id',
                'description'
            ]].to_excel(writer, sheet_name='Cheques_Without_Numbers', index=False)
            
            # Sheet 3: Summary
            summary_data = {
                'Category': [
                    'Total Cheque Payments',
                    'With Cheque Numbers',
                    'Without Cheque Numbers',
                    'Total Amount (With #)',
                    'Total Amount (Without #)',
                    'Grand Total'
                ],
                'Count': [
                    len(df),
                    len(with_chq),
                    len(without_chq),
                    len(with_chq),
                    len(without_chq),
                    len(df)
                ],
                'Total Amount': [
                    f"${df['gross_amount'].sum():,.2f}",
                    f"${with_chq['gross_amount'].sum():,.2f}",
                    f"${without_chq['gross_amount'].sum():,.2f}",
                    f"${with_chq['gross_amount'].sum():,.2f}",
                    f"${without_chq['gross_amount'].sum():,.2f}",
                    f"${df['gross_amount'].sum():,.2f}"
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        print(f"\n✅ Excel saved: {excel_file}")
        
        # Print summary stats
        print("\n" + "=" * 80)
        print("CHEQUE REGISTER SUMMARY")
        print("=" * 80)
        print(f"\nTotal cheque payments: {len(df):,}")
        print(f"  With numbers: {len(with_chq):,} (${with_chq['gross_amount'].sum():,.2f})")
        print(f"  Without numbers: {len(without_chq):,} (${without_chq['gross_amount'].sum():,.2f})")
        print(f"Grand total: ${df['gross_amount'].sum():,.2f}")
        
        print("\nTop 15 CHEQUES BY AMOUNT (WITH NUMBERS):")
        print("-" * 80)
        top_15 = with_chq.nlargest(15, 'gross_amount')[[
            'receipt_date', 'cheque_number', 'issuing_name', 'gross_amount'
        ]].copy()
        top_15.columns = ['Date', 'CHQ #', 'Issued To', 'Amount']
        print(top_15.to_string(index=False))
        
        # Also create CSV for easy import
        csv_file = f'l:/limo/reports/cheque_register_{timestamp}.csv'
        with_chq[[
            'receipt_date',
            'cheque_number',
            'issuing_name',
            'gross_amount',
            'category',
            'description'
        ]].to_csv(csv_file, index=False)
        print(f"\n✅ CSV saved: {csv_file}")
        
        print("\n✅ CHEQUE REGISTER COMPLETE")
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()
