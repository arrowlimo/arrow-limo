#!/usr/bin/env python3
"""
Add missing bank accounts to chart_of_accounts and create category mapping table.
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("="*80)
    print("ADDING MISSING ACCOUNTS & CATEGORY MAPPINGS")
    print("="*80)
    
    # 1. Add merchant processing account (3648117)
    print("\n1. Adding CIBC Merchant Processing (3648117)")
    print("-"*80)
    
    cur.execute("""
        INSERT INTO chart_of_accounts (
            account_code, parent_account, account_name, account_type,
            description, qb_account_type, account_level, is_header_account,
            normal_balance, bank_account_number, is_active
        ) VALUES (
            '1013', '1010', 'CIBC Merchant Processing 3648117', 'Asset',
            'Credit card merchant deposits - Square/Moneris batch settlements',
            'Bank', 2, false, 'DEBIT', '3648117', true
        )
        ON CONFLICT (account_code) DO UPDATE SET
            bank_account_number = EXCLUDED.bank_account_number,
            description = EXCLUDED.description,
            updated_at = CURRENT_TIMESTAMP
        RETURNING account_code, account_name
    """)
    
    result = cur.fetchone()
    if result:
        print(f"  ✓ Added/Updated: {result[0]} - {result[1]}")
    
    # 2. Add vehicle loans (8314462) as liability
    print("\n2. Adding Vehicle Loans Payable (8314462)")
    print("-"*80)
    
    cur.execute("""
        INSERT INTO chart_of_accounts (
            account_code, parent_account, account_name, account_type,
            description, qb_account_type, account_level, is_header_account,
            normal_balance, bank_account_number, is_active
        ) VALUES (
            '2210', '2200', 'Vehicle Loans Payable', 'Liability',
            'Vehicle financing and equipment loans - CIBC account 8314462',
            'LongTermLiability', 2, false, 'CREDIT', '8314462', true
        )
        ON CONFLICT (account_code) DO UPDATE SET
            bank_account_number = EXCLUDED.bank_account_number,
            description = EXCLUDED.description,
            updated_at = CURRENT_TIMESTAMP
        RETURNING account_code, account_name
    """)
    
    result = cur.fetchone()
    if result:
        print(f"  ✓ Added/Updated: {result[0]} - {result[1]}")
    
    # 3. Create category mapping table
    print("\n3. Creating category_to_account_map table")
    print("-"*80)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS category_to_account_map (
            mapping_id SERIAL PRIMARY KEY,
            category_code VARCHAR(50) NOT NULL,
            gl_account_code VARCHAR(20) NOT NULL,
            priority INTEGER DEFAULT 1,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gl_account_code) REFERENCES chart_of_accounts(account_code),
            UNIQUE (category_code, gl_account_code)
        )
    """)
    
    print("  ✓ Table created")
    
    # 4. Insert category mappings
    print("\n4. Inserting category → GL account mappings")
    print("-"*80)
    
    mappings = [
        ('FUEL', '5110', 1, 'Vehicle fuel expenses'),
        ('VEHICLE_RM', '5120', 1, 'Vehicle maintenance and repairs'),
        ('OFFICE_SUPPLIES', '5420', 1, 'Office supplies and stationery'),
        ('INTERNET', '5430', 1, 'Internet service'),
        ('TELEPHONE', '5430', 1, 'Telephone and mobile service'),
        ('MEALS_ENTERTAINMENT', '5325', 1, 'Business meals (50% deductible)'),
        ('INSURANCE', '5130', 1, 'Vehicle insurance'),
        ('INSURANCE', '5330', 2, 'Property/liability insurance'),
        ('BANK_CHARGES', '5710', 1, 'Bank fees and service charges'),
        ('CC_CHARGES', '5720', 1, 'Credit card processing fees'),
        ('ADVERTISING', '5610', 1, 'Advertising expenses'),
        ('PROFESSIONAL_FEES', '5510', 1, 'Legal and accounting fees'),
        ('RENT', '5410', 1, 'Office rent'),
        ('UTILITIES', '5440', 1, 'Electricity, water, gas'),
        ('UNIFORMS', '5830', 1, 'Driver uniforms'),
        ('LICENSES_PERMITS', '5140', 1, 'Vehicle licenses and permits'),
        ('EMPLOYEE_WAGES', '5210', 1, 'Driver and employee wages'),
        ('PAYROLL_EXP', '5230', 1, 'CPP, EI, WCB'),
        ('GRATUITY_INCOME', '4110', 1, 'Driver gratuities'),
        ('FUEL_SURCHARGE', '4120', 1, 'Fuel surcharge income'),
        ('LIMO_INCOME', '4010', 1, 'Charter service revenue'),
    ]
    
    inserted = 0
    for cat_code, gl_code, priority, notes in mappings:
        cur.execute("""
            INSERT INTO category_to_account_map (
                category_code, gl_account_code, priority, notes
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (category_code, gl_account_code) DO NOTHING
        """, (cat_code, gl_code, priority, notes))
        
        if cur.rowcount > 0:
            inserted += 1
    
    print(f"  ✓ Inserted {inserted} new mappings")
    
    # 5. Add gl_account_code column to account_categories
    print("\n5. Enhancing account_categories table")
    print("-"*80)
    
    cur.execute("""
        ALTER TABLE account_categories 
        ADD COLUMN IF NOT EXISTS gl_account_code VARCHAR(20)
    """)
    
    cur.execute("""
        ALTER TABLE account_categories 
        ADD COLUMN IF NOT EXISTS gl_account_code_alt VARCHAR(20)
    """)
    
    print("  ✓ Added gl_account_code columns")
    
    # 6. Update account_categories with GL codes
    print("\n6. Mapping categories to GL accounts")
    print("-"*80)
    
    cur.execute("""
        UPDATE account_categories ac
        SET gl_account_code = ctam.gl_account_code
        FROM category_to_account_map ctam
        WHERE ac.category_code = ctam.category_code
        AND ctam.priority = 1
    """)
    
    updated = cur.rowcount
    print(f"  ✓ Updated {updated} category mappings")
    
    conn.commit()
    
    # 7. Verification
    print("\n7. VERIFICATION")
    print("="*80)
    
    cur.execute("""
        SELECT account_code, account_name, bank_account_number
        FROM chart_of_accounts
        WHERE account_code IN ('1013', '2210')
    """)
    
    print("\nNew accounts in chart_of_accounts:")
    for code, name, bank_num in cur.fetchall():
        print(f"  • {code} - {name} ({bank_num})")
    
    cur.execute("SELECT COUNT(*) FROM category_to_account_map")
    map_count = cur.fetchone()[0]
    print(f"\nCategory mappings: {map_count}")
    
    cur.execute("""
        SELECT category_code, gl_account_code, notes
        FROM category_to_account_map
        ORDER BY category_code
        LIMIT 10
    """)
    
    print("\nSample mappings:")
    for cat, gl, notes in cur.fetchall():
        print(f"  {cat:<25} → {gl:<10} ({notes})")
    
    print("\n✓ All updates complete!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
