#!/usr/bin/env python3
"""
Create Woodridge Ford loan tracking table for 2008 Navigator L-19.

Tracks:
- Monthly payments ($965.50 including GST)
- NSF fees and reversals
- GST breakdown for CRA reporting
- Final settlement payments
"""

import os
import psycopg2

DB = dict(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***'),
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS vehicle_loan_payments (
    id SERIAL PRIMARY KEY,
    vehicle_id INTEGER,
    vehicle_vin VARCHAR(50),
    vehicle_description TEXT,
    lender_name VARCHAR(200),
    banking_transaction_id INTEGER,
    payment_date DATE NOT NULL,
    payment_type VARCHAR(50),  -- 'monthly', 'nsf_fee', 'final_settlement', 'reversal'
    gross_amount DECIMAL(12,2),
    gst_amount DECIMAL(12,2),
    net_amount DECIMAL(12,2),
    gst_rate DECIMAL(5,4) DEFAULT 0.05,
    nsf_related BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_banking_txn FOREIGN KEY (banking_transaction_id) 
        REFERENCES banking_transactions(transaction_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_vehicle_loan_payments_vehicle ON vehicle_loan_payments(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_vehicle_loan_payments_date ON vehicle_loan_payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_vehicle_loan_payments_banking ON vehicle_loan_payments(banking_transaction_id);
"""

def main():
    print("CREATING VEHICLE LOAN PAYMENTS TRACKING TABLE")
    print("=" * 80)
    
    with psycopg2.connect(**DB) as conn:
        with conn.cursor() as cur:
            # Create table (split into separate statements)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vehicle_loan_payments (
                    id SERIAL PRIMARY KEY,
                    vehicle_id INTEGER,
                    vehicle_vin VARCHAR(50),
                    vehicle_description TEXT,
                    lender_name VARCHAR(200),
                    banking_transaction_id INTEGER,
                    payment_date DATE NOT NULL,
                    payment_type VARCHAR(50),
                    gross_amount DECIMAL(12,2),
                    gst_amount DECIMAL(12,2),
                    net_amount DECIMAL(12,2),
                    gst_rate DECIMAL(5,4) DEFAULT 0.05,
                    nsf_related BOOLEAN DEFAULT FALSE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add FK constraint if not exists
            try:
                cur.execute("""
                    ALTER TABLE vehicle_loan_payments 
                    ADD CONSTRAINT fk_banking_txn 
                    FOREIGN KEY (banking_transaction_id) 
                    REFERENCES banking_transactions(transaction_id) 
                    ON DELETE SET NULL
                """)
            except psycopg2.errors.DuplicateObject:
                pass  # Constraint already exists
            
            # Create indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_loan_payments_vehicle ON vehicle_loan_payments(vehicle_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_loan_payments_date ON vehicle_loan_payments(payment_date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_vehicle_loan_payments_banking ON vehicle_loan_payments(banking_transaction_id)")
            
            conn.commit()
            print("[OK] Table 'vehicle_loan_payments' created")
            
            # Show table structure
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'vehicle_loan_payments'
                ORDER BY ordinal_position
            """)
            
            print("\nTable structure:")
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]} {'NULL' if row[2] == 'YES' else 'NOT NULL'}")

if __name__ == '__main__':
    main()
