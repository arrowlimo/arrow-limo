import psycopg2, os
c=psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REDACTED***').cursor()
c.execute("SELECT payment_method, COUNT(*), SUM(amount) FROM payments WHERE EXTRACT(YEAR FROM payment_date)=2012 AND (reserve_number IS NULL OR reserve_number NOT IN (SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL)) GROUP BY payment_method")
print("\n207 Unmatched 2012 Payments by Method:")
for r in c.fetchall():
    print(f"  {r[0]:20} {r[1]:4} payments ${r[2]:,.2f}")
