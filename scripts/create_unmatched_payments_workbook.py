"""Create Excel workbook with charters having payment matching issues.

Creates multiple worksheets:
1. Charters Without Payments - charters with no linked payment records
2. Charters With Balance - charters closed but still showing balance
3. Open Charters - active charters with balance owing
4. Summary - overview statistics
"""
import psycopg2
import pandas as pd
from datetime import datetime

def main():
    conn = psycopg2.connect(
        host='localhost',
        dbname='almsdata',
        user='postgres',
        password='***REDACTED***'
    )
    
    print("=" * 100)
    print("CREATING UNMATCHED CHARTER PAYMENTS WORKBOOK")
    print("=" * 100)
    print()
    
    # 1. Charters WITHOUT any payment records
    print("Querying charters without payments...")
    df_no_payments = pd.read_sql_query("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.pickup_time,
            c.status,
            c.closed,
            c.cancelled,
            cl.client_name,
            cl.email as client_email,
            c.rate,
            c.balance,
            c.deposit,
            c.pickup_address,
            c.dropoff_address,
            c.passenger_count,
            c.vehicle,
            c.driver,
            c.notes,
            c.booking_notes,
            c.payment_instructions,
            COALESCE(
                (SELECT COUNT(*) FROM payments p WHERE p.charter_id = c.charter_id),
                0
            ) as payment_count,
            COALESCE(
                (SELECT SUM(amount) FROM payments p WHERE p.charter_id = c.charter_id AND amount > 0),
                0
            ) as payments_total
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND NOT EXISTS (
            SELECT 1 FROM payments p WHERE p.charter_id = c.charter_id AND p.amount > 0
        )
        AND (c.rate > 0 OR c.balance > 0)
        ORDER BY c.charter_date DESC, c.reserve_number DESC
    """, conn)
    
    print(f"  Found {len(df_no_payments)} charters without payments")
    
    # 2. Charters WITH BALANCE (closed but balance > 0)
    print("Querying closed charters with balance owing...")
    df_with_balance = pd.read_sql_query("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.pickup_time,
            c.status,
            c.closed,
            cl.client_name,
            cl.email as client_email,
            c.rate,
            c.balance,
            c.deposit,
            c.pickup_address,
            c.dropoff_address,
            c.passenger_count,
            c.vehicle,
            c.driver,
            c.notes,
            c.booking_notes,
            c.payment_instructions,
            COALESCE(
                (SELECT COUNT(*) FROM payments p WHERE p.charter_id = c.charter_id AND p.amount > 0),
                0
            ) as payment_count,
            COALESCE(
                (SELECT SUM(amount) FROM payments p WHERE p.charter_id = c.charter_id AND amount > 0),
                0
            ) as payments_total,
            COALESCE(
                (SELECT STRING_AGG(DISTINCT payment_method, ', ')
                 FROM payments p WHERE p.charter_id = c.charter_id),
                ''
            ) as payment_methods
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.closed = true
        AND c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.balance > 0
        ORDER BY c.balance DESC, c.charter_date DESC
    """, conn)
    
    print(f"  Found {len(df_with_balance)} closed charters with balance owing")
    
    # 3. OPEN charters with balance owing
    print("Querying open charters with balance...")
    df_open_balance = pd.read_sql_query("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.pickup_time,
            c.status,
            c.closed,
            cl.client_name,
            cl.email as client_email,
            c.rate,
            c.balance,
            c.deposit,
            c.pickup_address,
            c.dropoff_address,
            c.passenger_count,
            c.vehicle,
            c.driver,
            c.notes,
            c.booking_notes,
            c.payment_instructions,
            COALESCE(
                (SELECT COUNT(*) FROM payments p WHERE p.charter_id = c.charter_id AND p.amount > 0),
                0
            ) as payment_count,
            COALESCE(
                (SELECT SUM(amount) FROM payments p WHERE p.charter_id = c.charter_id AND amount > 0),
                0
            ) as payments_total,
            COALESCE(
                (SELECT STRING_AGG(DISTINCT payment_method, ', ')
                 FROM payments p WHERE p.charter_id = c.charter_id),
                ''
            ) as payment_methods,
            CURRENT_DATE - c.charter_date as days_since_charter
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.closed = false
        AND c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.balance > 0
        ORDER BY c.charter_date, c.reserve_number
    """, conn)
    
    print(f"  Found {len(df_open_balance)} open charters with balance")
    
    # 4. Summary statistics
    print("Calculating summary statistics...")
    
    summary_data = {
        'Category': [
            'Charters Without Payments',
            'Closed With Balance',
            'Open With Balance',
            'TOTAL REQUIRING ATTENTION'
        ],
        'Count': [
            len(df_no_payments),
            len(df_with_balance),
            len(df_open_balance),
            len(df_no_payments) + len(df_with_balance) + len(df_open_balance)
        ],
        'Total Balance Owing': [
            df_no_payments['balance'].sum() if len(df_no_payments) > 0 else 0,
            df_with_balance['balance'].sum() if len(df_with_balance) > 0 else 0,
            df_open_balance['balance'].sum() if len(df_open_balance) > 0 else 0,
            (df_no_payments['balance'].sum() if len(df_no_payments) > 0 else 0) +
            (df_with_balance['balance'].sum() if len(df_with_balance) > 0 else 0) +
            (df_open_balance['balance'].sum() if len(df_open_balance) > 0 else 0)
        ],
        'Total Rate': [
            df_no_payments['rate'].sum() if len(df_no_payments) > 0 else 0,
            df_with_balance['rate'].sum() if len(df_with_balance) > 0 else 0,
            df_open_balance['rate'].sum() if len(df_open_balance) > 0 else 0,
            (df_no_payments['rate'].sum() if len(df_no_payments) > 0 else 0) +
            (df_with_balance['rate'].sum() if len(df_with_balance) > 0 else 0) +
            (df_open_balance['rate'].sum() if len(df_open_balance) > 0 else 0)
        ]
    }
    
    df_summary = pd.DataFrame(summary_data)
    
    # Create Excel file with multiple sheets
    excel_path = r'L:\limo\reports\UNMATCHED_CHARTER_PAYMENTS.xlsx'
    
    print(f"\nWriting to Excel: {excel_path}")
    
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        # Summary sheet
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        
        # Charters without payments
        if len(df_no_payments) > 0:
            df_no_payments.to_excel(writer, sheet_name='No Payments', index=False)
        
        # Closed with balance
        if len(df_with_balance) > 0:
            df_with_balance.to_excel(writer, sheet_name='Closed With Balance', index=False)
        
        # Open with balance
        if len(df_open_balance) > 0:
            df_open_balance.to_excel(writer, sheet_name='Open With Balance', index=False)
        
        # Auto-adjust column widths
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
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
            
            # Freeze top row for data sheets
            if sheet_name != 'Summary':
                worksheet.freeze_panes = 'A2'
    
    print("\n✓ Excel workbook created successfully")
    
    # Print summary
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print()
    print(df_summary.to_string(index=False))
    print()
    print("=" * 100)
    print(f"Excel file ready: {excel_path}")
    print("=" * 100)
    print()
    print("SHEETS:")
    print("  1. Summary - Overview statistics")
    print(f"  2. No Payments - {len(df_no_payments)} charters without any payment records")
    print(f"  3. Closed With Balance - {len(df_with_balance)} closed charters still showing balance")
    print(f"  4. Open With Balance - {len(df_open_balance)} active charters with balance owing")
    print()
    print("FEATURES:")
    print("  - Sortable/filterable columns")
    print("  - Frozen header row for easy scrolling")
    print("  - Auto-sized columns for readability")
    print("  - Client contact info included")
    print("  - Payment history counts included")
    print()
    print("Open in Excel to start reviewing and matching payments!")
    
    conn.close()

if __name__ == '__main__':
    main()
