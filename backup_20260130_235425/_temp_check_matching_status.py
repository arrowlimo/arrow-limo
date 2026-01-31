import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("=== EMAIL EVENTS SUMMARY ===")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE event_type ILIKE '%square%') as square_events,
        COUNT(*) FILTER (WHERE banking_transaction_id IS NOT NULL) as matched_banking
    FROM email_financial_events
""")
result = cur.fetchone()
print(f"Total email events: {result[0]:,}")
print(f"Square events: {result[1]:,}")
print(f"Matched to banking: {result[2]:,}")

print("\n=== SQUARE PAYMENT MATCHING STATUS ===")
cur.execute("""
    SELECT 
        COUNT(*) as total_square_payments,
        COUNT(banking_transaction_id) as with_banking,
        SUM(amount) as total_amount,
        SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount
    FROM payments
    WHERE square_transaction_id IS NOT NULL
""")
result = cur.fetchone()
total, with_banking, total_amt, matched_amt = result
match_pct = (with_banking / total * 100) if total > 0 else 0

print(f"Total Square payments: {total:,}")
print(f"Matched to banking: {with_banking:,} ({match_pct:.1f}%)")
print(f"Unmatched: {total - with_banking:,} ({100-match_pct:.1f}%)")
print(f"Total amount: ${total_amt:,.2f}")
print(f"Matched amount: ${matched_amt:,.2f}")

print("\n=== CURRENT PAYMENT-BANKING MATCH RATE (ALL PAYMENTS) ===")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(banking_transaction_id) as matched,
        SUM(amount) as total_amt
    FROM payments
""")
total, matched, total_amt = cur.fetchone()
overall_pct = (matched / total * 100) if total > 0 else 0
print(f"Total payments: {total:,}")
print(f"Matched to banking: {matched:,} ({overall_pct:.1f}%)")
print(f"Total amount: ${total_amt:,.2f}")

if overall_pct >= 98:
    print(f"\n🎉 ✅ TARGET ACHIEVED: {overall_pct:.1f}% ≥ 98%")
elif overall_pct >= 90:
    print(f"\n⚠️  CLOSE TO TARGET: {overall_pct:.1f}% (Need {98-overall_pct:.1f}% more)")
else:
    print(f"\n❌ BELOW TARGET: {overall_pct:.1f}% (Need {98-overall_pct:.1f}% more)")

conn.close()
