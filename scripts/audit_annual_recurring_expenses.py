#!/usr/bin/env python
"""Audit annual recurring expenses and vehicle compliance records."""

import psycopg2
import os
from datetime import datetime
from collections import defaultdict

# Database connection
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

def print_section(title):
    print("\n" + "=" * 100)
    print(title.center(100))
    print("=" * 100)

# ============================================================================
# 1. INSURANCE ANALYSIS
# ============================================================================
print_section("INSURANCE COVERAGE BY YEAR")

# Check for insurance payments/receipts by year
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as payment_count,
        SUM(gross_amount) as total_paid,
        STRING_AGG(DISTINCT vendor_name, ', ') as vendors
    FROM receipts
    WHERE LOWER(description) LIKE '%insurance%'
       OR LOWER(vendor_name) LIKE '%insurance%'
       OR LOWER(category) LIKE '%insurance%'
       OR LOWER(vendor_name) LIKE '%aviva%'
       OR LOWER(vendor_name) LIKE '%jevco%'
       OR LOWER(vendor_name) LIKE '%sgi%'
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")

insurance_receipts = cur.fetchall()
print(f"\n{'Year':<8} {'Payments':<12} {'Total Paid':<18} {'Vendors':<50}")
print("-" * 100)
for year, count, total, vendors in insurance_receipts:
    print(f"{int(year):<8} {count:<12} ${total:>15,.2f} {vendors or 'Unknown':<50}")

# Check email financial events for insurance
print("\n" + "-" * 100)
print("INSURANCE FROM EMAIL NOTIFICATIONS:")
print("-" * 100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM email_date) as year,
        COUNT(*) as notification_count,
        SUM(amount) as total_amount,
        STRING_AGG(DISTINCT entity, ', ') as entities
    FROM email_financial_events
    WHERE event_type IN ('insurance_payment', 'insurance_renewal', 'insurance_due')
       OR LOWER(notes) LIKE '%insurance%'
    GROUP BY EXTRACT(YEAR FROM email_date)
    ORDER BY year
""")

insurance_emails = cur.fetchall()
if cur.rowcount > 0:
    print(f"\n{'Year':<8} {'Notices':<12} {'Amount':<18} {'Entities':<50}")
    print("-" * 100)
    for year, count, total, entities in insurance_emails:
        print(f"{int(year):<8} {count:<12} ${total or 0:>15,.2f} {entities or 'Unknown':<50}")
else:
    print("\n⚠️  No insurance email events found")

# ============================================================================
# 2. HEFFNER AUTO FINANCING/LEASING
# ============================================================================
print_section("HEFFNER AUTO FINANCING - DOWN PAYMENTS & MONTHLY PAYMENTS")

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        EXTRACT(MONTH FROM receipt_date) as month,
        COUNT(*) as payment_count,
        SUM(gross_amount) as total_paid
    FROM receipts
    WHERE LOWER(vendor_name) LIKE '%heffner%'
       OR LOWER(description) LIKE '%heffner%'
    GROUP BY EXTRACT(YEAR FROM receipt_date), EXTRACT(MONTH FROM receipt_date)
    ORDER BY year, month
""")

heffner_payments = cur.fetchall()
if cur.rowcount > 0:
    print(f"\n{'Year-Month':<12} {'Payments':<12} {'Total Paid':<18}")
    print("-" * 100)
    
    year_totals = defaultdict(lambda: {'count': 0, 'amount': 0})
    for year, month, count, total in heffner_payments:
        print(f"{int(year)}-{int(month):02d}    {count:<12} ${total:>15,.2f}")
        year_totals[int(year)]['count'] += count
        year_totals[int(year)]['amount'] += total
    
    print("\n" + "-" * 100)
    print("ANNUAL HEFFNER TOTALS:")
    print("-" * 100)
    for year in sorted(year_totals.keys()):
        print(f"{year:<12} {year_totals[year]['count']:<12} ${year_totals[year]['amount']:>15,.2f}")
else:
    print("\n⚠️  No Heffner payments found in receipts")

# Check email events for Heffner
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM email_date) as year,
        COUNT(*) as event_count,
        SUM(amount) as total_amount
    FROM email_financial_events
    WHERE LOWER(entity) LIKE '%heffner%'
       OR lender_name = 'Heffner Auto Finance Corp'
    GROUP BY EXTRACT(YEAR FROM email_date)
    ORDER BY year
""")

heffner_emails = cur.fetchall()
if cur.rowcount > 0:
    print("\n" + "-" * 100)
    print("HEFFNER FROM EMAIL NOTIFICATIONS:")
    print("-" * 100)
    print(f"\n{'Year':<8} {'Events':<12} {'Amount':<18}")
    print("-" * 100)
    for year, count, total in heffner_emails:
        print(f"{int(year):<8} {count:<12} ${total or 0:>15,.2f}")

# ============================================================================
# 3. INTERNET, WEB HOSTING, EMAIL HOSTING
# ============================================================================
print_section("INTERNET, WEB HOSTING, EMAIL, AND LMS SERVICES")

service_patterns = [
    ('TELUS/ROGERS/BELL (Internet)', ['telus', 'rogers', 'bell', 'sasktel', 'shaw']),
    ('WEB HOSTING', ['hosting', 'godaddy', 'bluehost', 'hostgator', 'domain']),
    ('EMAIL HOSTING', ['email', 'gmail', 'outlook', 'office 365', 'microsoft 365']),
    ('LMS SOFTWARE', ['lms', 'limousine management', 'fleet software', 'dispatch'])
]

for service_name, patterns in service_patterns:
    where_conditions = ' OR '.join([f"LOWER(vendor_name) LIKE '%{p}%' OR LOWER(description) LIKE '%{p}%'" for p in patterns])
    
    cur.execute(f"""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as payment_count,
            SUM(gross_amount) as total_paid
        FROM receipts
        WHERE {where_conditions}
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    results = cur.fetchall()
    print(f"\n{service_name}:")
    print("-" * 100)
    
    if cur.rowcount > 0:
        print(f"{'Year':<8} {'Payments':<12} {'Total Paid':<18}")
        print("-" * 60)
        for year, count, total in results:
            print(f"{int(year):<8} {count:<12} ${total:>15,.2f}")
    else:
        print(f"⚠️  No {service_name} payments found")

# ============================================================================
# 4. CVIP RECORDS (Commercial Vehicle Inspection Program)
# ============================================================================
print_section("CVIP RECORDS FOR BUSES (>11 PASSENGERS)")

# First, identify buses
cur.execute("""
    SELECT 
        vehicle_id,
        unit_number,
        vehicle_type,
        make,
        model,
        year,
        passenger_capacity,
        license_plate
    FROM vehicles
    WHERE passenger_capacity > 11
       OR LOWER(vehicle_type) LIKE '%bus%'
       OR LOWER(vehicle_type) LIKE '%coach%'
    ORDER BY unit_number
""")

buses = cur.fetchall()
print(f"\n{'Unit#':<8} {'Type':<15} {'Make/Model':<25} {'Capacity':<10} {'License Plate':<15}")
print("-" * 100)

if cur.rowcount > 0:
    for vehicle_id, unit, vtype, make, model, year, capacity, plate in buses:
        make_model = f"{make or ''} {model or ''} {year or ''}".strip()
        print(f"{unit or 'N/A':<8} {vtype or 'Unknown':<15} {make_model:<25} {capacity or 'N/A':<10} {plate or 'N/A':<15}")
else:
    print("⚠️  No buses (>11 passengers) found in vehicles table")

# Check for CVIP payments/receipts
print("\n" + "-" * 100)
print("CVIP INSPECTION PAYMENTS:")
print("-" * 100)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as inspection_count,
        SUM(gross_amount) as total_paid
    FROM receipts
    WHERE LOWER(description) LIKE '%cvip%'
       OR LOWER(description) LIKE '%commercial vehicle inspection%'
       OR LOWER(category) LIKE '%inspection%'
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")

cvip_receipts = cur.fetchall()
if cur.rowcount > 0:
    print(f"\n{'Year':<8} {'Inspections':<12} {'Total Paid':<18}")
    print("-" * 60)
    for year, count, total in cvip_receipts:
        print(f"{int(year):<8} {count:<12} ${total:>15,.2f}")
else:
    print("⚠️  No CVIP inspection payments found")

# ============================================================================
# 5. RED DEER BUSINESS LICENSE RENEWALS
# ============================================================================
print_section("RED DEER BUSINESS LICENSE RENEWALS")

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as payment_count,
        SUM(gross_amount) as total_paid,
        STRING_AGG(DISTINCT description, ' | ') as descriptions
    FROM receipts
    WHERE (LOWER(vendor_name) LIKE '%red deer%' OR LOWER(description) LIKE '%red deer%')
      AND (LOWER(description) LIKE '%license%' 
           OR LOWER(description) LIKE '%licence%'
           OR LOWER(description) LIKE '%business%'
           OR LOWER(description) LIKE '%permit%')
    GROUP BY EXTRACT(YEAR FROM receipt_date)
    ORDER BY year
""")

rd_licenses = cur.fetchall()
if cur.rowcount > 0:
    print(f"\n{'Year':<8} {'Payments':<12} {'Total Paid':<18} {'Description':<50}")
    print("-" * 100)
    for year, count, total, desc in rd_licenses:
        desc_short = (desc[:47] + '...') if desc and len(desc) > 50 else (desc or '')
        print(f"{int(year):<8} {count:<12} ${total:>15,.2f} {desc_short:<50}")
else:
    print("⚠️  No Red Deer business license payments found")

# ============================================================================
# 6. OTHER ANNUAL FEES
# ============================================================================
print_section("OTHER ANNUAL FEES & GOVERNMENT CHARGES")

annual_fee_patterns = [
    ('SGI/VEHICLE REGISTRATION', ['sgi', 'registration', 'plate renewal']),
    ('WCB (Workers Compensation)', ['wcb', 'workers compensation', 'worker comp']),
    ('CRA/TAX PAYMENTS', ['canada revenue', 'cra', 'receiver general', 'tax payment']),
    ('CITY/MUNICIPAL FEES', ['city of red deer', 'municipal', 'property tax']),
    ('CORPORATE REGISTRY', ['corporate registry', 'alberta registry', 'annual return'])
]

for fee_name, patterns in annual_fee_patterns:
    where_conditions = ' OR '.join([f"LOWER(vendor_name) LIKE '%{p}%' OR LOWER(description) LIKE '%{p}%'" for p in patterns])
    
    cur.execute(f"""
        SELECT 
            EXTRACT(YEAR FROM receipt_date) as year,
            COUNT(*) as payment_count,
            SUM(gross_amount) as total_paid
        FROM receipts
        WHERE {where_conditions}
        GROUP BY EXTRACT(YEAR FROM receipt_date)
        ORDER BY year
    """)
    
    results = cur.fetchall()
    print(f"\n{fee_name}:")
    print("-" * 100)
    
    if cur.rowcount > 0:
        print(f"{'Year':<8} {'Payments':<12} {'Total Paid':<18}")
        print("-" * 60)
        for year, count, total in results:
            print(f"{int(year):<8} {count:<12} ${total:>15,.2f}")
    else:
        print(f"⚠️  No {fee_name} payments found")

# ============================================================================
# 7. SUMMARY OF MISSING YEARS
# ============================================================================
print_section("MISSING DATA SUMMARY (2007-2025)")

years_range = range(2007, 2026)
categories_to_check = {
    'Insurance': "LOWER(description) LIKE '%insurance%' OR LOWER(vendor_name) LIKE '%insurance%' OR LOWER(category) LIKE '%insurance%'",
    'Internet/Telecom': "LOWER(vendor_name) LIKE '%telus%' OR LOWER(vendor_name) LIKE '%rogers%' OR LOWER(vendor_name) LIKE '%bell%'",
    'Red Deer License': "(LOWER(vendor_name) LIKE '%red deer%' OR LOWER(description) LIKE '%red deer%') AND LOWER(description) LIKE '%license%'",
    'WCB': "LOWER(vendor_name) LIKE '%wcb%' OR LOWER(description) LIKE '%wcb%' OR LOWER(description) LIKE '%workers compensation%'",
    'Vehicle Registration': "LOWER(description) LIKE '%sgi%' OR LOWER(description) LIKE '%registration%' OR LOWER(description) LIKE '%plate%'"
}

print(f"\n{'Category':<25} {'Missing Years':<75}")
print("-" * 100)

for category, condition in categories_to_check.items():
    cur.execute(f"""
        SELECT DISTINCT EXTRACT(YEAR FROM receipt_date) as year
        FROM receipts
        WHERE {condition}
        ORDER BY year
    """)
    
    years_with_data = {int(row[0]) for row in cur.fetchall()}
    missing_years = [str(y) for y in years_range if y not in years_with_data]
    
    if missing_years:
        print(f"{category:<25} ⚠️  {', '.join(missing_years)}")
    else:
        print(f"{category:<25} ✅ All years covered")

cur.close()
conn.close()

print("\n" + "=" * 100)
print("\nAUDIT COMPLETE")
print("=" * 100)
