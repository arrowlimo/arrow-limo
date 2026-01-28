#!/usr/bin/env python3
"""
COMPREHENSIVE CHARGE MATCHING SYSTEM
====================================

Uses LMS rate mapping and charter_charges data to create a complete
extra charge matching and categorization system.
"""

import os
import psycopg2
from datetime import datetime
import argparse

# Database connection
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REMOVED***')

def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_charge_integration():
    """Analyze how charter_charges and LMS rate mapping can be integrated."""
    
    print("🔍 CHARGE INTEGRATION ANALYSIS")
    print("=" * 31)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Compare LMS rate mapping descriptions with charter_charges descriptions
    cur.execute("""
        SELECT 
            lrm.charge_description as lms_description,
            lrm.charge_category as lms_category,
            COUNT(cc.charge_id) as matching_charges,
            ROUND(AVG(cc.amount), 2) as avg_amount,
            ROUND(SUM(cc.amount), 2) as total_amount
        FROM lms_rate_mapping lrm
        LEFT JOIN charter_charges cc ON LOWER(cc.description) = LOWER(lrm.charge_description)
        WHERE cc.amount IS NOT NULL AND cc.amount != 0
        GROUP BY lrm.charge_description, lrm.charge_category
        ORDER BY matching_charges DESC, total_amount DESC
    """)
    
    matches = cur.fetchall()
    
    print("📊 LMS MAPPING → CHARTER CHARGES MATCHES:")
    print(f"{'LMS Description':<25} {'Category':<15} {'Matches':<8} {'Avg $':<8} {'Total $':<12}")
    print("-" * 80)
    
    total_matched = 0
    total_amount = 0
    
    for lms_desc, category, match_count, avg_amt, sum_amt in matches:
        if match_count > 0:
            total_matched += match_count
            total_amount += sum_amt or 0
            
            desc_short = (lms_desc[:22] + '...') if len(lms_desc) > 22 else lms_desc
            cat_short = (category[:12] + '...') if len(category) > 12 else category
            avg_str = f"${avg_amt:.2f}" if avg_amt else "N/A"
            sum_str = f"${sum_amt:,.2f}" if sum_amt else "N/A"
            
            print(f"{desc_short:<25} {cat_short:<15} {match_count:<8} {avg_str:<8} {sum_str:<12}")
    
    print(f"\n📊 SUMMARY: {total_matched:,} charges matched, ${total_amount:,.2f} total value")
    
    # Find unmatched charter charges that could be standardized
    cur.execute("""
        SELECT description, COUNT(*) as frequency, 
               ROUND(AVG(amount), 2) as avg_amount,
               ROUND(SUM(amount), 2) as total_amount
        FROM charter_charges 
        WHERE charge_type = 'other' 
        AND amount IS NOT NULL AND amount != 0
        AND description NOT IN (
            SELECT charge_description FROM lms_rate_mapping
        )
        GROUP BY description
        HAVING COUNT(*) >= 10  -- Only show frequent charges
        ORDER BY frequency DESC, total_amount DESC
        LIMIT 15
    """)
    
    unmatched = cur.fetchall()
    
    print(f"\n🔍 UNMATCHED FREQUENT CHARGES:")
    print(f"{'Description':<30} {'Freq':<6} {'Avg $':<8} {'Total $':<12}")
    print("-" * 65)
    
    for desc, freq, avg_amt, total_amt in unmatched:
        desc_short = (desc[:27] + '...') if len(desc) > 27 else desc
        avg_str = f"${avg_amt:.2f}" if avg_amt else "N/A"
        total_str = f"${total_amt:,.2f}" if total_amt else "N/A"
        print(f"{desc_short:<30} {freq:<6} {avg_str:<8} {total_str:<12}")
    
    cur.close()
    conn.close()

def create_unified_charge_lookup():
    """Create a unified charge lookup that combines LMS and existing data."""
    
    print(f"\n🔧 CREATING UNIFIED CHARGE LOOKUP")
    print("-" * 33)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Create unified lookup table
        cur.execute("""
            DROP TABLE IF EXISTS unified_charge_lookup CASCADE;
            CREATE TABLE unified_charge_lookup (
                lookup_id SERIAL PRIMARY KEY,
                charge_code VARCHAR(50) UNIQUE NOT NULL,
                standard_description VARCHAR(200) NOT NULL,
                category VARCHAR(100) NOT NULL,
                
                -- Statistics from actual usage
                usage_frequency INTEGER DEFAULT 0,
                avg_amount DECIMAL(10,2),
                min_amount DECIMAL(10,2), 
                max_amount DECIMAL(10,2),
                total_amount DECIMAL(15,2),
                
                -- Matching patterns
                search_patterns TEXT[],
                alternative_descriptions TEXT[],
                
                -- Business rules
                is_taxable BOOLEAN DEFAULT true,
                is_active BOOLEAN DEFAULT true,
                
                -- Source tracking
                lms_source BOOLEAN DEFAULT false,
                charter_charges_source BOOLEAN DEFAULT false,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("   [OK] Created unified_charge_lookup table")
        
        # Populate from LMS rate mapping
        cur.execute("""
            INSERT INTO unified_charge_lookup (
                charge_code, standard_description, category, is_taxable, 
                lms_source, search_patterns
            )
            SELECT 
                LOWER(REPLACE(REPLACE(charge_description, ' ', '_'), '/', '_')) as charge_code,
                charge_description,
                charge_category,
                is_taxable,
                true,
                ARRAY[LOWER(charge_description)] as search_patterns
            FROM lms_rate_mapping
            WHERE is_active = true
        """)
        
        lms_count = cur.rowcount
        print(f"   [OK] Added {lms_count} entries from LMS rate mapping")
        
        # Update with statistics from charter_charges
        cur.execute("""
            UPDATE unified_charge_lookup ucl
            SET 
                usage_frequency = cc_stats.frequency,
                avg_amount = cc_stats.avg_amount,
                min_amount = cc_stats.min_amount,
                max_amount = cc_stats.max_amount,
                total_amount = cc_stats.total_amount,
                charter_charges_source = true,
                updated_at = CURRENT_TIMESTAMP
            FROM (
                SELECT 
                    description,
                    COUNT(*) as frequency,
                    ROUND(AVG(amount), 2) as avg_amount,
                    ROUND(MIN(amount), 2) as min_amount,
                    ROUND(MAX(amount), 2) as max_amount,
                    ROUND(SUM(amount), 2) as total_amount
                FROM charter_charges
                WHERE amount IS NOT NULL AND amount != 0
                GROUP BY description
            ) cc_stats
            WHERE LOWER(ucl.standard_description) = LOWER(cc_stats.description)
        """)
        
        updated_count = cur.rowcount
        print(f"   [OK] Updated {updated_count} entries with charter_charges statistics")
        
        # Add high-frequency charges not in LMS
        cur.execute("""
            INSERT INTO unified_charge_lookup (
                charge_code, standard_description, category, 
                usage_frequency, avg_amount, min_amount, max_amount, total_amount,
                charter_charges_source, search_patterns
            )
            SELECT 
                LOWER(REPLACE(REPLACE(cc_stats.description, ' ', '_'), '/', '_')) as charge_code,
                cc_stats.description,
                CASE 
                    WHEN LOWER(cc_stats.description) LIKE '%gst%' OR LOWER(cc_stats.description) LIKE '%tax%' THEN 'Taxes'
                    WHEN LOWER(cc_stats.description) LIKE '%tip%' OR LOWER(cc_stats.description) LIKE '%gratuity%' THEN 'Gratuities'
                    WHEN LOWER(cc_stats.description) LIKE '%beverage%' OR LOWER(cc_stats.description) LIKE '%alcohol%' THEN 'Beverages'
                    WHEN LOWER(cc_stats.description) LIKE '%fuel%' OR LOWER(cc_stats.description) LIKE '%gas%' THEN 'Fuel'
                    WHEN LOWER(cc_stats.description) LIKE '%airport%' OR LOWER(cc_stats.description) LIKE '%stop%' THEN 'Transportation'
                    WHEN LOWER(cc_stats.description) LIKE '%clean%' OR LOWER(cc_stats.description) LIKE '%damage%' THEN 'Cleaning'
                    WHEN LOWER(cc_stats.description) LIKE '%fee%' OR LOWER(cc_stats.description) LIKE '%charge%' THEN 'Fees'
                    WHEN LOWER(cc_stats.description) LIKE '%discount%' THEN 'Discounts'
                    ELSE 'Other'
                END as category,
                cc_stats.frequency,
                cc_stats.avg_amount,
                cc_stats.min_amount, 
                cc_stats.max_amount,
                cc_stats.total_amount,
                true,
                ARRAY[LOWER(cc_stats.description)]
            FROM (
                SELECT 
                    description,
                    COUNT(*) as frequency,
                    ROUND(AVG(amount), 2) as avg_amount,
                    ROUND(MIN(amount), 2) as min_amount,
                    ROUND(MAX(amount), 2) as max_amount,
                    ROUND(SUM(amount), 2) as total_amount
                FROM charter_charges
                WHERE amount IS NOT NULL AND amount != 0
                AND description NOT IN (SELECT standard_description FROM unified_charge_lookup)
                GROUP BY description
                HAVING COUNT(*) >= 10  -- Only frequent charges
            ) cc_stats
            ON CONFLICT (charge_code) DO NOTHING
        """)
        
        added_count = cur.rowcount
        print(f"   [OK] Added {added_count} high-frequency charges from charter_charges")
        
        # Create indexes
        cur.execute("""
            CREATE INDEX idx_unified_charge_lookup_description 
            ON unified_charge_lookup(standard_description);
            
            CREATE INDEX idx_unified_charge_lookup_category 
            ON unified_charge_lookup(category);
            
            CREATE INDEX idx_unified_charge_lookup_patterns 
            ON unified_charge_lookup USING GIN(search_patterns);
        """)
        
        print("   [OK] Created indexes")
        
        conn.commit()
        
    except Exception as e:
        print(f"   [FAIL] Error creating unified lookup: {str(e)}")
        conn.rollback()
        return
    
    cur.close()
    conn.close()

def analyze_unified_lookup():
    """Analyze the unified charge lookup table."""
    
    print(f"\n📊 UNIFIED CHARGE LOOKUP ANALYSIS")
    print("-" * 34)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Category breakdown
    cur.execute("""
        SELECT 
            category,
            COUNT(*) as charge_types,
            SUM(usage_frequency) as total_usage,
            ROUND(AVG(avg_amount), 2) as category_avg_amount,
            ROUND(SUM(total_amount), 2) as category_total
        FROM unified_charge_lookup
        WHERE usage_frequency > 0
        GROUP BY category
        ORDER BY total_usage DESC, category_total DESC
    """)
    
    categories = cur.fetchall()
    
    print("📋 CATEGORY BREAKDOWN:")
    print(f"{'Category':<15} {'Types':<6} {'Usage':<8} {'Avg $':<8} {'Total $':<12}")
    print("-" * 60)
    
    grand_total_usage = 0
    grand_total_amount = 0
    
    for category, types, usage, avg_amt, total_amt in categories:
        grand_total_usage += usage or 0
        grand_total_amount += total_amt or 0
        
        usage_str = f"{usage:,}" if usage else "0"
        avg_str = f"${avg_amt:.2f}" if avg_amt else "N/A"
        total_str = f"${total_amt:,.2f}" if total_amt else "N/A"
        
        print(f"{category:<15} {types:<6} {usage_str:<8} {avg_str:<8} {total_str:<12}")
    
    print("-" * 60)
    print(f"{'TOTAL':<15} {'':<6} {grand_total_usage:<8,} {'':<8} ${grand_total_amount:,.2f}")
    
    # Top charges by usage
    print(f"\n🔥 TOP CHARGES BY USAGE:")
    cur.execute("""
        SELECT standard_description, category, usage_frequency, 
               avg_amount, total_amount
        FROM unified_charge_lookup
        WHERE usage_frequency > 0
        ORDER BY usage_frequency DESC
        LIMIT 15
    """)
    
    top_charges = cur.fetchall()
    
    for desc, category, freq, avg_amt, total_amt in top_charges:
        desc_short = (desc[:25] + '...') if len(desc) > 25 else desc
        avg_str = f"${avg_amt:.2f}" if avg_amt else "N/A"
        total_str = f"${total_amt:,.2f}" if total_amt else "N/A"
        print(f"   • {desc_short:<28} ({category:<12}) {freq:,} × {avg_str} = {total_str}")
    
    # Coverage analysis
    cur.execute("""
        SELECT 
            COUNT(*) as total_lookup_entries,
            COUNT(CASE WHEN lms_source THEN 1 END) as from_lms,
            COUNT(CASE WHEN charter_charges_source THEN 1 END) as from_charter_charges,
            COUNT(CASE WHEN usage_frequency > 0 THEN 1 END) as with_usage_data
        FROM unified_charge_lookup
    """)
    
    coverage = cur.fetchone()
    total, from_lms, from_cc, with_usage = coverage
    
    print(f"\n📊 COVERAGE ANALYSIS:")
    print(f"   • Total charge types: {total:,}")
    print(f"   • From LMS mapping: {from_lms:,}")
    print(f"   • From charter_charges: {from_cc:,}")
    print(f"   • With usage data: {with_usage:,}")
    
    cur.close()
    conn.close()

def match_charges_to_lookup(dry_run=True):
    """Match charges across tables using the unified lookup."""
    
    print(f"\n🎯 CHARGE MATCHING WITH UNIFIED LOOKUP")
    print("-" * 38)
    
    if dry_run:
        print("   📋 DRY RUN MODE - No changes will be made")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Find receipts that could be matched to charge categories
    cur.execute("""
        SELECT 
            r.id,
            r.vendor_name,
            r.description,
            r.gross_amount,
            r.category as current_category,
            ucl.standard_description,
            ucl.category as suggested_category,
            ucl.charge_code
        FROM receipts r
        CROSS JOIN unified_charge_lookup ucl
        WHERE (r.category IS NULL OR r.category = 'uncategorized')
        AND r.gross_amount > 5.00
        AND (
            LOWER(COALESCE(r.description, '')) LIKE '%' || ANY(ucl.search_patterns) || '%'
            OR LOWER(COALESCE(r.vendor_name, '')) LIKE '%' || ANY(ucl.search_patterns) || '%'
        )
        ORDER BY r.gross_amount DESC
        LIMIT 20
    """)
    
    receipt_matches = cur.fetchall()
    
    if receipt_matches:
        print(f"   📊 Found {len(receipt_matches)} receipt matching opportunities:")
        
        for receipt_id, vendor, desc, amount, current_cat, suggested_desc, suggested_cat, charge_code in receipt_matches[:10]:
            vendor_short = (vendor[:20] + '...') if vendor and len(vendor) > 20 else (vendor or 'N/A')
            desc_short = (desc[:25] + '...') if desc and len(desc) > 25 else (desc or 'N/A')
            print(f"      Receipt {receipt_id}: {vendor_short} - {desc_short}")
            print(f"         Amount: ${amount:.2f} → Suggest: {suggested_desc} ({suggested_cat})")
            
            if not dry_run:
                cur.execute("""
                    UPDATE receipts 
                    SET category = %s,
                        comment = COALESCE(comment, '') || %s
                    WHERE id = %s
                """, (
                    suggested_cat.lower(),
                    f" [Auto-matched to {charge_code}]",
                    receipt_id
                ))
    
    # Find payments that could be categorized
    cur.execute("""
        SELECT 
            p.payment_id,
            p.amount,
            p.notes,
            ucl.standard_description,
            ucl.category,
            ucl.charge_code
        FROM payments p
        CROSS JOIN unified_charge_lookup ucl
        WHERE p.notes IS NOT NULL
        AND p.amount > 5.00
        AND LOWER(p.notes) LIKE '%' || ANY(ucl.search_patterns) || '%'
        ORDER BY p.amount DESC
        LIMIT 10
    """)
    
    payment_matches = cur.fetchall()
    
    if payment_matches:
        print(f"\n   💰 Found {len(payment_matches)} payment matching opportunities:")
        
        for payment_id, amount, notes, suggested_desc, suggested_cat, charge_code in payment_matches:
            notes_short = (notes[:40] + '...') if notes and len(notes) > 40 else (notes or 'N/A')
            print(f"      Payment {payment_id}: ${amount:.2f}")
            print(f"         Notes: {notes_short}")
            print(f"         Suggest: {suggested_desc} ({suggested_cat})")
            
            if not dry_run:
                cur.execute("""
                    UPDATE payments 
                    SET notes = COALESCE(notes, '') || %s
                    WHERE payment_id = %s
                """, (
                    f" [Category: {suggested_cat}]",
                    payment_id
                ))
    
    if not dry_run and (receipt_matches or payment_matches):
        conn.commit()
        print(f"\n   [OK] Applied charge matches to database")
    elif dry_run:
        print(f"\n   📋 DRY RUN: Would update {len(receipt_matches)} receipts and {len(payment_matches)} payments")
    
    cur.close()
    conn.close()

def main():
    """Main charge matching system."""
    
    parser = argparse.ArgumentParser(description='Comprehensive Charge Matching System')
    parser.add_argument('--apply', action='store_true', help='Apply matches (default is dry run)')
    args = parser.parse_args()
    
    print("🎯 COMPREHENSIVE CHARGE MATCHING SYSTEM")
    print("=" * 40)
    
    # Step 1: Analyze integration opportunities
    analyze_charge_integration()
    
    # Step 2: Create unified lookup table
    create_unified_charge_lookup()
    
    # Step 3: Analyze the unified system
    analyze_unified_lookup()
    
    # Step 4: Match charges using the lookup
    match_charges_to_lookup(dry_run=not args.apply)
    
    print(f"\n[OK] CHARGE MATCHING SYSTEM COMPLETE")
    print("-" * 32)
    print("• Integrated LMS rate mapping with charter_charges data")
    print("• Created unified charge lookup with usage statistics")
    print("• Identified matching opportunities across tables")
    print("• Ready for ongoing charge categorization")
    
    if not args.apply:
        print("\n💡 To apply matches: --apply")

if __name__ == "__main__":
    # Set database environment
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_NAME'] = 'almsdata'
    os.environ['DB_USER'] = 'postgres'
    os.environ['DB_PASSWORD'] = '***REMOVED***'
    
    main()