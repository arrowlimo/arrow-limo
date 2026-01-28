"""Apply FK constraints to core tables after cleanup."""
import psycopg2

DB = dict(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")

# ALTER TABLE statements to add FKs
# Business keys first (reserve_number), then other links
FKS = [
    # Payments to Charters (business key)
    """
    ALTER TABLE payments
    ADD CONSTRAINT fk_payments_reserve_number
    FOREIGN KEY (reserve_number)
    REFERENCES charters (reserve_number)
    ON DELETE SET NULL
    ON UPDATE CASCADE;
    """,
    
    # Receipts to Charters (business key)
    """
    ALTER TABLE receipts
    ADD CONSTRAINT fk_receipts_reserve_number
    FOREIGN KEY (reserve_number)
    REFERENCES charters (reserve_number)
    ON DELETE SET NULL
    ON UPDATE CASCADE;
    """,
    
    # Receipts to Vehicles
    """
    ALTER TABLE receipts
    ADD CONSTRAINT fk_receipts_vehicle_id
    FOREIGN KEY (vehicle_id)
    REFERENCES vehicles (vehicle_id)
    ON DELETE SET NULL
    ON UPDATE CASCADE;
    """,
    
    # Charter_charges to Charters (business key)
    """
    ALTER TABLE charter_charges
    ADD CONSTRAINT fk_charter_charges_reserve_number
    FOREIGN KEY (reserve_number)
    REFERENCES charters (reserve_number)
    ON DELETE SET NULL
    ON UPDATE CASCADE;
    """,
    
    # Charter_payments to Payments
    """
    ALTER TABLE charter_payments
    ADD CONSTRAINT fk_charter_payments_payment_id
    FOREIGN KEY (payment_id)
    REFERENCES payments (payment_id)
    ON DELETE SET NULL
    ON UPDATE CASCADE;
    """,
]


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    
    print("Adding FK constraints...")
    for i, sql in enumerate(FKS, 1):
        try:
            cur.execute(sql)
            conn.commit()
            print(f"✓ FK {i}/{len(FKS)} added successfully")
        except Exception as e:
            conn.rollback()
            print(f"✗ FK {i}/{len(FKS)} failed: {e}")
    
    # Verify FKs were added
    cur.execute("""
        SELECT constraint_name, table_name
        FROM information_schema.table_constraints
        WHERE constraint_type = 'FOREIGN KEY'
          AND table_schema = 'public'
          AND table_name IN ('payments', 'receipts', 'charter_charges', 'charter_payments')
        ORDER BY table_name, constraint_name;
    """)
    
    print("\nFK constraints now present:")
    for name, table in cur.fetchall():
        print(f"  {table}.{name}")
    
    conn.close()


if __name__ == "__main__":
    main()
