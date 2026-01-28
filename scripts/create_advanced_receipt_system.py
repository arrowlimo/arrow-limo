#!/usr/bin/env python3
"""
Create advanced receipt categorization system with:
- Receipt line items (split receipts)
- Default vendor categorizations
- Personal vs business purchases
- Driver reimbursements
- Cash box tracking for driver floats
"""

import psycopg2
import os
import sys
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def save_progress(step_name, data):
    """Save progress for each step."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_dir = 'l:\\limo\\data\\receipt_system_setup'
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'{timestamp}_{step_name}.txt')
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"Step: {step_name}\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write("=" * 100 + "\n\n")
        f.write(data)
    
    print(f"✓ Progress saved: {log_file}")

def create_receipt_line_items_table(cur):
    """Create table for split receipts - multiple line items per receipt."""
    print("\n1. Creating receipt_line_items table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receipt_line_items (
            line_item_id SERIAL PRIMARY KEY,
            receipt_id INTEGER REFERENCES receipts(receipt_id) ON DELETE CASCADE,
            line_number INTEGER NOT NULL,
            item_description TEXT,
            category VARCHAR(100) NOT NULL,
            subcategory VARCHAR(100),
            quantity DECIMAL(10,2) DEFAULT 1,
            unit_price DECIMAL(12,2),
            line_amount DECIMAL(12,2) NOT NULL,
            gst_amount DECIMAL(12,2) DEFAULT 0,
            is_personal BOOLEAN DEFAULT false,
            is_driver_reimbursable BOOLEAN DEFAULT false,
            employee_id INTEGER REFERENCES employees(employee_id),
            vehicle_id INTEGER REFERENCES vehicles(vehicle_id),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_receipt_line UNIQUE (receipt_id, line_number)
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_line_items_receipt ON receipt_line_items(receipt_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_line_items_category ON receipt_line_items(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_line_items_employee ON receipt_line_items(employee_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_line_items_vehicle ON receipt_line_items(vehicle_id)")
    
    print("  ✓ receipt_line_items table created")
    
    data = """
    receipt_line_items table created with columns:
    - line_item_id: Primary key
    - receipt_id: Links to receipts table
    - line_number: Order on receipt
    - item_description: What was purchased
    - category: fuel, meals, beverages, supplies, personal, etc.
    - subcategory: More specific (premium_fuel, driver_meal, customer_water, etc.)
    - quantity, unit_price, line_amount: Item details
    - is_personal: Owner personal purchases
    - is_driver_reimbursable: Driver paid, company reimburses
    - employee_id, vehicle_id: Links for tracking
    """
    save_progress('step1_line_items_table', data)

def create_vendor_default_categories(cur):
    """Create vendor default categorization rules."""
    print("\n2. Creating vendor_default_categories table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vendor_default_categories (
            id SERIAL PRIMARY KEY,
            vendor_canonical_name VARCHAR(200) NOT NULL,
            default_category VARCHAR(100) NOT NULL,
            default_subcategory VARCHAR(100),
            allows_splits BOOLEAN DEFAULT true,
            common_split_categories TEXT[],
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_vendor_category UNIQUE (vendor_canonical_name)
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_vendor_categories ON vendor_default_categories(vendor_canonical_name)")
    
    print("  ✓ vendor_default_categories table created")
    
    data = """
    vendor_default_categories table created with columns:
    - vendor_canonical_name: Links to vendor_name_mapping
    - default_category: Primary category (fuel, meals, beverages, supplies)
    - default_subcategory: More specific classification
    - allows_splits: Can receipt have multiple categories
    - common_split_categories: Array of typical splits for this vendor
    - notes: Special instructions
    """
    save_progress('step2_vendor_categories', data)

def create_cash_box_table(cur):
    """Create cash box tracking for driver floats and reimbursements."""
    print("\n3. Creating cash_box_transactions table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cash_box_transactions (
            transaction_id SERIAL PRIMARY KEY,
            transaction_date DATE NOT NULL,
            transaction_type VARCHAR(50) NOT NULL,
            amount DECIMAL(12,2) NOT NULL,
            banking_transaction_id INTEGER REFERENCES banking_transactions(transaction_id),
            receipt_id INTEGER REFERENCES receipts(receipt_id),
            employee_id INTEGER REFERENCES employees(employee_id),
            description TEXT,
            balance_after DECIMAL(12,2),
            created_by VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            CHECK (transaction_type IN (
                'withdrawal_from_bank', 
                'driver_float_issued', 
                'driver_reimbursement',
                'customer_change',
                'deposit_to_bank',
                'adjustment'
            ))
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cashbox_date ON cash_box_transactions(transaction_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cashbox_type ON cash_box_transactions(transaction_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cashbox_employee ON cash_box_transactions(employee_id)")
    
    print("  ✓ cash_box_transactions table created")
    
    data = """
    cash_box_transactions table created with transaction types:
    - withdrawal_from_bank: ATM/bank withdrawal to replenish cash box
    - driver_float_issued: Cash given to driver for fuel/expenses
    - driver_reimbursement: Reimburse driver for out-of-pocket purchase
    - customer_change: Cash tips/change from customers
    - deposit_to_bank: Excess cash deposited back to bank
    - adjustment: Corrections and reconciliation
    
    Flow:
    1. ATM withdrawal ($500) → cash_box
    2. Driver float issued ($200) → driver has cash
    3. Driver spends on fuel/meals → receipts marked is_driver_reimbursable
    4. Driver reimbursement ($150) → cash paid back from cash_box
    """
    save_progress('step3_cash_box_table', data)

def create_driver_floats_table(cur):
    """Create table tracking active driver floats."""
    print("\n4. Creating driver_floats table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS driver_floats (
            float_id SERIAL PRIMARY KEY,
            employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
            issued_date DATE NOT NULL,
            issued_amount DECIMAL(12,2) NOT NULL,
            returned_date DATE,
            returned_amount DECIMAL(12,2),
            spent_amount DECIMAL(12,2) DEFAULT 0,
            outstanding_balance DECIMAL(12,2),
            status VARCHAR(20) DEFAULT 'active',
            cash_box_transaction_id INTEGER REFERENCES cash_box_transactions(transaction_id),
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CHECK (status IN ('active', 'returned', 'reconciled', 'written_off'))
        )
    """)
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_floats_employee ON driver_floats(employee_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_floats_status ON driver_floats(status)")
    
    print("  ✓ driver_floats table created")
    
    data = """
    driver_floats table tracks active cash floats:
    - employee_id: Which driver has the float
    - issued_date, issued_amount: When/how much given
    - returned_date, returned_amount: When/how much came back
    - spent_amount: Total receipts submitted
    - outstanding_balance: issued - returned - spent
    - status: active (still out), returned (cash back), reconciled (settled), written_off
    
    Example:
    - Issue $200 float to driver
    - Driver submits $150 in fuel receipts
    - Driver returns $50 cash
    - Float reconciled: $200 = $150 (spent) + $50 (returned)
    """
    save_progress('step4_driver_floats', data)

def populate_vendor_categories(cur):
    """Populate default vendor categories based on business knowledge."""
    print("\n5. Populating vendor default categories...")
    
    vendor_rules = [
        # Fuel stations - mostly fuel, sometimes meals/beverages
        ('FAS GAS', 'fuel', 'vehicle_fuel', True, ['fuel', 'driver_meal', 'customer_beverages']),
        ('CENTEX', 'fuel', 'vehicle_fuel', True, ['fuel', 'driver_meal', 'customer_beverages']),
        ('ESSO', 'fuel', 'vehicle_fuel', True, ['fuel', 'driver_meal', 'customer_beverages']),
        ('SHELL', 'fuel', 'vehicle_fuel', True, ['fuel', 'driver_meal', 'customer_beverages']),
        ('PETRO', 'fuel', 'vehicle_fuel', True, ['fuel', 'driver_meal', 'customer_beverages']),
        ('HUSKY', 'fuel', 'vehicle_fuel', True, ['fuel', 'driver_meal', 'customer_beverages']),
        ('CO-OP', 'fuel', 'vehicle_fuel', True, ['fuel', 'driver_meal', 'customer_beverages']),
        
        # Canadian Tire - fuel or supplies
        ('CANADIAN TIRE', 'supplies', 'vehicle_supplies', True, ['fuel', 'vehicle_maintenance', 'supplies']),
        
        # Liquor stores - customer beverages
        ('DD LIQUOR', 'customer_supplies', 'customer_beverages', True, ['customer_beverages', 'personal']),
        ('LIQUOR', 'customer_supplies', 'customer_beverages', True, ['customer_beverages', 'personal']),
        
        # Grocery stores - customer supplies or personal
        ('SOBEYS', 'customer_supplies', 'customer_beverages', True, ['customer_beverages', 'customer_snacks', 'personal']),
        ('SAFEWAY', 'customer_supplies', 'customer_beverages', True, ['customer_beverages', 'customer_snacks', 'personal']),
        ('WALMART', 'customer_supplies', 'customer_beverages', True, ['customer_beverages', 'customer_snacks', 'supplies', 'personal']),
        
        # Restaurants - driver meals
        ('TIM HORTONS', 'meals', 'driver_meal', False, ['driver_meal']),
        ('MCDONALDS', 'meals', 'driver_meal', False, ['driver_meal']),
        ('SUBWAY', 'meals', 'driver_meal', False, ['driver_meal']),
        ('A&W', 'meals', 'driver_meal', False, ['driver_meal']),
        
        # Office/business supplies
        ('STAPLES', 'office_supplies', 'office_general', True, ['office_supplies', 'personal']),
        
        # Vehicle maintenance
        ('MIDAS', 'vehicle_maintenance', 'vehicle_repair', False, ['vehicle_maintenance']),
        ('JIFFY LUBE', 'vehicle_maintenance', 'vehicle_service', False, ['vehicle_maintenance']),
        
        # Insurance/banking - pure business
        ('HEFFNER AUTO', 'vehicle_lease', 'vehicle_lease', False, ['vehicle_lease']),
        ('CMB INSURANCE', 'insurance', 'vehicle_insurance', False, ['insurance']),
        ('TELUS', 'communication', 'phone_internet', False, ['communication']),
        ('ROGERS', 'communication', 'phone_internet', False, ['communication']),
    ]
    
    inserted = 0
    for vendor, category, subcategory, splits, split_cats in vendor_rules:
        cur.execute("""
            INSERT INTO vendor_default_categories 
            (vendor_canonical_name, default_category, default_subcategory, 
             allows_splits, common_split_categories)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (vendor_canonical_name) DO UPDATE SET
                default_category = EXCLUDED.default_category,
                default_subcategory = EXCLUDED.default_subcategory,
                allows_splits = EXCLUDED.allows_splits,
                common_split_categories = EXCLUDED.common_split_categories,
                updated_at = CURRENT_TIMESTAMP
        """, (vendor, category, subcategory, splits, split_cats))
        inserted += 1
    
    print(f"  ✓ Populated {inserted} vendor category rules")
    
    data = f"""
    Populated {inserted} vendor default categories:
    
    FUEL STATIONS (7 vendors):
    - FAS GAS, CENTEX, ESSO, SHELL, PETRO, HUSKY, CO-OP
    - Default: vehicle_fuel
    - Splits allowed: fuel, driver_meal, customer_beverages
    
    CONVENIENCE/GROCERY (5 vendors):
    - CANADIAN TIRE, SOBEYS, SAFEWAY, WALMART, LIQUOR STORES
    - Default: customer_supplies or supplies
    - Splits allowed: beverages, snacks, personal
    
    RESTAURANTS (4 vendors):
    - TIM HORTONS, MCDONALDS, SUBWAY, A&W
    - Default: driver_meal
    - No splits (single category)
    
    BUSINESS SERVICES (5 vendors):
    - HEFFNER AUTO, CMB INSURANCE, TELUS, ROGERS, STAPLES
    - Pure business categories
    """
    save_progress('step5_vendor_categories_populated', data)

def add_columns_to_receipts(cur):
    """Add new columns to existing receipts table."""
    print("\n6. Adding columns to receipts table...")
    
    # Check and add columns
    columns_to_add = [
        ("is_split_receipt", "BOOLEAN DEFAULT false"),
        ("is_personal_purchase", "BOOLEAN DEFAULT false"),
        ("owner_personal_amount", "DECIMAL(12,2) DEFAULT 0"),
        ("is_driver_reimbursement", "BOOLEAN DEFAULT false"),
        ("reimbursed_via", "VARCHAR(50)"),  # 'etransfer', 'cash', 'payroll'
        ("reimbursement_date", "DATE"),
        ("cash_box_transaction_id", "INTEGER REFERENCES cash_box_transactions(transaction_id)"),
    ]
    
    added = 0
    for col_name, col_def in columns_to_add:
        try:
            cur.execute(f"ALTER TABLE receipts ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
            added += 1
        except Exception as e:
            print(f"  Column {col_name} might already exist: {e}")
    
    print(f"  ✓ Added {added} columns to receipts table")
    
    data = f"""
    Added {added} columns to receipts table:
    - is_split_receipt: Receipt has multiple line items
    - is_personal_purchase: Owner personal purchase (non-deductible)
    - owner_personal_amount: Amount that's personal
    - is_driver_reimbursement: Driver paid, needs reimbursement
    - reimbursed_via: How reimbursed (etransfer/cash/payroll)
    - reimbursement_date: When reimbursed
    - cash_box_transaction_id: Links to cash_box if paid in cash
    """
    save_progress('step6_receipts_columns', data)

def create_category_reference(cur):
    """Create reference table for valid categories."""
    print("\n7. Creating receipt_categories reference table...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receipt_categories (
            category_id SERIAL PRIMARY KEY,
            category_code VARCHAR(100) UNIQUE NOT NULL,
            category_name VARCHAR(200) NOT NULL,
            is_tax_deductible BOOLEAN DEFAULT true,
            requires_vehicle BOOLEAN DEFAULT false,
            requires_employee BOOLEAN DEFAULT false,
            parent_category VARCHAR(100),
            display_order INTEGER,
            notes TEXT
        )
    """)
    
    categories = [
        ('fuel', 'Vehicle Fuel', True, True, False, None, 1),
        ('vehicle_maintenance', 'Vehicle Maintenance', True, True, False, None, 2),
        ('vehicle_supplies', 'Vehicle Supplies', True, True, False, None, 3),
        ('driver_meal', 'Driver Meals', True, False, True, 'meals', 10),
        ('customer_beverages', 'Customer Beverages', True, False, False, 'customer_supplies', 20),
        ('customer_snacks', 'Customer Snacks', True, False, False, 'customer_supplies', 21),
        ('customer_supplies', 'Customer Supplies (General)', True, False, False, None, 22),
        ('office_supplies', 'Office Supplies', True, False, False, None, 30),
        ('communication', 'Phone/Internet', True, False, False, None, 40),
        ('insurance', 'Insurance', True, False, False, None, 50),
        ('vehicle_lease', 'Vehicle Lease/Financing', True, True, False, None, 51),
        ('banking_fees', 'Banking Fees', True, False, False, None, 60),
        ('personal', 'Personal (Non-deductible)', False, False, False, None, 90),
    ]
    
    for cat_code, cat_name, deductible, req_vehicle, req_employee, parent, order in categories:
        cur.execute("""
            INSERT INTO receipt_categories 
            (category_code, category_name, is_tax_deductible, 
             requires_vehicle, requires_employee, parent_category, display_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (category_code) DO UPDATE SET
                category_name = EXCLUDED.category_name,
                is_tax_deductible = EXCLUDED.is_tax_deductible,
                requires_vehicle = EXCLUDED.requires_vehicle,
                requires_employee = EXCLUDED.requires_employee,
                parent_category = EXCLUDED.parent_category,
                display_order = EXCLUDED.display_order
        """, (cat_code, cat_name, deductible, req_vehicle, req_employee, parent, order))
    
    print(f"  ✓ Created {len(categories)} category definitions")
    
    data = f"""
    Created {len(categories)} receipt categories:
    
    TAX DEDUCTIBLE:
    1. fuel - Vehicle Fuel (requires vehicle_id)
    2. vehicle_maintenance - Repairs/service (requires vehicle_id)
    3. vehicle_supplies - Parts/supplies (requires vehicle_id)
    10. driver_meal - Driver meals (requires employee_id)
    20-22. customer_supplies - Beverages, snacks for customers
    30. office_supplies - Office items
    40. communication - Phone/internet
    50-51. insurance/vehicle_lease
    60. banking_fees
    
    NON-DEDUCTIBLE:
    90. personal - Owner personal purchases
    
    Categories requiring tracking:
    - Vehicle categories → vehicle_id mandatory
    - Driver meals → employee_id mandatory
    """
    save_progress('step7_categories_created', data)

def main():
    write_mode = '--write' in sys.argv
    
    if not write_mode:
        print("\n" + "=" * 100)
        print("DRY RUN - Preview of advanced receipt system")
        print("=" * 100)
        print("\nThis will create:")
        print("  1. receipt_line_items - Split receipts into multiple categories")
        print("  2. vendor_default_categories - Auto-categorization rules")
        print("  3. cash_box_transactions - Track cash withdrawals and reimbursements")
        print("  4. driver_floats - Track driver float balances")
        print("  5. receipt_categories - Valid category definitions")
        print("  6. Add columns to receipts - is_split, is_personal, reimbursement tracking")
        print("\nRun with --write to create tables")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 100)
    print("CREATING ADVANCED RECEIPT SYSTEM")
    print("=" * 100)
    
    try:
        create_receipt_line_items_table(cur)
        create_vendor_default_categories(cur)
        create_cash_box_table(cur)
        create_driver_floats_table(cur)
        add_columns_to_receipts(cur)
        create_category_reference(cur)
        populate_vendor_categories(cur)
        
        conn.commit()
        
        print("\n" + "=" * 100)
        print("SYSTEM CREATION COMPLETE")
        print("=" * 100)
        print("\nAll tables created successfully!")
        print("Progress saved to: l:\\limo\\data\\receipt_system_setup\\")
        
        summary = """
        ADVANCED RECEIPT SYSTEM CREATED
        
        Tables:
        ✓ receipt_line_items - Split receipts
        ✓ vendor_default_categories - Auto-categorization (25 vendors configured)
        ✓ cash_box_transactions - Cash tracking
        ✓ driver_floats - Float management
        ✓ receipt_categories - 13 category definitions
        ✓ receipts - Enhanced with split/personal/reimbursement columns
        
        Capabilities:
        ✓ Split single receipt into multiple categories (fuel + meals + beverages)
        ✓ Track personal vs business portions
        ✓ Driver reimbursements (cash or e-transfer)
        ✓ Cash box for driver floats
        ✓ Auto-categorize by vendor with override capability
        ✓ Vehicle/employee tracking where required
        ✓ Tax deductible vs non-deductible classification
        """
        save_progress('FINAL_SUMMARY', summary)
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
