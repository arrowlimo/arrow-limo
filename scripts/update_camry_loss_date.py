#!/usr/bin/env python3
"""
Update Toyota Camry with date of loss from insurance claim
VIN: 4T1B61HK4JU014606
Date of Loss: October 26, 2019
Claim #: 8032663047
"""
import psycopg2
import os

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

def main():
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()
    
    # Find the Camry
    print("Searching for Toyota Camry (VIN: 4T1B61HK4JU014606)...")
    cur.execute("""
        SELECT vehicle_id, vehicle_number, make, model, year, vin_number, license_plate, operational_status, description
        FROM vehicles 
        WHERE vin_number LIKE %s OR (make ILIKE %s AND model ILIKE %s)
    """, ('%4T1B61HK4JU014606%', '%toyota%', '%camry%'))
    
    vehicles = cur.fetchall()
    
    if not vehicles:
        print("[FAIL] No Toyota Camry found in vehicles table")
        cur.close()
        conn.close()
        return
    
    print(f"\n[OK] Found {len(vehicles)} vehicle(s):")
    for v in vehicles:
        print(f"  ID={v[0]}, Number={v[1]}, {v[4]} {v[2]} {v[3]}, VIN={v[5]}, Plate={v[6]}, Status={v[7]}")
    
    # Update with loss information
    loss_date = '2019-10-26'
    claim_number = '8032663047'
    loss_notes = f"Total Loss - Stolen and Destroyed. Insurance Claim #{claim_number}. Settled $32,701.00. Date of Loss: {loss_date}."
    
    for v in vehicles:
        vehicle_id = v[0]
        existing_desc = v[8] or ""
        
        # Append loss info to description if not already present
        if claim_number not in existing_desc:
            updated_desc = f"{existing_desc}\n{loss_notes}".strip()
        else:
            updated_desc = existing_desc
            print(f"  ℹ️  Vehicle {vehicle_id} already has claim info in description")
            continue
        
        print(f"\n  Updating vehicle {vehicle_id}...")
        print(f"    Setting operational_status to 'Total Loss'")
        print(f"    Setting decommission_date to {loss_date}")
        print(f"    Adding description: {loss_notes}")
        
        cur.execute("""
            UPDATE vehicles 
            SET operational_status = 'Total Loss',
                decommission_date = %s,
                is_active = false,
                description = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE vehicle_id = %s
        """, (loss_date, updated_desc, vehicle_id))
        
        print(f"  [OK] Updated {cur.rowcount} vehicle record(s)")
    
    conn.commit()
    
    # Verify update
    print("\n\nVerifying update...")
    cur.execute("""
        SELECT vehicle_id, vehicle_number, make, model, year, operational_status, decommission_date, description
        FROM vehicles 
        WHERE vin_number LIKE %s OR (make ILIKE %s AND model ILIKE %s)
    """, ('%4T1B61HK4JU014606%', '%toyota%', '%camry%'))
    
    vehicles = cur.fetchall()
    for v in vehicles:
        print(f"\n  Vehicle ID: {v[0]}")
        print(f"  Number: {v[1]}")
        print(f"  Vehicle: {v[4]} {v[2]} {v[3]}")
        print(f"  Status: {v[5]}")
        print(f"  Decommission Date: {v[6]}")
        print(f"  Description: {v[7]}")
    
    cur.close()
    conn.close()
    
    print("\n🎉 Toyota Camry loss date updated successfully!")

if __name__ == "__main__":
    main()
