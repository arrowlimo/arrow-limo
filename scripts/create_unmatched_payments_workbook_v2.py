"""Create Excel workbook with charters having payment matching issues.

INCLUDES charter_charges totals for accurate financial amounts!

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
    print("CREATING UNMATCHED CHARTER PAYMENTS WORKBOOK (WITH CHARTER_CHARGES TOTALS)")
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
            GREATEST(c.rate, COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )) + COALESCE(c.driver_gratuity, 0) as total_owed,
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
            ) as payments_total,
            COALESCE(
                (SELECT SUM(amount) FROM charter_refunds r WHERE r.reserve_number = c.reserve_number),
                0
            ) as refunds_total
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.reserve_number NOT LIKE 'AUDIT%'
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
            GREATEST(c.rate, COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )) + COALESCE(c.driver_gratuity, 0) as total_owed,
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
            COALESCE(
                (SELECT SUM(amount) FROM charter_refunds r WHERE r.reserve_number = c.reserve_number),
                0
            ) as refunds_total
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.closed = true
        AND c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.reserve_number NOT LIKE 'AUDIT%'
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
            GREATEST(c.rate, COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )) + COALESCE(c.driver_gratuity, 0) as total_owed,
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
            COALESCE(
                (SELECT SUM(amount) FROM charter_refunds r WHERE r.reserve_number = c.reserve_number),
                0
            ) as refunds_total
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE c.closed = false
        AND c.cancelled = false
        AND c.charter_date < CURRENT_DATE
        AND c.reserve_number NOT LIKE 'AUDIT%'
        AND (c.balance > 0 OR 
            GREATEST(c.rate, COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )) + COALESCE(c.driver_gratuity, 0) > COALESCE(c.deposit, 0))
        ORDER BY c.charter_date DESC
    """, conn)
    
    print(f"  Found {len(df_open_balance)} open charters with balance")
    
    # Create summary stats
    print("\nCalculating summary statistics...")
    
    summary_data = {
        'Category': [
            'Charters Without Payments',
            'Closed With Balance',
            'Open With Balance',
            'TOTAL'
        ],
        'Count': [
            len(df_no_payments),
            len(df_with_balance),
            len(df_open_balance),
            len(df_no_payments) + len(df_with_balance) + len(df_open_balance)
        ],
        'Total Balance': [
            df_no_payments['balance'].sum() if len(df_no_payments) > 0 else 0,
            df_with_balance['balance'].sum() if len(df_with_balance) > 0 else 0,
            df_open_balance['balance'].sum() if len(df_open_balance) > 0 else 0,
            (df_no_payments['balance'].sum() if len(df_no_payments) > 0 else 0) +
            (df_with_balance['balance'].sum() if len(df_with_balance) > 0 else 0) +
            (df_open_balance['balance'].sum() if len(df_open_balance) > 0 else 0)
        ],
        'Total Owed': [
            df_no_payments['total_owed'].sum() if len(df_no_payments) > 0 else 0,
            df_with_balance['total_owed'].sum() if len(df_with_balance) > 0 else 0,
            df_open_balance['total_owed'].sum() if len(df_open_balance) > 0 else 0,
            (df_no_payments['total_owed'].sum() if len(df_no_payments) > 0 else 0) +
            (df_with_balance['total_owed'].sum() if len(df_with_balance) > 0 else 0) +
            (df_open_balance['total_owed'].sum() if len(df_open_balance) > 0 else 0)
        ]
    }
    
    df_summary = pd.DataFrame(summary_data)
    
    # Add refunds-only sheet
    print("Querying charters with refunds...")
    df_refunds = pd.read_sql_query("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.status,
            c.closed,
            cl.client_name,
            cl.email as client_email,
            GREATEST(c.rate, COALESCE(
                (SELECT SUM(amount) 
                 FROM charter_charges cc 
                 WHERE cc.charter_id = c.charter_id 
                 AND cc.charge_type != 'customer_tip'),
                0
            )) + COALESCE(c.driver_gratuity, 0) as total_owed,
            COALESCE(
                (SELECT SUM(amount) FROM payments p WHERE p.charter_id = c.charter_id AND amount > 0),
                0
            ) as payments_total,
            COALESCE(
                (SELECT SUM(amount) FROM charter_refunds r WHERE r.reserve_number = c.reserve_number),
                0
            ) as refunds_total,
            COALESCE(
                (SELECT COUNT(*) FROM charter_refunds r WHERE r.reserve_number = c.reserve_number),
                0
            ) as refund_count,
            c.balance,
            c.deposit,
            c.pickup_address,
            c.notes
        FROM charters c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE EXISTS (
            SELECT 1 FROM charter_refunds r WHERE r.reserve_number = c.reserve_number
        )
        AND c.reserve_number NOT LIKE 'AUDIT%'
        ORDER BY refunds_total DESC, c.charter_date DESC
    """, conn)
    
    print(f"  Found {len(df_refunds)} charters with refunds")
    
    # Write to Excel
    output_file = 'L:\\limo\\reports\\UNMATCHED_CHARTER_PAYMENTS.xlsx'
    print(f"\nWriting to {output_file}...")
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        df_no_payments.to_excel(writer, sheet_name='No Payments', index=False)
        df_with_balance.to_excel(writer, sheet_name='Closed With Balance', index=False)
        df_open_balance.to_excel(writer, sheet_name='Open With Balance', index=False)
        df_refunds.to_excel(writer, sheet_name='Charters With Refunds', index=False)
        
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
    
    conn.close()
    
    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(df_summary.to_string(index=False))
    print("\n✓ Workbook created successfully!")
    print(f"  Location: {output_file}")
    print("\nNOTE: total_owed = MAX(rate, charter_charges) + driver_gratuity")
    print("      - charter_charges INCLUDES the rate (rate + GST + fuel + extras)")
    print("      - Uses MAX() to avoid double-counting")
    print("      - Focus on: total_owed vs payments_total (ignore balance if wrong)")

if __name__ == '__main__':
    main()
