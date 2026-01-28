#!/usr/bin/env python3
"""
Check how we're currently tracking maintenance, bookings, fuel, insurance, and documents
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("CURRENT TABLE USAGE ANALYSIS")
print("=" * 80)

# 1. Check vehicles table for maintenance/insurance/document fields
print("\n1. VEHICLES TABLE - Current Schema:")
print("-" * 80)
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns 
    WHERE table_name='vehicles' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]:<40} {row[1]:<20} NULL={row[2]}")

# 2. Check for fuel-related data storage
print("\n2. FUEL TRACKING - Where is fuel data stored?")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) FROM receipts 
    WHERE description ILIKE '%fuel%' OR description ILIKE '%gas%' 
       OR payee ILIKE '%petro%' OR payee ILIKE '%shell%' 
       OR payee ILIKE '%esso%'
""")
fuel_receipts = cur.fetchone()[0]
print(f"  Fuel receipts in 'receipts' table: {fuel_receipts}")

cur.execute("""
    SELECT COUNT(*) FROM general_ledger 
    WHERE account_name ILIKE '%fuel%' OR account_name ILIKE '%gas%'
""")
fuel_gl = cur.fetchone()[0]
print(f"  Fuel entries in 'general_ledger': {fuel_gl}")

# Check if vehicle_fuel_log exists and has data
cur.execute("""
    SELECT COUNT(*) FROM vehicle_fuel_log
""")
fuel_log = cur.fetchone()[0]
print(f"  Entries in 'vehicle_fuel_log' table: {fuel_log}")

# 3. Check for insurance tracking
print("\n3. INSURANCE TRACKING - Where is insurance data stored?")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*), 
           COUNT(insurance_carrier),
           COUNT(insurance_policy)
    FROM vehicles 
    WHERE insurance_carrier IS NOT NULL OR insurance_policy IS NOT NULL
""")
row = cur.fetchone()
print(f"  Vehicles with insurance data in 'vehicles' table: {row[1]}")

cur.execute("""
    SELECT COUNT(*) FROM vehicle_insurance
""")
ins_table = cur.fetchone()[0]
print(f"  Entries in 'vehicle_insurance' table: {ins_table}")

cur.execute("""
    SELECT COUNT(*) FROM receipts 
    WHERE description ILIKE '%insurance%' OR payee ILIKE '%insurance%'
""")
ins_receipts = cur.fetchone()[0]
print(f"  Insurance receipts in 'receipts' table: {ins_receipts}")

# 4. Check for maintenance tracking
print("\n4. MAINTENANCE TRACKING - Where is maintenance data stored?")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) FROM maintenance_records
""")
maint_records = cur.fetchone()[0]
print(f"  Entries in 'maintenance_records' table: {maint_records}")

cur.execute("""
    SELECT COUNT(*) FROM receipts 
    WHERE description ILIKE '%maint%' OR description ILIKE '%repair%' 
       OR payee ILIKE '%tire%' OR payee ILIKE '%auto%'
""")
maint_receipts = cur.fetchone()[0]
print(f"  Maintenance receipts in 'receipts' table: {maint_receipts}")

# 5. Check for document storage
print("\n5. DOCUMENT STORAGE - Where are vehicle documents stored?")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) FROM vehicle_documents
""")
doc_table = cur.fetchone()[0]
print(f"  Entries in 'vehicle_documents' table: {doc_table}")

cur.execute("""
    SELECT COUNT(*) FROM driver_documents
""")
driver_docs = cur.fetchone()[0]
print(f"  Driver documents in 'driver_documents' table: {driver_docs}")

cur.execute("""
    SELECT COUNT(*) FROM financial_documents
""")
fin_docs = cur.fetchone()[0]
print(f"  Financial documents in 'financial_documents' table: {fin_docs}")

# 6. Check for booking/reservation system
print("\n6. BOOKING/RESERVATION SYSTEM - How do we track bookings?")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) FROM charters WHERE status ILIKE '%pend%' OR status ILIKE '%quot%'
""")
pending_charters = cur.fetchone()[0]
print(f"  Pending/quote charters in 'charters' table: {pending_charters}")

cur.execute("""
    SELECT COUNT(*) FROM bookings
""")
bookings_table = cur.fetchone()[0]
print(f"  Entries in 'bookings' table: {bookings_table}")

cur.execute("""
    SELECT DISTINCT status FROM charters WHERE status IS NOT NULL ORDER BY status
""")
print(f"  Charter statuses in use:")
for row in cur.fetchall():
    print(f"    - {row[0]}")

# 7. Check payment reconciliation
print("\n7. PAYMENT RECONCILIATION - Where is bank reconciliation stored?")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) FROM payment_reconciliation
""")
pay_recon = cur.fetchone()[0]
print(f"  Entries in 'payment_reconciliation' table: {pay_recon}")

cur.execute("""
    SELECT COUNT(*) FROM bank_reconciliation
""")
bank_recon = cur.fetchone()[0]
print(f"  Entries in 'bank_reconciliation' table: {bank_recon}")

cur.execute("""
    SELECT COUNT(*) FROM banking_transactions 
    WHERE reconciled = false OR reconciled IS NULL
""")
unreconciled = cur.fetchone()[0]
print(f"  Unreconciled banking_transactions: {unreconciled}")

# 8. Check for invoices
print("\n8. INVOICES - How do we track invoicing?")
print("-" * 80)
cur.execute("""
    SELECT COUNT(*) FROM invoices
""")
invoices_table = cur.fetchone()[0]
print(f"  Entries in 'invoices' table: {invoices_table}")

cur.execute("""
    SELECT COUNT(*) FROM charters WHERE balance > 0
""")
unpaid_charters = cur.fetchone()[0]
print(f"  Charters with outstanding balance: {unpaid_charters}")

cur.execute("""
    SELECT COUNT(*) FROM invoice_tracking
""")
invoice_tracking = cur.fetchone()[0]
print(f"  Entries in 'invoice_tracking' table: {invoice_tracking}")

print("\n" + "=" * 80)
print("SUMMARY & RECOMMENDATIONS")
print("=" * 80)

# Provide recommendations
recommendations = []

if fuel_receipts > 0 and fuel_log == 0:
    recommendations.append("✓ FUEL: Tracked in 'receipts' table - vehicle_fuel_log is EMPTY and can be DROPPED")

if ins_receipts > 0 and ins_table == 0:
    recommendations.append("✓ INSURANCE: Tracked in 'receipts' and 'vehicles' - vehicle_insurance is EMPTY and can be DROPPED")

if maint_receipts > 0 and maint_records == 0:
    recommendations.append("[WARN]  MAINTENANCE: Tracked in 'receipts' - maintenance_records is EMPTY but may be needed for scheduling")

if doc_table == 0 and driver_docs > 0:
    recommendations.append("✓ DOCUMENTS: Driver docs working (420 records), vehicle_documents is EMPTY and can be DROPPED")

if bookings_table == 0 and pending_charters > 0:
    recommendations.append("✓ BOOKINGS: Tracked in 'charters' table with status - bookings table is EMPTY and can be DROPPED")

if pay_recon == 0 and bank_recon > 0:
    recommendations.append("✓ RECONCILIATION: Using 'bank_reconciliation' and 'banking_transactions' - payment_reconciliation is EMPTY and can be DROPPED")

if invoices_table == 0 and invoice_tracking > 0:
    recommendations.append("✓ INVOICES: Tracked via invoice_tracking and charters.balance - invoices table is EMPTY and can be DROPPED")

for rec in recommendations:
    print(f"\n{rec}")

conn.close()
