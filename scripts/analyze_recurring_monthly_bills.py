#!/usr/bin/env python3
"""
Analyze recurring monthly bills from vendor_name_mapping.

Identifies and tracks recurring services:
- Telecommunications (Telus, Rogers, SaskTel, Bell, Shaw)
- Utilities (electricity, gas, water)
- Banking fees (CIBC, Scotia, TD, RBC)
- Insurance (vehicle, business, liability)
- Rent/Lease payments
- Other monthly services
"""

import psycopg2
import os
import sys
from datetime import datetime
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def save_progress(step_name, data, status='complete'):
    """Save progress for each analysis step."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_dir = 'l:\\limo\\data\\recurring_bills_analysis'
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'{timestamp}_{step_name}.txt')
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"Step: {step_name}\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Status: {status}\n")
        f.write("=" * 100 + "\n\n")
        f.write(data)
    
    print(f"✓ Progress saved: {log_file}")
    return log_file

def get_recurring_bill_vendors():
    """Get all vendors that appear to be recurring monthly services."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Known recurring service patterns
    recurring_patterns = [
        'TELUS', 'ROGERS', 'SASKTEL', 'BELL', 'SHAW', 'WIND',
        'UTILITIES', 'UTILITY', 'POWER', 'ELECTRIC', 'GAS', 'WATER',
        'BRANCH', 'CIBC', 'SCOTIABANK', 'TD', 'RBC', 'BMO',
        'INSURANCE', 'CMB', 'SGI', 'AVIVA', 'JEVCO',
        'RENT', 'LEASE', 'HEFFNER',
        'INTERNET', 'CABLE', 'PHONE'
    ]
    
    # Build WHERE clause more efficiently
    where_conditions = []
    for pattern in recurring_patterns:
        where_conditions.append(f"canonical_vendor_name ILIKE '%{pattern}%'")
    
    query = f"""
        SELECT 
            canonical_vendor_name,
            COUNT(DISTINCT raw_vendor_name) as variations,
            SUM(transaction_count) as total_txns,
            SUM(total_amount) as total_amount,
            STRING_AGG(DISTINCT source_systems::text, ', ') as sources
        FROM vendor_name_mapping
        WHERE {' OR '.join(where_conditions)}
        GROUP BY canonical_vendor_name
        ORDER BY total_amount DESC
    """
    
    cur.execute(query)
    results = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return results

def categorize_recurring_bills(vendors):
    """Categorize vendors into service types."""
    categories = {
        'telecommunications': [],
        'utilities': [],
        'banking_fees': [],
        'insurance': [],
        'rent_lease': [],
        'internet_cable': [],
        'other': []
    }
    
    for vendor, variations, txns, amount, sources in vendors:
        vendor_upper = vendor.upper()
        
        if any(x in vendor_upper for x in ['TELUS', 'ROGERS', 'SASKTEL', 'BELL', 'SHAW', 'WIND', 'PHONE']):
            categories['telecommunications'].append((vendor, variations, txns, amount, sources))
        elif any(x in vendor_upper for x in ['UTILITIES', 'UTILITY', 'POWER', 'ELECTRIC', 'GAS', 'WATER', 'ENMAX', 'EPCOR', 'ATCO']):
            categories['utilities'].append((vendor, variations, txns, amount, sources))
        elif any(x in vendor_upper for x in ['BRANCH', 'CIBC', 'SCOTIA', 'TD', 'RBC', 'BMO', 'FEE', 'SERVICE CHARGE']):
            categories['banking_fees'].append((vendor, variations, txns, amount, sources))
        elif any(x in vendor_upper for x in ['INSURANCE', 'CMB', 'SGI', 'AVIVA', 'JEVCO']):
            categories['insurance'].append((vendor, variations, txns, amount, sources))
        elif any(x in vendor_upper for x in ['RENT', 'LEASE', 'HEFFNER AUTO FC']):
            categories['rent_lease'].append((vendor, variations, txns, amount, sources))
        elif any(x in vendor_upper for x in ['INTERNET', 'CABLE']):
            categories['internet_cable'].append((vendor, variations, txns, amount, sources))
        else:
            categories['other'].append((vendor, variations, txns, amount, sources))
    
    return categories

def analyze_payment_patterns(vendor_name):
    """Analyze transaction frequency to confirm monthly pattern."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get transactions for this vendor from receipts
    cur.execute("""
        SELECT 
            DATE_TRUNC('month', receipt_date) as month,
            COUNT(*) as txn_count,
            SUM(gross_amount) as monthly_total
        FROM receipts
        WHERE vendor_name IN (
            SELECT raw_vendor_name 
            FROM vendor_name_mapping 
            WHERE canonical_vendor_name = %s
        )
        GROUP BY DATE_TRUNC('month', receipt_date)
        ORDER BY month DESC
        LIMIT 24
    """, (vendor_name,))
    
    receipt_pattern = cur.fetchall()
    
    # Get transactions from banking
    cur.execute("""
        SELECT 
            DATE_TRUNC('month', transaction_date) as month,
            COUNT(*) as txn_count,
            SUM(debit_amount) as monthly_total
        FROM banking_transactions
        WHERE COALESCE(vendor_extracted, description) IN (
            SELECT raw_vendor_name 
            FROM vendor_name_mapping 
            WHERE canonical_vendor_name = %s
        )
        AND debit_amount > 0
        GROUP BY DATE_TRUNC('month', transaction_date)
        ORDER BY month DESC
        LIMIT 24
    """, (vendor_name,))
    
    banking_pattern = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return receipt_pattern, banking_pattern

def print_category_report(category_name, vendors):
    """Print detailed report for a category."""
    if not vendors:
        return ""
    
    output = []
    output.append(f"\n{'=' * 100}")
    output.append(f"{category_name.upper().replace('_', ' ')}")
    output.append(f"{'=' * 100}")
    output.append(f"{'Vendor':<40} {'Variations':<12} {'Txns':<10} {'Total Amount':<20} {'Sources'}")
    output.append("-" * 100)
    
    total_amount = 0
    total_txns = 0
    
    for vendor, variations, txns, amount, sources in sorted(vendors, key=lambda x: x[3], reverse=True):
        sources_str = ', '.join(set([s for sublist in sources for s in (sublist if isinstance(sublist, list) else [sublist])]))
        output.append(f"{vendor:<40} {variations:<12} {txns:<10} ${amount:<19,.2f} {sources_str}")
        total_amount += amount
        total_txns += txns
    
    output.append("-" * 100)
    output.append(f"{'CATEGORY TOTAL':<40} {'':<12} {total_txns:<10} ${total_amount:<19,.2f}")
    output.append("")
    
    return "\n".join(output)

def create_recurring_bills_table(write=False):
    """Create a dedicated table for tracking recurring bills."""
    if not write:
        print("\nDRY RUN - Would create recurring_monthly_bills table")
        print("Run with --write to create the table")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\nCreating recurring_monthly_bills table...")
    
    # Drop existing
    cur.execute("DROP TABLE IF EXISTS recurring_monthly_bills CASCADE")
    
    # Create table
    cur.execute("""
        CREATE TABLE recurring_monthly_bills (
            id SERIAL PRIMARY KEY,
            vendor_canonical_name VARCHAR(200) NOT NULL,
            service_category VARCHAR(50) NOT NULL,
            expected_frequency VARCHAR(20) DEFAULT 'monthly',
            average_amount DECIMAL(12,2),
            last_payment_date DATE,
            last_payment_amount DECIMAL(12,2),
            account_number VARCHAR(100),
            auto_pay BOOLEAN DEFAULT false,
            notes TEXT,
            active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    cur.execute("CREATE INDEX idx_recurring_bills_vendor ON recurring_monthly_bills(vendor_canonical_name)")
    cur.execute("CREATE INDEX idx_recurring_bills_category ON recurring_monthly_bills(service_category)")
    cur.execute("CREATE INDEX idx_recurring_bills_active ON recurring_monthly_bills(active)")
    
    conn.commit()
    print("✓ Table created successfully")
    
    cur.close()
    conn.close()

def populate_recurring_bills_table(categories, write=False):
    """Populate recurring_monthly_bills table from analysis."""
    if not write:
        print("\nDRY RUN - Would populate recurring_monthly_bills table")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\nPopulating recurring_monthly_bills table...")
    
    inserted = 0
    for category_name, vendors in categories.items():
        for vendor, variations, txns, amount, sources in vendors:
            # Calculate average monthly amount
            avg_amount = amount / max(txns, 1)
            
            cur.execute("""
                INSERT INTO recurring_monthly_bills 
                (vendor_canonical_name, service_category, average_amount, notes)
                VALUES (%s, %s, %s, %s)
            """, (
                vendor,
                category_name,
                round(avg_amount, 2),
                f"{variations} name variations, {txns} transactions"
            ))
            inserted += 1
    
    conn.commit()
    print(f"✓ Inserted {inserted} recurring bill vendors")
    
    cur.close()
    conn.close()

def main():
    write_mode = '--write' in sys.argv
    
    print("=" * 100)
    print("RECURRING MONTHLY BILLS ANALYSIS")
    print("=" * 100)
    
    # Step 1: Get recurring bill vendors
    print("\nStep 1: Identifying recurring bill vendors...")
    vendors = get_recurring_bill_vendors()
    print(f"Found {len(vendors)} potential recurring bill vendors")
    
    step1_data = f"Found {len(vendors)} vendors\n"
    step1_data += "\n".join([f"{v[0]}: {v[2]} txns, ${v[3]:,.2f}" for v in vendors[:20]])
    save_progress('step1_identify_vendors', step1_data)
    
    # Step 2: Categorize by service type
    print("\nStep 2: Categorizing by service type...")
    categories = categorize_recurring_bills(vendors)
    
    step2_data = ""
    for cat_name, cat_vendors in categories.items():
        if cat_vendors:
            step2_data += f"\n{cat_name}: {len(cat_vendors)} vendors\n"
    save_progress('step2_categorize', step2_data)
    
    # Step 3: Generate detailed reports
    print("\nStep 3: Generating category reports...")
    
    full_report = ""
    full_report += f"\nRECURRING MONTHLY BILLS SUMMARY\n"
    full_report += f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    for category_name, cat_vendors in categories.items():
        report = print_category_report(category_name, cat_vendors)
        full_report += report
        print(report)
    
    save_progress('step3_detailed_report', full_report)
    
    # Step 4: Create tracking table
    print("\nStep 4: Create recurring bills tracking table...")
    create_recurring_bills_table(write=write_mode)
    
    if write_mode:
        save_progress('step4_create_table', 'Table created successfully')
    
    # Step 5: Populate table
    print("\nStep 5: Populate recurring bills table...")
    populate_recurring_bills_table(categories, write=write_mode)
    
    if write_mode:
        save_progress('step5_populate_table', 'Table populated successfully')
    
    print("\n" + "=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)
    print(f"\nAll progress saved to: l:\\limo\\data\\recurring_bills_analysis\\")

if __name__ == '__main__':
    main()
