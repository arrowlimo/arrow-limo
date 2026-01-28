
import psycopg2
import os
from decimal import Decimal

def main():
	conn = psycopg2.connect(
		dbname="almsdata",
		user="postgres",
		password="***REMOVED***",
		host="localhost"
	)
	cur = conn.cursor()
	# Get all charters with client info and original paid_amount (all years)
	cur.execute('''
		SELECT c.charter_id, c.reserve_number, c.charter_date, c.client_id, cl.company_name, c.total_amount_due, c.paid_amount, c.payment_status, c.status
		FROM v_charters_reportable c
		LEFT JOIN clients cl ON c.client_id = cl.client_id
		ORDER BY c.charter_date
	''')
	charters = cur.fetchall()
	# For each charter, sum all payments from the payments table (all types)
	charter_payments = {}
	charter_payment_details = {}
	for charter in charters:
		charter_id = charter[0]
		# Sum all payments linked to this charter
		cur.execute('''
			SELECT COALESCE(SUM(amount), 0)
			FROM payments
			WHERE charter_id = %s
		''', (charter_id,))
		paid_amt = cur.fetchone()
		paid_amt = paid_amt[0] if paid_amt and paid_amt[0] is not None else Decimal('0.00')
		charter_payments[charter_id] = paid_amt
		# Get all payment details for this charter
		cur.execute('''
			SELECT payment_id, amount, payment_date, payment_method, payment_key
			FROM payments
			WHERE charter_id = %s
			ORDER BY payment_date
		''', (charter_id,))
		charter_payment_details[charter_id] = cur.fetchall()
	seen = set()
	out_path = os.path.join(os.path.dirname(__file__), "charter_client_detailed_report.txt")
	with open(out_path, 'w', encoding='utf-8') as out:
		out.write("\n=== CHARTER PAYMENT RECONCILIATION REPORT (ALL YEARS, ALL PAYMENT TYPES) ===\n\n")
		for charter in charters:
			charter_id = charter[0]
			if charter_id in seen:
				continue
			seen.add(charter_id)
			total_due = charter[5] or Decimal('0.00')
			payment_rows = charter_payment_details.get(charter_id, [])
			payment_sum = sum((p[1] or Decimal('0.00')) for p in payment_rows)
			payment_types = {}
			for p in payment_rows:
				method = p[3] or 'unknown'
				payment_types.setdefault(method, Decimal('0.00'))
				payment_types[method] += p[1] or Decimal('0.00')
			fully_paid = abs(payment_sum - total_due) < Decimal('0.01')
			charter_date_str = charter[2].strftime('%Y-%m-%d') if charter[2] and hasattr(charter[2], 'strftime') else (str(charter[2]) if charter[2] else 'N/A')
			client_name = str(charter[4]) if charter[4] is not None else 'N/A'
			reserve_number = str(charter[1]) if charter[1] is not None else 'N/A'
			charter_status = str(charter[8]) if len(charter) > 8 and charter[8] is not None else 'N/A'
			out.write(f"Client: {client_name:<30} Charter#: {reserve_number:<10} Date: {charter_date_str}  Status: {charter_status}\n")
			out.write(f"  Amount Due: ${total_due:>10,.2f}\n")
			out.write(f"  Total Payments: ${payment_sum:>10,.2f}  {'(FULLY RECONCILED)' if fully_paid else '(NOT RECONCILED)'}\n")
			payment_status = str(charter[7]) if len(charter) > 7 and charter[7] is not None else 'N/A'
			out.write(f"  Payment Status: {payment_status:<12}\n")
			out.write("  Note: Manual ledger entry only — this system does not process online payments.\n")
			out.write(f"  Payment Breakdown by Type:\n")
			for method, amt in payment_types.items():
				out.write(f"    {method:<15}: ${amt:>10,.2f}\n")
			if len(payment_rows) > 1:
				out.write(f"  (Split Payment: {len(payment_rows)} payments)\n")
			out.write(f"  Linked Payments Details:\n")
			for pay in payment_rows:
				out.write(f"    PaymentID: {pay[0]}, Amount: ${pay[1]:.2f}, Date: {pay[2]}, Method: {pay[3]}, Key: {pay[4]}\n")
			out.write("-"*100 + "\n")
	cur.close()
	conn.close()
	print(f"Printable charter client detailed report generated: {out_path}")

if __name__ == "__main__":
	main()
