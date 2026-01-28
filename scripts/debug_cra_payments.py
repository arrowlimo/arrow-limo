import sys, os
sys.path.append(os.path.dirname(__file__))
import generate_tax_year_summary as g
import psycopg2

conn = psycopg2.connect(**g.DSN)
val = g.cra_payments_from_banking(conn, 2012)
print(f"cra_payments_from_banking(2012) = {val}")
conn.close()
