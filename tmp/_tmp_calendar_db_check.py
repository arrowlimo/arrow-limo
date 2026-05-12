import psycopg2
import os

conn = psycopg2.connect(
    host="localhost",
    dbname="almsdata",
    user="postgres",
    password=os.getenv("ALMS_DB_PASSWORD", ""),
)
cur = conn.cursor()

cur.execute("select count(*) from charters")
print("charters_total", cur.fetchone()[0])

cur.execute("select min(charter_date), max(charter_date) from charters")
print("date_range", cur.fetchone())

cur.execute("select count(*) from charters where charter_date=current_date")
print("today_total", cur.fetchone()[0])

cur.execute(
    "select count(*) from charters where charter_date=current_date and employee_id is not null"
)
print("today_with_driver_id", cur.fetchone()[0])

cur.execute(
    "select count(*) from charters where charter_date=current_date and vehicle_id is not null"
)
print("today_with_vehicle_id", cur.fetchone()[0])

cur.execute(
    "select count(*) from charters where charter_date between current_date-interval '30 day' and current_date and employee_id is not null"
)
print("last30_with_driver_id", cur.fetchone()[0])

cur.execute(
    "select count(*) from charters where charter_date between current_date-interval '30 day' and current_date and vehicle_id is not null"
)
print("last30_with_vehicle_id", cur.fetchone()[0])

cur.execute(
    """
    select column_name
    from information_schema.columns
    where table_schema='public'
      and table_name='charters'
      and column_name in (
        'calendar_sync_status','calendar_color','calendar_notes','outlook_entry_id',
        'do_time','dropoff_time','employee_id','vehicle_id','driver','vehicle'
      )
    order by column_name
    """
)
print("cols", [r[0] for r in cur.fetchall()])

cur.close()
conn.close()
