"""
Populate vehicle specifications using VIN decoder APIs.

Uses NHTSA (National Highway Traffic Safety Administration) free VIN decoder
to populate missing vehicle data like fuel type, engine specs, weight, etc.

NHTSA API: https://vpic.nhtsa.dot.gov/api/
- Free, no API key required
- Comprehensive vehicle specifications
- Works for US/Canada vehicles

Usage:
    python populate_vehicle_specs_from_vin.py --dry-run  # Preview changes
    python populate_vehicle_specs_from_vin.py --write    # Apply changes
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import time
from datetime import datetime

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# NHTSA VIN Decoder API
NHTSA_API_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"

def decode_vin(vin):
    """
    Decode VIN using NHTSA API.
    
    Returns dictionary with vehicle specifications.
    """
    try:
        url = NHTSA_API_URL.format(vin=vin)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('Count') == 0:
            return None
        
        results = data.get('Results', [{}])[0]
        
        # Extract relevant fields
        specs = {
            'make': results.get('Make'),
            'model': results.get('Model'),
            'year': results.get('ModelYear'),
            'vehicle_type': results.get('VehicleType'),
            'body_class': results.get('BodyClass'),
            'engine_cylinders': results.get('EngineCylinders'),
            'displacement_liters': results.get('DisplacementL'),
            'fuel_type': results.get('FuelTypePrimary'),
            'gross_vehicle_weight_rating': results.get('GVWR'),
            'curb_weight': results.get('CurbWeightLB'),
            'manufacturer': results.get('Manufacturer'),
            'plant_city': results.get('PlantCity'),
            'plant_country': results.get('PlantCountry'),
            'transmission_style': results.get('TransmissionStyle'),
            'drive_type': results.get('DriveType'),
            'brake_system_type': results.get('BrakeSystemType'),
            'tire_size_front': results.get('WheelSizeFront'),
            'tire_size_rear': results.get('WheelSizeRear'),
            'error_code': results.get('ErrorCode'),
            'error_text': results.get('ErrorText'),
        }
        
        # Clean up None values
        specs = {k: v for k, v in specs.items() if v and v != ''}
        
        return specs
        
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️  API Error: {e}")
        return None
    except Exception as e:
        print(f"   ⚠️  Decode Error: {e}")
        return None

def map_fuel_type(nhtsa_fuel):
    """Map NHTSA fuel type to our database values."""
    if not nhtsa_fuel:
        return None
    
    fuel_map = {
        'Gasoline': 'Gasoline',
        'Diesel': 'Diesel',
        'Flex Fuel': 'Flex Fuel',
        'Electric': 'Electric',
        'Hybrid': 'Hybrid',
        'Natural Gas': 'Natural Gas',
        'Propane': 'Propane',
    }
    
    for key, value in fuel_map.items():
        if key.lower() in nhtsa_fuel.lower():
            return value
    
    return nhtsa_fuel  # Return as-is if no match

def lbs_to_kg(lbs_str):
    """Convert pounds to kilograms."""
    try:
        lbs = int(lbs_str.replace(',', '').strip())
        return round(lbs * 0.453592)
    except:
        return None

def get_tire_size(front, rear):
    """Determine tire size from front/rear specs."""
    if front and rear:
        if front == rear:
            return front
        else:
            return f"Front: {front}, Rear: {rear}"
    return front or rear or None

def main():
    dry_run = '--write' not in sys.argv
    
    print("=" * 100)
    print("VEHICLE SPECIFICATIONS POPULATION (VIN Decoder)")
    print("=" * 100)
    print(f"Data Source: NHTSA VIN Decoder API (free)")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Use --write to apply changes\n")
    else:
        print("✍️  WRITE MODE - Changes will be applied to database\n")
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get vehicles with VINs
        cur.execute("""
            SELECT 
                vehicle_id,
                make,
                model,
                year,
                vin_number,
                license_plate,
                fuel_type,
                curb_weight,
                gross_vehicle_weight,
                tire_size,
                type as vehicle_type
            FROM vehicles
            WHERE vin_number IS NOT NULL
            ORDER BY vehicle_id
        """)
        
        vehicles = cur.fetchall()
        
        print(f"📊 Found {len(vehicles)} vehicles with VIN numbers\n")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for vehicle in vehicles:
            vin = vehicle['vin_number']
            vehicle_id = vehicle['vehicle_id']
            
            print(f"\n{'=' * 100}")
            print(f"🚗 Vehicle #{vehicle_id}: {vehicle['year']} {vehicle['make']} {vehicle['model']}")
            print(f"   VIN: {vin}")
            print(f"   License Plate: {vehicle['license_plate'] or 'N/A'}")
            
            # Check if already has data
            has_fuel_type = bool(vehicle['fuel_type'])
            has_weight = bool(vehicle['curb_weight'])
            has_tire_size = bool(vehicle['tire_size'])
            
            if has_fuel_type and has_weight and has_tire_size:
                print(f"   ✓ Already has complete data (fuel, weight, tires) - skipping")
                skipped_count += 1
                continue
            
            # Decode VIN
            print(f"   🔍 Decoding VIN via NHTSA API...")
            specs = decode_vin(vin)
            
            if not specs:
                print(f"   ❌ VIN decode failed")
                error_count += 1
                continue
            
            # Check for errors
            if specs.get('error_code') and specs['error_code'] != '0':
                print(f"   ⚠️  API Error: {specs.get('error_text', 'Unknown error')}")
                error_count += 1
                continue
            
            # Display decoded data
            print(f"\n   📋 Decoded Specifications:")
            print(f"      Make: {specs.get('make', 'N/A')}")
            print(f"      Model: {specs.get('model', 'N/A')}")
            print(f"      Year: {specs.get('year', 'N/A')}")
            print(f"      Body: {specs.get('body_class', 'N/A')}")
            print(f"      Fuel: {specs.get('fuel_type', 'N/A')}")
            print(f"      Engine: {specs.get('engine_cylinders', 'N/A')} cyl, {specs.get('displacement_liters', 'N/A')}L")
            print(f"      Weight: {specs.get('curb_weight', 'N/A')} lbs")
            print(f"      GVWR: {specs.get('gross_vehicle_weight_rating', 'N/A')}")
            print(f"      Drive: {specs.get('drive_type', 'N/A')}")
            print(f"      Transmission: {specs.get('transmission_style', 'N/A')}")
            print(f"      Tires: Front={specs.get('tire_size_front', 'N/A')}, Rear={specs.get('tire_size_rear', 'N/A')}")
            
            # Prepare update fields
            updates = {}
            
            if not has_fuel_type and specs.get('fuel_type'):
                updates['fuel_type'] = map_fuel_type(specs['fuel_type'])
            
            if not has_weight and specs.get('curb_weight'):
                updates['curb_weight'] = lbs_to_kg(specs['curb_weight'])
            
            if specs.get('gross_vehicle_weight_rating'):
                # GVWR class (e.g., "Class 2E: 6,001 - 7,000 lb")
                gvwr_str = specs['gross_vehicle_weight_rating']
                if 'lb' in gvwr_str.lower():
                    # Extract max weight from range
                    import re
                    match = re.search(r'(\d[\d,]+)\s*lb', gvwr_str)
                    if match:
                        updates['gross_vehicle_weight'] = lbs_to_kg(match.group(1))
            
            if not has_tire_size:
                tire_size = get_tire_size(
                    specs.get('tire_size_front'),
                    specs.get('tire_size_rear')
                )
                if tire_size:
                    updates['tire_size'] = tire_size
            
            # Additional fields we can populate
            if specs.get('vehicle_type') and not vehicle['vehicle_type']:
                updates['type'] = specs['vehicle_type']
            
            if not updates:
                print(f"   ℹ️  No new data to add (all fields already populated)")
                skipped_count += 1
                continue
            
            # Display what will be updated
            print(f"\n   📝 Fields to Update:")
            for field, value in updates.items():
                current = vehicle.get(field)
                print(f"      {field}: {current or 'NULL'} → {value}")
            
            if not dry_run:
                # Build UPDATE query
                set_clauses = []
                values = []
                
                for field, value in updates.items():
                    set_clauses.append(f"{field} = %s")
                    values.append(value)
                
                values.append(vehicle_id)
                
                update_sql = f"""
                    UPDATE vehicles
                    SET {', '.join(set_clauses)}
                    WHERE vehicle_id = %s
                """
                
                cur.execute(update_sql, values)
                conn.commit()
                
                print(f"   ✅ Updated {len(updates)} fields")
                updated_count += 1
            else:
                print(f"   [DRY RUN] Would update {len(updates)} fields")
                updated_count += 1
            
            # Rate limiting - be nice to NHTSA API
            time.sleep(0.5)
        
        # Summary
        print(f"\n{'=' * 100}")
        print(f"📊 SUMMARY")
        print(f"{'=' * 100}")
        print(f"Total vehicles processed: {len(vehicles)}")
        print(f"  ✅ Updated: {updated_count}")
        print(f"  ⏭️  Skipped (already complete): {skipped_count}")
        print(f"  ❌ Errors: {error_count}")
        
        if dry_run and updated_count > 0:
            print(f"\n💡 Run with --write to apply {updated_count} updates")
        elif not dry_run and updated_count > 0:
            print(f"\n✓ Successfully updated {updated_count} vehicles")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
