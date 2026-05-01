import fitz
import os
import re
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost', port=5432, database='almsdata',
    user='postgres', password='ArrowLimousine'
)
cur = conn.cursor()

cur.execute(
    'SELECT driver, vehicle, charter_date, on_duty_time FROM charters WHERE charter_id=4606'
)
row = cur.fetchone()
driver_code_raw, vehicle_raw, charter_date, on_duty = row

cur.execute(
    """SELECT COALESCE(first_name,''), COALESCE(last_name,''),
              COALESCE(employee_number::text, COALESCE(driver_code::text,''))
       FROM employees
       WHERE lower(COALESCE(driver_code::text,''))=lower(%s)
          OR lower(COALESCE(employee_number::text,''))=lower(%s)
       LIMIT 1""",
    (driver_code_raw, driver_code_raw),
)
emp = cur.fetchone()
cur.close()
conn.close()

driver_name = (
    f"{emp[0].strip()} {emp[1].strip()}".strip()
    if emp and (emp[0] or emp[1])
    else driver_code_raw
)
driver_code = emp[2].strip() if emp and emp[2] else driver_code_raw

# Vehicle L-xx
veh = re.sub(r'(?i)^limo\s*0*', 'L-', vehicle_raw) if vehicle_raw else ''
m = re.match(r'^L-(\d+)$', veh)
if m:
    vehicle_id = f'L-{int(m.group(1)):02d}'
else:
    vehicle_id = vehicle_raw or ''

# Date parts
month_text = charter_date.strftime('%B')
day_text = f'{charter_date.day:02d}'
year_text = str(charter_date.year)

# Time HH:MM
if on_duty:
    parts = str(on_duty).split(':')
    shift_start = f'{parts[0].zfill(2)}:{parts[1]}'
else:
    shift_start = ''

print(f'driver_name={driver_name!r}')
print(f'driver_code={driver_code!r}')
print(f'date={month_text} {day_text} {year_text}')
print(f'time={shift_start}')
print(f'vehicle={vehicle_id}')

template_path = r'L:\Confirmation\Daily trip inspection record.pdf'
out_path = r'l:\limo\tmp\inspection_v5.pdf'

doc = fitz.open(template_path)
page = doc[0]

page.insert_text((68, 89), month_text, fontsize=11)
page.insert_text((142, 89), day_text, fontsize=11)
page.insert_text((177, 89), year_text, fontsize=11)
page.insert_text((306, 89), shift_start, fontsize=11)
page.insert_text((198, 121), vehicle_id, fontsize=11)
page.insert_text((80, 143), driver_name, fontsize=11)
page.insert_text((278, 143), driver_code, fontsize=11)

doc.save(out_path)
doc.close()

# Convert to PNG for preview
doc2 = fitz.open(out_path)
pix = doc2[0].get_pixmap(dpi=150)
pix.save(r'l:\limo\tmp\inspection_v5.png')
doc2.close()

print('Saved: l:\\limo\\tmp\\inspection_v5.png')
