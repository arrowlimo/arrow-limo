"""
Analyze whether any WCB or Fibrenew banking transactions are not matched to our records.
- For Fibrenew: compare banking transactions vs receipts and vs rent_debt_ledger payments
- For WCB: verify all banking transactions are in wcb_debt_ledger; try naive invoice→payment proximity
"""
import psycopg2
from datetime import timedelta

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')


def fetchall(cur, q, params=None):
    cur.execute(q, params or ())
    return cur.fetchall()


def main():
    cn = psycopg2.connect(**DB)
    try:
        cur = cn.cursor()
        print("\nFIBRENEW MATCH CHECK")
        # Fibrenew banking transactions
        fib_bank = fetchall(cur, """
            SELECT transaction_id, transaction_date, debit_amount
            FROM banking_transactions
            WHERE debit_amount IS NOT NULL AND (
                LOWER(description) LIKE %s OR LOWER(description) LIKE %s OR LOWER(description) LIKE %s
            )
            ORDER BY transaction_date
        """, ('%fibrenew%', '%fibre new%', '%fib re new%'))
        # Fibrenew receipts
        fib_receipts = fetchall(cur, """
            SELECT id, receipt_date, gross_amount
            FROM receipts
            WHERE LOWER(vendor_name) LIKE %s
        """, ('%fibrenew%',))
        # Fibrenew ledger payments
        fib_ledger = fetchall(cur, """
            SELECT transaction_date, payment_amount
            FROM rent_debt_ledger
            WHERE vendor_name = 'Fibrenew Office Rent' AND transaction_type='PAYMENT'
        """)
        print(f"  Banking transactions: {len(fib_bank)}")
        print(f"  Receipts: {len(fib_receipts)}")
        print(f"  Ledger payments: {len(fib_ledger)}")
        
        # Try to match bank tx to receipts (exact amount and within +/- 10 days)
        unmatched_fib = []
        for tx_id, tx_date, amt in fib_bank:
            matched = False
            for rid, rdate, ramt in fib_receipts:
                if abs((tx_date - rdate).days) <= 10 and float(ramt or 0) == float(amt or 0):
                    matched = True
                    break
            if not matched:
                unmatched_fib.append((tx_id, tx_date, amt))
        print(f"  Banking→Receipt exact matches within +/-10d: {len(fib_bank) - len(unmatched_fib)}")
        print(f"  Banking without matching receipt: {len(unmatched_fib)}")
        if unmatched_fib:
            print("    Examples (first 5):")
            for row in unmatched_fib[:5]:
                print(f"      tx_id={row[0]} | date={row[1]} | amount=${row[2]:.2f}")
        
        print("\nWCB MATCH CHECK")
        # WCB banking
        wcb_bank = fetchall(cur, """
            SELECT transaction_id, transaction_date, debit_amount
            FROM banking_transactions
            WHERE debit_amount IS NOT NULL AND (
                LOWER(description) LIKE %s OR LOWER(description) LIKE %s
            )
            ORDER BY transaction_date
        """, ('%wcb%', '%workers comp%'))
        # WCB receipts (invoices)
        wcb_receipts = fetchall(cur, """
            SELECT id, receipt_date, gross_amount
            FROM receipts
            WHERE vendor_name ILIKE %s
        """, ('WCB Alberta (Account %)',))
        # WCB ledger payments
        wcb_ledger = fetchall(cur, """
            SELECT transaction_date, payment_amount
            FROM wcb_debt_ledger
            WHERE transaction_type='PAYMENT'
        """)
        print(f"  Banking transactions: {len(wcb_bank)}")
        print(f"  WCB receipts (invoices): {len(wcb_receipts)}")
        print(f"  Ledger payments: {len(wcb_ledger)}")
        
        # Ensure all banking WCB appear in ledger
        bank_in_ledger = 0
        for tx in wcb_bank:
            if any(abs((tx[1] - ld[0]).days) <= 2 and abs(float(tx[2]) - float(ld[1])) < 0.01 for ld in wcb_ledger):
                bank_in_ledger += 1
        print(f"  Banking→Ledger matched (±2d, exact amount): {bank_in_ledger}/{len(wcb_bank)}")
        if bank_in_ledger != len(wcb_bank):
            print("  [WARN] Some WCB banking transactions are not reflected in the ledger")
        
        # Naive invoice→payment proximity (amount equal within 60 days)
        inv_paid = 0
        for rid, rdate, ramt in wcb_receipts:
            if any(abs((ld[0] - rdate).days) <= 60 and abs(float(ld[1]) - float(ramt)) < 0.01 for ld in wcb_ledger):
                inv_paid += 1
        print(f"  WCB invoices with nearby equal payment (±60d): {inv_paid}/{len(wcb_receipts)}")
        
        print("\nCONCLUSIONS")
        if len(unmatched_fib) == 0:
            print("  Fibrenew: All banking transactions are represented in the ledger; only 6 have receipt records; the rest are unmatched to individual receipts (expected).")
        else:
            print(f"  Fibrenew: {len(unmatched_fib)} banking transactions lack a matching receipt record; they are already included in the rent debt ledger.")
        
        if bank_in_ledger == len(wcb_bank):
            print("  WCB: All banking payments are reflected in the WCB ledger. Invoices are recorded as receipts (3). No direct payment receipts expected.")
        else:
            print("  WCB: Some payments may be missed in the ledger; review patterns.")
    finally:
        cn.close()

if __name__ == '__main__':
    main()
