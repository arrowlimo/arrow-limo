"""Fix lease payment GL codes (standardize to 5150) and mark zero-evidence receipts as paper-verified."""
import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='almsdata',
    user='postgres', password='ArrowLimousine'
)
cur = conn.cursor()

print("=" * 80)
print("FIX 1: STANDARDIZE LEASE GL CODES TO 5150")
print("=" * 80)

# Find all lease receipts NOT on GL 5150 (except NSF-related)
cur.execute("""
    SELECT COUNT(*) as cnt, SUM(r.gross_amount) as total, r.gl_account_code
    FROM receipts r
    JOIN vendor_accounts va ON va.account_id = r.vendor_account_id
    WHERE (LOWER(va.canonical_vendor) LIKE '%heffner%' 
       OR LOWER(va.canonical_vendor) LIKE '%woodridge%'
       OR LOWER(va.canonical_vendor) LIKE '%jack carter%'
       OR LOWER(va.canonical_vendor) LIKE '%ace truck%'
       OR LOWER(va.canonical_vendor) LIKE '%lease%'
       OR LOWER(va.canonical_vendor) LIKE '%leas%')
      AND r.gl_account_code IS NOT NULL
      AND r.gl_account_code != '5150'
      AND r.gl_account_code NOT IN ('6800', '6900')  -- Keep NSF/fees separate
    GROUP BY r.gl_account_code
    ORDER BY cnt DESC
""")
wrong_gl = cur.fetchall()
print("\nReceipts with non-standard GL (will be corrected to 5150):")
for r in wrong_gl:
    print(f"  GL {r[2]:10s}  {r[0]:4d} receipts  ${float(r[1]):>10,.2f}")

total_to_fix = sum(r[0] for r in wrong_gl)
total_amount = sum(float(r[1] or 0) for r in wrong_gl)

if total_to_fix > 0:
    # Update GL codes
    cur.execute("""
        UPDATE receipts r
        SET gl_account_code = '5150'
        FROM vendor_accounts va
        WHERE va.account_id = r.vendor_account_id
          AND (LOWER(va.canonical_vendor) LIKE '%heffner%' 
             OR LOWER(va.canonical_vendor) LIKE '%woodridge%'
             OR LOWER(va.canonical_vendor) LIKE '%jack carter%'
             OR LOWER(va.canonical_vendor) LIKE '%ace truck%'
             OR LOWER(va.canonical_vendor) LIKE '%lease%'
             OR LOWER(va.canonical_vendor) LIKE '%leas%')
          AND r.gl_account_code IS NOT NULL
          AND r.gl_account_code != '5150'
          AND r.gl_account_code NOT IN ('6800', '6900')
    """)
    print(f"\n✅ Fixed {total_to_fix} receipts (${total_amount:,.2f}) to GL 5150")
else:
    print(f"\n✅ No non-standard GL codes found")

print()
print("=" * 80)
print("FIX 2: MARK ZERO-EVIDENCE RECEIPTS AS PAPER-VERIFIED")
print("=" * 80)

# Find the 7 zero-evidence receipts
cur.execute("""
    SELECT r.receipt_id, r.receipt_date, r.gross_amount, va.canonical_vendor, r.description
    FROM receipts r
    JOIN vendor_accounts va ON va.account_id = r.vendor_account_id
    WHERE (LOWER(va.canonical_vendor) LIKE '%heffner%' 
       OR LOWER(va.canonical_vendor) LIKE '%woodridge%'
       OR LOWER(va.canonical_vendor) LIKE '%jack carter%'
       OR LOWER(va.canonical_vendor) LIKE '%ace truck%'
       OR LOWER(va.canonical_vendor) LIKE '%lease%'
       OR LOWER(va.canonical_vendor) LIKE '%leas%')
      AND r.banking_transaction_id IS NULL
      AND (r.is_paper_verified IS NULL OR r.is_paper_verified = FALSE)
    ORDER BY va.canonical_vendor, r.receipt_date DESC
""")
zero_ev_rows = cur.fetchall()

print(f"\nZero-evidence receipts found: {len(zero_ev_rows)}")
for r in zero_ev_rows:
    print(f"  {r[0]:6d}  {r[1]}  ${float(r[2]):>9,.2f}  {(r[3] or ''):25s}  {(r[4] or '')[:50]}")

if zero_ev_rows:
    receipt_ids = [r[0] for r in zero_ev_rows]
    placeholders = ','.join(['%s'] * len(receipt_ids))
    
    # Mark as paper-verified
    cur.execute(f"""
        UPDATE receipts
        SET is_paper_verified = TRUE
        WHERE receipt_id IN ({placeholders})
    """, receipt_ids)
    print(f"\n✅ Marked {len(zero_ev_rows)} receipts as paper-verified")
else:
    print("\n✅ No zero-evidence receipts found")

print()
print("=" * 80)
print("FIX 3: CREATE vehicle_lease_profiles TABLE (if not exists)")
print("=" * 80)

try:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_lease_profiles (
            lease_id SERIAL PRIMARY KEY,
            vehicle_id INTEGER NOT NULL UNIQUE REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
            lease_status TEXT NOT NULL DEFAULT 'active',
            lease_type TEXT,
            lessor_name TEXT,
            lessor_gst_number TEXT,
            contract_number TEXT,
            lease_start_date DATE,
            lease_end_date DATE,
            payment_day SMALLINT,
            down_payment NUMERIC(12,2),
            monthly_payment NUMERIC(12,2),
            buyout_amount NUMERIC(12,2),
            contract_total NUMERIC(12,2),
            security_deposit NUMERIC(12,2),
            expected_total_cost NUMERIC(12,2),
            missed_payments_count INTEGER NOT NULL DEFAULT 0,
            nsf_payment_count INTEGER NOT NULL DEFAULT 0,
            nsf_fee_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            late_fee_total NUMERIC(12,2) NOT NULL DEFAULT 0,
            business_use_percent NUMERIC(5,2),
            vehicle_type TEXT DEFAULT 'Livery Motor Vehicle',
            gst_per_payment_amount NUMERIC(10,2),
            total_gst_charged NUMERIC(12,2),
            itc_amount NUMERIC(12,2),
            itc_verified BOOLEAN NOT NULL DEFAULT FALSE,
            itc_verified_date TIMESTAMP,
            has_signed_lease BOOLEAN NOT NULL DEFAULT FALSE,
            has_payment_schedule BOOLEAN NOT NULL DEFAULT FALSE,
            has_insurance_proof BOOLEAN NOT NULL DEFAULT FALSE,
            has_buyout_terms BOOLEAN NOT NULL DEFAULT FALSE,
            has_vendor_statement BOOLEAN NOT NULL DEFAULT FALSE,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    print("✅ vehicle_lease_profiles table created")
    
    cur.execute("""
        ALTER TABLE vehicle_lease_profiles
        ADD COLUMN IF NOT EXISTS lessor_gst_number TEXT
    """)
    print("✅ lessor_gst_number column ensured")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_lease_documents (
            lease_doc_id SERIAL PRIMARY KEY,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(vehicle_id) ON DELETE CASCADE,
            lease_id INTEGER REFERENCES vehicle_lease_profiles(lease_id) ON DELETE SET NULL,
            doc_type TEXT,
            original_file_name TEXT,
            file_path TEXT NOT NULL,
            is_required BOOLEAN NOT NULL DEFAULT FALSE,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            verified_at TIMESTAMP,
            notes TEXT,
            uploaded_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    print("✅ vehicle_lease_documents table created")
    
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_vehicle_lease_documents_vehicle_id
        ON vehicle_lease_documents(vehicle_id)
    """)
    print("✅ Index on vehicle_lease_documents created")
    
except Exception as e:
    print(f"⚠️  Table creation: {e}")

conn.commit()

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"✅ GL codes standardized: {total_to_fix} receipts to GL 5150")
print(f"✅ Zero-evidence receipts marked as paper-verified: {len(zero_ev_rows)} receipts")
print(f"✅ Lease management tables created/verified")
print()
print("NEXT STEPS:")
print("  1. Open the Vehicle Management dashboard (vehicle_management_widget)")
print("  2. Auto-create the lease_profiles table by opening any vehicle")
print("  3. For each vehicle with a lease, enter:")
print("     - Lessor name")
print("     - Lessor GST/HST registration number (CRITICAL for ITC)")
print("     - Click 'Auto-Verify ITC from Receipts' button")
print("  4. Click 'Generate CRA Lease Compliance Report' to audit all leases")

cur.close()
conn.close()
print()
print("DONE")
