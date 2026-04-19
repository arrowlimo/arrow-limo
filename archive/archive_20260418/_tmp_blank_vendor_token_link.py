import re
import psycopg2
from psycopg2.extras import RealDictCursor

STOPWORDS = {
    'POINT','OF','SALE','INTERAC','RETAIL','PURCHASE','BRANCH','TRANSACTION','SERVICE','CHARGE',
    'FULL','SELF','OVERDRAFT','INTEREST','ELECTRONIC','FUNDS','TRANSFER','NETWORK','FEE',
    'ATM','CANADA','GAB','PAYMENT','DEBIT','CREDIT','CHEQUE','WITHDRAWAL','MOBILE','DEPOSIT'
}

merchant_pat = re.compile(r"[A-Z][A-Z'&.-]{2,}")
exclude_pat = re.compile(r"(transfer|e-?transfer|payment\s+received|deposit|refund|reversal|nsf\s*reversal|cash withdrawal|atm withdrawal|owner draw)", re.IGNORECASE)

def extract_tokens(desc: str):
    toks = []
    for t in merchant_pat.findall((desc or '').upper()):
        if t.isdigit() or t in STOPWORDS:
            continue
        if len(t) < 3:
            continue
        toks.append(t)
    # unique preserve order
    out=[]
    seen=set()
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:4]


def run(apply=False):
    conn = psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, description
        FROM banking_transactions
        WHERE COALESCE(debit_amount,0) > 0
          AND receipt_id IS NULL
          AND (vendor_extracted IS NULL OR vendor_extracted='')
        ORDER BY transaction_date, transaction_id
        """)
        txs = cur.fetchall()

        matches = []
        for tx in txs:
            desc = tx['description'] or ''
            if exclude_pat.search(desc):
                continue
            tokens = extract_tokens(desc)
            if not tokens:
                continue

            # get very small candidate pool first by amount/date
            cur.execute("""
            SELECT receipt_id, vendor_name, description
            FROM receipts
            WHERE banking_transaction_id IS NULL
              AND COALESCE(gross_amount,0) > 0
              AND ABS(COALESCE(gross_amount,0) - %s) < 0.01
              AND receipt_date BETWEEN (%s::date - INTERVAL '2 day') AND (%s::date + INTERVAL '2 day')
            LIMIT 20
            """, (tx['debit_amount'], tx['transaction_date'], tx['transaction_date']))
            candidates = cur.fetchall()
            token_matches = []
            for c in candidates:
                hay = f"{(c['vendor_name'] or '').upper()} {(c['description'] or '').upper()}"
                if any(tok in hay for tok in tokens):
                    token_matches.append(c)

            if len(token_matches) == 1:
                rid = token_matches[0]['receipt_id']
                matches.append((tx['transaction_id'], rid))

        if apply and matches:
            for tx_id, rid in matches:
                cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s AND banking_transaction_id IS NULL", (tx_id, rid))
                cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s AND receipt_id IS NULL", (rid, tx_id))
            conn.commit()
        else:
            conn.rollback()

        print('apply_mode', apply)
        print('candidate_transactions', len(txs))
        print('safe_unique_token_matches', len(matches))
        return len(matches)
    finally:
        cur.close()
        conn.close()

m = run(apply=False)
print('---')
if m > 0:
    run(apply=True)
else:
    print('nothing to apply')
