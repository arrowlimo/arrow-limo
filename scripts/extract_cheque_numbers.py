"""
Extract all cheque numbers with issuing names
"""
import psycopg2
import pandas as pd
from datetime import datetime

def main():
    print("=" * 80)
    print("CHEQUE NUMBERS WITH ISSUING NAMES")
    print("=" * 80)
    
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    
    try:
        # Extract cheque numbers from receipts
        query = """
            SELECT DISTINCT
                receipt_id,
                receipt_date,
                vendor_name,
                description,
                gross_amount,
                category,
                payment_method
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
        
        print(f"\nFound {len(df):,} cheque payments\n")
        
        # Extract cheque numbers from description
        def extract_chq_num(desc):
            if not desc:
                return ""
            import re
            # Look for CHQ, Check, Cheque followed by numbers
            match = re.search(r'(?:CHQ|CHECK|CHEQUE|CHQUE)\s*#?(\d{4,6})', str(desc), re.IGNORECASE)
            if match:
                return match.group(1)
            return ""
        
        df['chq_number'] = df['description'].apply(extract_chq_num)
        
        # Filter only rows with extracted cheque numbers
        chq_df = df[df['chq_number'] != ''].copy()
        print(f"Extracted {len(chq_df):,} cheque numbers\n")
        
        # Output to CSV and Excel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = f'l:/limo/reports/cheque_numbers_{timestamp}.csv'
        xlsx_file = f'l:/limo/reports/cheque_numbers_{timestamp}.xlsx'
        
        # CSV output
        chq_df[['receipt_date', 'chq_number', 'vendor_name', 'description', 'gross_amount', 'payment_method']].to_csv(csv_file, index=False)
        print(f"✅ CSV saved: {csv_file}")
        
        # Excel output
        chq_df[['receipt_date', 'chq_number', 'vendor_name', 'description', 'gross_amount', 'payment_method']].to_excel(xlsx_file, index=False, sheet_name='Cheques')
        print(f"✅ Excel saved: {xlsx_file}")
        
        # Print summary
        print("\nCHEQUE SUMMARY:")
        print(f"  Total cheque payments: {len(chq_df):,}")
        print(f"  Total amount: ${chq_df['gross_amount'].sum():,.2f}")
        
        print("\nTOP 20 CHEQUES BY AMOUNT:")
        top_20 = chq_df.nlargest(20, 'gross_amount')[['receipt_date', 'chq_number', 'vendor_name', 'gross_amount']]
        print(top_20.to_string(index=False))
        
        print("\n✅ EXTRACTION COMPLETE")
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()
