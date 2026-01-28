import psycopg2

DB_CONFIG = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432
}

CHARTER_IDS = [
18403,18408,18413,18415,18417,18419,18422,18424,18432,18434,18437,18439,18441,18443,18405,18445,18411,18404,18448,18449,18451,18453,18456,18459,18463,18462,18465,18468,18471,18474,18476,18478,18481,18483,18484,18485,18486,18490,18494,3369,8502,18502,18504
]

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print("CharterID | Reserve# | Date | Client | Description | Notes | Status | Vehicle | Total Due | Paid | Payment Status")
    print("-"*160)
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
            continue
        charter_dict = dict(zip([desc[0] for desc in cur.description], charter))
        desc = charter_dict.get('vehicle_description') or ''
        notes = charter_dict.get('vehicle_notes') or ''
        print(f"{charter_dict['charter_id']} | {charter_dict['reserve_number']} | {charter_dict['charter_date']} | {charter_dict['display_name']} | {desc} | {notes} | {charter_dict['status']} | {charter_dict['vehicle_booked_id']} | {charter_dict['total_amount_due']} | {charter_dict['paid_amount']} | {charter_dict['payment_status']}")
    print("\n--- Client/Location/Notes summary for best guess ---\n")
    cur.execute("SELECT DISTINCT COALESCE(cl.client_name, cl.company_name) AS display_name FROM v_charters_reportable c LEFT JOIN clients cl ON c.client_id = cl.client_id WHERE c.charter_id = ANY(%s)", (CHARTER_IDS,))
    for row in cur.fetchall():
        print("Client:", row[0])
    cur.execute("SELECT DISTINCT vehicle_description FROM v_charters_reportable WHERE charter_id = ANY(%s)", (CHARTER_IDS,))
    for row in cur.fetchall():
        print("Vehicle Description:", row[0])
    cur.execute("SELECT DISTINCT vehicle_notes FROM v_charters_reportable WHERE charter_id = ANY(%s)", (CHARTER_IDS,))
    for row in cur.fetchall():
        if row[0]:
            print("Notes:", row[0])
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
