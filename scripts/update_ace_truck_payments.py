import psycopg2

conn = psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REDACTED***')
conn.autocommit = True
cur = conn.cursor()

print("=" * 100)
print("UPDATING ACE TRUCK RENTAL PAYMENTS")
print("=" * 100)

# Find all Ace Truck Rental payments
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount
    FROM banking_transactions
    WHERE description ILIKE '%ACE TRUCK%'
       OR description ILIKE '%ACC TRUCK%'
    ORDER BY transaction_date
""")

ace_payments = cur.fetchall()

print(f"\nFound {len(ace_payments)} Ace Truck Rental payments:")
total_paid = 0

for payment in ace_payments:
    trans_id, date, desc, amount = payment
    print(f"  {trans_id} | {date} | ${amount:.2f} | {desc[:60]}")
    total_paid += amount

print(f"\nTotal paid to Ace Truck Rentals: ${total_paid:,.2f}")

# Create/update receipts for these payments
print("\n" + "=" * 100)
print("Creating receipts for vehicle lease payments...")
print("=" * 100)

print("\nVehicle: L-14 shuttle/party bus split")
print("Vendor: Glubber International (original seller)")
print("Financed through: Ace Truck Rentals")
print("Status: Repossessed due to missed payment")

created = 0
updated = 0

for payment in ace_payments:
    trans_id, date, desc, amount = payment
    
    # Create hash FIRST to check for duplicates
    import hashlib
    source_hash = hashlib.sha256(f"ace_truck|{date}|{amount}".encode()).hexdigest()
    
    # Check if receipt already exists (by mapped_bank_account_id OR source_hash)
    cur.execute("""
        SELECT id FROM receipts 
        WHERE mapped_bank_account_id = %s OR source_hash = %s
    """, (trans_id, source_hash))
    
    existing = cur.fetchone()
    
    if existing:
        # Update existing receipt
        cur.execute("""
            UPDATE receipts
            SET vendor_name = 'Ace Truck Rentals',
                description = 'L-14 shuttle/party bus split lease payment (Glubber International) - REPOSSESSED',
                category = 'Vehicle Lease',
                expense_account = 'Vehicle Lease Payments',
                vehicle_number = 'L-14'
            WHERE id = %s
        """, (existing[0],))
        updated += 1
        print(f"  Updated receipt {existing[0]} for ${amount:.2f} on {date}")
    else:
        # Create new receipt
        cur.execute("""
            INSERT INTO receipts (
                source_system,
                source_reference,
                receipt_date,
                vendor_name,
                description,
                gross_amount,
                category,
                expense_account,
                vehicle_number,
                mapped_bank_account_id,
                source_hash,
                created_at,
                created_from_banking,
                document_type
            ) VALUES (
                'banking_event',
                %s,
                %s,
                'Ace Truck Rentals',
                'L-14 shuttle/party bus split lease payment (Glubber International) - REPOSSESSED',
                %s,
                'Vehicle Lease',
                'Vehicle Lease Payments',
                'L-14',
                %s,
                %s,
                NOW(),
                true,
                'VEHICLE_LEASE'
            )
        """, (f"banking_{trans_id}", date, amount, trans_id, source_hash))
        created += 1
        print(f"  Created receipt for ${amount:.2f} on {date}")

print(f"\n✓ Created {created} new receipts")
print(f"✓ Updated {updated} existing receipts")

# Summary
print("\n" + "=" * 100)
print("VEHICLE LEASE SUMMARY - L-14")
print("=" * 100)
print(f"Purchased from: Glubber International (spelling uncertain)")
print(f"Vehicle type: Shuttle/party bus split")
print(f"Financed by: Ace Truck Rentals")
print(f"Total payments: ${total_paid:,.2f}")
print(f"Number of payments: {len(ace_payments)}")
print(f"Status: REPOSSESSED due to missed payment")

if ace_payments:
    first_payment = min(p[1] for p in ace_payments)
    last_payment = max(p[1] for p in ace_payments)
    print(f"Payment period: {first_payment} to {last_payment}")
    
    from datetime import datetime
    delta = (last_payment - first_payment).days
    months = delta / 30
    print(f"Duration: {months:.1f} months")

cur.close()
conn.close()

print("\n" + "=" * 100)
