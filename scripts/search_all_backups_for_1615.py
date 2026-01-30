#!/usr/bin/env python3
"""
Search ALL banking backup tables for 1615 2012 data
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("SEARCHING ALL BACKUP TABLES FOR CIBC 1615 DATA")
print("="*80)

# Get all banking_transactions backup tables
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name LIKE 'banking_transactions%backup%'
    ORDER BY table_name
""")

backup_tables = [row[0] for row in cur.fetchall()]

print(f"\nFound {len(backup_tables)} backup tables")
print("\nSearching for account 1615 in 2012...\n")

results = []

for table in backup_tables:
    try:
        # Check if has account_number column
        cur.execute(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{table}'
              AND column_name = 'account_number'
        """)
        
        if not cur.fetchone():
            continue
        
        # Check for 1615 data in 2012
        cur.execute(f"""
            SELECT 
                COUNT(*) as count,
                COUNT(CASE WHEN EXTRACT(YEAR FROM transaction_date) = 2012 THEN 1 END) as count_2012,
                MIN(transaction_date) as first_date,
                MAX(transaction_date) as last_date
            FROM {table}
            WHERE account_number = '1615'
        """)
        
        data = cur.fetchone()
        total_count = data[0]
        count_2012 = data[1]
        
        if total_count > 0:
            results.append({
                'table': table,
                'total': total_count,
                'count_2012': count_2012,
                'first_date': data[2],
                'last_date': data[3]
            })
            
            if count_2012 > 50:  # Potentially has full 2012 data
                print(f"🔍 FOUND: {table}")
                print(f"   Total: {total_count}, 2012: {count_2012}")
                print(f"   Range: {data[2]} to {data[3]}")
                
                # Get monthly breakdown for 2012
                cur.execute(f"""
                    SELECT 
                        EXTRACT(MONTH FROM transaction_date) as month,
                        COUNT(*) as count
                    FROM {table}
                    WHERE account_number = '1615'
                      AND EXTRACT(YEAR FROM transaction_date) = 2012
                    GROUP BY EXTRACT(MONTH FROM transaction_date)
                    ORDER BY month
                """)
                
                months = cur.fetchall()
                print(f"   Months: ", end="")
                for month, count in months:
                    print(f"{int(month):02d}({count}) ", end="")
                print("\n")
    
    except Exception as e:
        pass  # Skip tables with errors

print("\n" + "="*80)
print("SUMMARY OF ALL TABLES WITH 1615 DATA")
print("="*80)
print(f"{'Table':<70} {'Total':<8} {'2012':<8}")
print("-" * 90)

for r in sorted(results, key=lambda x: x['count_2012'], reverse=True):
    print(f"{r['table']:<70} {r['total']:<8} {r['count_2012']:<8}")

cur.close()
conn.close()

print("\n" + "="*80)
print("If no backup has full 2012 data, the original data may need to be")
print("re-imported from source files (PDFs, CSVs, QuickBooks exports)")
print("="*80)
