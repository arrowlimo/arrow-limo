"""
fix_46_mismatches.py
====================
Applies all four categories of fixes to charter_payments:

  Cat 1: Delete duplicate CRR rows where manual_backfill already has the
         correct entry on same reserve+amount
  Cat 2: Insert missing LMS negative/reversal rows
  Cat 3: Delete stray incorrect rows (wrong reserve or wrong amount)
  Cat 4: Insert missing positive payments

Run with DRY_RUN=True first to preview, then set False to apply.
"""
import psycopg2, psycopg2.extras, decimal
from datetime import date

DRY_RUN = False

PG = "host=localhost port=5432 dbname=almsdata user=postgres password=ArrowLimousine"

pg = psycopg2.connect(PG)
cur = pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

actions = []   # (action, description, sql, params)

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 1 — Delete exact duplicate CRR rows (manual_backfill already correct)
# ─────────────────────────────────────────────────────────────────────────────

# Essential Coil 007896–007901: LMS key 0008246 (one cheque split across 6 reserves)
# manual_backfill has correct date 2013-07-03; CRR re-imported same rows dated 2025-07-24
# Delete the CRR duplicates:
cat1_deletes = [
    (8986,  '007896 Essential Coil $550.00 CRR dup'),
    (8976,  '007897 Essential Coil $468.75 CRR dup'),
    (8932,  '007898 Essential Coil $328.12 CRR dup'),
    (9593,  '007899 Essential Coil $710.94 CRR dup'),
    (9134,  '007900 Essential Coil $1015.62 CRR dup'),
    (8902,  '007901 Essential Coil $550.00 CRR dup'),
    (9248,  '008347 Quality Tubing $723.71 CRR dup'),
    (10637, '009777 Van Meter $175.00 CRR dup'),
    (10904, '009777 Van Meter $430.06 CRR dup'),
    (9730,  '008696 Lerners $68.25 CRR dup'),
    (13878, '011813 Paul Santana $150.00 CRR dup'),
    # 011696 Drouillard: manual_backfill has real dates for $480+$1000;
    # CRR re-imported them with fake 2025-07-24 dates → delete CRR dups
    (13240, '011696 Drouillard $480.00 CRR dup'),
    (13213, '011696 Drouillard $1000.00 CRR dup'),
]

for row_id, desc in cat1_deletes:
    actions.append(('DELETE', f'Cat1: {desc}',
                    "DELETE FROM charter_payments WHERE id = %s", (row_id,)))

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 2 — Insert missing LMS negative/reversal rows
# ─────────────────────────────────────────────────────────────────────────────
# LMS records reversals/NSF/corrections as negative Payment.Amount rows.
# These were never imported into almsdata.

cat2_inserts = [
    # (reserve_no, amount, payment_date, payment_method, lms_key, note)
    ('003959', -867.50, '2011-08-22', 'check',         '0004844', 'Hamm reversal'),
    ('012903', -552.00, '2017-08-22', 'credit_card',   '0014115', 'Ermel reversal'),
    ('013966',  -70.50, '2018-07-27', 'credit_card',   '0015076', 'Vandijk adjustment'),
    ('013044',  -26.25, '2017-04-21', 'credit_card',   '0013784', 'Sawyer adjustment'),
    ('012334',   -6.00, '2017-01-09', 'check',         '0013546', 'Progressive Waste adj'),
    ('009000', -114.99, '2014-03-27', 'credit_card',   '0009506', 'Neufeld reversal'),
    ('009034', -100.00, '2014-01-30', 'cash',          '0009291', 'Cash/Credit adj'),
    ('003553', -189.75, '2010-04-20', 'credit_card',   '0003086', 'Royal One reversal'),
    ('006504', -384.99, '2012-07-20', 'check',         '0006281', 'Little reversal'),
    ('007571', -500.00, '2013-10-25', 'check',         '0008751', 'Armstrong reversal'),
    ('011300', -105.00, '2015-06-24', 'credit_card',   '0011662', 'Whitetail adjustment'),
    ('007223',   -0.10, '2012-12-28', 'check',         '0007311', 'Hildereth rounding adj'),
    ('009583',-1760.00, '2014-07-02', 'unknown',       '0009982', 'Papp full reversal'),
]

INSERT_SQL = """
    INSERT INTO charter_payments
        (charter_id, amount, payment_date, payment_method, payment_key, source, client_name)
    VALUES (%s, %s, %s, %s, %s, 'lms_negative_import', %s)
"""
for res, amt, dt, meth, key, note in cat2_inserts:
    # Look up client name from charters
    cur.execute("SELECT client_display_name FROM charters WHERE reserve_number = %s LIMIT 1", (res,))
    row = cur.fetchone()
    client = row['client_display_name'] if row else ''
    actions.append(('INSERT', f'Cat2: {res} {note} {amt}',
                    INSERT_SQL, (res, amt, dt, meth, key, client)))

# 013060 Alkins: LMS net=$0 (200 - 200), ALMS net=$200 (has $200, -$200, $200 = +$200)
# ALMS has 3 rows: id=15378 (-$200 CRR), id=14945 ($200 CRR), id=14965 ($200 CRR)
# Should be: one $200 + one -$200 = $0 net.  Delete the extra $200 positive (id=14965)
actions.append(('DELETE', 'Cat2/Cat3: 013060 Alkins extra +$200 CRR row id=14965',
                "DELETE FROM charter_payments WHERE id = %s", (14965,)))

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 3 — Delete stray / wrong rows
# ─────────────────────────────────────────────────────────────────────────────
# 013878 Cameron: has duplicate $3.20 from LMS_IMPORT id=26308 (already in backfill id=27238)
# and a fix_script $264.60 id=25119 that has no LMS equivalent
cat3_deletes = [
    (26308, '013878 Cameron $3.20 LMS_IMPORT dup of backfill id=27238'),
    (25119, '013878 Cameron $264.60 fix_script — no LMS equivalent'),
]
# 006242 Short: ALMS $250 CRR id=6450 has no LMS basis (LMS only has $540)
cat3_deletes.append((6450,  '006242 Short $250.00 CRR — no LMS basis'))
# 014013 Busch: ALMS $225 CRR id=16186 has no LMS basis (LMS has $500+$784+$216)
cat3_deletes.append((16186, '014013 Busch $225.00 CRR — no LMS basis'))
# 007244 Buller: ALMS $82.50 CRR id=7726 has no LMS basis (LMS only has $480)
cat3_deletes.append((7726,  '007244 Buller $82.50 CRR — no LMS basis'))
# 012224 McKenna: $50 credit_card CRR id=24174 is a dup of the $50 bank_transfer id=11533
cat3_deletes.append((24174, '012224 McKenna $50.00 credit_card CRR dup of id=11533'))
# 002263 Sutyla: $4.29 CRR id=2846 has no LMS basis (LMS has $205+$204.50)
cat3_deletes.append((2846,  '002263 Sutyla $4.29 CRR — no LMS basis'))
# 003485 Mitten: $0.06 CRR id=3109 has no LMS basis
cat3_deletes.append((3109,  '003485 Mitten $0.06 CRR — no LMS basis'))

for row_id, desc in cat3_deletes:
    actions.append(('DELETE', f'Cat3: {desc}',
                    "DELETE FROM charter_payments WHERE id = %s", (row_id,)))

# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY 4 — Insert missing payments (in LMS but never in ALMS)
# ─────────────────────────────────────────────────────────────────────────────
cat4_inserts = [
    # Gerein 014286 — 3 payments never imported
    ('014286',  200.00, '2018-12-08', 'check', '0015464', 'Gerein deposit'),
    ('014286', 1159.50, '2018-12-21', 'check', '0015504', 'Gerein balance'),
    ('014286',  342.00, '2019-01-03', 'check', '0015507', 'Gerein final'),
    # Abel 012574 — 2 payments never imported
    ('012574',  205.00, '2016-06-28', 'check', '0013040', 'Abel deposit'),
    ('012574',  497.13, '2016-07-20', 'check', '0013112', 'Abel balance'),
    # Sloat 001918
    ('001918',  205.00, '2008-03-29', 'check', '0000985', 'Sloat deposit'),
    # Scott 006157 — first $200 missing
    ('006157',  200.00, '2012-05-03', 'check', '0005854', 'Scott deposit'),
    # Whitelaw 006824 — second installment missing
    ('006824',   82.50, '2012-12-28', 'check', '0007306', 'Whitelaw balance'),
    # Uniglobe 013353 — second $150.41 missing
    ('013353',  150.41, '2017-10-12', 'credit_card', '0014268', 'Uniglobe balance'),
    # Brown 010170 — deposit missing ($75 on 2014-10-15, reserve date 2016)
    ('010170',   75.00, '2014-10-15', 'check', '0010457', 'Brown deposit'),
    # Gibsons 006493 — first payment missing
    ('006493',  568.53, '2012-07-19', 'check', '0006269', 'Gibsons first'),
    # Brothers 006063 — second $250 missing
    ('006063',  250.00, '2012-04-17', 'check', '0005784', 'Brothers balance'),
    # Campkin 001995 — 2 of 4 $169.40 payments missing
    ('001995',  169.40, '2008-06-30', 'check', '0001250', 'Campkin pmt3'),
    ('001995',  169.40, '2008-06-30', 'check', '0001251', 'Campkin pmt4'),
    # VNO 004001
    ('004001',   51.56, '2010-10-26', 'check', '0003719', 'VNO balance'),
    # Arrow Limo 006729 — $160 on 2012-10-11 missing
    ('006729',  160.00, '2012-10-11', 'check', '0006767', 'Arrow Limo pmt'),
]

for res, amt, dt, meth, key, note in cat4_inserts:
    cur.execute("SELECT client_display_name FROM charters WHERE reserve_number = %s LIMIT 1", (res,))
    row = cur.fetchone()
    client = row['client_display_name'] if row else ''
    actions.append(('INSERT', f'Cat4: {res} {note} ${amt}',
                    INSERT_SQL, (res, amt, dt, meth, key, client)))

# ─────────────────────────────────────────────────────────────────────────────
# Execute
# ─────────────────────────────────────────────────────────────────────────────
deletes  = [a for a in actions if a[0] == 'DELETE']
inserts  = [a for a in actions if a[0] == 'INSERT']

print(f"Actions planned: {len(actions)} total  ({len(deletes)} deletes, {len(inserts)} inserts)")
print(f"DRY_RUN = {DRY_RUN}\n")

for action, desc, sql, params in actions:
    print(f"  [{action}] {desc}")

if not DRY_RUN:
    print("\nApplying ...")
    for action, desc, sql, params in actions:
        cur.execute(sql, params)
    pg.commit()
    print(f"Done. {len(actions)} changes committed.")
else:
    print("\n(dry run — no changes made)")

pg.close()
