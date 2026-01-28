import pandas as pd
import psycopg2
from pathlib import Path
import time
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
            password='***REMOVED***',
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
            
            # Get counts by year in database
            print("\nJournal entries by year in database:")
            cur.execute("""
                SELECT date_part('year', "Date") AS year, COUNT(*) 
                FROM journal 
                WHERE "Date" IS NOT NULL 
                GROUP BY year 
                ORDER BY year
            """)
            
            db_years = {}
            for row in cur.fetchall():
                year, count = int(row[0]), row[1]
                db_years[year] = count
                print(f"  {year}: {count:,} entries")
            
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
                        
                        # Check by month
                        year_df = df_journal[df_journal['Date'].dt.year == year]
                        monthly_file = year_df.groupby(year_df['Date'].dt.month).size().to_dict()
                        
                        # Get monthly data from database
                        cur.execute(f"""
                            SELECT date_part('month', "Date") AS month, COUNT(*) 
                            FROM journal 
                            WHERE "Date" IS NOT NULL AND date_part('year', "Date") = {year}
                            GROUP BY month 
                            ORDER BY month
                        """)
                        
                        monthly_db = {int(row[0]): row[1] for row in cur.fetchall()}
                        
                        for month, file_count in monthly_file.items():
                            db_count = monthly_db.get(month, 0)
                            if db_count < file_count * 0.9:  # Less than 90% in database
                                print(f"    Month {month}/{year}: Database has {db_count:,} entries but file has {file_count:,} entries")
            
            # Get summary of missing data
            print("\nSummary of missing data:")
            total_in_file = len(df_journal)
            total_in_db = db_count
            missing = total_in_file - total_in_db
            
            print(f"  Total entries in QuickBooks file: {total_in_file:,}")
            print(f"  Total entries in database: {total_in_db:,}")
            print(f"  Missing entries: {missing:,} ({missing/total_in_file*100:.1f}% of file data)")
            
            # Recommendation
            if missing > 0:
                print("\nRecommendation:")
                print("  Use the SQL script generated by quickbooks_journal_importer_final.py to import the missing data")
                print("  Location: L:/limo/reports/import_results/journal_import.sql")
                print("\nAdditional specific query to check missing data:")
                print("""
  -- This query will find journal entries in the QuickBooks data that don't exist in the database
  WITH qb_data AS (
    -- This would be a table or temporary table of your QuickBooks data
    SELECT 
      date_col AS qb_date,
      account_col AS qb_account,
      debit_col AS qb_debit,
      credit_col AS qb_credit
    FROM quickbooks_import_table
  )
  
  SELECT qb.* 
  FROM qb_data qb
  LEFT JOIN journal j ON 
    j."Date" = qb.qb_date AND
    j."Account" = qb.qb_account AND
    (
      (j."Debit" = qb.qb_debit AND qb.qb_debit IS NOT NULL) OR
      (j."Credit" = qb.qb_credit AND qb.qb_credit IS NOT NULL)
    )
  WHERE j.journal_id IS NULL
  ORDER BY qb.qb_date;
                """)
            
        else:
            print("No journal entries found in database with valid dates")
    except Exception as e:
        print(f"Error analyzing date range: {str(e)}")

def check_specific_examples(df_journal, conn):
    """Check specific examples of entries that might be missing"""
    cur = conn.cursor()
    
    # Find the years with biggest gaps
    file_by_year = df_journal.groupby(df_journal['Date'].dt.year).size()
    
    # Query the database for the same years
    years_to_check = file_by_year.index.tolist()
    
    for year in years_to_check[:3]:  # Check the first 3 years
        # Get the first day of the year
        first_date = df_journal[df_journal['Date'].dt.year == year]['Date'].min()
        
        if pd.isna(first_date):
            continue
            
        # Format date for SQL
        sql_date = first_date.strftime('%Y-%m-%d')
        
        # Check if any entries exist for this date
        cur.execute(f"""
            SELECT COUNT(*) FROM journal 
            WHERE "Date" = '{sql_date}'
        """)
        db_count = cur.fetchone()[0]
        
        # Count entries in file for this date
        file_count = len(df_journal[df_journal['Date'] == first_date])
        
        print(f"  Date {sql_date}: Database has {db_count} entries, QuickBooks file has {file_count} entries")
        
        # If missing entries, show sample
        if db_count < file_count:
            # Get some examples from the file
            examples = df_journal[df_journal['Date'] == first_date].head(3)
            
            print(f"  Example entries missing from database for {sql_date}:")
            for i, (_, row) in enumerate(examples.iterrows()):
                print(f"    {i+1}. Amount: Debit={row.get('Debit', 'N/A')}, Credit={row.get('Credit', 'N/A')}, Account: {row.get('Account', 'N/A')}")
                
                # Check if this exact entry exists
                if pd.notna(row.get('Debit')) and pd.notna(row.get('Account')):
                    try:
                        cur.execute(f"""
                            SELECT COUNT(*) FROM journal 
                            WHERE "Date" = '{sql_date}' 
                            AND "Debit" = {row.get('Debit')} 
                            AND "Account" = '{row.get('Account').replace("'", "''")}'
                        """)
                        exact_match = cur.fetchone()[0]
                        if exact_match == 0:
                            print(f"       → This exact entry is missing from database")
                        else:
                            print(f"       → This entry exists in database")
                    except Exception as e:
                        print(f"       → Error checking match: {str(e)}")

if __name__ == "__main__":
    main()