import os
from datetime import datetime

import fitz
import psycopg2

TEMPLATE = r"L:\Confirmation\Daily trip inspection record.pdf"
OUT_DIR = r"l:\limo\tmp"
os.makedirs(OUT_DIR, exist_ok=True)

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="almsdata",
    user="postgres",
    password="ArrowLimousine",
)
cur = conn.cursor()

cur.execute(
    """
SELECT c.charter_id,
       COALESCE(c.reserve_number::text,''),
       c.charter_date::date,
       COALESCE(c.pickup_time::text,''),
       COALESCE(e.first_name,'') || ' ' || COALESCE(e.last_name,''),
       COALESCE(v.vehicle_number,'')
FROM charters c
LEFT JOIN employees e ON e.employee_id = (
    SELECT employee_id FROM employees
    WHERE (COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) = COALESCE(c.driver,'')
    LIMIT 1
)
LEFT JOIN vehicles v ON v.vehicle_id = (
    SELECT vehicle_id FROM vehicles
    WHERE COALESCE(vehicle_number,'') = COALESCE(c.vehicle,'')
    LIMIT 1
)
WHERE c.charter_date::date >= DATE '2012-01-01'
  AND c.charter_date::date < DATE '2013-01-01'
  AND COALESCE(c.driver::text,'') <> ''
  AND COALESCE(c.vehicle::text,'') <> ''
ORDER BY c.charter_date::date, c.charter_id
LIMIT 1
"""
)
row = cur.fetchone()
cur.close()
conn.close()

if not row:
    raise RuntimeError("No 2012 charter with driver and vehicle found")

charter_id, reserve_no, cdate, pickup_time, driver_name, vehicle_no = row
driver_name = (driver_name or "").strip() or "Driver"
vehicle_no = (vehicle_no or "").strip() or "L-00"
if vehicle_no.upper().startswith("LIMO"):
    digits = "".join(ch for ch in vehicle_no if ch.isdigit())
    if digits:
        vehicle_no = f"L-{digits.zfill(2)}"

month_text = cdate.strftime("%B")
day_text = cdate.strftime("%d")
year_text = cdate.strftime("%Y")
shift_start = (pickup_time or "").strip() or "08:00"
if len(shift_start) >= 5 and shift_start[2] == ":":
    shift_start = shift_start[:5]

pdf_out = os.path.join(OUT_DIR, f"inspection_filled_2012_{reserve_no}_v2.pdf")
png_out = os.path.join(OUT_DIR, f"inspection_filled_2012_{reserve_no}_v2.png")

doc = fitz.open(TEMPLATE)
page = doc[0]
page.insert_text((86, 89), month_text, fontsize=11)
page.insert_text((167, 89), day_text, fontsize=11)
page.insert_text((210, 89), year_text, fontsize=11)
page.insert_text((288, 89), shift_start, fontsize=11)
page.insert_text((198, 121), vehicle_no, fontsize=11)
page.insert_text((255, 143), driver_name, fontsize=11)
doc.save(pdf_out)

pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
pix.save(png_out)
doc.close()

print(f"charter_id={charter_id}")
print(f"reserve_no={reserve_no}")
print(f"month={month_text} day={day_text} year={year_text}")
print(f"shift_start={shift_start}")
print(f"driver_name={driver_name}")
print(f"vehicle_no={vehicle_no}")
print(f"pdf_out={pdf_out}")
print(f"png_out={png_out}")
