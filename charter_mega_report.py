import psycopg2
import json
from datetime import datetime

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

def print_section(title, data, indent=2):
    prefix = ' ' * indent
    print(f"{prefix}{title}:")
    if isinstance(data, dict):
        for k, v in data.items():
            print(f"{prefix}  {k}: {v}")
    elif isinstance(data, list):
        for item in data:
            print(f"{prefix}  - {item}")
    else:
        print(f"{prefix}  {data}")

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    # Get all reportable charters (filters out placeholders via view)
    cur.execute('''
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.client_id, cl.company_name, c.total_amount_due, c.paid_amount, c.payment_status, c.status,
               c.vehicle_booked_id, c.vehicle_type_requested, c.vehicle_description, c.passenger_load, c.odometer_start, c.odometer_end, c.total_kms, c.fuel_added, c.vehicle_notes, c.retainer, c.charter_data,
               c.driver, c.driver_hours_1, c.driver_hours_2, c.driver_pay_1, c.driver_pay_2,
               COALESCE(e.full_name, e.first_name || ' ' || e.last_name, c.driver, 'UNKNOWN') AS driver_name
        FROM v_charters_reportable c
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        LEFT JOIN employees e ON c.driver = e.employee_number
        ORDER BY c.charter_date DESC
    ''')
    charters = cur.fetchall()
    charter_columns = [desc[0] for desc in cur.description]
    report_lines = []
    for charter in charters:
        try:
            charter_dict = dict(zip(charter_columns, charter))
            line = []
            line.append("\n" + "="*120)
            line.append(f"Charter #{charter_dict['charter_id']} | Reserve#: {charter_dict['reserve_number']} | Date: {charter_dict['charter_date']} | Client: {charter_dict['company_name']}")
            # Driver info
            line.append(f"  Driver: {charter_dict.get('driver_name', charter_dict.get('driver', 'UNKNOWN'))}")
            h1 = charter_dict.get('driver_hours_1')
            h2 = charter_dict.get('driver_hours_2')
            p1 = charter_dict.get('driver_pay_1')
            p2 = charter_dict.get('driver_pay_2')
            hours = h2 if h2 not in (None, '', 0) else h1
            pay = p2 if p2 not in (None, '', 0) else p1
            line.append(f"  Hours: {hours}  Pay: {pay}")
            for k in ['total_amount_due', 'paid_amount', 'payment_status', 'status', 'retainer']:
                line.append(f"  {k}: {charter_dict[k]}")
            line.append("  Note: Manual ledger entry only — this system does not process online payments.")
            for k in ['vehicle_booked_id', 'vehicle_type_requested', 'vehicle_description', 'passenger_load', 'odometer_start', 'odometer_end', 'total_kms', 'fuel_added', 'vehicle_notes']:
                line.append(f"  {k}: {charter_dict[k]}")
            # Charter data (JSON)
            if charter_dict['charter_data']:
                try:
                    charter_data = json.loads(charter_dict['charter_data'])
                    # Use print_section to get lines
                    from io import StringIO
                    import sys
                    buf = StringIO()
                    sys_stdout = sys.stdout
                    sys.stdout = buf
                    print_section('Charter Data', charter_data, indent=4)
                    sys.stdout = sys_stdout
                    line.extend(buf.getvalue().splitlines())
                except Exception:
                    line.append(f"    Charter Data: {charter_dict['charter_data']}")
            # Payments
            try:
                cur.execute("SELECT amount, payment_date, payment_method, payment_key FROM payments WHERE charter_id = %s ORDER BY payment_date", (charter_dict['charter_id'],))
                payments = cur.fetchall()
                if payments:
                    line.append("    Payments:")
                    for p in payments:
                        line.append(f"      - Amount: {p[0]}, Date: {p[1]}, Method: {p[2]}, Key: {p[3]}")
            except Exception as e:
                line.append(f"    [Error loading payments: {e}]")
                conn.rollback()
            # Charter Charges (GST, gratuity, extra, invoice, etc.)
            try:
                cur.execute("SELECT charge_type, amount, description FROM charter_charges WHERE charter_id = %s ORDER BY charge_type", (charter_dict['charter_id'],))
                charges = cur.fetchall()
                if charges:
                    line.append("    Charter Charges:")
                    for ch in charges:
                        line.append(f"      - Type: {ch[0]}, Amount: {ch[1]}, Desc: {ch[2]}")
            except Exception as e:
                line.append(f"    [Error loading charter_charges: {e}]")
                conn.rollback()
            # Retainer transfer info (skip if columns do not exist)
            try:
                cur.execute("SELECT retainer_transferred_to, retainer_transfer_date FROM charters WHERE charter_id = %s", (charter_dict['charter_id'],))
                ret = cur.fetchone()
                if ret and (ret[0] or ret[1]):
                    line.append(f"    Retainer transferred to: {ret[0]} on {ret[1]}")
            except Exception:
                conn.rollback()
            # Confirmations (if table exists)
            try:
                cur.execute("SELECT confirmation_id, confirmed_by, confirmation_date, notes FROM confirmations WHERE charter_id = %s", (charter_dict['charter_id'],))
                confirmations = cur.fetchall()
                if confirmations:
                    line.append("    Confirmations:")
                    for conf in confirmations:
                        line.append(f"      - ID: {conf[0]}, By: {conf[1]}, Date: {conf[2]}, Notes: {conf[3]}")
            except Exception:
                conn.rollback()
            # Itinerary (if present in charter_data)
            if charter_dict['charter_data']:
                try:
                    charter_data = json.loads(charter_dict['charter_data'])
                    if 'itinerary' in charter_data:
                        line.append("    Itinerary:")
                        for stop in charter_data['itinerary']:
                            line.append(f"      - {stop}")
                except Exception:
                    pass
            report_lines.extend(line)
        except Exception as e:
            report_lines.append(f"[Error processing charter_id {charter[0]}: {e}]")
            conn.rollback()
    cur.close()
    conn.close()
    report_lines.append("\nEnd of Charter Mega Report.")
    # Print to terminal
    for l in report_lines:
        print(l)
    # Write to file
    out_path = "charter_mega_report.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        for l in report_lines:
            f.write(l + "\n")

if __name__ == '__main__':
    main()
