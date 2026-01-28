"""
Comprehensive Fibrenew data analysis from all sources:
- Receipt PDFs (26 receipts 2021-2025)
- Statement PDF (66+ entries 2019-2025)
- Database receipts table (existing data 2012+)
- Database rent_debt_ledger (existing rent tracking)
"""
import psycopg2
import os

os.environ['DB_HOST'] = 'localhost'
os.environ['DB_NAME'] = 'almsdata'
os.environ['DB_USER'] = 'postgres'
os.environ['DB_PASSWORD'] = '***REMOVED***'

def main():
    conn = psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    cur = conn.cursor()
    
    print("=" * 80)
    print("COMPREHENSIVE FIBRENEW DATA ANALYSIS")
    print("=" * 80)
    print()
    
    # 1. Receipt PDFs analyzed (from earlier parse)
    print("1. RECEIPT PDFs (from audit_records/fibrenew/):")
    print("-" * 80)
    print("   26 receipt PDFs parsed covering 2021-2025:")
    print("   - Receipt from Fibrenew Central Alberta(1-22).pdf")
    print("   - Receipt from Fibrenew Central Alberta.pdf")
    print("   - Payment Receipt from Fibrenew Central Alberta.pdf")
    print("   - Statement from Fibrenew Central Alberta.pdf")
    print("   - shawns wedding.pdf")
    print()
    print("   Total from PDFs: $16,542.73")
    print("   Date range: July 2021 - November 2025")
    print()
    
    # 2. Statement data (from PDF text extraction)
    print("2. STATEMENT PDF DATA:")
    print("-" * 80)
    print("   Statement #1063, dated 26/11/2025")
    print("   Covers: 2019-2025")
    print()
    print("   Parsed Summary:")
    print("   2019: 20 charges ($8,422.36)")
    print("   2020: 20 charges ($9,624.79)")  
    print("   2021:  7 charges ($3,951.13)")
    print("   2023:  6 payments ($2,900.00)")
    print("   2024:  1 charge + 7 payments (Net: -$2,997.50)")
    print("   2025:  6 payments ($3,100.00)")
    print()
    print("   NOTE: Statement shows MANY more 2024-2025 invoices not parsed")
    print("   (Invoice #12131-12133, 12177, 12226, 12419, 12494, 12540, 12601, 12664,")
    print("    12714, 12775, 12835, 12909, 12973, 13041, 13103, 13180, 13248, 13310, 13379)")
    print()
    
    # 3. Database receipts table
    print("3. DATABASE - RECEIPTS TABLE:")
    print("-" * 80)
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as count,
            SUM(gross_amount) as total
        FROM receipts
        WHERE LOWER(vendor_name) LIKE '%%fibrenew%%'
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    db_receipts = cur.fetchall()
    total_db_receipts = 0
    total_db_amount = 0
    
    for year, count, total in db_receipts:
        print(f"   {int(year)}: {count} receipts (${total:,.2f})")
        total_db_receipts += count
        total_db_amount += total or 0
    
    print(f"   TOTAL: {total_db_receipts} receipts (${total_db_amount:,.2f})")
    print()
    
    # Show some receipt details
    cur.execute("""
        SELECT receipt_date, vendor_name, gross_amount, description, created_from_banking
        FROM receipts
        WHERE LOWER(vendor_name) LIKE '%%fibrenew%%'
        ORDER BY receipt_date
        LIMIT 15
    """)
    
    print("   Sample receipts:")
    for row in cur.fetchall():
        created_flag = " [AUTO]" if row[4] else ""
        print(f"   {row[0]} | ${row[2]:>8,.2f} | {row[1][:30]}{created_flag}")
    
    print()
    
    # 4. Database rent_debt_ledger table
    print("4. DATABASE - RENT_DEBT_LEDGER TABLE:")
    print("-" * 80)
    
    # Check if table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'rent_debt_ledger'
        )
    """)
    
    if cur.fetchone()[0]:
        # First check what columns exist
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'rent_debt_ledger'
        """)
        ledger_cols = [row[0] for row in cur.fetchall()]
        
        # Use correct column name
        amount_col = 'debit_amount' if 'debit_amount' in ledger_cols else 'credit_amount' if 'credit_amount' in ledger_cols else 'amount'
        
        cur.execute(f"""
            SELECT 
                EXTRACT(YEAR FROM transaction_date) as year,
                transaction_type,
                COUNT(*) as count,
                SUM({amount_col}) as total
            FROM rent_debt_ledger
            WHERE LOWER(vendor) LIKE '%%fibrenew%%'
            GROUP BY EXTRACT(YEAR FROM transaction_date), transaction_type
            ORDER BY year, transaction_type
        """)
        
        ledger_data = cur.fetchall()
        if ledger_data:
            for year, txn_type, count, total in ledger_data:
                print(f"   {int(year)} {txn_type}: {count} entries (${total:,.2f})")
        else:
            print("   ⚠️  No Fibrenew entries in rent_debt_ledger")
    else:
        print("   ⚠️  rent_debt_ledger table does not exist")
    
    print()
    
    # 5. Key findings and discrepancies
    print("=" * 80)
    print("KEY FINDINGS:")
    print("=" * 80)
    print()
    print("✅ STATEMENT PDF contains complete history:")
    print("   - 2019-2021: Invoices only (rent charges)")
    print("   - 2022: No data (gap year)")
    print("   - 2023: Journal entries #21-22 (trade of services ~$6,275)")
    print("   - 2023-2025: Monthly payments ($500-$2,500 range)")
    print("   - 2024-2025: New invoices at $1,102.50 then $1,260 monthly")
    print()
    print("✅ RECEIPT PDFs confirm recent payments:")
    print("   - 2021: $840/month rent payments (3 receipts)")
    print("   - 2023: $500/month payments (15 receipts)")
    print("   - 2024: $400-$500 payments (2 receipts)")
    print("   - 2025: Various payments including $3,534.05 for 'shawns wedding'")
    print()
    print("⚠️  DATABASE GAPS:")
    print(f"   - receipts table: {total_db_receipts} Fibrenew receipts (${total_db_amount:,.2f})")
    print("   - Many duplicate receipts from different import sources")
    print("   - rent_debt_ledger: No systematic tracking of rent invoices")
    print()
    print("💡 RECOMMENDATIONS:")
    print("   1. Import statement invoices to rent_debt_ledger (2019-2025)")
    print("   2. Deduplicate receipts using source_hash")
    print("   3. Link receipt PDFs to database records")
    print("   4. Create rent reconciliation report")
    print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
