#!/usr/bin/env python3
"""Apply reserve_number linkage from email_financial_events to ETR payments"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("\n" + "="*80)
print("E-TRANSFER EMAIL MATCHING STATUS")
print("="*80)

# Check current ETR payment status
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as has_reserve,
        SUM(amount) as total_amount
    FROM payments
    WHERE payment_key LIKE 'ETR:%'
""")

total, no_res, has_res, amt = cur.fetchone()
print(f"\n📧 ETR Payments (payment_key LIKE 'ETR:%'):")
print(f"   Total: {total:,}")
print(f"   With reserve_number: {has_res:,} ({has_res/total*100:.1f}%)")
print(f"   Missing reserve_number: {no_res:,} ({no_res/total*100:.1f}%)")
print(f"   Total amount: ${amt:,.2f}")

# Check email_financial_events matching
cur.execute("""
    SELECT 
        COUNT(DISTINCT p.payment_id) as linkable,
        SUM(p.amount) as linkable_amount
    FROM payments p
    INNER JOIN email_financial_events e 
        ON e.reference_code = SUBSTRING(p.payment_key FROM 5)
    WHERE p.payment_key LIKE 'ETR:%'
    AND p.reserve_number IS NULL
    AND e.reserve_number IS NOT NULL
""")

linkable, link_amt = cur.fetchone()
print(f"\n🔗 Email Matching Available:")
print(f"   Linkable via email_financial_events: {linkable:,}")
print(f"   Linkable amount: ${link_amt:,.2f}" if link_amt else "   Linkable amount: $0.00")

if linkable == 0:
    print(f"\n✅ All ETR payments already matched or no email data available")
    cur.close()
    conn.close()
    exit(0)

# Show sample matches
cur.execute("""
    SELECT 
        p.payment_id,
        p.payment_key,
        p.amount,
        p.payment_date,
        e.reserve_number,
        e.sender_name,
        e.event_date
    FROM payments p
    INNER JOIN email_financial_events e 
        ON e.reference_code = SUBSTRING(p.payment_key FROM 5)
    WHERE p.payment_key LIKE 'ETR:%'
    AND p.reserve_number IS NULL
    AND e.reserve_number IS NOT NULL
    ORDER BY p.payment_date DESC
    LIMIT 10
""")

print(f"\n📋 Sample Matches:")
print(f"{'Pay ID':<8} {'Key':<12} {'Amount':<12} {'Pay Date':<12} {'Reserve':<10} {'Sender':<30}")
print("-"*90)
for pid, key, amt, pdate, reserve, sender, edate in cur.fetchall():
    print(f"{pid:<8} {key:<12} ${amt:<11,.2f} {str(pdate):<12} {reserve:<10} {(sender or '')[:28]:<30}")

# Apply updates
print(f"\n" + "="*80)
print("APPLYING EMAIL RESERVE NUMBER LINKAGE")
print("="*80)

cur.execute("""
    UPDATE payments p
    SET reserve_number = e.reserve_number
    FROM email_financial_events e
    WHERE e.reference_code = SUBSTRING(p.payment_key FROM 5)
    AND p.payment_key LIKE 'ETR:%'
    AND p.reserve_number IS NULL
    AND e.reserve_number IS NOT NULL
""")

updated = cur.rowcount
conn.commit()

print(f"\n✅ Updated {updated:,} ETR payments with reserve_number from email events")

# Verify final status
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) as has_reserve
    FROM payments
    WHERE payment_key LIKE 'ETR:%'
""")

total, no_res, has_res = cur.fetchone()
print(f"\n📊 Final ETR Payment Status:")
print(f"   Total: {total:,}")
print(f"   With reserve_number: {has_res:,} ({has_res/total*100:.1f}%)")
print(f"   Missing reserve_number: {no_res:,} ({no_res/total*100:.1f}%)")

# Overall 2025 status
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN reserve_number IS NULL THEN 1 END) as no_reserve
    FROM payments
    WHERE EXTRACT(YEAR FROM payment_date) = 2025
""")

total_2025, no_res_2025 = cur.fetchone()
print(f"\n📈 Overall 2025 Payment Status:")
print(f"   Total: {total_2025:,}")
print(f"   Missing reserve_number: {no_res_2025:,} ({no_res_2025/total_2025*100:.1f}%)")
print(f"   With reserve_number: {total_2025 - no_res_2025:,} ({(total_2025-no_res_2025)/total_2025*100:.1f}%)")

cur.close()
conn.close()

print("\n" + "="*80)
print("NEXT STEP: Update Square payments and other 2025 data from LMS")
print("="*80)
