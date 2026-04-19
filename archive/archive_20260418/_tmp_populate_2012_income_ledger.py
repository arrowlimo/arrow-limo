#!/usr/bin/env python3
"""
Populate income_ledger from charter_payments for 2012.
This creates the single source of truth for T2 revenue reporting.
Standard process for all future years.

PROCESS:
  1. Extract from charter_payments (actual cash received)
  2. Link to charters for reserve_number and charter metadata
  3. Calculate GST at AB rate (5%)
  4. Record in income_ledger with standardized categories
  5. Run audit comparison to verify completeness
  6. Use income_ledger for all T2 revenue extraction
"""

import psycopg2
from decimal import Decimal
from datetime import datetime, date

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'almsdata'
DB_USER = 'postgres'
DB_PASSWORD = 'ArrowLimousine'

DRY_RUN = True  # Set to False to apply changes

def calculate_fiscal_quarter(payment_date):
    """Calculate fiscal quarter from payment date."""
    if payment_date is None:
        return None
    month = payment_date.month
    if month <= 3:
        return 1
    elif month <= 6:
        return 2
    elif month <= 9:
        return 3
    else:
        return 4

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()

    print("\n" + "="*80)
    print(f"POPULATE INCOME_LEDGER FROM CHARTER PAYMENTS (2012) - DRY RUN: {DRY_RUN}")
    print("="*80)

    # Get all 2012 charter payments to record
    query = """
    SELECT 
        cp.id as payment_id,
        cp.charter_id,
        cp.amount,
        cp.payment_date,
        cp.payment_method,
        c.charter_id as charter_rec_id,
        c.client_id,
        c.reserve_number
    FROM charter_payments cp
    LEFT JOIN charters c ON cp.charter_id = c.reserve_number
    WHERE EXTRACT(YEAR FROM cp.payment_date) = 2012
    ORDER BY cp.payment_date, cp.id;
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    
    print(f"\nFound {len(rows)} charter payment records for 2012")
    
    # Prepare insert statements
    inserts = []
    total_gross = Decimal('0')
    total_gst = Decimal('0')
    unmatched_count = 0
    
    for payment_id, charter_id_ref, amount, payment_date, payment_method, charter_rec_id, client_id, reserve_number in rows:
        amount = Decimal(str(amount)) if amount else Decimal('0')
        
        # Calculate GST (Alberta is 5%, tax-inclusive)
        gst_collected = (amount * Decimal('5')) / Decimal('105')
        gst_collected = gst_collected.quantize(Decimal('0.01'))
        net_amount = amount - gst_collected
        
        # Calculate fiscal quarter
        fiscal_year = Decimal('2012')
        fiscal_quarter = calculate_fiscal_quarter(payment_date)
        
        # Determine if charter is matched
        if charter_rec_id is None:
            unmatched_count += 1
            # Still record it, with null charter/client fields
        
        total_gross += amount
        total_gst += gst_collected
        
        # Prepare insert values
        insert_dict = {
            'payment_id': payment_id,
            'source_system': 'charter_payments',
            'transaction_date': payment_date,
            'fiscal_year': int(fiscal_year),
            'fiscal_quarter': fiscal_quarter,
            'revenue_category': 'Operating Revenue',
            'revenue_subcategory': 'Charter Services',
            'gross_amount': float(amount),
            'gst_collected': float(gst_collected),
            'net_amount': float(net_amount),
            'is_taxable': True,
            'tax_province': 'AB',
            'client_id': client_id,
            'charter_id': charter_rec_id,
            'reserve_number': reserve_number,
            'payment_method': payment_method,
            'payment_reference': f'PMT-{payment_id}',
            'description': f'Charter #{charter_rec_id} - Res #{reserve_number} - {payment_method}' if charter_rec_id else f'Charter payment (reserve {charter_id_ref})',
            'created_by': 'populate_2012_income_ledger.py'
        }
        inserts.append(insert_dict)
    
    print(f"\nCalculated totals:")
    print(f"  Gross amount:   ${float(total_gross):,.2f}")
    print(f"  GST collected:  ${float(total_gst):,.2f}")
    print(f"  Net amount:     ${float(total_gross - total_gst):,.2f}")
    print(f"  Unmatched reserves (no charter record): {unmatched_count}")
    
    # Show sample
    print(f"\n--- SAMPLE RECORDS (first 5) ---")
    for i, insert_dict in enumerate(inserts[:5]):
        print(f"\n{i+1}. Payment ID {insert_dict['payment_id']}")
        print(f"   Date: {insert_dict['transaction_date']}")
        print(f"   Charter: {insert_dict['charter_id']} | Reserve: {insert_dict['reserve_number']}")
        print(f"   Amount: ${insert_dict['gross_amount']:.2f} | GST: ${insert_dict['gst_collected']:.2f}")
    
    if not DRY_RUN:
        print(f"\n--- APPLYING INSERTS ---")
        insert_count = 0
        for insert_dict in inserts:
            insert_sql = """
            INSERT INTO income_ledger (
                payment_id, source_system, transaction_date, fiscal_year, fiscal_quarter,
                revenue_category, revenue_subcategory, gross_amount, gst_collected, net_amount,
                is_taxable, tax_province, client_id, charter_id, reserve_number,
                payment_method, payment_reference, description, created_by
            ) VALUES (
                %(payment_id)s, %(source_system)s, %(transaction_date)s, %(fiscal_year)s, %(fiscal_quarter)s,
                %(revenue_category)s, %(revenue_subcategory)s, %(gross_amount)s, %(gst_collected)s, %(net_amount)s,
                %(is_taxable)s, %(tax_province)s, %(client_id)s, %(charter_id)s, %(reserve_number)s,
                %(payment_method)s, %(payment_reference)s, %(description)s, %(created_by)s
            );
            """
            try:
                cur.execute(insert_sql, insert_dict)
                insert_count += 1
            except Exception as e:
                print(f"Error inserting payment {insert_dict['payment_id']}: {e}")
        
        conn.commit()
        print(f"✓ Inserted {insert_count} income_ledger records for 2012")
        
        # Verify
        cur.execute("SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) FROM income_ledger WHERE fiscal_year = 2012;")
        verify_count, verify_total = cur.fetchone()
        print(f"\nVERIFICATION:")
        print(f"  income_ledger 2012 rows: {verify_count}")
        print(f"  income_ledger 2012 total: ${float(verify_total):,.2f}")
    else:
        print(f"\n--- DRY RUN MODE ---")
        print(f"Would insert {len(inserts)} records totaling ${float(total_gross):,.2f}")
        print(f"To apply: Set DRY_RUN = False")
    
    print("\n" + "="*80)
    print("AFTER POPULATION, T2 EXTRACTION WILL:")
    print("="*80)
    print("""
1. Query income_ledger WHERE fiscal_year = 2012 AND is_taxable = true
2. SUM(gross_amount) for total revenue = $XXX,XXX.XX
3. SUM(gst_collected) for GST remitted = $XX,XXX.XX
4. Link audit via payment_id back to charter_payments
5. Run t2_deductibility_audit to compare against receipts GL codes
6. Generate T2 return with verified revenue and Schedule 1 add-backs
""")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
