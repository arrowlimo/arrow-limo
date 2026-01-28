"""
Analyze Receipts Table for Standardization Opportunities
Based on receipts table layout template - find duplicates/variations to consolidate
"""

import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def analyze_receipt_standardization():
    """Analyze receipt fields for standardization"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("RECEIPTS TABLE STANDARDIZATION ANALYSIS")
    print("=" * 100)
    
    # 1. Check what columns exist
    print("\n📋 CHECKING RECEIPT TABLE STRUCTURE...")
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'receipts'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    print(f"\nFound {len(columns)} columns:")
    
    # Fields from template to check
    template_fields = [
        'type', 'tax_category', 'classification', 'document_type', 
        'payment_method', 'expense_account', 'sales_tax'
    ]
    
    for col, dtype, nullable in columns:
        marker = "✓" if col in template_fields else " "
        print(f"  {marker} {col:30s} {dtype:20s} {'NULL' if nullable == 'YES' else 'NOT NULL'}")
    
    # 2. Analyze each standardizable field
    fields_to_analyze = [
        ('payment_method', 'PAYMENT METHODS'),
        ('vendor_name', 'VENDOR NAMES (top duplicates)'),
        ('description', 'DESCRIPTIONS (top patterns)'),
    ]
    
    # Check if template fields exist
    existing_cols = [col[0] for col in columns]
    if 'type' in existing_cols:
        fields_to_analyze.append(('type', 'EXPENSE TYPES'))
    if 'tax_category' in existing_cols:
        fields_to_analyze.append(('tax_category', 'TAX CATEGORIES'))
    if 'classification' in existing_cols:
        fields_to_analyze.append(('classification', 'CLASSIFICATIONS'))
    if 'document_type' in existing_cols:
        fields_to_analyze.append(('document_type', 'DOCUMENT TYPES'))
    
    for field, title in fields_to_analyze:
        if field not in existing_cols:
            print(f"\n⚠️  Field '{field}' does not exist in receipts table")
            continue
            
        print(f"\n{'=' * 100}")
        print(f"📊 {title}")
        print('=' * 100)
        
        limit = 50 if field == 'vendor_name' else 30
        
        cur.execute(f"""
            SELECT {field}, COUNT(*) as count, SUM(gross_amount) as total
            FROM receipts
            WHERE {field} IS NOT NULL AND TRIM({field}) != ''
            GROUP BY {field}
            ORDER BY count DESC
            LIMIT {limit}
        """)
        
        values = cur.fetchall()
        
        if values:
            print(f"\n{len(values)} unique values found:")
            for val, count, total in values:
                val_str = str(val)[:60] if val else 'NULL'
                total_amt = total if total is not None else 0.0
                print(f"  {val_str:60s} | {count:>6} receipts | ${total_amt:>12,.2f}")
        else:
            print("  No data")
    
    # 3. Find vendor name variations (fuzzy duplicates)
    print(f"\n{'=' * 100}")
    print("🔍 VENDOR NAME VARIATIONS (potential duplicates)")
    print('=' * 100)
    
    cur.execute("""
        SELECT vendor_name, COUNT(*), SUM(gross_amount)
        FROM receipts
        WHERE vendor_name IS NOT NULL
        GROUP BY vendor_name
        ORDER BY vendor_name
    """)
    
    all_vendors = cur.fetchall()
    
    # Group by similarity (first 15 chars)
    vendor_groups = defaultdict(list)
    for vendor, count, total in all_vendors:
        if vendor:
            key = vendor[:15].upper().strip()
            vendor_groups[key].append((vendor, count, total))
    
    # Show groups with multiple variations
    print("\nVendor groups with multiple spellings/variations:")
    dup_count = 0
    for key, vendors in sorted(vendor_groups.items()):
        if len(vendors) > 1:
            dup_count += 1
            total_receipts = sum(v[1] for v in vendors)
            total_amount = sum(v[2] for v in vendors)
            print(f"\n{dup_count}. '{key}*' group ({len(vendors)} variations, {total_receipts} receipts, ${total_amount:,.2f}):")
            for vendor, count, total in sorted(vendors, key=lambda x: -x[1]):
                print(f"   → {vendor:50s} {count:>4} receipts ${total:>10,.2f}")
    
    # 4. Recommendations
    print("\n" + "=" * 100)
    print("💡 STANDARDIZATION RECOMMENDATIONS")
    print("=" * 100)
    
    print("\n1. VENDOR NAMES:")
    print("   • Create vendor_aliases table for name normalization")
    print(f"   • Found ~{dup_count} vendor groups with variations")
    print("   • Standardize: FAS GAS variations, RUN'N ON EMPTY, etc.")
    
    print("\n2. PAYMENT METHODS:")
    print("   • Standardize to: Cash, Debit, Credit, E-Transfer, Check")
    print("   • Consolidate variations (e.g., 'Debit Card' → 'Debit')")
    
    print("\n3. CREATE MISSING TEMPLATE FIELDS:")
    for field in template_fields:
        if field not in existing_cols:
            print(f"   • ALTER TABLE receipts ADD COLUMN {field} VARCHAR;")
    
    print("\n4. GL CODE CONSISTENCY:")
    print("   • Use 4115 for Client Beverages")
    print("   • Use 5116 for Client Amenities")
    print("   • Use 5110 for Vehicle Fuel (consolidate from 5210)")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)


if __name__ == "__main__":
    analyze_receipt_standardization()
