#!/usr/bin/env python
"""TIER 1 - FOUNDATION: Create pay_periods table (2011-2026, bi-weekly).
Populate 26 bi-weekly pay periods for each year.
"""
import psycopg2
import os
from datetime import date, timedelta

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("TIER 1A: CREATING PAY_PERIODS TABLE (2011-2026, BI-WEEKLY)")
print("="*100)
print()

# Drop if exists
cur.execute("DROP TABLE IF EXISTS pay_periods CASCADE")
print("✅ Dropped existing pay_periods table")

# Create table
cur.execute("""
    CREATE TABLE pay_periods (
        pay_period_id SERIAL PRIMARY KEY,
        fiscal_year INT NOT NULL,
        period_number INT NOT NULL,  -- 1-26 (bi-weekly)
        period_start_date DATE NOT NULL,
        period_end_date DATE NOT NULL,
        pay_date DATE NOT NULL,
        is_closed BOOLEAN DEFAULT false,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        notes TEXT
    );
    CREATE INDEX idx_pay_periods_year_period ON pay_periods(fiscal_year, period_number);
    CREATE INDEX idx_pay_periods_dates ON pay_periods(period_start_date, period_end_date);
""")
print("✅ Created pay_periods table with indexes")

# Populate 2011-2026
print("\nPopulating bi-weekly pay periods (2011-2026)...")
print("-" * 100)

total_created = 0
for year in range(2011, 2027):
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    
    current_date = year_start
    period_num = 1
    
    while current_date.year == year and period_num <= 26:
        # Bi-weekly: start to start+14 days, pay on Friday (or end date if earlier)
        period_end = current_date + timedelta(days=13)
        if period_end > year_end:
            period_end = year_end
        
        # Pay date: Friday of end week (or end date)
        pay_date = period_end
        # If end date is weekday, move to end of that week Friday
        days_until_friday = (4 - pay_date.weekday()) % 7
        if days_until_friday == 0 and pay_date.weekday() > 4:  # Already past Friday
            days_until_friday = 7
        if days_until_friday > 0:
            pay_date = pay_date + timedelta(days=days_until_friday)
        if pay_date > year_end:
            pay_date = year_end
        
        cur.execute("""
            INSERT INTO pay_periods (fiscal_year, period_number, period_start_date, period_end_date, pay_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (year, period_num, current_date, period_end, pay_date))
        
        total_created += 1
        current_date = period_end + timedelta(days=1)
        period_num += 1
        
        if period_num > 26:
            break

conn.commit()
print(f"✅ Created {total_created} pay periods ({26*16} expected for 16 years)")

# Show sample
print("\nSample pay periods (first 10 of 2024):")
print("-" * 100)
cur.execute("""
    SELECT pay_period_id, fiscal_year, period_number, period_start_date, period_end_date, pay_date
    FROM pay_periods
    WHERE fiscal_year = 2024
    ORDER BY period_number
    LIMIT 10
""")
print("Period | Year | Num | Start Date | End Date | Pay Date")
print("-" * 100)
for pp_id, yr, num, start, end, pay in cur.fetchall():
    print(f"{pp_id:>6} | {yr} | {num:>2} | {start} | {end} | {pay}")

# Verify coverage
cur.execute("SELECT fiscal_year, COUNT(*) FROM pay_periods GROUP BY fiscal_year ORDER BY fiscal_year")
print("\nCoverage by year:")
print("Year | Periods")
print("-" * 100)
for yr, cnt in cur.fetchall():
    print(f"{yr} | {cnt:>3}")

cur.close()
conn.close()

print("\n✅ PAY_PERIODS TABLE COMPLETE!")
