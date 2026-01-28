#!/usr/bin/env python3
"""
Step 4: Generate comprehensive Excel report with all receipts.
One sheet per bank account, with all required columns for accounting.
"""
import psycopg2
import pandas as pd
from datetime import datetime
import os

DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = os.environ.get('DB_PASSWORD')

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    
    print("="*70)
    print("GENERATING COMPREHENSIVE RECEIPTS EXCEL REPORT")
    print("="*70)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"L:\\limo\\reports\\receipts_by_bank_account_{timestamp}.xlsx"
    
    # Query for all receipts with banking info
    query = """
        SELECT 
            r.receipt_id,
            r.receipt_date as "Date",
            r.vendor_name as "Vendor Name",
            r.description as "Description",
            
            -- Withdrawal (expense) and Deposit (revenue) columns
            CASE 
                WHEN r.gross_amount > 0 THEN r.gross_amount 
                ELSE NULL 
            END as "Withdrawal",
            CASE 
                WHEN r.revenue > 0 THEN r.revenue
                WHEN r.gross_amount < 0 THEN ABS(r.gross_amount)
                ELSE NULL 
            END as "Deposit",
            
            -- GST columns
            r.gst_amount as "GST Amount",
            r.net_amount as "Amount Less GST",
            CASE 
                WHEN r.gst_amount > 0 THEN 'GST'
                WHEN r.gst_amount = 0 THEN 'No GST'
                ELSE 'Exempt'
            END as "GST Category",
            
            -- Business classification
            COALESCE(r.business_personal, 'Business') as "Business/Personal",
            
            -- Categories
            r.category as "Category",
            r.sub_classification as "Subcategory",
            
            -- Payment details
            r.card_number as "Card Number",
            r.canonical_pay_method as "Payment Method",
            
            -- Vehicle info
            r.vehicle_number as "Vehicle Number",
            r.vehicle_id as "Vehicle ID",
            r.fuel_amount as "Fuel Amount (LTS)",
            
            -- Charter/reservation  
            '' as "Charter/Reserve Number",
            
            -- Split receipt tracking
            r.is_split_receipt as "Is Split Receipt",
            r.parent_receipt_id as "Parent Receipt ID",
            r.split_key as "Split Group Key",
            
            -- Banking info
            CASE 
                WHEN bt.bank_id = 1 THEN 'CIBC 0228362'
                WHEN bt.bank_id = 2 THEN 'Scotia 903990106011'
                WHEN bt.bank_id = 4 THEN 'CIBC 1615'
                ELSE COALESCE(bt.account_number, 'Unknown')
            END as "Bank Account",
            bt.bank_id,
            
            -- Verification status
            CASE 
                WHEN r.is_verified_banking IS TRUE THEN 'VERIFIED'
                WHEN r.potential_duplicate IS TRUE THEN 'POTENTIAL DUPLICATE - REVIEW'
                ELSE 'OK'
            END as "Status",
            r.verified_source as "Verified Source",
            
            -- Additional fields
            r.comment as "Comments",
            r.source_system as "Source System",
            r.deductible_status as "Deductible Status"
            
        FROM receipts r
        LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        ORDER BY 
            bt.bank_id NULLS LAST,
            r.receipt_date,
            r.receipt_id
    """
    
    print("\nQuerying receipts data...")
    df = pd.read_sql_query(query, conn)
    
    print(f"✅ Retrieved {len(df):,} receipts\n")
    
    # Create Excel writer
    print(f"Creating Excel file: {output_file}")
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        
        # Sheet 1: All Receipts (Summary)
        print("  Creating 'All Receipts' sheet...")
        summary_df = df.drop(columns=['receipt_id', 'bank_id'])
        summary_df.to_excel(writer, sheet_name='All Receipts', index=False)
        
        # Sheet 2: CIBC 0228362
        print("  Creating 'CIBC 0228362' sheet...")
        cibc_0228362 = df[df['bank_id'] == 1].drop(columns=['receipt_id', 'bank_id'])
        if len(cibc_0228362) > 0:
            cibc_0228362.to_excel(writer, sheet_name='CIBC 0228362', index=False)
            print(f"    → {len(cibc_0228362):,} receipts")
        
        # Sheet 3: Scotia 903990106011
        print("  Creating 'Scotia 903990106011' sheet...")
        scotia = df[df['bank_id'] == 2].drop(columns=['receipt_id', 'bank_id'])
        if len(scotia) > 0:
            scotia.to_excel(writer, sheet_name='Scotia 903990106011', index=False)
            print(f"    → {len(scotia):,} receipts")
        
        # Sheet 4: CIBC 1615
        print("  Creating 'CIBC 1615' sheet...")
        cibc_1615 = df[df['bank_id'] == 4].drop(columns=['receipt_id', 'bank_id'])
        if len(cibc_1615) > 0:
            cibc_1615.to_excel(writer, sheet_name='CIBC 1615', index=False)
            print(f"    → {len(cibc_1615):,} receipts")
        
        # Sheet 5: No Banking Link
        print("  Creating 'No Banking Link' sheet...")
        no_banking = df[df['bank_id'].isna()].drop(columns=['receipt_id', 'bank_id'])
        if len(no_banking) > 0:
            no_banking.to_excel(writer, sheet_name='No Banking Link', index=False)
            print(f"    → {len(no_banking):,} receipts")
        
        # Sheet 6: Verified Only
        print("  Creating 'Verified Banking Only' sheet...")
        verified = df[df['Status'] == 'VERIFIED'].drop(columns=['receipt_id', 'bank_id'])
        if len(verified) > 0:
            verified.to_excel(writer, sheet_name='Verified Banking Only', index=False)
            print(f"    → {len(verified):,} receipts")
        
        # Sheet 7: Potential Duplicates
        print("  Creating 'Potential Duplicates' sheet...")
        duplicates = df[df['Status'] == 'POTENTIAL DUPLICATE - REVIEW'].drop(columns=['receipt_id', 'bank_id'])
        if len(duplicates) > 0:
            duplicates.to_excel(writer, sheet_name='Potential Duplicates', index=False)
            print(f"    → {len(duplicates):,} receipts")
        
        # Sheet 8: Summary Statistics
        print("  Creating 'Summary' sheet...")
        summary_stats = pd.DataFrame({
            'Category': [
                'Total Receipts',
                'Verified Banking (Clean)',
                'Potential Duplicates (Review)',
                'Other (OK)',
                '',
                'By Bank Account:',
                '  CIBC 0228362',
                '  Scotia 903990106011',
                '  CIBC 1615',
                '  No Banking Link'
            ],
            'Count': [
                len(df),
                len(df[df['Status'] == 'VERIFIED']),
                len(df[df['Status'] == 'POTENTIAL DUPLICATE - REVIEW']),
                len(df[df['Status'] == 'OK']),
                '',
                '',
                len(df[df['bank_id'] == 1]),
                len(df[df['bank_id'] == 2]),
                len(df[df['bank_id'] == 4]),
                len(df[df['bank_id'].isna()])
            ]
        })
        summary_stats.to_excel(writer, sheet_name='Summary', index=False)
    
    file_size = os.path.getsize(output_file) / (1024*1024)
    
    print(f"\n{'='*70}")
    print("✅ EXCEL REPORT GENERATED SUCCESSFULLY!")
    print(f"{'='*70}")
    print(f"File: {output_file}")
    print(f"Size: {file_size:.2f} MB")
    print(f"Total receipts: {len(df):,}")
    print(f"\nSheets created:")
    print(f"  1. All Receipts ({len(df):,} rows)")
    print(f"  2. CIBC 0228362 ({len(cibc_0228362):,} rows)")
    print(f"  3. Scotia 903990106011 ({len(scotia):,} rows)")
    print(f"  4. CIBC 1615 ({len(cibc_1615):,} rows)")
    print(f"  5. No Banking Link ({len(no_banking):,} rows)")
    print(f"  6. Verified Banking Only ({len(verified):,} rows)")
    print(f"  7. Potential Duplicates ({len(duplicates):,} rows)")
    print(f"  8. Summary")
    
    print(f"\n{'='*70}")
    print("PROJECT COMPLETE!")
    print(f"{'='*70}")
    print("\nNext steps:")
    print("  1. Review 'Verified Banking Only' sheet - these are clean")
    print("  2. Review 'Potential Duplicates' sheet - identify true duplicates")
    print("  3. Delete true duplicates, keep legitimate recurring payments")
    print("  4. Categorize remaining receipts for accounting")
    
    conn.close()

if __name__ == '__main__':
    main()
