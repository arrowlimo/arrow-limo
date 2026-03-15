"""
Verification script for charter schema fixes.
Run this AFTER creating a test charter via the web UI.

This script will:
1. Find the most recent charter
2. Verify all schema mappings are correct
3. Check that data was saved to correct columns
4. Verify JOINs work for display
"""
import sys
sys.path.insert(0, 'l:\\limo\\modern_backend')

from app.db import cursor

print("=" * 80)
print("CHARTER SCHEMA FIX VERIFICATION")
print("=" * 80)

with cursor() as cur:
    # Get the most recent charter
    cur.execute("""
        SELECT charter_id, reserve_number, charter_date, client_id,
               passenger_count, vehicle_id, employee_id,
               pickup_time, pickup_address, dropoff_address,
               client_notes, driver_notes, vehicle_notes,
               total_amount_due, status, created_at
        FROM charters
        ORDER BY created_at DESC
        LIMIT 1
    """)
    
    charter = cur.fetchone()
    if not charter:
        print("\n❌ NO CHARTERS FOUND - Create a test charter first!")
        exit(1)
    
    (charter_id, reserve_number, charter_date, client_id,
     passenger_count, vehicle_id, employee_id,
     pickup_time, pickup_address, dropoff_address,
     client_notes, driver_notes, vehicle_notes,
     total_amount_due, status, created_at) = charter
    
    print(f"\n✅ MOST RECENT CHARTER: {reserve_number}")
    print(f"   Created: {created_at}")
    print(f"   Charter Date: {charter_date}")
    print("-" * 80)
    
    # Verify schema mappings
    print("\n📋 SCHEMA MAPPING VERIFICATION:")
    print("-" * 80)
    
    errors = []
    warnings = []
    
    # Check passenger_count (form sends passenger_load)
    if passenger_count is not None:
        print(f"✅ passenger_count = {passenger_count} (form.passenger_load mapped correctly)")
    else:
        errors.append("❌ passenger_count is NULL (form.passenger_load NOT mapped)")
    
    # Check vehicle_id (form sends vehicle_booked_id)
    if vehicle_id is not None:
        print(f"✅ vehicle_id = {vehicle_id} (form.vehicle_booked_id mapped correctly)")
        
        # Verify JOIN to vehicles table works
        cur.execute("""
            SELECT vehicle_number, make, model 
            FROM vehicles 
            WHERE vehicle_id = %s
        """, (vehicle_id,))
        vehicle = cur.fetchone()
        if vehicle:
            print(f"   → Vehicle: #{vehicle[0]} {vehicle[1]} {vehicle[2]}")
        else:
            warnings.append(f"⚠️  vehicle_id={vehicle_id} not found in vehicles table")
    else:
        warnings.append("⚠️  vehicle_id is NULL (optional field)")
    
    # Check employee_id (form sends assigned_driver_id)
    if employee_id is not None:
        print(f"✅ employee_id = {employee_id} (form.assigned_driver_id mapped correctly)")
        
        # Verify JOIN to employees table works
        cur.execute("""
            SELECT first_name, last_name 
            FROM employees 
            WHERE employee_id = %s
        """, (employee_id,))
        employee = cur.fetchone()
        if employee:
            print(f"   → Driver: {employee[0]} {employee[1]}")
        else:
            warnings.append(f"⚠️  employee_id={employee_id} not found in employees table")
    else:
        warnings.append("⚠️  employee_id is NULL (optional field)")
    
    # Check pickup_time (was missing from INSERT)
    if pickup_time is not None:
        print(f"✅ pickup_time = {pickup_time} (now saving correctly)")
    else:
        warnings.append("⚠️  pickup_time is NULL (may not have been provided)")
    
    # Check notes fields (form.customer_notes, dispatcher_notes, special_requests)
    if client_notes:
        print(f"✅ client_notes = '{client_notes[:50]}...' (form.customer_notes mapped)")
    else:
        warnings.append("⚠️  client_notes is NULL (form.customer_notes may be empty)")
    
    if driver_notes:
        print(f"✅ driver_notes = '{driver_notes[:50]}...' (form.dispatcher_notes mapped)")
    else:
        warnings.append("⚠️  driver_notes is NULL (form.dispatcher_notes may be empty)")
    
    if vehicle_notes:
        print(f"✅ vehicle_notes = '{vehicle_notes[:50]}...' (form.special_requests mapped)")
    else:
        warnings.append("⚠️  vehicle_notes is NULL (form.special_requests may be empty)")
    
    # Check client record
    print("\n👤 CLIENT RECORD VERIFICATION:")
    print("-" * 80)
    
    cur.execute("""
        SELECT client_name, phone, email, 
               billing_address, city, province, zip_code
        FROM clients
        WHERE client_id = %s
    """, (client_id,))
    
    client = cur.fetchone()
    if client:
        (client_name, phone, email, billing_address, city, province, zip_code) = client
        print(f"✅ client_name = {client_name}")
        print(f"✅ phone = {phone}")
        print(f"✅ email = {email}")
        
        if billing_address:
            print(f"✅ billing_address = {billing_address} (now saving)")
        else:
            warnings.append("⚠️  billing_address is NULL (may not have been provided)")
        
        if city:
            print(f"✅ city = {city} (now saving)")
        else:
            warnings.append("⚠️  city is NULL (may not have been provided)")
        
        if province:
            print(f"✅ province = {province} (now saving)")
        else:
            warnings.append("⚠️  province is NULL (may not have been provided)")
        
        if zip_code:
            print(f"✅ zip_code = {zip_code} (form.postal_code mapped correctly)")
        else:
            warnings.append("⚠️  zip_code is NULL (form.postal_code may be empty)")
    
    # Check charter_routes
    print("\n🗺️  CHARTER ROUTES VERIFICATION:")
    print("-" * 80)
    
    cur.execute("""
        SELECT route_id, route_sequence, 
               pickup_location, pickup_time,
               dropoff_location, dropoff_time
        FROM charter_routes
        WHERE charter_id = %s
        ORDER BY route_sequence
    """, (charter_id,))
    
    routes = cur.fetchall()
    if routes:
        print(f"✅ Found {len(routes)} route(s)")
        for route in routes:
            (route_id, seq, pu_loc, pu_time, do_loc, do_time) = route
            print(f"   Route #{seq}:")
            if pu_loc:
                print(f"     Pickup: {pu_loc[:40]}... at {pu_time or 'NO TIME'}")
            if do_loc:
                print(f"     Dropoff: {do_loc[:40]}... at {do_time or 'NO TIME'}")
    else:
        warnings.append("⚠️  No routes found (itinerary may have been empty)")
    
    # Check charges
    print("\n💰 CHARGES VERIFICATION:")
    print("-" * 80)
    
    cur.execute("""
        SELECT charge_type, amount, description
        FROM charges
        WHERE reserve_number = %s
    """, (reserve_number,))
    
    charges = cur.fetchall()
    total_charges = 0
    if charges:
        print(f"✅ Found {len(charges)} charge(s)")
        for charge in charges:
            charge_type, amount, description = charge
            total_charges += amount or 0
            print(f"   {charge_type}: ${amount:,.2f} - {description}")
        print(f"   TOTAL CHARGES: ${total_charges:,.2f}")
        
        if total_amount_due:
            if abs(total_charges - total_amount_due) < 0.01:
                print(f"✅ Charges match total_amount_due (${total_amount_due:,.2f})")
            else:
                errors.append(f"❌ Charges (${total_charges:,.2f}) ≠ total_amount_due (${total_amount_due:,.2f})")
    else:
        warnings.append("⚠️  No charges found")
    
    # Test the bookings list query
    print("\n📊 BOOKINGS LIST QUERY TEST:")
    print("-" * 80)
    
    cur.execute("""
        SELECT
            c.reserve_number,
            c.passenger_count,
            c.vehicle_id,
            COALESCE(v.vehicle_number, '') AS vehicle,
            COALESCE(v.make || ' ' || v.model, '') AS vehicle_description,
            COALESCE(e.first_name || ' ' || e.last_name, '') AS driver_name,
            c.nrd_amount AS retainer,
            c.fuel_litres AS fuel_added
        FROM charters c
        LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
        LEFT JOIN employees e ON c.employee_id = e.employee_id
        WHERE c.charter_id = %s
    """, (charter_id,))
    
    booking = cur.fetchone()
    if booking:
        (res, pass_cnt, veh_id, vehicle, veh_desc, driver, retainer, fuel) = booking
        print(f"✅ Bookings list query works:")
        print(f"   reserve_number: {res}")
        print(f"   passenger_count: {pass_cnt}")
        print(f"   vehicle: {vehicle} (from JOIN)")
        print(f"   vehicle_description: {veh_desc} (from JOIN)")
        print(f"   driver_name: {driver or '(none)'} (from JOIN)")
        
        if not vehicle and vehicle_id:
            errors.append(f"❌ vehicle JOIN failed (vehicle_id={vehicle_id} but no vehicle found)")
        if not driver and employee_id:
            errors.append(f"❌ driver JOIN failed (employee_id={employee_id} but no employee found)")
    
    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    
    if errors:
        print(f"\n❌ ERRORS FOUND ({len(errors)}):")
        for error in errors:
            print(f"   {error}")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings:
            print(f"   {warning}")
    
    if not errors and not warnings:
        print("\n🎉 ALL CHECKS PASSED! Schema fixes are working correctly!")
    elif not errors:
        print("\n✅ No critical errors - Some optional fields may be NULL")
    else:
        print("\n❌ CRITICAL ERRORS FOUND - Schema fixes may not be working correctly")

print("\n" + "=" * 80)
print("To test manually:")
print("1. Open http://127.0.0.1:8000 in browser")
print("2. Navigate to Booking Form (New Charter)")
print("3. Fill in ALL fields including notes, billing address, postal code")
print("4. Add itinerary with pickup/dropoff times")
print("5. Add charges")
print("6. Submit the form")
print("7. Run this script again to verify")
print("=" * 80)
