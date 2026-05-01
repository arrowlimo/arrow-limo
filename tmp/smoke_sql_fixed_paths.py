import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

# 1) Verify load_charter path on schemas with/without charter_data.
cur.execute(
    """
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'charters'
          AND column_name = 'charter_data'
    )
    """
)
has_charter_data = bool(cur.fetchone()[0])
charter_data_col = "c.charter_data" if has_charter_data else "NULL::jsonb"

cur.execute(
    f"""
    SELECT
        c.reserve_number,
        c.charter_date,
        c.pickup_time,
        c.passenger_count,
        c.notes,
        c.status,
        c.client_id,
        {charter_data_col},
        COALESCE(c.is_out_of_town, FALSE),
        c.employee_id,
        c.vehicle_id,
        COALESCE(c.charter_type, ''),
        COALESCE(c.hourly_rate, 0),
        COALESCE(c.gratuity_percent, 18.0),
        COALESCE(c.quoted_hours, 0),
        COALESCE(c.extra_time_rate, 0),
        COALESCE(c.standby_rate, 0),
        COALESCE(c.nrd_received, FALSE),
        COALESCE(c.nrd_amount, 0),
        COALESCE(c.nrd_method, ''),
        COALESCE(c.nrr_received, FALSE),
        COALESCE(c.nrr_amount, 0),
        COALESCE(c.gst_exempt, FALSE),
        COALESCE(c.gst_permit_number, ''),
        COALESCE(c.pickup_address, ''),
        COALESCE(c.dropoff_address, ''),
        c.do_time,
        c.dropoff_time
    FROM charters c
    ORDER BY c.charter_id DESC
    LIMIT 1
    """
)
row = cur.fetchone()
print('load_charter_sql_ok', row is not None)

# 2) Verify invoice query fixed aliases and column count.
cur.execute(
    """
    SELECT c.charter_id, c.reserve_number,
           COALESCE(cl.company_name, cl.client_name, 'Unknown') AS customer,
           cl.primary_phone, cl.email,
           c.charter_date, c.pickup_time,
           c.total_amount_due,
           COALESCE(c.amount_paid, 0)
    FROM charters c
    LEFT JOIN clients cl ON c.client_id = cl.client_id
    ORDER BY c.charter_id DESC
    LIMIT 1
    """
)
invoice_row = cur.fetchone()
print('invoice_sql_ok', invoice_row is not None, 'cols', len(invoice_row) if invoice_row else 0)

# 3) Verify vehicle lease report projection with vin_number.
cur.execute(
    """
    SELECT
        v.vehicle_number, v.make, v.model, v.year, v.vin_number,
        lp.lease_status
    FROM vehicle_lease_profiles lp
    JOIN vehicles v ON v.vehicle_id = lp.vehicle_id
    LIMIT 1
    """
)
lease_row = cur.fetchone()
print('lease_sql_ok', lease_row is not None)

cur.close()
conn.close()
print('smoke_sql_fixed_paths_done')
