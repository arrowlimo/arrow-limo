#!/usr/bin/env python3
"""
Create comprehensive income/revenue tracking ledger from payments table.
Categorizes income similar to QuickBooks with GST extraction and audit trails.

This script:
1. Analyzes all payments in the payments table
2. Categorizes revenue by service type (charter, retainer, misc)
3. Extracts GST collected (reverse calculation from gross amounts)
4. Creates income_ledger table with full audit trail
5. Links to original payment records for reconciliation
"""

import psycopg2
import argparse
from datetime import datetime
from decimal import Decimal

def get_db_connection():
    """Connect to PostgreSQL database."""
    return psycopg2.connect(
        dbname='almsdata',
        user='postgres',
        password='***REMOVED***',
        host='localhost'
    )

def analyze_payments_schema():
    """Analyze payments table schema and data."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("PAYMENTS TABLE ANALYSIS")
    print("="*80)
    
    # Schema
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'payments'
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    print(f"\nSchema: {len(columns)} columns")
    for col in columns[:15]:  # Show first 15
        print(f"  • {col[0]}: {col[1]} {'(nullable)' if col[2] == 'YES' else ''}")
    
    # Data summary
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            COUNT(DISTINCT client_id) as unique_clients,
            COUNT(DISTINCT charter_id) as unique_charters,
            MIN(payment_date) as first_payment,
            MAX(payment_date) as last_payment,
            SUM(amount) FILTER (WHERE amount > 0) as total_revenue,
            SUM(amount) FILTER (WHERE amount < 0) as total_refunds,
            COUNT(*) FILTER (WHERE amount > 0) as positive_payments,
            COUNT(*) FILTER (WHERE amount < 0) as negative_payments
        FROM payments
    """)
    summary = cur.fetchone()
    
    print(f"\nData Summary:")
    print(f"  • Total payments: {summary[0]:,}")
    print(f"  • Unique clients: {summary[1]:,}")
    print(f"  • Unique charters: {summary[2]:,}")
    print(f"  • Date range: {summary[3]} to {summary[4]}")
    print(f"  • Total revenue: ${summary[5]:,.2f}")
    print(f"  • Total refunds: ${summary[6]:,.2f}")
    print(f"  • Positive payments: {summary[7]:,}")
    print(f"  • Negative payments: {summary[8]:,}")
    
    # Payment methods
    cur.execute("""
        SELECT payment_method, COUNT(*), SUM(amount)
        FROM payments
        WHERE amount > 0
        GROUP BY payment_method
        ORDER BY SUM(amount) DESC
    """)
    methods = cur.fetchall()
    print(f"\nPayment Methods:")
    for method, count, total in methods[:10]:
        print(f"  • {method or 'NULL'}: {count:,} payments, ${total:,.2f}")
    
    cur.close()
    conn.close()
    
    return columns

def categorize_income(payment_method, charter_id, reserve_number, notes, amount):
    """
    Categorize income similar to QuickBooks chart of accounts.
    Returns (revenue_category, revenue_subcategory, is_taxable)
    """
    # Charter/limousine service revenue (taxable)
    if charter_id or reserve_number:
        return ('Operating Revenue', 'Charter Services', True)
    
    # Payment method-based categorization
    method = (payment_method or '').lower()
    notes_lower = (notes or '').lower()
    
    # Retainer/advance deposits
    if 'retainer' in notes_lower or 'deposit' in notes_lower:
        return ('Operating Revenue', 'Retainers & Deposits', True)
    
    # Credit card processing fees are expenses, not revenue
    if 'refund' in notes_lower:
        return ('Contra Revenue', 'Refunds & Adjustments', False)
    
    # Miscellaneous/other income
    if amount < 50:  # Small amounts likely misc
        return ('Other Revenue', 'Miscellaneous Income', False)
    
    # Default: charter services (most payments are charter-related)
    return ('Operating Revenue', 'Charter Services', True)

def calculate_gst_from_gross(gross_amount, province='AB'):
    """
    Extract GST from gross amount (GST is INCLUDED in payment amount).
    Alberta: 5% GST
    Formula: GST = gross × (0.05 / 1.05)
    """
    if gross_amount <= 0:
        return Decimal('0.00')
    
    gst_rate = Decimal('0.05')  # 5% for Alberta
    gst_amount = gross_amount * gst_rate / (Decimal('1.00') + gst_rate)
    return round(gst_amount, 2)

def create_income_ledger_table(dry_run=True):
    """Create the income_ledger table structure."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("CREATING INCOME LEDGER TABLE")
    print("="*80)
    
    create_sql = """
    CREATE TABLE IF NOT EXISTS income_ledger (
        income_id SERIAL PRIMARY KEY,
        
        -- Source tracking
        payment_id INTEGER REFERENCES payments(payment_id),
        source_system VARCHAR(50) DEFAULT 'payments',  -- 'payments', 'square', 'lms'
        
        -- Transaction details
        transaction_date DATE NOT NULL,
        fiscal_year INTEGER GENERATED ALWAYS AS (EXTRACT(YEAR FROM transaction_date)) STORED,
        fiscal_quarter INTEGER GENERATED ALWAYS AS (EXTRACT(QUARTER FROM transaction_date)) STORED,
        
        -- Revenue categorization (QuickBooks-style)
        revenue_category VARCHAR(100) NOT NULL,  -- 'Operating Revenue', 'Other Revenue', 'Contra Revenue'
        revenue_subcategory VARCHAR(100),  -- 'Charter Services', 'Retainers', 'Miscellaneous', etc.
        
        -- Amounts
        gross_amount DECIMAL(12,2) NOT NULL,  -- Total payment amount
        gst_collected DECIMAL(12,2) DEFAULT 0,  -- GST extracted from gross
        net_amount DECIMAL(12,2) GENERATED ALWAYS AS (gross_amount - gst_collected) STORED,
        
        -- Tax flags
        is_taxable BOOLEAN DEFAULT true,
        tax_province VARCHAR(2) DEFAULT 'AB',
        
        -- Client/charter linkage
        client_id INTEGER,
        charter_id INTEGER,
        reserve_number VARCHAR(50),
        
        -- Payment details
        payment_method VARCHAR(100),
        payment_reference VARCHAR(200),  -- Check#, Square ID, etc.
        
        -- Audit trail
        description TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by VARCHAR(100) DEFAULT 'create_income_ledger.py',
        
        -- Reconciliation
        reconciled BOOLEAN DEFAULT false,
        reconciled_date DATE,
        reconciled_by VARCHAR(100)
    );
    
    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_income_ledger_payment_id ON income_ledger(payment_id);
    CREATE INDEX IF NOT EXISTS idx_income_ledger_transaction_date ON income_ledger(transaction_date);
    CREATE INDEX IF NOT EXISTS idx_income_ledger_fiscal_year ON income_ledger(fiscal_year);
    CREATE INDEX IF NOT EXISTS idx_income_ledger_revenue_category ON income_ledger(revenue_category);
    CREATE INDEX IF NOT EXISTS idx_income_ledger_client_id ON income_ledger(client_id);
    CREATE INDEX IF NOT EXISTS idx_income_ledger_charter_id ON income_ledger(charter_id);
    
    -- Comments for documentation
    COMMENT ON TABLE income_ledger IS 'Revenue tracking ledger with QuickBooks-style categorization and GST extraction';
    COMMENT ON COLUMN income_ledger.gst_collected IS 'GST extracted from gross_amount using included-tax formula (AB: 5%)';
    COMMENT ON COLUMN income_ledger.revenue_category IS 'Top-level revenue classification: Operating Revenue, Other Revenue, Contra Revenue';
    COMMENT ON COLUMN income_ledger.revenue_subcategory IS 'Detailed revenue type: Charter Services, Retainers, Miscellaneous, etc.';
    """
    
    if dry_run:
        print("DRY-RUN: Would create income_ledger table with:")
        print("  • Transaction tracking with fiscal year/quarter")
        print("  • QuickBooks-style revenue categorization")
        print("  • GST extraction from gross amounts")
        print("  • Full audit trail and reconciliation flags")
        print("  • Links to payments, clients, charters")
    else:
        cur.execute(create_sql)
        conn.commit()
        print("[OK] income_ledger table created successfully")
    
    cur.close()
    conn.close()

def populate_income_ledger(year=None, dry_run=True):
    """
    Populate income_ledger from payments table.
    Categorizes revenue and extracts GST.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print(f"POPULATING INCOME LEDGER{' (DRY-RUN)' if dry_run else ''}")
    print("="*80)
    
    # Build query
    where_clauses = ["amount > 0"]  # Only positive payments (revenue)
    params = []
    
    if year:
        where_clauses.append("EXTRACT(YEAR FROM payment_date) = %s")
        params = [year]
    
    where_clause = "WHERE " + " AND ".join(where_clauses)
    
    query = f"""
        SELECT 
            payment_id, client_id, charter_id, reserve_number,
            payment_date, amount, payment_method,
            reference_number, notes,
            square_transaction_id
        FROM payments
        {where_clause}
        ORDER BY payment_date, payment_id
    """
    
    cur.execute(query, params)
    payments = cur.fetchall()
    
    print(f"\nFound {len(payments):,} payment records to process")
    
    if not payments:
        print("No payments found for specified criteria")
        cur.close()
        conn.close()
        return
    
    # Statistics
    stats = {
        'processed': 0,
        'inserted': 0,
        'skipped': 0,
        'total_revenue': Decimal('0.00'),
        'total_gst': Decimal('0.00'),
        'by_category': {},
    }
    
    for payment in payments:
        payment_id, client_id, charter_id, reserve_number, payment_date, amount, \
            payment_method, reference_number, notes, square_transaction_id = payment
        
        stats['processed'] += 1
        
        # Categorize revenue
        category, subcategory, is_taxable = categorize_income(
            payment_method, charter_id, reserve_number, notes, amount
        )
        
        # Calculate GST if taxable
        gst_collected = calculate_gst_from_gross(Decimal(str(amount))) if is_taxable else Decimal('0.00')
        
        # Build description
        description_parts = []
        if charter_id:
            description_parts.append(f"Charter #{charter_id}")
        if reserve_number:
            description_parts.append(f"Res #{reserve_number}")
        if payment_method:
            description_parts.append(payment_method)
        description = " - ".join(description_parts) or "Payment received"
        
        # Payment reference
        payment_ref = square_transaction_id or reference_number or f"PMT-{payment_id}"
        
        # Track stats
        stats['total_revenue'] += Decimal(str(amount))
        stats['total_gst'] += gst_collected
        cat_key = f"{category} > {subcategory}"
        if cat_key not in stats['by_category']:
            stats['by_category'][cat_key] = {'count': 0, 'amount': Decimal('0.00'), 'gst': Decimal('0.00')}
        stats['by_category'][cat_key]['count'] += 1
        stats['by_category'][cat_key]['amount'] += Decimal(str(amount))
        stats['by_category'][cat_key]['gst'] += gst_collected
        
        if not dry_run:
            # Insert into income_ledger
            try:
                cur.execute("""
                    INSERT INTO income_ledger (
                        payment_id, transaction_date, revenue_category, revenue_subcategory,
                        gross_amount, gst_collected, is_taxable, tax_province,
                        client_id, charter_id, reserve_number,
                        payment_method, payment_reference, description, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    payment_id, payment_date, category, subcategory,
                    amount, gst_collected, is_taxable, 'AB',
                    client_id, charter_id, reserve_number,
                    payment_method, payment_ref, description, notes
                ))
                if cur.rowcount > 0:
                    stats['inserted'] += 1
                else:
                    stats['skipped'] += 1
            except Exception as e:
                print(f"  [WARN]  Error inserting payment {payment_id}: {e}")
                stats['skipped'] += 1
    
    if not dry_run:
        conn.commit()
    
    # Print summary
    print(f"\n{'DRY-RUN ' if dry_run else ''}SUMMARY:")
    print(f"  Processed: {stats['processed']:,}")
    if not dry_run:
        print(f"  Inserted:  {stats['inserted']:,}")
        print(f"  Skipped:   {stats['skipped']:,}")
    print(f"\n  Total Revenue: ${stats['total_revenue']:,.2f}")
    print(f"  Total GST Collected: ${stats['total_gst']:,.2f}")
    print(f"  Net Revenue: ${stats['total_revenue'] - stats['total_gst']:,.2f}")
    
    print(f"\n  Revenue by Category:")
    for cat_key in sorted(stats['by_category'].keys()):
        cat = stats['by_category'][cat_key]
        print(f"    • {cat_key}:")
        print(f"        Count: {cat['count']:,}, Gross: ${cat['amount']:,.2f}, GST: ${cat['gst']:,.2f}, Net: ${cat['amount'] - cat['gst']:,.2f}")
    
    cur.close()
    conn.close()

def generate_revenue_reports(year=None):
    """Generate QuickBooks-style revenue reports."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print(f"REVENUE REPORTS{f' - {year}' if year else ' - ALL YEARS'}")
    print("="*80)
    
    where_clause = f"WHERE fiscal_year = {year}" if year else ""
    
    # Summary by category
    cur.execute(f"""
        SELECT 
            revenue_category,
            revenue_subcategory,
            COUNT(*) as transaction_count,
            SUM(gross_amount) as total_gross,
            SUM(gst_collected) as total_gst,
            SUM(net_amount) as total_net
        FROM income_ledger
        {where_clause}
        GROUP BY revenue_category, revenue_subcategory
        ORDER BY revenue_category, total_gross DESC
    """)
    
    print("\nRevenue by Category:")
    print(f"{'Category':<30} {'Subcategory':<30} {'Transactions':>12} {'Gross':>15} {'GST':>15} {'Net':>15}")
    print("-"*117)
    
    for row in cur.fetchall():
        cat, subcat, count, gross, gst, net = row
        print(f"{cat:<30} {subcat or '-':<30} {count:>12,} ${gross:>14,.2f} ${gst:>14,.2f} ${net:>14,.2f}")
    
    # Summary by fiscal year
    cur.execute(f"""
        SELECT 
            fiscal_year,
            COUNT(*) as transaction_count,
            SUM(gross_amount) as total_gross,
            SUM(gst_collected) as total_gst,
            SUM(net_amount) as total_net
        FROM income_ledger
        GROUP BY fiscal_year
        ORDER BY fiscal_year
    """)
    
    print("\n\nRevenue by Fiscal Year:")
    print(f"{'Year':<6} {'Transactions':>12} {'Gross Revenue':>18} {'GST Collected':>18} {'Net Revenue':>18}")
    print("-"*78)
    
    for row in cur.fetchall():
        yr, count, gross, gst, net = row
        print(f"{int(yr):<6} {count:>12,} ${gross:>17,.2f} ${gst:>17,.2f} ${net:>17,.2f}")
    
    cur.close()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description='Create and populate income ledger from payments')
    parser.add_argument('--analyze', action='store_true', help='Analyze payments table schema and data')
    parser.add_argument('--create-table', action='store_true', help='Create income_ledger table')
    parser.add_argument('--populate', action='store_true', help='Populate income_ledger from payments')
    parser.add_argument('--year', type=int, help='Process specific year only')
    parser.add_argument('--report', action='store_true', help='Generate revenue reports')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run)')
    parser.add_argument('--all', action='store_true', help='Run all steps: analyze, create, populate, report')
    
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    if args.all:
        analyze_payments_schema()
        create_income_ledger_table(dry_run=dry_run)
        populate_income_ledger(year=args.year, dry_run=dry_run)
        if not dry_run:
            generate_revenue_reports(year=args.year)
    else:
        if args.analyze:
            analyze_payments_schema()
        
        if args.create_table:
            create_income_ledger_table(dry_run=dry_run)
        
        if args.populate:
            populate_income_ledger(year=args.year, dry_run=dry_run)
        
        if args.report:
            generate_revenue_reports(year=args.year)

if __name__ == '__main__':
    main()
