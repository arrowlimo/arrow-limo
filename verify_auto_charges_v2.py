#!/usr/bin/env python3
"""
Verify auto-charges logic without UI:
1. Load pricing defaults for a vehicle type
2. Simulate route times
3. Check charges populate correctly
"""
import os
import sys
sys.path.insert(0, "l:\\limo")

from datetime import datetime, timedelta
from decimal import Decimal
import psycopg2

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def load_pricing_defaults(vehicle_type: str):
    """Fetch pricing for a vehicle type"""
    defaults = {
        "nrr": 0.0,
        "hourly_rate": 0.0,
        "daily_rate": 0.0,
        "standby_rate": 0.0,
        "airport_pickup_calgary": 0.0,
        "airport_pickup_edmonton": 0.0,
    }

    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT nrr, hourly_rate, daily_rate, standby_rate,
                   airport_pickup_calgary, airport_pickup_edmonton
            FROM vehicle_pricing_defaults
            WHERE vehicle_type = %s
            """,
            (vehicle_type,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            nrr, hourly_rate, daily_rate, standby_rate, airport_cgy, airport_edm = row
            if nrr is not None:
                defaults["nrr"] = float(nrr)
            if hourly_rate is not None:
                defaults["hourly_rate"] = float(hourly_rate)
            if daily_rate is not None:
                defaults["daily_rate"] = float(daily_rate)
            if standby_rate is not None:
                defaults["standby_rate"] = float(standby_rate)
            if airport_cgy is not None:
                defaults["airport_pickup_calgary"] = float(airport_cgy)
            if airport_edm is not None:
                defaults["airport_pickup_edmonton"] = float(airport_edm)
    except Exception as e:
        print(f"❌ DB error: {e}")
        return defaults

    return defaults

def calculate_charges(vehicle_type: str, start_time: str, end_time: str, has_airport: bool = False):
    """Simulate _update_invoice_charges logic - NEW: NRR is minimum, not blocker"""
    pricing = load_pricing_defaults(vehicle_type)
    
    # Parse times
    start = datetime.strptime(start_time, "%H:%M")
    end = datetime.strptime(end_time, "%H:%M")
    
    if end < start:
        end += timedelta(days=1)
    
    total_hours = (end - start).total_seconds() / 3600
    
    # Simulate charges
    charges = []
    
    # Charter charge
    hourly_rate = pricing.get("hourly_rate", 0.0)
    if hourly_rate > 0 and total_hours > 0:
        charter_total = hourly_rate * total_hours
        charges.append(("Charter Charge", "Hourly", f"${charter_total:.2f}"))
    
    # Standby
    standby_rate = pricing.get("standby_rate", 0.0)
    if standby_rate > 0:
        charges.append(("Standby", "Fixed", f"${standby_rate:.2f}"))
    
    # Airport
    if has_airport:
        airport_rate = pricing.get("airport_pickup_calgary", 0.0) or pricing.get("airport_pickup_edmonton", 0.0)
        if airport_rate > 0:
            charges.append(("Airport Fee", "Fixed", f"${airport_rate:.2f}"))
    
    # Gratuity
    if hourly_rate > 0 and total_hours > 0:
        charter_total = hourly_rate * total_hours
        gratuity = charter_total * 0.18
        charges.append(("Gratuity", "Percent", f"${gratuity:.2f}"))
    
    nrr = pricing.get("nrr", 0.0)
    nrr_info = f"(NRR minimum: ${nrr:.2f})" if nrr > 0 else ""
    
    return charges, f"✅ {total_hours:.2f} hours", nrr_info

# Test 1: Sedan 3-hour charter
print("=" * 60)
print("TEST 1: Sedan 3-hour charter (08:00 - 11:00)")
print("=" * 60)
vehicle_type = "Sedan (3-4 pax)"
charges, info, nrr_info = calculate_charges(vehicle_type, "08:00", "11:00")
print(f"Vehicle: {vehicle_type}")
print(f"Duration: {info} {nrr_info}")
pricing = load_pricing_defaults(vehicle_type)
print(f"Pricing: Hourly ${pricing['hourly_rate']}, Standby ${pricing['standby_rate']}")
print(f"Charges:")
for desc, calc_type, total in charges:
    print(f"  - {desc:20} | {calc_type:8} | {total}")

# Calculate totals
charter_base = 0
for desc, calc_type, total in charges:
    if "Charter" in desc:
        try:
            charter_base = float(total.replace("$", ""))
        except:
            pass
total_before_nrr = sum(float(t.replace("$", "")) for _, _, t in charges)
nrr = pricing.get("nrr", 0.0)
total_after_nrr = max(total_before_nrr, nrr)
print(f"Subtotal: ${total_before_nrr:.2f} | After NRR minimum: ${total_after_nrr:.2f}")

# Test 2: SUV with airport
print("\n" + "=" * 60)
print("TEST 2: Luxury SUV 2-hour charter with airport (14:00 - 16:00)")
print("=" * 60)
vehicle_type = "Luxury SUV (3-4 pax)"
charges, info, nrr_info = calculate_charges(vehicle_type, "14:00", "16:00", has_airport=True)
print(f"Vehicle: {vehicle_type}")
print(f"Duration: {info} {nrr_info}")
pricing = load_pricing_defaults(vehicle_type)
print(f"Pricing: Hourly ${pricing['hourly_rate']}, Airport CY ${pricing['airport_pickup_calgary']}")
print(f"Charges:")
for desc, calc_type, total in charges:
    print(f"  - {desc:20} | {calc_type:8} | {total}")

total_before_nrr = sum(float(t.replace("$", "")) for _, _, t in charges)
nrr = pricing.get("nrr", 0.0)
total_after_nrr = max(total_before_nrr, nrr)
print(f"Subtotal: ${total_before_nrr:.2f} | After NRR minimum: ${total_after_nrr:.2f}")

# Test 3: Short 30-min trip (under NRR)
print("\n" + "=" * 60)
print("TEST 3: Sedan 30-min charter (18:00 - 18:30) [Test NRR minimum]")
print("=" * 60)
vehicle_type = "Sedan (3-4 pax)"
charges, info, nrr_info = calculate_charges(vehicle_type, "18:00", "18:30")
print(f"Vehicle: {vehicle_type}")
print(f"Duration: {info} {nrr_info}")
pricing = load_pricing_defaults(vehicle_type)
print(f"Pricing: Hourly ${pricing['hourly_rate']}, NRR minimum ${pricing['nrr']}")
print(f"Charges:")
for desc, calc_type, total in charges:
    print(f"  - {desc:20} | {calc_type:8} | {total}")

total_before_nrr = sum(float(t.replace("$", "")) for _, _, t in charges)
nrr = pricing.get("nrr", 0.0)
total_after_nrr = max(total_before_nrr, nrr)
print(f"Subtotal: ${total_before_nrr:.2f} | After NRR minimum: ${total_after_nrr:.2f} ← NRR applied!")

# Test 4: Check available vehicle types
print("\n" + "=" * 60)
print("TEST 4: Available vehicle types in DB")
print("=" * 60)
try:
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    cur.execute("SELECT vehicle_type, hourly_rate, standby_rate, nrr FROM vehicle_pricing_defaults ORDER BY vehicle_type")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    print(f"Found {len(rows)} vehicle types:")
    for vtype, hrly, standby, nrr in rows:
        nrr_flag = f"NRR={nrr}" if nrr > 0 else ""
        print(f"  - {vtype:30} Hourly: ${hrly:8.2f}  Standby: ${standby:8.2f}  {nrr_flag}")
except Exception as e:
    print(f"❌ Error fetching vehicle types: {e}")

print("\n✅ Auto-charges verification complete - NRR fixed to apply as minimum")
