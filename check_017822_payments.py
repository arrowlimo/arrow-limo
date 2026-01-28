import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

reserve = "017822"

# Check payments
cur.execute("""
    SELECT payment_id, reserve_number, amount, payment_date, payment_method, notes
    FROM payments
    WHERE reserve_number = %s
    ORDER BY payment_date
""", (reserve,))

payments = cur.fetchall()

print(f"Charter {reserve} - PAYMENTS IN DATABASE")
print("="*70)

if payments:
    print(f"{'ID':<8} {'Reserve':<10} {'Amount':>12} {'Date':<12} {'Method':<20} {'Notes'}")
    print("-"*70)
    total = 0
    for p in payments:
        print(f"{p[0]:<8} {str(p[1]):<10} ${p[2]:>11.2f} {str(p[3])[:10]:<12} {(p[4] or '')[:20]:<20} {p[5] or ''}")
        total += p[2]
    print("-"*70)
    print(f"{'TOTAL':<40} ${total:>11.2f}")
else:
    print("No payments found")

# Check charges
print(f"\n{'='*70}")
print(f"Charter {reserve} - CHARGES IN DATABASE")
print("="*70)

cur.execute("""
    SELECT charge_id, description, amount, created_at
    FROM charter_charges
    WHERE reserve_number = %s
    ORDER BY created_at
""", (reserve,))

charges = cur.fetchall()

if charges:
    print(f"{'ID':<8} {'Description':<35} {'Amount':>12} {'Date':<12}")
    print("-"*70)
    total = 0
    for c in charges:
        print(f"{c[0]:<8} {(c[1] or '')[:35]:<35} ${c[2]:>11.2f} {str(c[3])[:10]}")
        total += c[2]
    print("-"*70)
    print(f"{'TOTAL':<47} ${total:>11.2f}")
else:
    print("No charges found")

cur.close()
conn.close()
