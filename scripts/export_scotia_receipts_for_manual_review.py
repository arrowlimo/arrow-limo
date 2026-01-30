"""
Export Scotia 2012 receipts to Excel for manual verification before reconciliation.
Creates a spreadsheet with receipts sorted by date for easy review.
"""
import psycopg2
import pandas as pd
from datetime import datetime

def main():
    print("=" * 80)
    print("SCOTIA 2012 RECEIPTS - EXPORT FOR MANUAL REVIEW")
    print("=" * 80)
    
    # Connect to database
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    
    try:
        # Export receipts
        print("\nExporting Scotia 2012 receipts...")
        
        query = """
            SELECT 
                r.receipt_id,
                r.receipt_date,
                r.vendor_name,
                r.description,
                r.gross_amount,
                r.gst_amount,
                r.net_amount,
                r.category,
                r.payment_method,
                CASE 
                    WHEN r.banking_transaction_id IS NOT NULL THEN 'MATCHED'
                    ELSE 'UNMATCHED'
                END as match_status,
                r.banking_transaction_id,
                r.created_at,
                r.updated_at,
                r.notes
            FROM receipts r
            WHERE r.mapped_bank_account_id = 2
            AND EXTRACT(YEAR FROM r.receipt_date) = 2012
            ORDER BY r.receipt_date, r.vendor_name, r.gross_amount
        """
        
        df = pd.read_sql_query(query, conn)
        
        print(f"  Loaded {len(df):,} receipts")
        
        # Add verification columns
        df['verified'] = ''
        df['verification_notes'] = ''
        df['action_needed'] = ''
        
        # Create output filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'l:/limo/reports/scotia_2012_receipts_manual_review_{timestamp}.xlsx'
        
        # Write to Excel with formatting
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Receipts', index=False)
            
            # Get the worksheet
            worksheet = writer.sheets['Receipts']
            
            # Set column widths
            column_widths = {
                'A': 12,  # receipt_id
                'B': 12,  # receipt_date
                'C': 30,  # vendor_name
                'D': 40,  # description
                'E': 12,  # gross_amount
                'F': 12,  # gst_amount
                'G': 12,  # net_amount
                'H': 20,  # category
                'I': 15,  # payment_method
                'J': 12,  # match_status
                'K': 15,  # banking_transaction_id
                'L': 20,  # created_at
                'M': 20,  # updated_at
                'N': 40,  # notes
                'O': 10,  # verified
                'P': 50,  # verification_notes
                'Q': 30,  # action_needed
            }
            
            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width
            
            # Freeze header row
            worksheet.freeze_panes = 'A2'
        
        print(f"\n✅ Exported to: {output_file}")
        
        # Print summary statistics
        print("\n" + "=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)
        
        print(f"\nTotal receipts: {len(df):,}")
        print(f"  Matched: {(df['match_status'] == 'MATCHED').sum():,}")
        print(f"  Unmatched: {(df['match_status'] == 'UNMATCHED').sum():,}")
        
        print(f"\nTotal amount: ${df['gross_amount'].sum():,.2f}")
        print(f"  Matched: ${df[df['match_status'] == 'MATCHED']['gross_amount'].sum():,.2f}")
        print(f"  Unmatched: ${df[df['match_status'] == 'UNMATCHED']['gross_amount'].sum():,.2f}")
        
        print("\nBy category:")
        category_summary = df.groupby('category').agg({
            'receipt_id': 'count',
            'gross_amount': 'sum'
        }).sort_values('gross_amount', ascending=False)
        
        for category, row in category_summary.iterrows():
            print(f"  {category or 'UNCATEGORIZED'}: {int(row['receipt_id']):,} receipts, ${row['gross_amount']:,.2f}")
        
        print("\nTop 10 vendors by amount:")
        vendor_summary = df.groupby('vendor_name').agg({
            'receipt_id': 'count',
            'gross_amount': 'sum'
        }).sort_values('gross_amount', ascending=False).head(10)
        
        for vendor, row in vendor_summary.iterrows():
            print(f"  {vendor}: {int(row['receipt_id']):,} receipts, ${row['gross_amount']:,.2f}")
        
        print("\n" + "=" * 80)
        print("MANUAL VERIFICATION INSTRUCTIONS")
        print("=" * 80)
        print("""
1. Open the exported Excel file
2. Review each receipt row for accuracy:
   - Check vendor name is correct
   - Verify amount matches source documents
   - Confirm date is accurate
   - Check category assignment
   
3. In the 'verified' column, mark:
   - 'OK' if receipt is correct
   - 'DELETE' if receipt is a duplicate or error
   - 'FIX' if receipt needs correction
   
4. In 'verification_notes' column, add:
   - Why marked for deletion
   - What needs to be fixed
   - Reference to source document
   
5. In 'action_needed' column, specify:
   - 'Merge with receipt #123' (for duplicates)
   - 'Update amount to $456.78'
   - 'Change vendor to XYZ'
   - etc.

6. Save the file with your verification results
7. Import the verified file back into the system

NOTE: Focus on unmatched receipts first (1,512 records)
These are the ones that need reconciliation with banking.
        """)
        
        print("\n✅ EXPORT COMPLETE")
        
    finally:
        conn.close()

if __name__ == '__main__':
    main()
