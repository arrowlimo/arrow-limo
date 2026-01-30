import pandas as pd
import psycopg2
from pathlib import Path
import time
import re
from datetime import datetime

def main():
    print("QuickBooks Data Gap Analyzer")
    print("==========================")
    
    # Load the extracted journal data
    journal_csv = Path('L:/limo/reports/import_results/journal_data_clean.csv')
    if not journal_csv.exists():
        print(f"Journal data file not found: {journal_csv}")
        return
    
    print(f"Loading journal data from {journal_csv}...")
    df_journal = pd.read_csv(journal_csv)
    print(f"Loaded {len(df_journal)} journal entries")
    
    # Convert date string to datetime
    df_journal['Date'] = pd.to_datetime(df_journal['Date'])
    
    # Database connection
    print("\nConnecting to database...")
    try:
        conn = psycopg2.connect(
            dbname='almsdata',
            user='postgres',
            password='***REDACTED***',
            host='localhost'
        )
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection failed: {str(e)}")
        return
    
    # Analyze data gaps
    analyze_data_gaps(df_journal, conn)
    
    conn.close()

def analyze_data_gaps(df_journal, conn):
    """Analyze gaps between journal data and database"""
    cur = conn.cursor()
    
    # Get date range in database
    print("\nChecking date range in database...")
    try:
        cur.execute('SELECT MIN("Date"), MAX("Date") FROM journal WHERE "Date" IS NOT NULL')
        db_min_date, db_max_date = cur.fetchone()
        
        if db_min_date and db_max_date:
            print(f"Database date range: {db_min_date} to {db_max_date}")
            
            # Get total count
            cur.execute('SELECT COUNT(*) FROM journal')
            db_count = cur.fetchone()[0]
            print(f"Total journal entries in database: {db_count:,}")
            
            # Check database date type
            cur.execute("SELECT data_type FROM information_schema.columns WHERE table_name = 'journal' AND column_name = 'Date'")
            date_type = cur.fetchone()[0]
            print(f"Database Date column type: {date_type}")
            
            # Check first few journal entries
            print("\nSample journal entries from database:")
            cur.execute('SELECT "Date", "Debit", "Credit", "Account" FROM journal WHERE "Date" IS NOT NULL LIMIT 5')
            for row in cur.fetchall():
                print(f"  {row[0]} - Debit: {row[1]}, Credit: {row[2]}, Account: {row[3]}")
            
            # Since dates are stored as text, we need to extract year and month differently
            # Get counts by year in database - using substring for text dates
            print("\nJournal entries by year in database:")
            
            # This assumes dates are in MM/DD/YYYY format
            cur.execute("""
                SELECT DISTINCT RIGHT("Date", 4) as year 
                FROM journal 
                WHERE "Date" IS NOT NULL
            """)
            
            years = [row[0] for row in cur.fetchall()]
            db_years = {}
            
            for year in years:
                try:
                    year_int = int(year)
                    cur.execute(f"""
                        SELECT COUNT(*) 
                        FROM journal 
                        WHERE "Date" IS NOT NULL AND RIGHT("Date", 4) = '{year}'
                    """)
                    count = cur.fetchone()[0]
                    db_years[year_int] = count
                    print(f"  {year}: {count:,} entries")
                except ValueError:
                    print(f"  Invalid year format: {year}")
            
            # Get counts by year in file
            print("\nJournal entries by year in QuickBooks file:")
            file_years = df_journal.groupby(df_journal['Date'].dt.year).size().to_dict()
            for year, count in sorted(file_years.items()):
                print(f"  {year}: {count:,} entries")
            
            # Find missing years and months
            print("\nIdentifying missing data:")
            for year in file_years:
                if year not in db_years:
                    print(f"  Year {year} is completely missing from database ({file_years[year]:,} entries)")
                else:
                    file_count = file_years[year]
                    db_count = db_years.get(year, 0)
                    
                    if file_count > db_count * 1.1:  # More than 10% difference
                        print(f"  Year {year}: Database has {db_count:,} entries but file has {file_count:,} entries")
                        
                        # For text dates, checking by month is more complex and less reliable
                        # We'll skip the monthly breakdown for simplicity
            
            # Get summary of missing data
            print("\nSummary of missing data:")
            total_in_file = len(df_journal)
            total_in_db = db_count
            missing = total_in_file - total_in_db
            
            print(f"  Total entries in QuickBooks file: {total_in_file:,}")
            print(f"  Total entries in database: {total_in_db:,}")
            print(f"  Missing entries: {missing:,} ({missing/total_in_file*100:.1f}% of file data)")
            
            # Create specific SQL to check for missing data
            print("\nSpecific SQL query to check for missing data:")
            print("""
-- First create a temporary table for the QuickBooks data
CREATE TEMPORARY TABLE quickbooks_data (
    qb_date DATE,
    qb_account TEXT, 
    qb_debit NUMERIC,
    qb_credit NUMERIC
);

-- Then load the QuickBooks data into this temp table
-- (This would be done using a COPY command or similar)

-- Now query to find entries in QuickBooks that don't exist in journal table
SELECT 
    qb_date,
    qb_account,
    qb_debit,
    qb_credit
FROM 
    quickbooks_data qb
LEFT JOIN journal j ON 
    TO_DATE(j."Date", 'MM/DD/YYYY') = qb.qb_date AND
    j."Account" = qb.qb_account AND
    (
        (j."Debit" = qb.qb_debit AND qb.qb_debit IS NOT NULL) OR
        (j."Credit" = qb.qb_credit AND qb.qb_credit IS NOT NULL)
    )
WHERE 
    j.journal_id IS NULL
ORDER BY 
    qb.qb_date;
            """)
            
            # Recommendation
            print("\nRecommendation:")
            print("  Use the SQL script generated by quickbooks_journal_importer_final.py to import the missing data")
            print("  Location: L:/limo/reports/import_results/journal_import.sql")
            
        else:
            print("No journal entries found in database with valid dates")
    except Exception as e:
        print(f"Error analyzing date range: {str(e)}")

if __name__ == "__main__":
    main()