#!/usr/bin/env python3
"""
Receipt Standardization Analysis v2 - With Banking Pattern Parsing
Analyzes receipts table for consolidation opportunities with intelligent
extraction of real vendor names from banking transaction patterns.
"""

import os
import csv
import psycopg2
from collections import defaultdict
import re

# Database connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def load_vendor_aliases():
    """Load vendor alias prefixes -> canonical names from CSV if present."""
    aliases = []
    alias_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "vendor_aliases.csv"))
    if not os.path.exists(alias_path):
        return aliases
    with open(alias_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical = (row.get("canonical_name") or "").strip()
            prefix = (row.get("alias_prefix") or "").strip()
            if not canonical or not prefix:
                continue
            aliases.append((prefix.upper(), canonical))
    return aliases

def extract_real_vendor(vendor_name):
    """Extract actual vendor from banking transaction patterns."""
    if not vendor_name:
        return vendor_name
        
    # INTERAC RETAIL PURCHASE [trace] [vendor]
    if vendor_name.startswith("INTERAC RETAIL PURCHASE "):
        parts = vendor_name.split(maxsplit=3)
        if len(parts) >= 4:
            return parts[3].strip()
        return vendor_name
    
    # INTERNET BANKING [type] [account#] [vendor]
    if vendor_name.startswith("INTERNET BANKING "):
        # Extract vendor after account number pattern
        parts = vendor_name.replace("INTERNET BANKING ", "")
        
        # Skip "INTERNET BILL PAY" or "CORRECTION" prefix
        if "INTERNET BILL PAY" in parts:
            # Find the vendor after the account number pattern
            match = re.search(r'INTERNET BILL PAY\s+\d+\s+(.+)$', vendor_name)
            if match:
                return match.group(1).strip()
        elif "CORRECTION" in parts:
            # Corrections don't have vendor names
            return "INTERNET BANKING CORRECTION"
            
        return vendor_name
    
    # INTERNET BILL PAY (standalone)
    if vendor_name.startswith("INTERNET BILL PAY "):
        match = re.search(r'INTERNET BILL PAY\s+\d+\s+(.+)$', vendor_name)
        if match:
            return match.group(1).strip()
        return vendor_name
    
    # VISA DEBIT [type] [details] [vendor]
    if vendor_name.startswith("VISA DEBIT "):
        # Extract vendor after transaction ID, before USD amount if present
        match = re.search(r'\d{12}\s+(.+?)(?:\s+\d+\.\d+\s+USD)?$', vendor_name)
        if match:
            return match.group(1).strip()
        return vendor_name
    
    # PRE-AUTH DEBIT / PREAUTHORIZED DEBIT [amount/id]
    if vendor_name.startswith(("PRE-AUTH DEBIT ", "PREAUTHORIZED DEBIT ")):
        # These are internal debits without vendor names
        return "PREAUTHORIZED DEBIT"
    
    # PURCHASE [vendor]
    if vendor_name.startswith("PURCHASE "):
        return vendor_name.replace("PURCHASE ", "", 1).strip()
    
    # RETAIL PURCHASE [trace] [vendor]
    if vendor_name.startswith("RETAIL PURCHASE "):
        parts = vendor_name.split(maxsplit=2)
        if len(parts) >= 3:
            return parts[2].strip()
        return vendor_name
    
    # MISC PAYMENT (Global Payments fees)
    if vendor_name.startswith("MISC PAYMENT "):
        return "GLOBAL PAYMENTS FEES"
    
    # E-TRANSFER / EMAIL MONEY TRANSFER (can be incoming OR outgoing)
    # INCOMING: Customer charter payments (income)
    # OUTGOING: Driver payments, employee reimbursements (expenses)
    # Each e-Transfer MUST have a person name to identify sender/recipient
    if "E-TRANSFER" in vendor_name.upper() or "EMAIL MONEY TRANSFER" in vendor_name.upper():
        # Extract recipient/sender name if present
        match = re.search(r'(?:E-TRANSFER|EMAIL MONEY TRANSFER)\s+(?:TO\s+|FROM\s+)?(.+?)(?:\s+\d{12})?$', vendor_name, re.IGNORECASE)
        if match:
            party = match.group(1).strip()
            return f"E-TRANSFER: {party}"
        # If no name found, keep original (each e-Transfer should be uniquely identifiable)
        return vendor_name
    
    
    return vendor_name


def apply_vendor_alias(vendor_name, aliases):
    """Map truncated/variant vendor names to canonical names using alias prefixes."""
    if not vendor_name:
        return vendor_name
    upper_name = vendor_name.upper()
    for prefix, canonical in aliases:
        if upper_name.startswith(prefix):
            return canonical
    return vendor_name


def main():
    print("=" * 100)
    print("RECEIPT STANDARDIZATION ANALYSIS v2 - WITH BANKING PATTERN PARSING")
    print("=" * 100)
    
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    alias_rules = load_vendor_aliases()
    print(f"Loaded {len(alias_rules)} vendor alias rules")
    
    # 1. Table structure
    print("\n📋 RECEIPTS TABLE STRUCTURE")
    print("=" * 100)
    
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'receipts' 
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    print(f"\nFound {len(columns)} columns in receipts table")
    
    # Check for template fields
    template_fields = ['type', 'tax_category', 'classification', 'document_type', 
                      'payment_method', 'expense_account', 'sales_tax']
    
    existing_fields = [col[0] for col in columns]
    print(f"\nTemplate field check:")
    for field in template_fields:
        status = "✓" if field in existing_fields else "✗"
        print(f"  {status} {field}")
    
    # 2. Payment method analysis
    print(f"\n{'=' * 100}")
    print("💳 PAYMENT METHOD ANALYSIS")
    print('=' * 100)
    
    cur.execute("""
        SELECT payment_method, COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE payment_method IS NOT NULL AND TRIM(payment_method) != ''
        GROUP BY payment_method
        ORDER BY count DESC
    """)
    
    payment_methods = cur.fetchall()
    print(f"\n{len(payment_methods)} unique payment methods found:")
    for method, count, total in payment_methods:
        total_amt = total if total is not None else 0.0
        print(f"  {method:30s} | {count:>6} receipts | ${total_amt:>12,.2f}")
    
    # 3. Raw vendor analysis
    print(f"\n{'=' * 100}")
    print("🏪 VENDOR NAME ANALYSIS (RAW - before parsing)")
    print('=' * 100)
    
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE vendor_name IS NOT NULL AND vendor_name != ''
        GROUP BY vendor_name
        ORDER BY count DESC
        LIMIT 30
    """)
    
    raw_vendors = cur.fetchall()
    print(f"\nTop 30 raw vendor names (showing banking patterns):")
    for vendor, count, total in raw_vendors:
        total_amt = total if total is not None else 0.0
        print(f"{vendor[:70]:70s} {count:>5} rcpts ${total_amt:>12,.2f}")
    
    # 4. Parse vendors and re-aggregate
    print(f"\n{'=' * 100}")
    print("🔧 PARSED VENDOR NAMES (after extracting from banking patterns)")
    print('=' * 100)
    
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE vendor_name IS NOT NULL AND vendor_name != ''
        GROUP BY vendor_name
    """)
    
    all_vendors_raw = cur.fetchall()
    
    # Parse and aggregate
    parsed_vendors = {}
    for vendor_raw, count, total in all_vendors_raw:
        vendor_parsed = extract_real_vendor(vendor_raw)
        vendor_parsed = apply_vendor_alias(vendor_parsed, alias_rules)
        if vendor_parsed not in parsed_vendors:
            parsed_vendors[vendor_parsed] = {'count': 0, 'total': 0.0}
        parsed_vendors[vendor_parsed]['count'] += count
        parsed_vendors[vendor_parsed]['total'] += float(total if total else 0.0)
    
    # Show top 50 parsed vendors
    sorted_parsed = sorted(parsed_vendors.items(), key=lambda x: -x[1]['count'])[:50]
    print(f"\nTop 50 vendors after parsing:")
    for vendor, stats in sorted_parsed:
        print(f"{vendor[:70]:70s} {stats['count']:>5} rcpts ${stats['total']:>12,.2f}")
    
    # 5. Group parsed vendors by similarity
    print(f"\n{'=' * 100}")
    print("🔍 VENDOR CONSOLIDATION OPPORTUNITIES (grouped by first 15 chars)")
    print('=' * 100)
    
    # Group by first 15 characters
    vendor_groups = {}
    for vendor, stats in parsed_vendors.items():
        key = vendor[:15].upper().strip()
        if key not in vendor_groups:
            vendor_groups[key] = []
        vendor_groups[key].append((vendor, stats['count'], stats['total']))
    
    # Show groups with multiple variations
    print("\nVendor groups with multiple spellings/variations:")
    group_num = 0
    for key in sorted(vendor_groups.keys()):
        variations = vendor_groups[key]
        if len(variations) > 1:  # Multiple variations
            group_num += 1
            total_count = sum(v[1] for v in variations)
            total_amount = sum(v[2] for v in variations)
            
            print(f"\n{group_num}. '{key}*' group ({len(variations)} variations, {total_count} receipts, ${total_amount:,.2f}):")
            
            # Show each variation
            for vendor, count, total in sorted(variations, key=lambda x: -x[1]):
                print(f"   → {vendor:50s} {count:>5} rcpts ${total:>12,.2f}")
    
    # 6. Recommendations
    print("\n" + "=" * 100)
    print("💡 STANDARDIZATION RECOMMENDATIONS")
    print("=" * 100)
    
    print("\n1. VENDOR NAMES:")
    print(f"   • Create vendor_aliases table for name normalization")
    print(f"   • Found ~{group_num} vendor groups with variations (after parsing)")
    print(f"   • Banking patterns successfully parsed: INTERAC RETAIL, INTERNET BANKING, VISA DEBIT, etc.")
    
    print("\n2. PAYMENT METHODS:")
    print("   • Standardize to: Cash, Debit, Credit, E-Transfer, Check")
    print("   • Consolidate variations (e.g., 'Debit Card' → 'Debit')")
    print("   • E-Transfers are BIDIRECTIONAL:")
    print("     - INCOMING: Customer charter payments (payments table)")
    print("     - OUTGOING: Driver pay, employee reimbursements (receipts table)")
    print("   • Direction determined by table context (receipts=expense, payments=income)")
    
    print("\n3. GL CODE CONSISTENCY:")
    print("   • Use 4115 for Client Beverages")
    print("   • Use 5116 for Client Amenities")
    print("   • Use 5110 for Vehicle Fuel (consolidate from 5210)")
    
    print("\n4. BANKING PATTERN HANDLING:")
    print("   • Add transaction_type field to store: INTERAC, VISA_DEBIT, INTERNET_BANKING, etc.")
    print("   • Keep vendor_name for real vendor, transaction_type for banking prefix")
    print("   • Parse automatically on import from banking transactions")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    print("ANALYSIS COMPLETE")
    print("=" * 100)


if __name__ == "__main__":
    main()
