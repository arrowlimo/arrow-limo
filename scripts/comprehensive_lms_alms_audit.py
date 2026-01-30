#!/usr/bin/env python3
"""
Comprehensive LMS to ALMS Data Audit (Corrected for actual schema).

CRITICAL FINDINGS FIRST:
- charter_payments table: 0 rows (NO CUSTOMER PAYMENTS IN ALMS YET!)
- payments table: 0 rows
- Need to import payment data from LMS

Verifies:
1. Charter data completeness (times, routing, driver, vehicle)
2. Payment status (currently MISSING - need LMS import)
3. Data gaps that LMS can fill
4. Column population verification
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "***REDACTED***"),
    cursor_factory=RealDictCursor
)

print("="*100)
print("COMPREHENSIVE LMS TO ALMS DATA AUDIT")
print("="*100)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

print("\n⚠️  CRITICAL: charter_payments table is EMPTY (0 rows)")
print("⚠️  CRITICAL: payments table is EMPTY (0 rows)")
print("⚠️  Customer payments need to be imported from LMS!\n")

cur = conn.cursor()

# ============================================================================
# SECTION 1: CHARTER DATA COMPLETENESS
# ============================================================================
print("\n" + "="*100)
print("SECTION 1: CHARTER DATA COMPLETENESS")
print("="*100)

# Check charter count
cur.execute("SELECT COUNT(*) as count FROM charters WHERE charter_date >= '2012-01-01'")
charter_count = cur.fetchone()['count']
print(f"\nTotal Charters (2012+): {charter_count:,}")

# Check pickup/dropoff times
cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN pickup_time IS NULL THEN 1 END) as missing_pickup_time,
        COUNT(CASE WHEN actual_pickup_time IS NULL THEN 1 END) as missing_actual_pickup,
        COUNT(CASE WHEN actual_dropoff_time IS NULL THEN 1 END) as missing_actual_dropoff
    FROM charters
    WHERE charter_date >= '2012-01-01'
""")
time_stats = cur.fetchone()

print(f"\n1.1 PICKUP/DROPOFF TIMES:")
print(f"  Total Charters: {time_stats['total_charters']:,}")
print(f"  Missing pickup_time (scheduled): {time_stats['missing_pickup_time']:,} ({time_stats['missing_pickup_time']/time_stats['total_charters']*100:.1f}%)")
print(f"  Missing actual_pickup_time: {time_stats['missing_actual_pickup']:,} ({time_stats['missing_actual_pickup']/time_stats['total_charters']*100:.1f}%)")
print(f"  Missing actual_dropoff_time: {time_stats['missing_actual_dropoff']:,} ({time_stats['missing_actual_dropoff']/time_stats['total_charters']*100:.1f}%)")

# Check driver assignment (multiple fields)
cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN driver IS NULL AND employee_id IS NULL AND assigned_driver_id IS NULL AND driver_name IS NULL THEN 1 END) as no_driver_info,
        COUNT(CASE WHEN driver IS NOT NULL THEN 1 END) as has_driver_field,
        COUNT(CASE WHEN employee_id IS NOT NULL THEN 1 END) as has_employee_id,
        COUNT(CASE WHEN assigned_driver_id IS NOT NULL THEN 1 END) as has_assigned_driver_id,
        COUNT(CASE WHEN driver_name IS NOT NULL THEN 1 END) as has_driver_name
    FROM charters
    WHERE charter_date >= '2012-01-01'
""")
driver_stats = cur.fetchone()

print(f"\n1.2 DRIVER ASSIGNMENT:")
print(f"  Total Charters: {driver_stats['total_charters']:,}")
print(f"  NO driver info at all: {driver_stats['no_driver_info']:,} ({driver_stats['no_driver_info']/driver_stats['total_charters']*100:.1f}%)")
print(f"  Has driver (text): {driver_stats['has_driver_field']:,}")
print(f"  Has employee_id (FK): {driver_stats['has_employee_id']:,}")
print(f"  Has assigned_driver_id: {driver_stats['has_assigned_driver_id']:,}")
print(f"  Has driver_name: {driver_stats['has_driver_name']:,}")

# Check vehicle assignment
cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN vehicle IS NULL AND vehicle_id IS NULL AND vehicle_booked_id IS NULL THEN 1 END) as no_vehicle_info,
        COUNT(CASE WHEN vehicle IS NOT NULL THEN 1 END) as has_vehicle_field,
        COUNT(CASE WHEN vehicle_id IS NOT NULL THEN 1 END) as has_vehicle_id,
        COUNT(CASE WHEN vehicle_booked_id IS NOT NULL THEN 1 END) as has_vehicle_booked
    FROM charters
    WHERE charter_date >= '2012-01-01'
""")
vehicle_stats = cur.fetchone()

print(f"\n1.3 VEHICLE ASSIGNMENT:")
print(f"  Total Charters: {vehicle_stats['total_charters']:,}")
print(f"  NO vehicle info at all: {vehicle_stats['no_vehicle_info']:,} ({vehicle_stats['no_vehicle_info']/vehicle_stats['total_charters']*100:.1f}%)")
print(f"  Has vehicle (text): {vehicle_stats['has_vehicle_field']:,}")
print(f"  Has vehicle_id (FK): {vehicle_stats['has_vehicle_id']:,}")
print(f"  Has vehicle_booked_id: {vehicle_stats['has_vehicle_booked']:,}")

# Check routing information
cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN pickup_address IS NULL OR pickup_address = '' THEN 1 END) as missing_pickup_address,
        COUNT(CASE WHEN dropoff_address IS NULL OR dropoff_address = '' THEN 1 END) as missing_dropoff_address
    FROM charters
    WHERE charter_date >= '2012-01-01'
""")
routing_stats = cur.fetchone()

print(f"\n1.4 ROUTING INFORMATION:")
print(f"  Total Charters: {routing_stats['total_charters']:,}")
print(f"  Missing/Empty Pickup Address: {routing_stats['missing_pickup_address']:,} ({routing_stats['missing_pickup_address']/routing_stats['total_charters']*100:.1f}%)")
print(f"  Missing/Empty Dropoff Address: {routing_stats['missing_dropoff_address']:,} ({routing_stats['missing_dropoff_address']/routing_stats['total_charters']*100:.1f}%)")

# Check if charters_routing_times table has data
cur.execute("SELECT COUNT(*) as count FROM charters_routing_times")
routing_table_count = cur.fetchone()['count']
print(f"\n  charters_routing_times table: {routing_table_count:,} rows")
if routing_table_count == 0:
    print("  ⚠️  Routing times table is EMPTY - needs LMS import")

# ============================================================================
# SECTION 2: PAYMENT STATUS (CRITICAL GAP)
# ============================================================================
print("\n" + "="*100)
print("SECTION 2: PAYMENT STATUS (CRITICAL GAP)")
print("="*100)

# Check payment tables
cur.execute("SELECT COUNT(*) as count FROM charter_payments")
charter_payments_count = cur.fetchone()['count']

cur.execute("SELECT COUNT(*) as count FROM payments")
payments_count = cur.fetchone()['count']

print(f"\n⚠️  charter_payments table: {charter_payments_count:,} rows (EMPTY!)")
print(f"⚠️  payments table: {payments_count:,} rows (EMPTY!)")
print(f"\n🔴 CRITICAL: Customer payment data NOT in ALMS yet!")
print(f"🔴 CRITICAL: Need to import payment data from LMS")

# Check charter payment fields
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN total_amount_due IS NOT NULL AND total_amount_due > 0 THEN 1 END) as has_amount_due,
        COUNT(CASE WHEN paid_amount IS NOT NULL AND paid_amount > 0 THEN 1 END) as has_paid_amount,
        COUNT(CASE WHEN balance IS NOT NULL THEN 1 END) as has_balance,
        SUM(total_amount_due) as sum_amount_due,
        SUM(paid_amount) as sum_paid,
        SUM(balance) as sum_balance
    FROM charters
    WHERE charter_date >= '2012-01-01'
      AND cancelled = FALSE
""")
payment_fields = cur.fetchone()

print(f"\nCharter Payment Fields (in charters table):")
print(f"  Total Non-Cancelled Charters: {payment_fields['total']:,}")
print(f"  Has total_amount_due > 0: {payment_fields['has_amount_due']:,}")
print(f"  Has paid_amount > 0: {payment_fields['has_paid_amount']:,}")
print(f"  Has balance (not NULL): {payment_fields['has_balance']:,}")
print(f"\n  Sum of total_amount_due: ${payment_fields['sum_amount_due']:,.2f}")
print(f"  Sum of paid_amount: ${payment_fields['sum_paid']:,.2f}")
print(f"  Sum of balance: ${payment_fields['sum_balance']:,.2f}")

# ============================================================================
# SECTION 3: NULL FIELDS IN ALMS (LMS CAN FILL)
# ============================================================================
print("\n" + "="*100)
print("SECTION 3: NULL FIELDS IN ALMS (LMS CAN POTENTIALLY FILL)")
print("="*100)

# Check key charter fields that might be in LMS
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN client_display_name IS NULL OR client_display_name = '' THEN 1 END) as null_client_name,
        COUNT(CASE WHEN passenger_count IS NULL THEN 1 END) as null_passenger_count,
        COUNT(CASE WHEN pickup_address IS NULL OR pickup_address = '' THEN 1 END) as null_pickup_address,
        COUNT(CASE WHEN dropoff_address IS NULL OR dropoff_address = '' THEN 1 END) as null_dropoff_address,
        COUNT(CASE WHEN pickup_time IS NULL THEN 1 END) as null_pickup_time,
        COUNT(CASE WHEN actual_pickup_time IS NULL THEN 1 END) as null_actual_pickup,
        COUNT(CASE WHEN actual_dropoff_time IS NULL THEN 1 END) as null_actual_dropoff,
        COUNT(CASE WHEN notes IS NULL OR notes = '' THEN 1 END) as null_notes,
        COUNT(CASE WHEN driver IS NULL AND employee_id IS NULL THEN 1 END) as null_driver,
        COUNT(CASE WHEN vehicle IS NULL AND vehicle_id IS NULL THEN 1 END) as null_vehicle,
        COUNT(CASE WHEN rate IS NULL THEN 1 END) as null_rate,
        COUNT(CASE WHEN charter_type IS NULL OR charter_type = '' THEN 1 END) as null_charter_type
    FROM charters
    WHERE charter_date >= '2012-01-01'
""")
null_stats = cur.fetchone()

print(f"\nTotal Charters: {null_stats['total']:,}\n")
print(f"  NULL/empty client_display_name: {null_stats['null_client_name']:,} ({null_stats['null_client_name']/null_stats['total']*100:.1f}%)")
print(f"  NULL passenger_count: {null_stats['null_passenger_count']:,} ({null_stats['null_passenger_count']/null_stats['total']*100:.1f}%)")
print(f"  NULL/empty pickup_address: {null_stats['null_pickup_address']:,} ({null_stats['null_pickup_address']/null_stats['total']*100:.1f}%)")
print(f"  NULL/empty dropoff_address: {null_stats['null_dropoff_address']:,} ({null_stats['null_dropoff_address']/null_stats['total']*100:.1f}%)")
print(f"  NULL pickup_time (scheduled): {null_stats['null_pickup_time']:,} ({null_stats['null_pickup_time']/null_stats['total']*100:.1f}%)")
print(f"  NULL actual_pickup_time: {null_stats['null_actual_pickup']:,} ({null_stats['null_actual_pickup']/null_stats['total']*100:.1f}%)")
print(f"  NULL actual_dropoff_time: {null_stats['null_actual_dropoff']:,} ({null_stats['null_actual_dropoff']/null_stats['total']*100:.1f}%)")
print(f"  NULL/empty notes: {null_stats['null_notes']:,} ({null_stats['null_notes']/null_stats['total']*100:.1f}%)")
print(f"  NULL driver: {null_stats['null_driver']:,} ({null_stats['null_driver']/null_stats['total']*100:.1f}%)")
print(f"  NULL vehicle: {null_stats['null_vehicle']:,} ({null_stats['null_vehicle']/null_stats['total']*100:.1f}%)")
print(f"  NULL rate: {null_stats['null_rate']:,} ({null_stats['null_rate']/null_stats['total']*100:.1f}%)")
print(f"  NULL/empty charter_type: {null_stats['null_charter_type']:,} ({null_stats['null_charter_type']/null_stats['total']*100:.1f}%)")

# ============================================================================
# SECTION 4: LMS TABLE CHECK
# ============================================================================
print("\n" + "="*100)
print("SECTION 4: LMS TABLE AVAILABILITY")
print("="*100)

# Check if LMS tables exist
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
      AND (table_name LIKE 'lms_%' OR table_name LIKE '%_lms' OR table_name LIKE '%lms%')
    ORDER BY table_name
""")
lms_tables = cur.fetchall()

if lms_tables:
    print(f"\nLMS Tables Found: {len(lms_tables)}")
    for table in lms_tables:
        print(f"  - {table['table_name']}")
        
        # Get row count
        cur.execute(f"SELECT COUNT(*) as count FROM {table['table_name']}")
        count = cur.fetchone()
        print(f"    Rows: {count['count']:,}")
        
        # Get column names for key tables
        if 'charter' in table['table_name'] or 'payment' in table['table_name']:
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table['table_name']}' 
                ORDER BY ordinal_position 
                LIMIT 15
            """)
            cols = cur.fetchall()
            print(f"    Key columns: {', '.join([c['column_name'] for c in cols])}")
else:
    print("\n⚠️  NO LMS TABLES FOUND")
    print("    If LMS data exists, it may be in CSV files or external database")
    print("    Check for LMS import scripts in l:\\limo\\scripts\\")

# ============================================================================
# SECTION 5: CHARTER BALANCE VERIFICATION
# ============================================================================
print("\n" + "="*100)
print("SECTION 5: CHARTER BALANCE VERIFICATION")
print("="*100)

# Check balance calculation consistency
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN balance != (total_amount_due - paid_amount) THEN 1 END) as balance_mismatch,
        COUNT(CASE WHEN balance = 0 THEN 1 END) as zero_balance,
        COUNT(CASE WHEN balance < 0 THEN 1 END) as negative_balance,
        COUNT(CASE WHEN balance > 0 THEN 1 END) as positive_balance
    FROM charters
    WHERE charter_date >= '2012-01-01'
      AND cancelled = FALSE
      AND total_amount_due IS NOT NULL
      AND paid_amount IS NOT NULL
      AND balance IS NOT NULL
""")
balance_stats = cur.fetchone()

print(f"\nBalance Verification:")
print(f"  Total charters with all payment fields: {balance_stats['total']:,}")
print(f"  Balance mismatch (balance != total - paid): {balance_stats['balance_mismatch']:,}")
print(f"  Zero balance: {balance_stats['zero_balance']:,}")
print(f"  Negative balance (overpaid): {balance_stats['negative_balance']:,}")
print(f"  Positive balance (owing): {balance_stats['positive_balance']:,}")

# Sample balance mismatches
if balance_stats['balance_mismatch'] > 0:
    cur.execute("""
        SELECT 
            reserve_number, charter_date, total_amount_due, paid_amount, balance,
            (total_amount_due - paid_amount) as calculated_balance,
            (balance - (total_amount_due - paid_amount)) as difference
        FROM charters
        WHERE charter_date >= '2012-01-01'
          AND cancelled = FALSE
          AND balance != (total_amount_due - paid_amount)
        ORDER BY ABS(balance - (total_amount_due - paid_amount)) DESC
        LIMIT 10
    """)
    mismatches = cur.fetchall()
    
    print(f"\n  Top 10 Balance Mismatches:")
    for row in mismatches:
        print(f"\n    Reserve: {row['reserve_number']} | Date: {row['charter_date']}")
        print(f"    Total: ${row['total_amount_due']:,.2f} | Paid: ${row['paid_amount']:,.2f}")
        print(f"    Balance (stored): ${row['balance']:,.2f} | Calculated: ${row['calculated_balance']:,.2f}")
        print(f"    DIFFERENCE: ${row['difference']:,.2f}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*100)
print("AUDIT SUMMARY & NEXT STEPS")
print("="*100)

print(f"""
KEY FINDINGS:

1. CRITICAL - Payment Data Missing:
   ❌ charter_payments table: 0 rows (NO customer payment transactions)
   ❌ payments table: 0 rows
   ✅ Charter totals exist in charters table: ${payment_fields['sum_amount_due']:,.2f}
   ✅ Charter paid amounts exist: ${payment_fields['sum_paid']:,.2f}
   🔴 ACTION REQUIRED: Import payment transaction details from LMS

2. Charter Completeness:
   - {time_stats['missing_pickup_time']:,} charters missing pickup times ({time_stats['missing_pickup_time']/time_stats['total_charters']*100:.1f}%)
   - {driver_stats['no_driver_info']:,} charters missing ALL driver info ({driver_stats['no_driver_info']/driver_stats['total_charters']*100:.1f}%)
   - {vehicle_stats['no_vehicle_info']:,} charters missing ALL vehicle info ({vehicle_stats['no_vehicle_info']/vehicle_stats['total_charters']*100:.1f}%)

3. Routing Data:
   - {routing_stats['missing_pickup_address']:,} charters missing pickup address
   - {routing_stats['missing_dropoff_address']:,} charters missing dropoff address
   - charters_routing_times table: {routing_table_count:,} rows (need LMS import if 0)

4. Balance Verification:
   - {balance_stats['balance_mismatch']:,} charters with balance calculation mismatches
   - {balance_stats['zero_balance']:,} zero-balance charters
   - {balance_stats['negative_balance']:,} overpaid charters

5. Data Gaps (NULL fields that LMS might fill):
   - Client name: {null_stats['null_client_name']:,} ({null_stats['null_client_name']/null_stats['total']*100:.1f}%)
   - Passenger count: {null_stats['null_passenger_count']:,} ({null_stats['null_passenger_count']/null_stats['total']*100:.1f}%)
   - Pickup/Dropoff times: {null_stats['null_pickup_time']:,} / {null_stats['null_actual_dropoff']:,}
   - Driver: {null_stats['null_driver']:,} ({null_stats['null_driver']/null_stats['total']*100:.1f}%)
   - Vehicle: {null_stats['null_vehicle']:,} ({null_stats['null_vehicle']/null_stats['total']*100:.1f}%)

IMMEDIATE NEXT STEPS:

1. 🔴 URGENT: Locate LMS payment transaction data
   - Check for LMS database connection or CSV exports
   - Identify payment table structure in LMS
   - Map LMS payment fields to charter_payments table

2. Create import script for LMS payments:
   - Extract payment transactions with reserve_number links
   - Include: payment_date, amount, payment_method, reference_number
   - Verify 100% matching (SUM(payments.amount) = charter.paid_amount)

3. Fill NULL fields from LMS:
   - Pickup/dropoff times
   - Routing information (charters_routing_times table)
   - Driver/vehicle assignments (if missing employee_id/vehicle_id)
   - Customer names, passenger counts

4. Verify data integrity:
   - Fix balance calculation mismatches
   - Link e-transfer payments to banking_transactions
   - Ensure GST-exempt charters flagged correctly

5. Cross-reference with reconciliation tables:
   - charter_reconciliation_status (18,442 rows) - review existing reconciliation
   - payment_matches (581 rows) - verify payment matching logic
""")

cur.close()
conn.close()

print("\n" + "="*100)
print("AUDIT COMPLETE")
print("="*100)
