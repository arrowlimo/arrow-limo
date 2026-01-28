"""
Fix Fibrenew receipts where GST should be included in the price (not added on top).

Actions:
1) Update six early-2019 Fibrenew invoices to use included totals and recompute GST.
   - 8487 rent: total 682.50, GST 32.50 (net 650.00)
   - 8488 utilities: total 306.17, GST 14.58 (net 291.59)
   - 8691 rent: total 682.50, GST 32.50
   - 8690 utilities: total 295.69, GST 14.08 (net 281.61)
   - 8743 rent: total 682.50, GST 32.50
   - 8744 utilities: total 254.32, GST 12.11 (net 242.21)
2) For statement-based Fibrenew receipts (FIBRENEW_STATEMENT), recompute GST from gross
   using the included-in-price rule for AB: gst = gross * 0.05 / 1.05 (rounded 2).

Dry-run by default. Use --write to apply updates.
"""
import argparse
import psycopg2
from decimal import Decimal, ROUND_HALF_UP
from psycopg2.extras import RealDictCursor

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

GST_RATE = Decimal('0.05')

# Mapping for early-2019 invoices with correct included totals and GST
EARLY_FIXES = {
    'FIBRENEW-8487': {'gross': Decimal('682.50'), 'gst': Decimal('32.50')},  # rent
    'FIBRENEW-8488': {'gross': Decimal('306.17'), 'gst': Decimal('14.58')},  # utilities
    'FIBRENEW-8691': {'gross': Decimal('682.50'), 'gst': Decimal('32.50')},  # rent
    'FIBRENEW-8690': {'gross': Decimal('295.69'), 'gst': Decimal('14.08')},  # utilities
    'FIBRENEW-8743': {'gross': Decimal('682.50'), 'gst': Decimal('32.50')},  # rent
    'FIBRENEW-8744': {'gross': Decimal('254.32'), 'gst': Decimal('12.11')},  # utilities
}

def round2(x: Decimal) -> Decimal:
    return x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def recompute_gst_included(gross: Decimal) -> Decimal:
    # gst portion when included in price: gross * r / (1+r)
    return round2(gross * GST_RATE / (Decimal('1.05')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply updates')
    args = ap.parse_args()

    with psycopg2.connect(**DB) as cn:
        with cn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1) Fix early-2019 specific invoices
            print("\nFixing early-2019 detailed invoices (included GST):")
            fixed = 0
            for ref, vals in EARLY_FIXES.items():
                cur.execute(
                    """
                    SELECT id, source_reference, receipt_date, gross_amount, gst_amount
                    FROM receipts
                    WHERE source_system = 'FIBRENEW_INVOICE' AND source_reference = %s
                    """,
                    (ref,)
                )
                rows = cur.fetchall()
                if not rows:
                    print(f"  - {ref}: not found (skip)")
                    continue
                for r in rows:
                    if r['gross_amount'] != vals['gross'] or r['gst_amount'] != vals['gst']:
                        print(f"  - Updating {r['id']} {ref}: gross {r['gross_amount']} -> {vals['gross']}, gst {r['gst_amount']} -> {vals['gst']}")
                        if args.write:
                            cur.execute(
                                """
                                UPDATE receipts
                                SET gross_amount = %s, gst_amount = %s
                                WHERE id = %s
                                """,
                                (vals['gross'], vals['gst'], r['id'])
                            )
                            fixed += 1
                    else:
                        print(f"  - {r['id']} {ref}: already correct")

            # 2) Recompute GST for Fibrenew statement receipts
            print("\nRecomputing GST on Fibrenew statement receipts (included-in-price):")
            cur.execute(
                """
                SELECT id, gross_amount, gst_amount, description
                FROM receipts
                WHERE source_system = 'FIBRENEW_STATEMENT'
                """
            )
            rows = cur.fetchall()
            stmt_fixed = 0
            for r in rows:
                new_gst = recompute_gst_included(r['gross_amount'])
                if r['gst_amount'] != new_gst:
                    print(f"  - id {r['id']}: gst {r['gst_amount']} -> {new_gst} (gross {r['gross_amount']})")
                    if args.write:
                        cur.execute(
                            """
                            UPDATE receipts SET gst_amount = %s WHERE id = %s
                            """,
                            (new_gst, r['id'])
                        )
                        stmt_fixed += 1
                else:
                    # silent when already correct to reduce noise
                    pass

            if args.write:
                print(f"\nApplied: {fixed} early-invoice updates, {stmt_fixed} statement gst recalculations.")
            else:
                print(f"\nDry-run complete. Re-run with --write to apply updates.")

if __name__ == '__main__':
    main()
