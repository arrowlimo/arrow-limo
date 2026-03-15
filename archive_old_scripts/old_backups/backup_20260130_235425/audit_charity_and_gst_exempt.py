import re
import psycopg2
from decimal import Decimal

DSN = dict(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

CHARITY_KEYWORDS = [
  # High-signal words that indicate donated/promo/trade activity
  'promo', 'promotion', 'trade', 'donation', 'donate', 'auction', 'silent auction',
  'certificate', 'gift certificate', 'voucher', 'prize', 'comp', 'complimentary',
  'gratis', 'pro bono', 'sponsorship'
]
CLIENT_HINTS = [
  # Org types commonly charitable; schools are intentionally excluded per business rule
  'foundation', 'charity', 'church', 'temple', 'mosque', 'synagogue',
  'society', 'association', 'non-profit', 'nonprofit', 'hospital', 'clinic',
  'rotary', 'lions'
]

# Explicit client-name exclusions (youth development/schools are not charity by policy unless promo/trade keywords present)
EXCLUDE_CLIENTS = [
  'aspen heights school',
  'st joseph highschool',
  'st. joseph highschool',
  'st joseph school',
  'st. joseph school'
]

KW_SQL = " | ".join([k.replace("'", "''") for k in CHARITY_KEYWORDS])
CL_SQL = " | ".join([k.replace("'", "''") for k in CLIENT_HINTS])


def fmt_money(x):
    if x is None:
        return '$0.00'
    if isinstance(x, Decimal):
        x = float(x)
    return f"${x:,.2f}"

SUMMARY_SQL = f"""
WITH c AS (
  SELECT ch.charter_id, ch.reserve_number, ch.charter_date, ch.status,
         ch.client_id, cl.client_name,
         ch.rate,
         COALESCE(ch.airport_dropoff_price,0) + COALESCE(ch.airport_pickup_price,0) AS airport_fees,
         ch.beverage_service_required,
         ch.booking_notes, ch.client_notes, ch.notes
  FROM charters ch
  LEFT JOIN clients cl USING (client_id)
  WHERE COALESCE(ch.status,'') NOT IN ('cancelled','Cancelled')
)
, tagged AS (
  SELECT *,
    LOWER(COALESCE(client_name,'')) ~* '(aspen heights school|st\\.? joseph (?:highschool|school))' AS is_school_excluded,
    (
      (COALESCE(booking_notes,'') ~* '(promo|promotion|trade|donation|donate|auction|silent auction|certificate|gift certificate|voucher|prize|comp|complimentary|gratis|pro bono|sponsorship)') OR
      (COALESCE(client_notes,'')  ~* '(promo|promotion|trade|donation|donate|auction|silent auction|certificate|gift certificate|voucher|prize|comp|complimentary|gratis|pro bono|sponsorship)') OR
      (COALESCE(notes,'')         ~* '(promo|promotion|trade|donation|donate|auction|silent auction|certificate|gift certificate|voucher|prize|comp|complimentary|gratis|pro bono|sponsorship)') OR
      (COALESCE(client_name,'')   ~* '(foundation|charity|church|temple|mosque|synagogue|society|association|non-profit|nonprofit|hospital|clinic|rotary|lions)')
    ) AND NOT (LOWER(COALESCE(client_name,'')) ~* '(aspen heights school|st\\.? joseph (?:highschool|school))') AS is_charity_hint
  FROM c
)
, pay AS (
  SELECT charter_id,
         COUNT(*) AS pay_count,
         COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0) AS pay_total,
         COALESCE(SUM(CASE WHEN amount<0 THEN amount ELSE 0 END),0) AS refunds_total
  FROM payments
  GROUP BY charter_id
)
SELECT 
  COUNT(*) FILTER (WHERE is_charity_hint) AS suspected_charity_count,
  COALESCE(SUM(rate) FILTER (WHERE is_charity_hint),0) AS suspected_charity_base,
  COALESCE(SUM(airport_fees) FILTER (WHERE is_charity_hint),0) AS suspected_charity_airport,
  COALESCE(SUM(pay_total) FILTER (WHERE is_charity_hint),0) AS suspected_charity_payments,
  COALESCE(SUM(refunds_total) FILTER (WHERE is_charity_hint),0) AS suspected_charity_refunds
FROM tagged t
LEFT JOIN pay p USING (charter_id);
"""

SAMPLE_SQL = f"""
WITH c AS (
  SELECT ch.charter_id, ch.reserve_number, ch.charter_date, ch.status,
         ch.client_id, cl.client_name,
         ch.rate,
         COALESCE(ch.airport_dropoff_price,0) + COALESCE(ch.airport_pickup_price,0) AS airport_fees,
         ch.beverage_service_required,
         ch.booking_notes, ch.client_notes, ch.notes
  FROM charters ch
  LEFT JOIN clients cl USING (client_id)
  WHERE COALESCE(ch.status,'') NOT IN ('cancelled','Cancelled')
)
, tagged AS (
  SELECT *,
    (
      (COALESCE(booking_notes,'') ~* '(promo|promotion|trade|donation|donate|auction|silent auction|certificate|gift certificate|voucher|prize|comp|complimentary|gratis|pro bono|sponsorship)') OR
      (COALESCE(client_notes,'')  ~* '(promo|promotion|trade|donation|donate|auction|silent auction|certificate|gift certificate|voucher|prize|comp|complimentary|gratis|pro bono|sponsorship)') OR
      (COALESCE(notes,'')         ~* '(promo|promotion|trade|donation|donate|auction|silent auction|certificate|gift certificate|voucher|prize|comp|complimentary|gratis|pro bono|sponsorship)') OR
      (COALESCE(client_name,'')   ~* '(foundation|charity|church|temple|mosque|synagogue|society|association|non-profit|nonprofit|hospital|clinic|rotary|lions)')
    ) AND NOT (LOWER(COALESCE(client_name,'')) ~* '(aspen heights school|st\\.? joseph (?:highschool|school))') AS is_charity_hint
  FROM c
)
SELECT 
  t.charter_date, t.reserve_number, t.client_name, t.rate, t.airport_fees,
  t.beverage_service_required, LEFT(COALESCE(t.booking_notes,''),120) AS booking_excerpt,
  LEFT(COALESCE(t.client_notes,''),120) AS client_excerpt,
  LEFT(COALESCE(t.notes,''),120) AS notes_excerpt,
  p.pay_count, p.pay_total
FROM tagged t
LEFT JOIN (
  SELECT charter_id, COUNT(*) AS pay_count, COALESCE(SUM(amount),0) AS pay_total
  FROM payments GROUP BY charter_id
) p ON p.charter_id = t.charter_id
WHERE t.is_charity_hint
ORDER BY t.charter_date DESC
LIMIT 50;
"""

PAY_NOTE_SQL = """
SELECT COUNT(*) AS payment_note_hits, COALESCE(SUM(amount),0) AS total
FROM payments
WHERE COALESCE(notes,'') ~* '(charity|donation|auction|certificate)';
"""


def main():
    conn = psycopg2.connect(**DSN)
    cur = conn.cursor()

    print('='*80)
    print('Charity / GST-exempt audit (keyword-based indicators)')
    print('='*80)

    cur.execute(SUMMARY_SQL)
    sc = cur.fetchone()
    print('Suspected charity runs (by notes/client name hints):')
    print(f"  Count: {sc[0]:,}")
    print(f"  Base rate (sum): {fmt_money(sc[1])}")
    print(f"  Airport fees (sum): {fmt_money(sc[2])}")
    print(f"  Payments (sum): {fmt_money(sc[3])}")
    print(f"  Refunds (sum): {fmt_money(sc[4])}")

    print('\nPayment notes mentioning charity/auction/certificate:')
    cur.execute(PAY_NOTE_SQL)
    pn = cur.fetchone()
    print(f"  Payments matched: {pn[0]:,} | Amount: {fmt_money(pn[1])}")

    print('\nRecent suspected charity samples:')
    cur.execute(SAMPLE_SQL)
    rows = cur.fetchall()
    print(f"{'date':<12} {'res':<8} {'client':<28} {'rate':>10} {'airport':>10} {'bev':>4} {'notes':<40}")
    print('-'*110)
    for r in rows:
        date, res, client, rate, airport, bev, b_ex, c_ex, n_ex, pc, pt = r
        note = (b_ex or c_ex or n_ex or '')[:40]
        print(f"{str(date):<12} {str(res or ''):<8} {str(client or '')[:28]:<28} {fmt_money(rate):>10} {fmt_money(airport):>10} {('Y' if bev else 'N'):>4} {note:<40}")

    print('\nGuidance (accounting & GST treatment):')
    print('- If we donate the base charter as a prize/certificate (no consideration received for base):')
    print('  • Treat the donated base as promotional/charitable expense at fair value (no revenue).')
    print('  • GST is charged only on amounts actually paid by the redeemer (extras like beverages, overage, upgrades).')
    print('  • Calculate GST using included model on extras collected (gst = gross * r/(1+r)).')
    print('- If a partial discount (we issue our own coupon): GST applies on the discounted price actually paid.')
    print('- Keep certificate metadata: charity_org, certificate_code, donation_value, redemption_date.')

    conn.close()
    print('\nDone.')

if __name__ == '__main__':
    main()
