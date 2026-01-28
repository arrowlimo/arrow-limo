import psycopg2
import json

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

# List of charter_ids to report on
CHARTER_IDS = [
18403,18408,18413,18415,18417,18419,18422,18424,18432,18434,18437,18439,18441,18443,18405,18445,18411,18404,18448,18449,18451,18453,18456,18459,18463,18462,18465,18468,18471,18474,18476,18478,18481,18483,18484,18485,18486,18490,18494,3369,8502,18502,18504
]

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
    for charter_id in CHARTER_IDS:
        cur.execute('''
                 SELECT c.charter_id, c.reserve_number, c.charter_date, c.client_id,
                     COALESCE(cl.client_name, cl.company_name) AS display_name,
                     c.total_amount_due, c.paid_amount, c.payment_status, c.status,
                   c.vehicle_booked_id, c.vehicle_type_requested, c.vehicle_description, c.passenger_load, c.odometer_start, c.odometer_end, c.total_kms, c.fuel_added, c.vehicle_notes, c.retainer, c.charter_data
            FROM v_charters_reportable c
            LEFT JOIN clients cl ON c.client_id = cl.client_id
            WHERE c.charter_id = %s
        ''', (charter_id,))
        charter = cur.fetchone()
        if not charter:
            print(f"Charter {charter_id} not found.")
            continue
        charter_columns = [desc[0] for desc in cur.description]
        charter_dict = dict(zip(charter_columns, charter))
        print("\n" + "="*120)
        print(f"Charter #{charter_dict['charter_id']} | Reserve#: {charter_dict['reserve_number']} | Date: {charter_dict['charter_date']} | Client: {charter_dict['display_name']}")
        for k in ['total_amount_due', 'paid_amount', 'payment_status', 'status', 'retainer']:
            print(f"  {k}: {charter_dict[k]}")
        for k in ['vehicle_booked_id', 'vehicle_type_requested', 'vehicle_description', 'passenger_load', 'odometer_start', 'odometer_end', 'total_kms', 'fuel_added', 'vehicle_notes']:
            print(f"  {k}: {charter_dict[k]}")
        if charter_dict['charter_data']:
            try:
                charter_data = json.loads(charter_dict['charter_data'])
                print_section('Charter Data', charter_data, indent=4)
            except Exception:
                print(f"    Charter Data: {charter_dict['charter_data']}")
        # Payments
        try:
            cur.execute("SELECT amount, payment_date, payment_method, payment_key FROM payments WHERE charter_id = %s ORDER BY payment_date", (charter_id,))
            payments = cur.fetchall()
            if payments:
                print("    Payments:")
                for p in payments:
                    print(f"      - Amount: {p[0]}, Date: {p[1]}, Method: {p[2]}, Key: {p[3]}")
        except Exception as e:
            print(f"    [Error loading payments: {e}]")
        # Charter Charges
        try:
            cur.execute("SELECT charge_type, amount, description FROM charter_charges WHERE charter_id = %s ORDER BY charge_type", (charter_id,))
            charges = cur.fetchall()
            if charges:
                print("    Charter Charges:")
                for ch in charges:
                    print(f"      - Type: {ch[0]}, Amount: {ch[1]}, Desc: {ch[2]}")
        except Exception as e:
            print(f"    [Error loading charter_charges: {e}]")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
