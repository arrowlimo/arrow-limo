"""
Add payment breakdown and driver trip log support to match LMS charter sheet.

Changes:
1. payments.payment_label - Label payments (NRD, Deposit, Final Payment, etc.)
2. charters.actual_* columns - Driver trip log (time in/out, odometer, fuel)
3. Payment method: add 'e_transfer'
"""
import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    try:
        print("Adding payment_label to payments table...")
        
        # Add payment_label column
        cur.execute("""
            ALTER TABLE payments
            ADD COLUMN IF NOT EXISTS payment_label VARCHAR(50)
        """)
        print("✅ Added payment_label column")
        
        # Update payment_method constraint to include e_transfer
        cur.execute("""
            ALTER TABLE payments
            DROP CONSTRAINT IF EXISTS chk_payment_method
        """)
        
        cur.execute("""
            ALTER TABLE payments
            ADD CONSTRAINT chk_payment_method CHECK (
                payment_method IN (
                    'cash', 'check', 'credit_card', 'debit_card', 
                    'bank_transfer', 'e_transfer', 'trade_of_services', 
                    'unknown', 'credit_adjustment'
                )
            )
        """)
        print("✅ Updated payment_method constraint (added e_transfer)")
        
        print("\nAdding driver trip log columns to charters...")
        
        # Add driver trip log fields
        cur.execute("""
            ALTER TABLE charters
            ADD COLUMN IF NOT EXISTS actual_pickup_time TIME,
            ADD COLUMN IF NOT EXISTS actual_dropoff_time TIME,
            ADD COLUMN IF NOT EXISTS actual_hours DECIMAL(5,2),
            ADD COLUMN IF NOT EXISTS odometer_start INTEGER,
            ADD COLUMN IF NOT EXISTS odometer_end INTEGER,
            ADD COLUMN IF NOT EXISTS total_miles INTEGER,
            ADD COLUMN IF NOT EXISTS fuel_gallons DECIMAL(8,2),
            ADD COLUMN IF NOT EXISTS fuel_price_per_gallon DECIMAL(6,2),
            ADD COLUMN IF NOT EXISTS fuel_total_cost DECIMAL(10,2),
            ADD COLUMN IF NOT EXISTS driver_phone_in TIME,
            ADD COLUMN IF NOT EXISTS driver_phone_out TIME
        """)
        print("✅ Added driver trip log columns")
        
        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_payments_reserve_label 
            ON payments(reserve_number, payment_label);
            
            CREATE INDEX IF NOT EXISTS idx_charters_actual_times
            ON charters(actual_pickup_time, actual_dropoff_time);
        """)
        print("✅ Created indexes")
        
        conn.commit()
        print("\n✅ DONE: Payment breakdown and driver trip log support added")
        
        print("\n" + "="*80)
        print("PAYMENT LABEL EXAMPLES:")
        print("="*80)
        print("  NRD              - Non-refundable deposit")
        print("  Deposit          - Initial deposit payment")
        print("  Final Payment    - Final balance payment")
        print("  Balance          - Balance payment")
        print("  Retainer         - Retainer payment")
        print("  Installment 1    - First installment")
        print("  Installment 2    - Second installment")
        print("  Overpayment      - Customer overpaid (credit)")
        
        print("\n" + "="*80)
        print("PAYMENT METHOD OPTIONS:")
        print("="*80)
        cur.execute("""
            SELECT unnest(enum_range(NULL::text)) 
            FROM (VALUES ('cash'), ('check'), ('credit_card'), ('debit_card'),
                         ('bank_transfer'), ('e_transfer'), ('trade_of_services'),
                         ('unknown'), ('credit_adjustment')) AS t(enum_range)
        """)
        methods = ['cash', 'check', 'credit_card', 'debit_card', 'bank_transfer', 
                   'e_transfer', 'trade_of_services', 'unknown', 'credit_adjustment']
        for method in methods:
            print(f"  {method}")
        
        print("\n" + "="*80)
        print("DRIVER TRIP LOG FIELDS (New):")
        print("="*80)
        print("  actual_pickup_time        - Time driver left garage")
        print("  actual_dropoff_time       - Time driver returned")
        print("  actual_hours              - Calculated hours (auto or manual)")
        print("  odometer_start            - Odometer reading at start")
        print("  odometer_end              - Odometer reading at end")
        print("  total_miles               - Miles driven (calculated)")
        print("  fuel_gallons              - Gallons of fuel purchased")
        print("  fuel_price_per_gallon     - Price per gallon")
        print("  fuel_total_cost           - Total fuel cost")
        print("  driver_phone_in           - Time driver called in")
        print("  driver_phone_out          - Time driver called out")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
