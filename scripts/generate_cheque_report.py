"""
Generate detailed report of found cheques (197, 209, 242, 252).
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    output = []
    output.append("="*80)
    output.append("DETAILED CHEQUE SEARCH REPORT")
    output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    output.append("="*80)
    
    cheques = [
        ('197', 550.00, 'Not specified'),
        ('209', 550.00, '106.7 The Drive advertising'),
        ('242', 953.25, 'Not specified'),
        ('252', 525.00, 'Not specified')
    ]
    
    for chq_num, amount, purpose in cheques:
        output.append(f"\n{'='*80}")
        output.append(f"CHEQUE #{chq_num} - ${amount:.2f}")
        if purpose != 'Not specified':
            output.append(f"Purpose: {purpose}")
        output.append('='*80)
        
        # Search banking by amount
        cur.execute("""
            SELECT transaction_date, description, debit_amount, account_number, transaction_id
            FROM banking_transactions
            WHERE debit_amount = %s
            AND (description ILIKE %s OR description ILIKE %s)
            ORDER BY transaction_date
        """, (amount, f'%{chq_num}%', f'%CHEQUE%{chq_num}%'))
        
        banking_results = cur.fetchall()
        
        if banking_results:
            output.append(f"\n✅ FOUND IN BANKING TRANSACTIONS ({len(banking_results)} record(s)):")
            for row in banking_results:
                account = 'CIBC 0228362' if row[3] == '0228362' else 'Scotia 903990106011' if row[3] == '903990106011' else f'Account {row[3]}'
                output.append(f"\n  Date: {row[0]}")
                output.append(f"  Description: {row[1]}")
                output.append(f"  Amount: ${row[2]:,.2f}")
                output.append(f"  Account: {account}")
                output.append(f"  Transaction ID: {row[4]}")
                
                # Check if linked to receipt
                cur.execute("""
                    SELECT receipt_id FROM banking_receipt_matching_ledger
                    WHERE banking_transaction_id = %s
                """, (row[4],))
                receipt_link = cur.fetchone()
                if receipt_link:
                    output.append(f"  ✓ Linked to Receipt ID: {receipt_link[0]}")
                else:
                    output.append(f"  ⚠ NOT linked to any receipt")
        else:
            # Try just by amount
            cur.execute("""
                SELECT transaction_date, description, debit_amount, account_number, transaction_id
                FROM banking_transactions
                WHERE debit_amount = %s
                ORDER BY transaction_date
            """, (amount,))
            
            amt_results = cur.fetchall()
            if amt_results:
                output.append(f"\n⚠ NOT FOUND by cheque number, but found {len(amt_results)} transaction(s) with amount ${amount:.2f}:")
                for row in amt_results[:5]:  # Show first 5
                    account = 'CIBC 0228362' if row[3] == '0228362' else 'Scotia 903990106011' if row[3] == '903990106011' else f'Account {row[3]}'
                    output.append(f"\n  {row[0]} | {account}")
                    output.append(f"  {row[1][:75]}")
                if len(amt_results) > 5:
                    output.append(f"\n  ... and {len(amt_results) - 5} more")
            else:
                output.append(f"\n❌ NOT FOUND in banking transactions")
        
        # Search receipts
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, category
            FROM receipts
            WHERE gross_amount = %s
            AND (description ILIKE %s OR vendor_name ILIKE %s OR description ILIKE %s)
            ORDER BY receipt_date
        """, (amount, f'%{chq_num}%', f'%{chq_num}%', f'%CHEQUE%{chq_num}%'))
        
        receipt_results = cur.fetchall()
        
        if receipt_results:
            output.append(f"\n✅ FOUND IN RECEIPTS ({len(receipt_results)} record(s)):")
            for row in receipt_results:
                output.append(f"\n  Receipt ID: {row[0]}")
                output.append(f"  Date: {row[1]}")
                output.append(f"  Vendor: {row[2]}")
                output.append(f"  Amount: ${row[3]:,.2f}")
                output.append(f"  Category: {row[5] or 'None'}")
                if row[4]:
                    desc = row[4].replace('\n', ' ')[:100]
                    output.append(f"  Description: {desc}")
                
                # Check if linked to banking
                cur.execute("""
                    SELECT banking_transaction_id FROM banking_receipt_matching_ledger
                    WHERE receipt_id = %s
                """, (row[0],))
                banking_link = cur.fetchone()
                if banking_link:
                    output.append(f"  ✓ Linked to Banking Transaction ID: {banking_link[0]}")
                else:
                    output.append(f"  ⚠ NOT linked to any banking transaction")
        else:
            # Try just by amount
            cur.execute("""
                SELECT receipt_id, receipt_date, vendor_name, gross_amount, description, category
                FROM receipts
                WHERE gross_amount = %s
                ORDER BY receipt_date DESC
                LIMIT 5
            """, (amount,))
            
            amt_results = cur.fetchall()
            if amt_results:
                output.append(f"\n⚠ NOT FOUND by cheque number, but found receipts with amount ${amount:.2f}")
            else:
                output.append(f"\n❌ NOT FOUND in receipts")
    
    # Special search for "106.7" and "The Drive"
    output.append(f"\n\n{'='*80}")
    output.append("ADDITIONAL SEARCH: '106.7 THE DRIVE' ADVERTISING")
    output.append('='*80)
    
    cur.execute("""
        SELECT transaction_date, description, debit_amount, account_number
        FROM banking_transactions
        WHERE (description ILIKE '%106.7%' OR description ILIKE '%DRIVE%')
        AND debit_amount BETWEEN 500 AND 600
        ORDER BY transaction_date
    """)
    
    results = cur.fetchall()
    if results:
        output.append(f"\n✅ Found {len(results)} transaction(s) with '106.7' or 'DRIVE':")
        for row in results:
            account = 'CIBC 0228362' if row[3] == '0228362' else 'Scotia 903990106011' if row[3] == '903990106011' else f'Account {row[3]}'
            output.append(f"\n  {row[0]} | ${row[2]:,.2f} | {account}")
            output.append(f"  {row[1]}")
    
    cur.execute("""
        SELECT receipt_date, vendor_name, gross_amount, description
        FROM receipts
        WHERE (vendor_name ILIKE '%106.7%' OR vendor_name ILIKE '%DRIVE%' 
               OR description ILIKE '%106.7%' OR description ILIKE '%DRIVE%')
        AND gross_amount BETWEEN 500 AND 600
        ORDER BY receipt_date
    """)
    
    results = cur.fetchall()
    if results:
        output.append(f"\n✅ Found {len(results)} receipt(s) with '106.7' or 'DRIVE':")
        for row in results:
            output.append(f"\n  {row[0]} | {row[1]} | ${row[2]:,.2f}")
            if row[3]:
                desc = row[3].replace('\n', ' ')[:75]
                output.append(f"  {desc}")
    
    # Summary
    output.append(f"\n\n{'='*80}")
    output.append("SUMMARY")
    output.append('='*80)
    output.append("\n✅ FOUND:")
    output.append("  - Cheque #209 ($550.00) - 106.7 The Drive advertising - Feb 2, 2012")
    output.append("  - Cheque #242 ($953.25) - April 11, 2012")
    output.append("  - Cheque #252 ($525.00) - April 26, 2012")
    output.append("\n❌ NOT FOUND:")
    output.append("  - Cheque #197 ($550.00) - No record in database")
    output.append("\nRECOMMENDATIONS:")
    output.append("  1. Cheque #197 may be from a different account or time period")
    output.append("  2. Check if 2012 CIBC statements for January-February are complete")
    output.append("  3. Verify if cheque #197 was actually written/cleared")
    output.append("  4. All found cheques are from 2012 CIBC account (0228362)")
    
    # Write to file
    report_file = r'L:\limo\reports\cheque_search_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    # Print to console
    print('\n'.join(output))
    print(f"\n\nReport saved to: {report_file}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
