"""
Update February 2012 cheque vendor names from scanned cheque images.

Based on scanned cheques:
- Cheque 209: Feb 8, 2012 - $550.00 - Fas Gas (Tax Hundred + Fifty)
- Cheque 211: Feb 14, 2012 - $3,293.56 - Canada Revenue Agency (Three Thousand Two Hundred Ninety Three)
- Cheque 212: Feb 23, 2012 - $112.96 - Andrew Cabmt (One Hundred Twelve)
"""
import psycopg2
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    parser = argparse.ArgumentParser(description='Update Feb 2012 cheque vendor names')
    parser.add_argument('--write', action='store_true', help='Actually update database (default is dry-run)')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Cheque data extracted from images
    cheques = [
        {
            'number': '209',
            'date': '2012-02-08',
            'amount': 550.00,
            'vendor': 'Fas Gas',
            'notes': 'Tax Hundred + Fifty dollars - fuel expense'
        },
        {
            'number': '211',
            'date': '2012-02-14',
            'amount': 3293.56,
            'vendor': 'Canada Revenue Agency',
            'notes': 'Three Thousand Two Hundred Ninety Three - tax payment'
        },
        {
            'number': '212',
            'date': '2012-02-23',
            'amount': 112.96,
            'vendor': 'Andrew Cabmt',
            'notes': 'One Hundred Twelve - payroll/contractor payment'
        }
    ]
    
    print("February 2012 Cheque Vendor Update")
    print("=" * 80)
    print()
    
    # Check current banking_transactions data
    print("Current banking_transactions entries:")
    cur.execute("""
        SELECT transaction_id, transaction_date, description, debit_amount, vendor_extracted
        FROM banking_transactions
        WHERE transaction_date >= '2012-02-01' AND transaction_date <= '2012-02-29'
        AND (description ILIKE '%cheque%' OR description ILIKE '%chq%')
        ORDER BY transaction_date
    """)
    
    current_cheques = cur.fetchall()
    if current_cheques:
        for row in current_cheques:
            print(f"  ID {row[0]}: {row[1]} | {row[2]} | ${row[3]} | Vendor: {row[4]}")
    else:
        print("  No cheque records found in banking_transactions")
    
    print()
    print("Scanned cheque details to add:")
    for chq in cheques:
        print(f"  Cheque {chq['number']}: {chq['date']} | ${chq['amount']} | {chq['vendor']}")
        print(f"    Notes: {chq['notes']}")
    
    print()
    
    if args.write:
        print("WRITE MODE: Updating banking_transactions...")
        
        for chq in cheques:
            # Try to find matching transaction
            cur.execute("""
                SELECT transaction_id, description
                FROM banking_transactions
                WHERE transaction_date = %s
                AND ABS(debit_amount - %s) < 0.01
                AND (description ILIKE '%%cheque%%' OR description ILIKE '%%chq%%')
            """, (chq['date'], chq['amount']))
            
            match = cur.fetchone()
            if match:
                trans_id, desc = match
                print(f"  Found match: ID {trans_id} - {desc}")
                
                # Update vendor_extracted field
                cur.execute("""
                    UPDATE banking_transactions
                    SET vendor_extracted = %s,
                        description = description || ' - ' || %s
                    WHERE transaction_id = %s
                """, (chq['vendor'], f"Cheque #{chq['number']} payable to {chq['vendor']}", trans_id))
                
                print(f"    ✓ Updated vendor to: {chq['vendor']}")
            else:
                print(f"  [WARN]  No match found for Cheque {chq['number']} - may need manual entry")
        
        conn.commit()
        print()
        print("✓ Updates committed to database")
    else:
        print("DRY RUN MODE: No changes made. Use --write to apply updates.")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
