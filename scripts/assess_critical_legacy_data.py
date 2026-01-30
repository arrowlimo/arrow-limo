#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 3: Determine what CRITICAL columns in legacy tables need migration to ALMS clients.
"""
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("="*80)
print("STEP 3: CRITICAL DATA IN LEGACY TABLES")
print("="*80)

print("\n1. limo_clients - Columns with DATA (non-NULL values):")
print("-" * 80)

cols_to_check = [
    'contact_person', 'service_preferences', 'work_phone', 'home_phone', 
    'cell_phone', 'fax_phone', 'cross_street', 'map_reference', 'department', 
    'attention', 'data_issues', 'created_date', 'address_line2'
]

for col in cols_to_check:
    cur.execute(f"""
        SELECT COUNT(*) as total, 
               COUNT(CASE WHEN "{col}" IS NOT NULL THEN 1 END) as with_data
        FROM limo_clients
    """)
    total, with_data = cur.fetchone()
    pct = (with_data / total * 100) if total > 0 else 0
    if with_data > 0:
        print(f"  {col:<25} {with_data:>6} / {total:<6} ({pct:>5.1f}%)")

print("\n2. lms_customers_enhanced - Columns with DATA (non-NULL values):")
print("-" * 80)

cols_to_check = [
    'primary_name', 'attention', 'work_phone', 'home_phone', 'cell_phone', 
    'fax_phone', 'address_line2', 'account_type', 'admin_contacts',
    'additional_addresses', 'full_name_search'
]

for col in cols_to_check:
    cur.execute(f"""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN "{col}" IS NOT NULL AND TRIM("{col}"::text) != '' THEN 1 END) as with_data
        FROM lms_customers_enhanced
    """)
    total, with_data = cur.fetchone()
    pct = (with_data / total * 100) if total > 0 else 0
    if with_data > 0:
        print(f"  {col:<25} {with_data:>6} / {total:<6} ({pct:>5.1f}%)")

print("\n" + "="*80)
print("ASSESSMENT:")
print("="*80)
print("""
✅ ALMS clients table already captures:
   - Basic info: name, phone, email, address
   - Billing: company_name, account_number, address_line1, city, state, zip_code
   - Financial: balance, credit_limit, discount, gratuity, interest rates
   - Status: is_inactive, status, is_taxable, is_gst_exempt
   - Collections: bad_debt_status, writeoff_date, recovery_probability
   - Tax: tax_code, sales_tax_code, exemption data
   - Integrations: qb_customer_id, square_customer_id, lms_customer_number

⚠️  UNIQUE in limo_clients (LOW PRIORITY):
   - service_preferences (reference data, not critical to operations)
   - contact_person, department, attention (contact detail variations)
   - work_phone, home_phone, cell_phone (already have primary_phone + phone)
   - fax_phone (legacy, rarely used)
   - cross_street, map_reference (location helpers, not operationally used)

⚠️  UNIQUE in lms_customers_enhanced (MEDIUM PRIORITY):
   - full_name_search (fuzzy matching field used by customer_name_resolver view)
   - account_type (account classification)
   - admin_contacts, additional_addresses (JSONB metadata)
   - primary_name (name variant - already have name, company_name)

🚨 CRITICAL DEPENDENCY:
   - customer_name_resolver VIEW uses lms_customers_enhanced.full_name_search
   - This view is used by square_to_lms_matcher_postgres.py for payment reconciliation
   - Must migrate full_name_search to ALMS before dropping lms_customers_enhanced
""")

cur.close()
conn.close()
