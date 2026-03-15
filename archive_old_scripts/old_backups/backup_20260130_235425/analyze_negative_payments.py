#!/usr/bin/env python3
"""
Detailed analysis of the 171 negative payment amounts.
These could be refunds, chargebacks, or data entry errors.
"""

import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

print("\n" + "="*80)
print("NEGATIVE PAYMENT ANALYSIS")
print("="*80)

print("\n" + "-"*80)
print("1. OVERVIEW OF NEGATIVE PAYMENTS")
print("-"*80)

cur.execute('''
    SELECT
        COUNT(*) AS total_negative,
        COUNT(CASE WHEN amount < -1 THEN 1 END) AS significant_negative,
        COUNT(CASE WHEN amount >= -1 AND amount < 0 THEN 1 END) AS small_negative,
        ROUND(SUM(amount)::numeric, 2) AS total_negative_amount,
        ROUND(MIN(amount)::numeric, 2) AS smallest_amount,
        ROUND(MAX(amount)::numeric, 2) AS largest_amount,
        ROUND(AVG(amount)::numeric, 2) AS avg_negative,
        COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) AS with_charter_id,
        COUNT(CASE WHEN reserve_number IS NOT NULL THEN 1 END) AS with_reserve_number
    FROM payments
    WHERE amount < 0
''')

row = cur.fetchone()
print(f"\n📊 Negative Payment Overview:")
print(f"   Total negative payments: {row[0]:,}")
print(f"   Significant (< -$1): {row[1]:,}")
print(f"   Small (>= -$1): {row[2]:,}")
print(f"   Total amount (negative): ${row[3]:,.2f}")
print(f"   Range: ${row[5]:,.2f} to ${row[4]:,.2f}")
print(f"   Average: ${row[6]:,.2f}")
print(f"   With charter_id: {row[7]:,}")
print(f"   With reserve_number: {row[8]:,}")

print("\n" + "-"*80)
print("2. DISTRIBUTION BY AMOUNT RANGE")
print("-"*80)

cur.execute('''
    SELECT
        CASE
            WHEN amount < -1000 THEN '>-$1000'
            WHEN amount < -100 THEN '-$100 to -$1000'
            WHEN amount < -10 THEN '-$10 to -$100'
            WHEN amount < -1 THEN '-$1 to -$10'
            ELSE '-$0.01 to -$0.99'
        END AS amount_range,
        COUNT(*) AS count,
        ROUND(SUM(amount)::numeric, 2) AS total,
        ROUND(AVG(ABS(amount))::numeric, 2) AS avg_abs
    FROM payments
    WHERE amount < 0
    GROUP BY
        CASE
            WHEN amount < -1000 THEN 1
            WHEN amount < -100 THEN 2
            WHEN amount < -10 THEN 3
            WHEN amount < -1 THEN 4
            ELSE 5
        END,
        CASE
            WHEN amount < -1000 THEN '>-$1000'
            WHEN amount < -100 THEN '-$100 to -$1000'
            WHEN amount < -10 THEN '-$10 to -$100'
            WHEN amount < -1 THEN '-$1 to -$10'
            ELSE '-$0.01 to -$0.99'
        END
    ORDER BY
        CASE
            WHEN amount < -1000 THEN 1
            WHEN amount < -100 THEN 2
            WHEN amount < -10 THEN 3
            WHEN amount < -1 THEN 4
            ELSE 5
        END
''')

print(f"\n{'Amount Range':<20} {'Count':>8} {'Total Amount':>15} {'Avg':>12}")
print("-" * 60)
for row in cur.fetchall():
    print(f"{row[0]:<20} {row[1]:>8,} ${row[2]:>14,.2f} ${row[3]:>11,.2f}")

print("\n" + "-"*80)
print("3. TOP 20 LARGEST NEGATIVE PAYMENTS")
print("-"*80)

cur.execute('''
    SELECT
        p.payment_id,
        p.charter_id,
        p.reserve_number,
        p.amount,
        p.payment_method,
        p.payment_date,
        p.payment_key,
        c.total_amount_due,
        COALESCE(c.status, 'NULL') AS status
    FROM payments p
    LEFT JOIN charters c ON c.reserve_number = p.reserve_number
    WHERE p.amount < 0
    ORDER BY p.amount ASC
    LIMIT 20
''')

print(f"\n{'ID':>7} {'Reserve':>8} {'Amount':>12} {'Method':>12} {'Date':<12} {'Charter Due':>12}")
print("-" * 70)

for row in cur.fetchall():
    reserve = str(row[2]) if row[2] else "NULL"
    due = row[7] if row[7] is not None else 0
    print(f"{row[0]:>7} {reserve:>8} ${row[3]:>11,.2f} {str(row[4])[:11]:>12} {str(row[5])[:12]:<12} ${due:>11,.2f}")

print("\n" + "-"*80)
print("4. NEGATIVE PAYMENTS BY METHOD")
print("-"*80)

cur.execute('''
    SELECT
        COALESCE(payment_method, 'NULL') AS method,
        COUNT(*) AS count,
        ROUND(SUM(amount)::numeric, 2) AS total_amount,
        ROUND(AVG(ABS(amount))::numeric, 2) AS avg_abs,
        MIN(payment_date) AS earliest,
        MAX(payment_date) AS latest
    FROM payments
    WHERE amount < 0
    GROUP BY payment_method
    ORDER BY ABS(SUM(amount)) DESC
''')

print(f"\n{'Method':<15} {'Count':>8} {'Total Amount':>15} {'Avg':>12} {'Date Range':<30}")
print("-" * 85)

for row in cur.fetchall():
    date_range = f"{row[4]} to {row[5]}" if row[4] and row[5] else "No dates"
    print(f"{row[0]:<15} {row[1]:>8,} ${row[2]:>14,.2f} ${row[3]:>11,.2f} {date_range:<30}")

print("\n" + "-"*80)
print("5. NEGATIVE PAYMENTS BY YEAR")
print("-"*80)

cur.execute('''
    SELECT
        EXTRACT(YEAR FROM payment_date)::int AS year,
        COUNT(*) AS count,
        ROUND(SUM(amount)::numeric, 2) AS total_amount,
        ROUND(AVG(ABS(amount))::numeric, 2) AS avg_abs,
        ROUND(MAX(amount)::numeric, 2) AS largest,
        ROUND(MIN(amount)::numeric, 2) AS smallest
    FROM payments
    WHERE amount < 0
    GROUP BY EXTRACT(YEAR FROM payment_date)
    ORDER BY year DESC
''')

print(f"\n{'Year':>6} {'Count':>8} {'Total Amount':>15} {'Avg Abs':>12} {'Largest':>12} {'Smallest':>12}")
print("-" * 70)

for row in cur.fetchall():
    year = int(row[0]) if row[0] else 0
    print(f"{year:>6} {row[1]:>8,} ${row[2]:>14,.2f} ${row[3]:>11,.2f} ${row[4]:>11,.2f} ${row[5]:>11,.2f}")

print("\n" + "-"*80)
print("6. RESERVES WITH NEGATIVE PAYMENTS")
print("-"*80)

cur.execute('''
    WITH reserve_negatives AS (
        SELECT
            reserve_number,
            COUNT(*) AS neg_payment_count,
            SUM(amount) AS total_negative,
            (SELECT SUM(COALESCE(amount, 0)) FROM payments p2 
             WHERE p2.reserve_number = p1.reserve_number AND p2.amount > 0) AS total_positive,
            (SELECT total_amount_due FROM charters WHERE reserve_number = p1.reserve_number LIMIT 1) AS charter_due
        FROM payments p1
        WHERE amount < 0
        GROUP BY reserve_number
    )
    SELECT
        reserve_number,
        neg_payment_count,
        ROUND(total_negative::numeric, 2) AS total_negative,
        ROUND(total_positive::numeric, 2) AS total_positive,
        ROUND((COALESCE(total_positive, 0) + COALESCE(total_negative, 0))::numeric, 2) AS net_paid,
        ROUND(charter_due::numeric, 2) AS charter_due,
        ROUND((COALESCE(charter_due, 0) - (COALESCE(total_positive, 0) + COALESCE(total_negative, 0)))::numeric, 2) AS balance
    FROM reserve_negatives
    WHERE COALESCE(total_positive, 0) + COALESCE(total_negative, 0) != 0
    ORDER BY ABS(total_negative) DESC
    LIMIT 15
''')

print(f"\n{'Reserve':>8} {'Neg Cnt':>8} {'Negative':>12} {'Positive':>12} {'Net Paid':>12} {'Due':>12} {'Balance':>12}")
print("-" * 90)

for row in cur.fetchall():
    print(f"{row[0]:>8} {row[1]:>8,} ${row[2]:>11,.2f} ${row[3]:>11,.2f} ${row[4]:>11,.2f} ${row[5]:>11,.2f} ${row[6]:>11,.2f}")

print("\n" + "-"*80)
print("7. POTENTIAL ISSUES & QUESTIONS")
print("-"*80)

print("""
🔍 Questions to investigate:

1. Are negative payments legitimate refunds?
   - Check if each negative payment corresponds to a positive payment
   - Verify dates match (negative should be after positive)
   - Look for "refund", "chargeback", "reversal" in notes

2. Are there cents-only negatives that indicate rounding errors?
   - Check payments with amount between -$1 and $0
   - May indicate incorrect GST or fee calculations

3. Which reserves have more negative than positive payments?
   - Could indicate over-collection or payment reversal

4. Are negative payments properly offset in balance calculations?
   - Check if overpaid status includes negative payments
   - Verify refund processing logic

5. Are there patterns in negative payment timing?
   - Do they cluster in certain months/years?
   - Suggest systemic issue vs. one-off refunds?
""")

print("\n" + "="*80 + "\n")

cur.close()
conn.close()
