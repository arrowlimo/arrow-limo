#!/usr/bin/env python3
"""
Import extracted PDF data into main almsdata tables
Processes receipts, payroll, insurance, banking, and vehicle data
"""
import os
import psycopg2
from datetime import datetime
import json
import hashlib

def _get_columns(cur, table_name: str):
    """Return set of column names for a table (lowercase)."""
    cur.execute(
        """
        SELECT LOWER(column_name)
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        """,
        (table_name,)
    )
    return {r[0] for r in cur.fetchall()}

DSN = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

def import_receipts(conn):
    """Import receipt data into receipts table"""
    cur = conn.cursor()
    cols = _get_columns(cur, 'receipts')
    # Determine available target columns with fallbacks
    amount_col = 'gross_amount' if 'gross_amount' in cols else ('amount' if 'amount' in cols else None)
    vendor_col = 'vendor_name' if 'vendor_name' in cols else ('vendor' if 'vendor' in cols else None)
    date_col = 'receipt_date' if 'receipt_date' in cols else ('date' if 'date' in cols else None)
    desc_col = 'description' if 'description' in cols else None
    cat_col = 'category' if 'category' in cols else None
    pymt_col = 'payment_method' if 'payment_method' in cols else None
    src_ref_col = 'source_reference' if 'source_reference' in cols else None
    src_hash_col = 'source_hash' if 'source_hash' in cols else None
    created_from_pdf_col = 'created_from_pdf' if 'created_from_pdf' in cols else None
    
    # Get receipts with amounts
    cur.execute("""
        SELECT id, file_name, extracted_data, date_detected, year_detected
        FROM pdf_staging
        WHERE category = 'receipt'
          AND extracted_data->>'amount' IS NOT NULL
          AND status = 'processed'
    """)
    
    receipts = cur.fetchall()
    imported = 0
    
    print(f"\n📄 Importing {len(receipts)} receipts...")
    
    for pdf_id, file_name, data, date_detected, year_detected in receipts:
        try:
            amount = float(data.get('amount', 0))
            vendor = data.get('vendor', 'Unknown')[:200]
            invoice_num = data.get('invoice_number', '')[:50]
            date_str = data.get('date', date_detected)
            
            # Try to parse date
            receipt_date = date_detected if date_detected else datetime.now().date()

            # Build deterministic source hash for idempotency (even if column doesn't exist we'll use it for duplicate check)
            sh = hashlib.sha256(f"{vendor}|{amount:.2f}|{receipt_date}|{file_name}".encode('utf-8')).hexdigest()

            # Duplicate check: prefer source_hash when available; otherwise check by vendor+amount+date+file hint
            if src_hash_col and src_hash_col in cols:
                cur.execute(f"SELECT 1 FROM receipts WHERE {src_hash_col} = %s LIMIT 1", (sh,))
                if cur.fetchone():
                    continue
            else:
                if vendor_col and amount_col and date_col:
                    cur.execute(
                        f"SELECT 1 FROM receipts WHERE {vendor_col} = %s AND {amount_col} = %s AND {date_col} = %s AND ({desc_col} ILIKE %s OR %s IS NULL)",
                        (vendor, amount, receipt_date, f"%{file_name}%" if desc_col else None, f"%{file_name}%" if desc_col else None)
                    )
                    if cur.fetchone():
                        continue
            
            # Insert into receipts
            columns = []
            values = []
            placeholders = []

            if date_col:
                columns.append(date_col); values.append(receipt_date); placeholders.append('%s')
            if vendor_col:
                columns.append(vendor_col); values.append(vendor); placeholders.append('%s')
            if amount_col:
                columns.append(amount_col); values.append(amount); placeholders.append('%s')
            if desc_col:
                columns.append(desc_col); values.append(f"Extracted from PDF: {file_name}"); placeholders.append('%s')
            if cat_col:
                columns.append(cat_col); values.append('other'); placeholders.append('%s')
            if pymt_col:
                columns.append(pymt_col); values.append('Unknown'); placeholders.append('%s')
            if src_ref_col:
                columns.append(src_ref_col); values.append(f"pdf_staging_id:{pdf_id}"); placeholders.append('%s')
            if src_hash_col:
                columns.append(src_hash_col); values.append(sh); placeholders.append('%s')
            if created_from_pdf_col:
                columns.append(created_from_pdf_col); values.append(True); placeholders.append('%s')

            cols_sql = ', '.join(columns + ['created_at'])
            ph_sql = ', '.join(placeholders + ['CURRENT_TIMESTAMP'])
            insert_sql = f"INSERT INTO receipts ({cols_sql}) VALUES ({ph_sql})"

            cur.execute(insert_sql, tuple(values))
            
            if cur.rowcount > 0:
                imported += 1
                
        except Exception as e:
            print(f"  [WARN]  Error importing receipt {file_name}: {e}")
    
    conn.commit()
    print(f"  [OK] Imported {imported} receipts")
    cur.close()
    return imported

def import_financial_events(conn):
    """Import insurance and vehicle financial events"""
    cur = conn.cursor()
    
    # Insurance premiums
    cur.execute("""
        SELECT id, file_name, extracted_data, date_detected, year_detected
        FROM pdf_staging
        WHERE category = 'insurance'
          AND extracted_data->>'premium' IS NOT NULL
          AND status = 'processed'
    """)
    
    events = cur.fetchall()
    imported = 0
    
    print(f"\n🏦 Importing {len(events)} insurance events...")
    
    for pdf_id, file_name, data, date_detected, year_detected in events:
        try:
            premium = float(data.get('premium', 0))
            policy_num = data.get('policy_number', '')[:50]
            eff_date = data.get('effective_date', date_detected)
            vins = data.get('vins', [])
            
            # Insert into email_financial_events
            cur.execute("""
                INSERT INTO email_financial_events (
                    source, entity, from_email, subject, email_date,
                    event_type, amount, currency, due_date, status,
                    policy_number, notes, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT DO NOTHING
            """, (
                'PDF Extract',
                'Insurance Premium',
                'insurance@extracted.pdf',
                f"Policy {policy_num}",
                date_detected or datetime.now().date(),
                'Insurance Premium',
                premium,
                'CAD',
                eff_date,
                'Extracted',
                policy_num,
                f"Extracted from {file_name}. VINs: {', '.join(vins[:5])}"
            ))
            
            if cur.rowcount > 0:
                imported += 1
                
        except Exception as e:
            print(f"  [WARN]  Error importing insurance {file_name}: {e}")
    
    conn.commit()
    print(f"  [OK] Imported {imported} insurance events")
    cur.close()
    return imported

def import_banking_transactions(conn):
    """Import banking statement data"""
    cur = conn.cursor()
    
    # Banking statements with balances
    cur.execute("""
        SELECT id, file_name, extracted_data, date_detected, year_detected
        FROM pdf_staging
        WHERE category = 'banking'
          AND (extracted_data->>'closing_balance' IS NOT NULL
               OR extracted_data->>'account_number' IS NOT NULL)
          AND status = 'processed'
    """)
    
    statements = cur.fetchall()
    imported = 0
    
    print(f"\n🏦 Found {len(statements)} banking statements with data")
    print(f"  ℹ️  Banking data requires manual reconciliation with banking_transactions table")
    
    # Don't auto-import banking - too complex for reconciliation
    # Just report what we have
    for pdf_id, file_name, data, date_detected, year_detected in statements[:5]:
        account = data.get('account_number', 'N/A')
        closing = data.get('closing_balance', 'N/A')
        print(f"  📊 {file_name[:50]} | Acct: {account} | Balance: {closing}")
    
    if len(statements) > 5:
        print(f"  ... and {len(statements) - 5} more statements")
    
    cur.close()
    return 0

def import_vehicle_data(conn):
    """Import vehicle document data"""
    cur = conn.cursor()
    
    # Vehicles with VINs
    cur.execute("""
        SELECT id, file_name, extracted_data, date_detected, year_detected
        FROM pdf_staging
        WHERE category = 'vehicle'
          AND extracted_data->>'vin' IS NOT NULL
          AND status = 'processed'
    """)
    
    vehicles = cur.fetchall()
    imported = 0
    
    print(f"\n🚗 Found {len(vehicles)} vehicle documents with VINs")
    
    for pdf_id, file_name, data, date_detected, year_detected in vehicles:
        vin = data.get('vin', '')
        make = data.get('make', '')
        model = data.get('model', '')
        year = data.get('year', year_detected)
        lease_num = data.get('lease_number', '')
        
        print(f"  📋 {file_name[:40]} | VIN: {vin} | {year} {make} {model}")
        
        # Check if VIN already exists
        cur.execute("SELECT vehicle_id FROM vehicles WHERE vin_number = %s", (vin,))
        if cur.fetchone():
            print(f"     ℹ️  VIN already in database")
        else:
            print(f"     [WARN]  New VIN - requires manual verification before import")
    
    cur.close()
    return 0

def main():
    print("="*70)
    print("PDF DATA IMPORT TO MAIN TABLES")
    print("="*70)
    
    conn = psycopg2.connect(**DSN)
    
    total_imported = 0
    
    # Import receipts (safe to auto-import)
    total_imported += import_receipts(conn)
    
    # Import insurance events (safe to auto-import)
    total_imported += import_financial_events(conn)
    
    # Banking (manual review required)
    import_banking_transactions(conn)
    
    # Vehicles (manual review required)
    import_vehicle_data(conn)
    
    # Summary
    print("\n" + "="*70)
    print("IMPORT SUMMARY")
    print("="*70)
    print(f"[OK] Auto-imported: {total_imported} records")
    print(f"[WARN]  Banking statements: Manual reconciliation required")
    print(f"[WARN]  Vehicle data: Manual verification required")
    
    print(f"\n📋 Next steps:")
    print(f"  1. Verify imported receipts: SELECT * FROM receipts WHERE source_reference LIKE 'pdf_staging_id:%' ORDER BY created_at DESC")
    print(f"  2. Verify insurance events: SELECT * FROM email_financial_events WHERE source='PDF Extract'")
    print(f"  3. Review banking statements manually for reconciliation")
    print(f"  4. Review vehicle VINs for potential new vehicle additions")
    
    conn.close()

if __name__ == "__main__":
    main()
