"""Add unmatched payments sheet to the workbook for easy cross-referencing."""
import psycopg2
import pandas as pd
from openpyxl import load_workbook

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***'
    )
    
    print("=" * 100)
    print("ADDING UNMATCHED PAYMENTS SHEET TO WORKBOOK")
    print("=" * 100)
    print()
    
    # Get unmatched payments
    print("Querying unmatched payments...")
    df_unmatched = pd.read_sql_query("""
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.account_number,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.payment_key,
            p.check_number,
            p.credit_card_last4,
            p.square_transaction_id,
            p.square_card_brand,
            p.square_customer_name,
            p.square_customer_email,
            p.reference_number,
            p.notes,
            p.created_at,
            cl.client_name,
            cl.email as client_email,
            -- Try to find potential charter match by reserve_number
            (SELECT c.charter_id FROM charters c WHERE c.reserve_number = p.reserve_number LIMIT 1) as potential_charter_id,
            (SELECT c.charter_date FROM charters c WHERE c.reserve_number = p.reserve_number LIMIT 1) as potential_charter_date,
            (SELECT c.status FROM charters c WHERE c.reserve_number = p.reserve_number LIMIT 1) as potential_charter_status
        FROM payments p
        LEFT JOIN clients cl ON p.client_id = cl.client_id
        WHERE p.charter_id IS NULL
        AND p.amount > 0
        ORDER BY p.payment_date DESC, p.amount DESC
    """, conn)
    
    print(f"  Found {len(df_unmatched)} unmatched payments (${df_unmatched['amount'].sum():,.2f})")
    
    # Load existing workbook and add new sheet
    excel_path = r'L:\limo\reports\UNMATCHED_CHARTER_PAYMENTS.xlsx'
    
    print(f"\nAdding 'Unmatched Payments' sheet to: {excel_path}")
    
    # Write new sheet using append mode
    with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df_unmatched.to_excel(writer, sheet_name='Unmatched Payments', index=False)
        
        # Auto-adjust column widths
        worksheet = writer.book['Unmatched Payments']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Freeze top row
        worksheet.freeze_panes = 'A2'
    
    print("\n✓ Sheet added successfully")
    
    # Payment method breakdown
    print("\n" + "=" * 100)
    print("UNMATCHED PAYMENTS BREAKDOWN")
    print("=" * 100)
    print()
    
    breakdown = df_unmatched.groupby('payment_method').agg({
        'payment_id': 'count',
        'amount': 'sum'
    }).reset_index()
    breakdown.columns = ['Payment Method', 'Count', 'Total Amount']
    breakdown = breakdown.sort_values('Total Amount', ascending=False)
    
    print(breakdown.to_string(index=False))
    print()
    print(f"TOTAL: {len(df_unmatched):,} payments, ${df_unmatched['amount'].sum():,.2f}")
    
    # Potential matches
    potential_matches = df_unmatched[df_unmatched['potential_charter_id'].notna()]
    
    if len(potential_matches) > 0:
        print()
        print("=" * 100)
        print(f"POTENTIAL MATCHES FOUND: {len(potential_matches)} payments")
        print("=" * 100)
        print()
        print("These unmatched payments have reserve_numbers that match existing charters.")
        print("Review the 'Unmatched Payments' sheet and cross-reference with charter sheets.")
        print(f"\nTotal amount that could be matched: ${potential_matches['amount'].sum():,.2f}")
    
    print()
    print("=" * 100)
    print("WORKBOOK COMPLETE")
    print("=" * 100)
    print()
    print(f"File: {excel_path}")
    print()
    print("SHEETS:")
    print("  1. Summary - Overview statistics")
    print("  2. No Payments - Charters without any payment records")
    print("  3. Closed With Balance - Closed charters still showing balance")
    print("  4. Open With Balance - Active charters with balance owing")
    print("  5. Unmatched Payments - Payments without charter linkage")
    print()
    print("WORKFLOW:")
    print("  1. Open Excel file")
    print("  2. Use filters to sort/search")
    print("  3. Cross-reference payment_id, reserve_number, client_name, dates, amounts")
    print("  4. Document matches for batch import")
    print()
    
    conn.close()

if __name__ == '__main__':
    main()
