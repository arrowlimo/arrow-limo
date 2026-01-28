import psycopg2, os, datetime

def get_conn():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST','localhost'),
        dbname=os.environ.get('DB_NAME','almsdata'),
        user=os.environ.get('DB_USER','postgres'),
        password=os.environ.get('DB_PASSWORD','***REMOVED***')
    )

def main():
    conn = get_conn()
    cur = conn.cursor()
    
    # Get the deleted payment from backup
    cur.execute("""
        SELECT payment_id, amount, payment_date
        FROM payment_backups
        WHERE payment_id = 78348 AND reserve_number = '019238'
    """)
    backup = cur.fetchone()
    
    if not backup:
        print("ERROR: Payment 78348 not found in backup")
        cur.close()
        conn.close()
        return
    
    payment_id, amount, payment_date = backup
    
    print(f"Found backup payment: ID={payment_id} amount=${amount} date={payment_date}")
    
    # Check if payment already exists
    cur.execute("SELECT payment_id FROM payments WHERE payment_id = %s", (payment_id,))
    if cur.fetchone():
        print(f"Payment {payment_id} already exists - updating reserve_number to 018885")
        cur.execute("""
            UPDATE payments 
            SET reserve_number = '018885',
                notes = COALESCE(notes || ' | ', '') || 'Moved from cancelled 019238 per calendar note',
                updated_at = CURRENT_TIMESTAMP
            WHERE payment_id = %s
        """, (payment_id,))
    else:
        print(f"Restoring payment {payment_id} with reserve_number 018885")
        # Restore payment with new reserve_number - use minimal columns
        cur.execute("""
            INSERT INTO payments (
                payment_id, reserve_number, amount, payment_date, notes, created_at
            ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (
            payment_id, '018885', amount, payment_date,
            'Moved from cancelled 019238 per calendar note'
        ))
    
    # Remove the credit from 019238 since payment is being moved, not refunded
    cur.execute("""
        DELETE FROM charter_credit_ledger
        WHERE source_reserve_number = '019238' 
        AND credit_amount = 479.70
        AND created_by = 'calendar_import'
    """)
    deleted_credits = cur.rowcount
    print(f"Removed {deleted_credits} credit(s) from 019238 (payment moved, not refunded)")
    
    # Recalculate 018885 balance
    cur.execute("""
        UPDATE charters
        SET paid_amount = (
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE reserve_number = '018885'
        ),
        balance = total_amount_due - (
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE reserve_number = '018885'
        )
        WHERE reserve_number = '018885'
    """)
    
    cur.execute("SELECT total_amount_due, paid_amount, balance FROM charters WHERE reserve_number = '018885'")
    total, paid, balance = cur.fetchone()
    print(f"\n018885 updated: total=${total} paid=${paid} balance=${balance}")
    
    conn.commit()
    print("\n✓ Payment restored and moved to 018885")
    print("✓ Credit removed from 019238")
    print("✓ Balances recalculated")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
