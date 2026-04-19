"""Audit lease payment paperwork — banking links, receipts, GL codes for known lessors."""
import psycopg2

conn = psycopg2.connect(
    host='localhost', port=5432, dbname='almsdata',
    user='postgres', password='ArrowLimousine'
)
cur = conn.cursor()

LESSOR_PATTERNS = [
    'heffner', 'woodridge', 'jack carter', 'ace truck',
    'ford', 'lease', 'leas', 'gm financial', 'toyota', 'honda',
    'chrysler', 'dodge', 'mercedes', 'bmw', 'kia', 'hyundai',
    'chevrolet', 'nissan', 'vw', 'volkswagen',
]

pattern_sql = ' OR '.join(
    [f"LOWER(va.canonical_vendor) LIKE '%{p}%'" for p in LESSOR_PATTERNS]
)

# 1. Vendor accounts for lessors
cur.execute(f"""
    SELECT va.account_id, va.display_name, va.canonical_vendor,
           COUNT(r.receipt_id) as receipt_count,
           COALESCE(SUM(r.gross_amount), 0) as total_paid
    FROM vendor_accounts va
    LEFT JOIN receipts r ON r.vendor_account_id = va.account_id
    WHERE {pattern_sql}
    GROUP BY va.account_id, va.display_name, va.canonical_vendor
    ORDER BY va.canonical_vendor
""")
vendor_rows = cur.fetchall()

print('=' * 80)
print('LESSOR VENDOR ACCOUNTS')
print('=' * 80)
if vendor_rows:
    for r in vendor_rows:
        print(f"  account_id={r[0]:4d}  receipts={r[3]:3d}  total=${float(r[4]):>12,.2f}  {r[2]}")
else:
    print('  NONE FOUND')

# 2. For each vendor account, check receipt quality
if vendor_rows:
    acct_ids = [r[0] for r in vendor_rows]
    placeholders = ','.join(['%s'] * len(acct_ids))

    cur.execute(f"""
        SELECT
            va.canonical_vendor,
            r.receipt_id,
            r.receipt_date,
            r.gross_amount,
            r.gl_account_code,
            r.payment_method,
            r.banking_transaction_id,
            r.is_paper_verified,
            r.source_reference,
            r.description,
            CASE
                WHEN r.banking_transaction_id IS NOT NULL AND r.is_paper_verified THEN 'FULL'
                WHEN r.banking_transaction_id IS NOT NULL THEN 'BANK_ONLY'
                WHEN r.is_paper_verified THEN 'PAPER_ONLY'
                ELSE 'NO_EVIDENCE'
            END as evidence_level
        FROM receipts r
        JOIN vendor_accounts va ON va.account_id = r.vendor_account_id
        WHERE r.vendor_account_id IN ({placeholders})
        ORDER BY va.canonical_vendor, r.receipt_date DESC
    """, acct_ids)
    receipt_rows = cur.fetchall()

    print()
    print('=' * 80)
    print('RECEIPT DETAIL PER LESSOR')
    print('=' * 80)

    current_vendor = None
    full = bank_only = paper_only = no_ev = 0
    for r in receipt_rows:
        vendor, rid, rdate, amount, gl, method, btid, paper, srcref, desc, ev = r
        if vendor != current_vendor:
            if current_vendor is not None:
                print(f"    --- Summary: FULL={full} BANK_ONLY={bank_only} PAPER_ONLY={paper_only} NO_EVIDENCE={no_ev} ---")
                full = bank_only = paper_only = no_ev = 0
            current_vendor = vendor
            print(f"\n  [{vendor}]")
        ev_icon = {'FULL': '✅', 'BANK_ONLY': '🏦', 'PAPER_ONLY': '📄', 'NO_EVIDENCE': '❌'}.get(ev, '?')
        gl_flag = '⚠️ NO GL' if not gl else ''
        print(f"    {ev_icon} {rdate}  ${float(amount):>9,.2f}  GL={gl or 'NONE':8s}  {method or '':15s}  bank={'YES' if btid else 'NO ':3s}  paper={'YES' if paper else 'NO'}  {gl_flag}  {(desc or '')[:40]}")
        if ev == 'FULL': full += 1
        elif ev == 'BANK_ONLY': bank_only += 1
        elif ev == 'PAPER_ONLY': paper_only += 1
        else: no_ev += 1
    if current_vendor:
        print(f"    --- Summary: FULL={full} BANK_ONLY={bank_only} PAPER_ONLY={paper_only} NO_EVIDENCE={no_ev} ---")

# 3. Check ITC GL codes used
print()
print('=' * 80)
print('GL CODES ON LEASE RECEIPTS (should be 2807/2808 or equivalent lease GL)')
print('=' * 80)
if vendor_rows:
    cur.execute(f"""
        SELECT r.gl_account_code, COUNT(*) as cnt, SUM(r.gross_amount) as total
        FROM receipts r
        WHERE r.vendor_account_id IN ({placeholders})
        GROUP BY r.gl_account_code
        ORDER BY cnt DESC
    """, acct_ids)
    gl_rows = cur.fetchall()
    for g in gl_rows:
        print(f"  GL {g[0] or 'NONE':10s}  count={g[1]:3d}  total=${float(g[2]):>12,.2f}")

# 4. Any lease receipts NOT linked to banking
print()
print('=' * 80)
print('RECEIPTS MISSING BANKING LINK (potential ITC risk)')
print('=' * 80)
if vendor_rows:
    cur.execute(f"""
        SELECT va.canonical_vendor, COUNT(*) as cnt, SUM(r.gross_amount) as total
        FROM receipts r
        JOIN vendor_accounts va ON va.account_id = r.vendor_account_id
        WHERE r.vendor_account_id IN ({placeholders})
          AND r.banking_transaction_id IS NULL
          AND (r.is_paper_verified IS NULL OR r.is_paper_verified = FALSE)
        GROUP BY va.canonical_vendor
        ORDER BY cnt DESC
    """, acct_ids)
    risk_rows = cur.fetchall()
    if risk_rows:
        for r in risk_rows:
            print(f"  ❌ {r[0]:40s}  {r[1]:3d} receipts  ${float(r[2]):>10,.2f}")
    else:
        print('  ✅ All lease receipts have banking or paper evidence')

# 5. Check vehicle_lease_profiles for these vendors
print()
print('=' * 80)
print('VEHICLE LEASE PROFILES — GST/ITC STATUS')
print('=' * 80)
try:
    cur.execute("""
        SELECT v.vehicle_number, lp.lessor_name, lp.lessor_gst_number,
               lp.itc_verified, lp.itc_amount, lp.total_gst_charged,
               lp.lease_status
        FROM vehicle_lease_profiles lp
        JOIN vehicles v ON v.vehicle_id = lp.vehicle_id
        ORDER BY v.vehicle_number
    """)
    profile_rows = cur.fetchall()
    if profile_rows:
        for r in profile_rows:
            gst_flag = '❌ MISSING GST#' if not r[2] else f'GST# {r[2]}'
            itc_flag = '✅ VERIFIED' if r[3] else '⏳ unverified'
            print(f"  Vehicle {r[0]:6s}  {(r[1] or 'NO LESSOR'):30s}  {gst_flag:25s}  ITC=${float(r[4] or 0):>8,.2f}  {itc_flag}  [{r[6]}]")
    else:
        print('  No lease profiles entered yet — use the Lease Compliance tab in the vehicle dashboard')
except Exception as e:
    print(f'  ⚠️  vehicle_lease_profiles table not yet created (open the vehicle dashboard to auto-create it)')
    print(f'  Error: {e}')

cur.close()
conn.close()
print()
print('DONE')
