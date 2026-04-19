"""
Backfill receipts for 73 unmatched banking debit transactions.
All transactions from account 0228362, period 2016-2018.
Run with DRY_RUN=True to preview, then set False to apply.
"""
import psycopg2

DRY_RUN = False

CONN = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')

# Vendor account mapping:  canonical_vendor -> (account_id, gl_code, category)
VENDOR_MAP = {
    'OWNER WITHDRAWAL':    (227,  '3100', 'owner_draw'),
    "RUN'N ON EMPTY":      (124,  '5110', 'fuel'),
    'CAVALCADE AUTO':      (None, '5120', 'vehicle_maintenance'),
    'LIQUOR BARN':         (91,   '5116', 'client_amenities'),
    'NORTHLAND RADIATOR':  (None, '5120', 'vehicle_maintenance'),
    'BOSTON PIZZA':        (263,  '6100', 'staff_meals'),
    'CINEPLEX':            (153,  '5860', 'supplies_general'),
    'RED DEER REGISTRIES': (119,  '5140', 'vehicle_registration'),
    'AUTOMOTIVE UNIVERSE': (None, '5120', 'vehicle_maintenance'),
    'GREGG DISTRIBUTORS':  (None, '5860', 'supplies_general'),
    'SOBEYS':              (129,  '5116', 'client_amenities'),
    'STAPLES':             (143,  '5420', 'office_supplies'),
    'PLENTY OF LIQUOR':    (116,  '5116', 'client_amenities'),
    'SAVE ON FOODS':       (146,  '5116', 'client_amenities'),
    'WALMART':             (137,  '5860', 'supplies_general'),
    'PHOENIX BUFFET':      (1474, '6100', 'staff_meals'),
    'KFC':                 (1476, '6100', 'staff_meals'),
    'EAST SIDE MARIO':     (None, '6100', 'staff_meals'),
    'ONE STOP LICENCE':    (None, '5140', 'vehicle_registration'),
    'THE TIRE GARAGE':     (247,  '5120', 'vehicle_maintenance'),
    'SUPER CLEAN 2':       (157,  '5120', 'vehicle_maintenance'),
    'WCB':                 (28,   '5220', 'employee_benefits'),
}

# Banking transactions to create receipts for
TRANSACTIONS = [
    (100367, '2016-07-29',  500.00, 'BANK WITHDRAWAL',    'OWNER WITHDRAWAL'),
    (100368, '2016-12-21',   50.00, 'RUN\'N ON EMPTY',    "RUN'N ON EMPTY"),
    (100387, '2017-06-12', 1995.70, 'CAVALCADE AUTO',      'CAVALCADE AUTO'),
    (98292,  '2017-06-16',   47.00, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98291,  '2017-06-16',   81.91, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98324,  '2017-06-23',   28.54, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98319,  '2017-06-23',   86.93, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98317,  '2017-06-23',   89.77, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98316,  '2017-06-23',   97.76, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98323,  '2017-06-23',  171.87, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98318,  '2017-06-23',  173.62, 'LIQUOR BARN',         'LIQUOR BARN'),
    (100404, '2017-06-29',  800.00, 'NORTHLAND RADIATOR',  'NORTHLAND RADIATOR'),
    (100405, '2017-07-04',   81.57, 'BOSTON PIZZA',        'BOSTON PIZZA'),
    (98339,  '2017-07-04',   93.64, 'LIQUOR BARN',         'LIQUOR BARN'),
    (100408, '2017-07-13',   23.98, 'CINEPLEX',            'CINEPLEX'),
    (100409, '2017-07-13',   35.11, 'CINEPLEX',            'CINEPLEX'),
    (98384,  '2017-07-14',    7.45, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98386,  '2017-07-14',   73.83, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98385,  '2017-07-14',  134.44, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98387,  '2017-07-14',  182.93, 'LIQUOR BARN',         'LIQUOR BARN'),
    (100416, '2017-07-18',  597.00, 'RED DEER REGISTRIES', 'RED DEER REGISTRIES'),
    (98413,  '2017-07-21',   28.96, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98417,  '2017-07-21',  118.02, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98418,  '2017-07-21',  118.46, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98414,  '2017-07-21',  244.22, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98428,  '2017-07-24',   22.69, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98423,  '2017-07-24',   33.02, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98441,  '2017-07-28',  139.14, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98492,  '2017-08-14',   21.78, 'LIQUOR BARN',         'LIQUOR BARN'),
    (100438, '2017-08-17', 2000.00, 'AUTOMOTIVE UNIVERSE', 'AUTOMOTIVE UNIVERSE'),
    (100449, '2017-09-25',  371.80, 'RED DEER REGISTRIES', 'RED DEER REGISTRIES'),
    (98686,  '2017-10-10',   68.41, 'LIQUOR BARN',         'LIQUOR BARN'),
    (98704,  '2017-10-16',   54.56, 'LIQUOR BARN',         'LIQUOR BARN'),
    (100456, '2017-10-20',   77.45, 'RED DEER REGISTRIES', 'RED DEER REGISTRIES'),
    (100455, '2017-10-20',  153.45, 'RED DEER REGISTRIES', 'RED DEER REGISTRIES'),
    (100458, '2017-10-23',   92.45, 'RED DEER REGISTRIES', 'RED DEER REGISTRIES'),
    (100457, '2017-10-23',  262.50, 'GREGG DISTRIBUTORS',  'GREGG DISTRIBUTORS'),
    (100491, '2018-01-09',   39.53, 'SOBEYS',              'SOBEYS'),
    (100494, '2018-01-10',   45.80, 'STAPLES',             'STAPLES'),
    (100533, '2018-01-19',   60.00, 'PLENTY OF LIQUOR',    'PLENTY OF LIQUOR'),
    (100578, '2018-01-29',   32.51, 'SAVE ON FOODS',       'SAVE ON FOODS'),
    (100590, '2018-01-30',   27.92, 'WALMART',             'WALMART'),
    (100738, '2018-03-02',   29.30, 'PHOENIX BUFFET',      'PHOENIX BUFFET'),
    (100736, '2018-03-02',  121.12, 'WALMART',             'WALMART'),
    (100748, '2018-03-05',   37.58, 'SAVE ON FOODS',       'SAVE ON FOODS'),
    (100766, '2018-03-08',   63.68, 'SAVE ON FOODS',       'SAVE ON FOODS'),
    (100855, '2018-03-26',  111.28, 'KFC',                 'KFC'),
    (100875, '2018-03-29',   34.30, 'PHOENIX BUFFET',      'PHOENIX BUFFET'),
    (100888, '2018-04-02',    5.24, 'SOBEYS',              'SOBEYS'),
    (100909, '2018-04-04',   62.99, 'STAPLES',             'STAPLES'),
    (100908, '2018-04-04',   78.03, 'SOBEYS',              'SOBEYS'),
    (100938, '2018-04-12',   43.85, 'PHOENIX BUFFET',      'PHOENIX BUFFET'),
    (100987, '2018-04-24',  155.84, 'SOBEYS',              'SOBEYS'),
    (101030, '2018-05-02',   49.51, 'SOBEYS',              'SOBEYS'),
    (101094, '2018-05-14',   54.93, 'EAST SIDE MARIO',     'EAST SIDE MARIO'),
    (101148, '2018-05-28',   23.85, 'PHOENIX BUFFET',      'PHOENIX BUFFET'),
    (101154, '2018-05-28',  224.86, 'STAPLES',             'STAPLES'),
    (101156, '2018-05-29',   64.30, 'EAST SIDE MARIO',     'EAST SIDE MARIO'),
    (101184, '2018-06-04',   26.44, 'KFC',                 'KFC'),
    (101207, '2018-06-07',   49.40, 'ONE STOP LICENCE',    'ONE STOP LICENCE'),
    (101226, '2018-06-11',   98.23, 'STAPLES',             'STAPLES'),
    (101232, '2018-06-12',   49.19, 'STAPLES',             'STAPLES'),
    (101257, '2018-06-18',   87.91, 'STAPLES',             'STAPLES'),
    (101267, '2018-06-20',   32.50, 'THE TIRE GARAGE',     'THE TIRE GARAGE'),
    (101280, '2018-06-22',   41.70, 'PHOENIX BUFFET',      'PHOENIX BUFFET'),
    (101305, '2018-06-29',   61.16, 'SOBEYS',              'SOBEYS'),
    (101348, '2018-07-03',   14.65, 'PHOENIX BUFFET',      'PHOENIX BUFFET'),
    (101333, '2018-07-03',   31.30, 'PHOENIX BUFFET',      'PHOENIX BUFFET'),
    (101359, '2018-07-09',   16.79, 'SOBEYS',              'SOBEYS'),
    (101432, '2018-07-25',  645.58, 'STAPLES',             'STAPLES'),
    (101520, '2018-08-07',  149.81, 'SOBEYS',              'SOBEYS'),
    (101564, '2018-08-15',  161.96, 'SOBEYS',              'SOBEYS'),
    (101628, '2018-08-24',   10.00, 'SUPER CLEAN 2',       'SUPER CLEAN 2'),
]

INSERT_SQL = """
INSERT INTO receipts (
    receipt_date, vendor_name, canonical_vendor, gross_amount,
    payment_method, banking_transaction_id, receipt_source,
    vendor_account_id, gl_account_code, category, description,
    created_at
)
VALUES (
    %s, %s, %s, %s,
    'Bank Debit', %s, 'banking_backfill_20260410',
    %s, %s, %s, %s,
    NOW()
)
RETURNING receipt_id;
"""

UPDATE_BANKING_SQL = """
UPDATE banking_transactions
SET reconciliation_status = 'reconciled',
    reconciled_receipt_id = %s,
    reconciled_at = NOW()
WHERE transaction_id = %s;
"""

def main():
    conn = psycopg2.connect(**CONN)
    conn.autocommit = False
    cur = conn.cursor()

    inserted = 0
    total_amount = 0.0

    print(f"{'DRY RUN' if DRY_RUN else 'LIVE RUN'} — {len(TRANSACTIONS)} transactions")
    print(f"{'tx_id':>8}  {'date':>12}  {'amount':>10}  {'vendor':<30}  {'gl':>6}  {'receipt_id'}")
    print("-" * 90)

    for tx_id, date, amount, bank_desc, canonical in TRANSACTIONS:
        vendor_info = VENDOR_MAP.get(canonical)
        if vendor_info is None:
            print(f"  WARNING: no vendor map for '{canonical}' tx={tx_id} — SKIPPING")
            continue

        acct_id, gl_code, category = vendor_info

        if not DRY_RUN:
            cur.execute(INSERT_SQL, (
                date, bank_desc, canonical, amount,
                tx_id,
                acct_id, gl_code, category, bank_desc,
            ))
            receipt_id = cur.fetchone()[0]
            cur.execute(UPDATE_BANKING_SQL, (receipt_id, tx_id))
        else:
            receipt_id = '(DRY)'

        print(f"  {tx_id:>8}  {date}  {amount:>10.2f}  {canonical:<30}  {gl_code:>6}  {receipt_id}")
        inserted += 1
        total_amount += amount

    print("-" * 90)
    print(f"  {'TOTAL':>8}  {'':>12}  {total_amount:>10.2f}  {inserted} receipts")

    if not DRY_RUN:
        conn.commit()
        print("\nCOMMITTED.")
    else:
        conn.rollback()
        print("\n(Dry run — no changes made. Set DRY_RUN=False to apply.)")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
