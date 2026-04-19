"""
Amalgamate verified 8362 transactions into their 1615 counterparts.

Case B (auto-processed): 8362 has paper-verified receipt, 1615 is unreconciled.
  - Re-point receipt_banking_links to 1615 transaction
  - Update receipts.banking_transaction_id
  - Copy category, reconciliation fields from 8362 → 1615
  - Mark 1615 verified=True
  - Delete 8362 row (after confirming no remaining links)

Case A (report only): Both sides already reconciled — flag for manual review.

DRY_RUN=True: no changes applied.
"""
import psycopg2
from decimal import Decimal

DRY_RUN = False

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata',
                        user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# ── Fetch all verified 8362 rows that match 1615 (2012-2014) ────────────────
cur.execute("""
  SELECT
    bt8.transaction_id              AS bt8_id,
    bt1.transaction_id              AS bt1_id,
    bt8.transaction_date,
    COALESCE(bt8.debit_amount,0)    AS debit,
    COALESCE(bt8.credit_amount,0)   AS credit,
    bt8.description                 AS desc_8362,
    bt1.description                 AS desc_1615,
    bt8.category                    AS cat_8362,
    bt8.reconciliation_status       AS status_8362,
    bt1.reconciliation_status       AS status_1615,
    bt8.reconciled_receipt_id       AS rec_rcpt_8362,
    bt1.reconciled_receipt_id       AS rec_rcpt_1615,
    bt8.is_transfer                 AS xfer_8362,
    bt8.reconciliation_notes        AS notes_8362,
    r8.receipt_id                   AS linked_rcpt_id,
    r8.vendor_name                  AS rcpt_vendor,
    r8.gl_code,
    r8.gl_description,
    r8.vehicle_number,
    r8.fuel,
    r8.fuel_amount,
    r8.gross_amount                 AS rcpt_gross,
    r8.is_paper_verified,
    r8.banking_transaction_id       AS rcpt_bt_id,
    rbl.link_id,
    rbl.linked_amount,
    rbl.link_status,
    rbl.notes                       AS link_notes
  FROM banking_transactions bt8
  JOIN banking_transactions bt1
    ON bt1.account_number='1615'
    AND bt1.transaction_date = bt8.transaction_date
    AND COALESCE(bt1.debit_amount,0) = COALESCE(bt8.debit_amount,0)
    AND COALESCE(bt1.credit_amount,0) = COALESCE(bt8.credit_amount,0)
  JOIN receipt_banking_links rbl ON rbl.transaction_id = bt8.transaction_id
  JOIN receipts r8 ON r8.receipt_id = rbl.receipt_id
  WHERE bt8.account_number='0228362'
  AND bt8.transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
  AND bt8.verified=TRUE
  ORDER BY bt8.transaction_date, bt8.transaction_id
""")
rows = cur.fetchall()
cols = [d[0] for d in cur.description]
pairs = [dict(zip(cols, r)) for r in rows]

print(f"Total verified 8362↔1615 pairs with receipt links: {len(pairs)}\n")

# Split cases
case_a = [p for p in pairs if p['rec_rcpt_1615'] is not None or p['status_1615'] == 'reconciled']
case_b = [p for p in pairs if p['rec_rcpt_1615'] is None and p['status_1615'] != 'reconciled']

# ── CASE A: Report only ─────────────────────────────────────────────────────
print(f"{'='*70}")
print(f"Case A — BOTH SIDES ALREADY RECONCILED ({len(case_a)} rows) — MANUAL REVIEW")
print(f"{'='*70}")
print(f"{'Date':<12} {'Debit':>8} {'Credit':>8}  {'Desc 8362':<25} {'Desc 1615':<25}  {'8362 rcpt':>9}  {'1615 rcpt':>9}")
print("-"*110)
for p in case_a:
    print(f"  {p['transaction_date']}  {float(p['debit']):>8.2f} {float(p['credit']):>8.2f}  "
          f"{(p['desc_8362'] or ''):<25} {(p['desc_1615'] or ''):<25}  "
          f"{str(p['rec_rcpt_8362']):>9}  {str(p['rec_rcpt_1615']):>9}")
print()
print("  → These are NOT auto-processed. Both 1615 and 8362 have separate receipts.")
print("  → PAPER STMT FEE: each account is charged its own $3/mo fee — likely legitimate.")
print("  → FAS GAS 2014-07-08 $80.02: check if this was actually a 1615 expense imported to 8362.")

# ── CASE B: Amalgamate ──────────────────────────────────────────────────────
print(f"\n{'='*70}")
print(f"Case B — 1615 UNRECONCILED, 8362 HAS PAPER RECEIPT ({len(case_b)} rows) — AMALGAMATE")
print(f"{'='*70}")
print(f"{'Date':<12} {'Debit':>8}  {'Vendor':<22} {'GL':>5}  {'GL Desc':<20}  Veh   Fuel  PaperVerif  bt8→bt1")
print("-"*110)
for p in case_b:
    print(f"  {p['transaction_date']}  {float(p['debit']):>8.2f}  "
          f"{(p['rcpt_vendor'] or ''):<22} {(p['gl_code'] or ''):>5}  "
          f"{(p['gl_description'] or ''):20}  "
          f"{(p['vehicle_number'] or 'N/A'):<5} "
          f"{str(p['fuel'] or '—'):>5}L  "
          f"{str(p['is_paper_verified']):<11}  "
          f"{p['bt8_id']}→{p['bt1_id']}  rcpt={p['linked_rcpt_id']}")

print()
if DRY_RUN:
    print("[DRY RUN] The following would be applied for each Case B pair:")
    print("  1. UPDATE receipt_banking_links SET transaction_id=bt1_id WHERE link_id=link_id")
    print("  2. UPDATE receipts SET banking_transaction_id=bt1_id WHERE receipt_id=rcpt_id AND banking_transaction_id=bt8_id")
    print("  3. UPDATE banking_transactions (1615 row): status='reconciled', reconciled_receipt_id, category, verified=True")
    print("  4. DELETE banking_transactions WHERE transaction_id=bt8_id (8362 row)")
else:
    # Collect bt8 IDs that will be deleted — check no other links remain
    bt8_ids = list({p['bt8_id'] for p in case_b})
    link_ids = [p['link_id'] for p in case_b]

    processed = 0
    for p in case_b:
        bt8 = p['bt8_id']
        bt1 = p['bt1_id']
        rcpt = p['linked_rcpt_id']
        lnk  = p['link_id']

        print(f"  Processing {p['transaction_date']} ${float(p['debit']):.2f}  bt8={bt8} → bt1={bt1}  rcpt={rcpt}")

        # 1. Move receipt_banking_link to 1615
        cur.execute("""
            UPDATE receipt_banking_links
            SET transaction_id = %s
            WHERE link_id = %s AND transaction_id = %s
        """, (bt1, lnk, bt8))
        assert cur.rowcount == 1, f"Expected 1 rbl update, got {cur.rowcount}"

        # 2. Update receipt's banking_transaction_id if it points to bt8
        cur.execute("""
            UPDATE receipts
            SET banking_transaction_id = %s
            WHERE receipt_id = %s AND banking_transaction_id = %s
        """, (bt1, rcpt, bt8))
        print(f"    receipts.banking_transaction_id update: {cur.rowcount} rows")

        # 3. Update 1615 row — copy reconciliation fields from 8362
        cat_update = p['cat_8362'] or 'Bank Fees'
        cur.execute("""
            UPDATE banking_transactions
            SET reconciliation_status = %s,
                reconciled_receipt_id = %s,
                category = %s,
                verified = TRUE,
                reconciliation_notes = COALESCE(reconciliation_notes,
                    'amalgamated from 8362 bt_id=' || %s)
            WHERE transaction_id = %s
        """, (p['status_8362'], p['rec_rcpt_8362'] or rcpt, cat_update, str(bt8), bt1))
        assert cur.rowcount == 1, f"Expected 1 bt1 update, got {cur.rowcount}"

        processed += 1

    # 4. Verify no remaining receipt links on bt8 rows, then delete
    cur.execute("""
        SELECT transaction_id FROM receipt_banking_links
        WHERE transaction_id = ANY(%s)
    """, (bt8_ids,))
    remaining = cur.fetchall()
    if remaining:
        print(f"\nWARNING: {len(remaining)} receipt links still on 8362 rows after move — NOT deleting!")
        conn.rollback()
    else:
        cur.execute("""
            DELETE FROM banking_transactions
            WHERE transaction_id = ANY(%s)
            AND account_number = '0228362'
        """, (bt8_ids,))
        deleted = cur.rowcount
        conn.commit()
        print(f"\nCommitted: {processed} receipts moved to 1615, {deleted} 8362 rows deleted.")

if DRY_RUN:
    conn.rollback()

print("\nDone.")
conn.close()
