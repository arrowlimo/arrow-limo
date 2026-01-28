#!/usr/bin/env python3
"""
Scan lms.mdb Access database for cash payment report tables.
"""

import pyodbc

LMS_PATH = r'L:\limo\backups\lms.mdb'

def main():
    try:
        conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
        conn = pyodbc.connect(conn_str)
        cur = conn.cursor()
        
        print("=" * 100)
        print("LMS.MDB DATABASE - TABLE SCAN")
        print("=" * 100)
        print()
        
        # Get all tables
        tables = []
        for table_info in cur.tables(tableType='TABLE'):
            table_name = table_info.table_name
            if not table_name.startswith('MSys'):  # Skip system tables
                tables.append(table_name)
        
        print(f"Found {len(tables)} user tables:")
        for table in sorted(tables):
            print(f"  {table}")
        
        print()
        print("=" * 100)
        print("LOOKING FOR CASH/PAYMENT/RECEIPT RELATED TABLES:")
        print("=" * 100)
        print()
        
        # Look for payment/cash/receipt related tables
        payment_tables = [t for t in tables if any(keyword in t.lower() for keyword in 
                         ['cash', 'payment', 'receipt', 'deposit', 'trans'])]
        
        if payment_tables:
            for table in payment_tables:
                print(f"\n{table}:")
                print("-" * 80)
                
                # Get column info
                try:
                    cur.execute(f"SELECT TOP 1 * FROM [{table}]")
                    columns = [desc[0] for desc in cur.description]
                    print(f"  Columns ({len(columns)}): {', '.join(columns)}")
                    
                    # Get row count
                    cur.execute(f"SELECT COUNT(*) FROM [{table}]")
                    count = cur.fetchone()[0]
                    print(f"  Row count: {count:,}")
                    
                    # Show sample data
                    cur.execute(f"SELECT TOP 5 * FROM [{table}]")
                    print(f"\n  Sample data:")
                    for row in cur.fetchall():
                        print(f"    {row}")
                
                except Exception as e:
                    print(f"  Error accessing table: {e}")
        else:
            print("No obvious payment/cash/receipt tables found.")
            print("\nSearching all tables for 'American Express' or similar payment data...")
            
            # Try to find data that looks like the Cash Receipts Report
            for table in tables:
                try:
                    cur.execute(f"SELECT TOP 1 * FROM [{table}] WHERE [Account] = '01803' OR [Account] = '02173'")
                    row = cur.fetchone()
                    if row:
                        print(f"\n[OK] Found potential match in table: {table}")
                        cur.execute(f"SELECT TOP 1 * FROM [{table}]")
                        columns = [desc[0] for desc in cur.description]
                        print(f"  Columns: {', '.join(columns)}")
                        
                        cur.execute(f"SELECT COUNT(*) FROM [{table}]")
                        count = cur.fetchone()[0]
                        print(f"  Row count: {count:,}")
                        
                        cur.execute(f"SELECT TOP 10 * FROM [{table}] ORDER BY [Date Entered]")
                        print(f"\n  Sample data:")
                        for row in cur.fetchall():
                            print(f"    {row}")
                except:
                    pass
        
        # Check the Deposit table specifically
        print()
        print("=" * 100)
        print("DEPOSIT TABLE ANALYSIS:")
        print("=" * 100)
        print()
        
        try:
            cur.execute("SELECT TOP 1 * FROM Deposit")
            columns = [desc[0] for desc in cur.description]
            print(f"Columns: {', '.join(columns)}")
            
            cur.execute("SELECT COUNT(*) FROM Deposit")
            count = cur.fetchone()[0]
            print(f"Total records: {count:,}")
            
            # Check for payment type breakdown
            cur.execute("""
                SELECT [Type], COUNT(*) as count
                FROM Deposit
                GROUP BY [Type]
            """)
            print("\nPayment types:")
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]:,}")
            
            # Sample American Express entries
            print("\nSample American Express entries:")
            cur.execute("""
                SELECT TOP 20 [Date], [Number], [Key], [Total], [Type], [Transact]
                FROM Deposit
                WHERE [Type] = 'American Express'
                ORDER BY [Date]
            """)
            print(f"{'Date':<12} {'Number':<10} {'Key':<10} {'Total':<12} {'Type':<20} {'Transact':<10}")
            print("-" * 80)
            for row in cur.fetchall():
                date_val = row[0].strftime('%Y-%m-%d') if row[0] else 'N/A'
                print(f"{date_val:<12} {str(row[1]):<10} {str(row[2]):<10} ${float(row[3]) if row[3] else 0:<11.2f} {str(row[4]):<20} {str(row[5]):<10}")
            
        except Exception as e:
            print(f"Error accessing Deposit table: {e}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to LMS database: {e}")

if __name__ == "__main__":
    main()
