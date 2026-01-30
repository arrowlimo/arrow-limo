"""
Populate vehicles.unit_number with L-X format based on vehicle_id.

Maps:
- vehicle_id 1 → L-1
- vehicle_id 2 → L-2
- etc.

This enables charter.vehicle (L-X format) to map to vehicle_id.
"""

import psycopg2
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description='Populate vehicle unit numbers')
    parser.add_argument('--write', action='store_true', help='Apply changes (default is dry-run)')
    args = parser.parse_args()
    
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("POPULATING VEHICLE UNIT NUMBERS")
    print("=" * 100)
    
    # Get all vehicles
    cur.execute("""
        SELECT vehicle_id, unit_number, make, model, year, vehicle_type
        FROM vehicles
        ORDER BY vehicle_id
    """)
    vehicles = cur.fetchall()
    
    print(f"\nFound {len(vehicles)} vehicles")
    print("\nCurrent state:")
    print(f"{'ID':<4} {'Current Unit#':<15} {'New Unit#':<12} {'Vehicle':<50}")
    print("-" * 100)
    
    updates = []
    for vid, current_unit, make, model, year, vtype in vehicles:
        new_unit = f"L-{vid}"
        vehicle_desc = f"{make or ''} {model or ''} {year or ''}".strip()
        current_str = current_unit if current_unit else 'N/A'
        print(f"{vid:<4} {current_str:<15} {new_unit:<12} {vehicle_desc:<50}")
        updates.append((new_unit, vid))
    
    print(f"\n{'=' * 100}")
    print(f"Will update unit_number for {len(updates)} vehicles")
    
    if args.write:
        print("\nApplying updates...")
        for new_unit, vid in updates:
            cur.execute("""
                UPDATE vehicles 
                SET unit_number = %s
                WHERE vehicle_id = %s
            """, (new_unit, vid))
        
        conn.commit()
        print(f"✓ Updated {len(updates)} vehicles")
        
        # Verify
        cur.execute("SELECT vehicle_id, unit_number FROM vehicles ORDER BY vehicle_id")
        print("\nVerification:")
        for vid, unit in cur.fetchall():
            print(f"  Vehicle {vid}: {unit}")
    else:
        print("\nDRY RUN - No changes made")
        print("To apply changes, run with --write flag")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
