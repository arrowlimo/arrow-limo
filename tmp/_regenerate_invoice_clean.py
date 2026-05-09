import os
from io import BytesIO
from datetime import datetime
import psycopg2
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import Color
from pypdf import PdfReader, PdfWriter

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# 2012 multi-stop + non-zero charges
cur.execute('''
select c.charter_id, c.reserve_number, c.charter_date,
       count(distinct r.route_id) as route_count,
       count(distinct ch.charge_id) as charge_count,
       coalesce(sum(ch.amount),0) as charge_sum,
       coalesce(cl.company_name, cl.client_name, cl.name, 'Unknown') as customer,
       coalesce(cl.primary_phone, cl.phone, '') as phone,
       coalesce(v.vehicle_type, c.vehicle, '') as vehicle_type,
       coalesce(c.passenger_count,0) as passengers
from charters c
join charter_routes r on r.charter_id::text = c.charter_id::text
join charter_charges ch on ch.charter_id::text = c.charter_id::text
left join clients cl on cl.client_id = c.client_id
left join vehicles v on v.vehicle_id = c.vehicle_id
where extract(year from c.charter_date)=2012
group by c.charter_id,c.reserve_number,c.charter_date,cl.company_name,cl.client_name,cl.name,cl.primary_phone,cl.phone,v.vehicle_type,c.vehicle,c.passenger_count
having count(distinct r.route_id)>=2 and count(distinct ch.charge_id)>=2 and coalesce(sum(ch.amount),0)>0
order by charge_sum desc
limit 1
''')
row = cur.fetchone()
if not row:
    raise SystemExit('No matching charter found')
(cid,reserve,cdate,route_count,charge_count,charge_sum,customer,phone,vehicle_type,passengers)=row

cur.execute('''
select coalesce(description,''), coalesce(amount,0), coalesce(charge_type,'')
from charter_charges
where charter_id::text=%s
order by sequence, charge_id
''',(str(cid),))
charges = cur.fetchall()

cur.execute('''
select coalesce(route_sequence,0), coalesce(pickup_location,''), coalesce(dropoff_location,''), pickup_time, stop_time
from charter_routes
where charter_id::text=%s
order by route_sequence, route_id
''',(str(cid),))
routes = cur.fetchall()

cur.execute('''
select coalesce(amount,0), coalesce(payment_method,''), payment_date, coalesce(payment_key,'')
from charter_payments
where charter_id::text=%s or charter_id::text=%s
order by payment_date nulls last, id
''',(str(cid), str(reserve or '')))
payments = cur.fetchall()

cur.close(); conn.close()

# Totals
total_charges = float(charge_sum or 0)
paid_total = sum(float(p[0] or 0) for p in payments)
amount_due = total_charges - paid_total
gst = total_charges * 0.05 / 1.05 if total_charges > 0 else 0.0
service_subtotal = total_charges - gst

# Break out gratuity/service for left table
gratuity = 0.0
for d,a,t in charges:
    txt = f"{d} {t}".lower()
    if 'gratu' in txt:
        gratuity += float(a or 0)
service_fee = max(service_subtotal - gratuity, 0.0)

base_pdf = r'L:\Confirmation\INVOICE.pdf'  # blank template
out_pdf = r'L:\Confirmation\invoice_filled.pdf'

reader = PdfReader(base_pdf)
base_page = reader.pages[0]
w = float(base_page.mediabox.width)
h = float(base_page.mediabox.height)

buf = BytesIO()
c = canvas.Canvas(buf, pagesize=(w,h))

# Clear dynamic regions to avoid overlap with any placeholder/sample text
c.setFillColor(Color(1,1,1,1))
# Bill To / Customer
c.rect(0.95*inch, 6.02*inch, 6.5*inch, 0.58*inch, stroke=0, fill=1)
# Account / vehicle / date / invoice row
c.rect(0.95*inch, 5.58*inch, 6.5*inch, 0.33*inch, stroke=0, fill=1)
# Left charges data cell
c.rect(0.95*inch, 3.75*inch, 3.95*inch, 1.08*inch, stroke=0, fill=1)
# Right description/amount cell
c.rect(4.15*inch, 3.75*inch, 3.30*inch, 1.08*inch, stroke=0, fill=1)
# Comments rows body
c.rect(0.95*inch, 2.43*inch, 6.50*inch, 0.43*inch, stroke=0, fill=1)
# Bottom payments body
c.rect(0.95*inch, 0.63*inch, 2.95*inch, 0.74*inch, stroke=0, fill=1)
# Bottom routing body
c.rect(4.00*inch, 0.63*inch, 3.45*inch, 0.74*inch, stroke=0, fill=1)
# Remove old NET 0 DAYS / DUE DATE line area
c.rect(4.10*inch, 2.78*inch, 3.25*inch, 0.13*inch, stroke=0, fill=1)

c.setFillColor(Color(0,0,0,1))

# Header fields
c.setFont('Helvetica', 8.5)
c.drawString(1.02*inch, 6.47*inch, str(customer)[:36])
c.drawString(4.95*inch, 6.47*inch, str(customer)[:30])

c.setFont('Helvetica', 8.2)
c.drawString(1.03*inch, 5.72*inch, str(reserve or '')[:10])
c.drawString(6.05*inch, 5.72*inch, datetime.now().strftime('%m/%d/%Y'))
c.drawString(6.65*inch, 5.72*inch, f"{int(cid):06d}")
c.drawString(5.05*inch, 5.72*inch, str(vehicle_type or '')[:16])

# Left CHARGES table body
c.setFont('Helvetica', 8.0)
left_y = 4.58*inch
c.drawString(1.02*inch, left_y, 'Service Fee')
c.drawRightString(3.90*inch, left_y, f"${service_fee:,.2f}")
left_y -= 0.18*inch
c.drawString(1.02*inch, left_y, 'Gratuity')
c.drawRightString(3.90*inch, left_y, f"${gratuity:,.2f}")
left_y -= 0.18*inch
c.drawString(1.02*inch, left_y, 'G.S.T.')
c.drawRightString(3.90*inch, left_y, f"${gst:,.2f}")
left_y -= 0.20*inch
c.setFont('Helvetica-Bold', 8.2)
c.drawString(1.02*inch, left_y, 'TOTAL CHARGES')
c.drawRightString(3.90*inch, left_y, f"${total_charges:,.2f}")

# Right DESCRIPTION/AMOUNT block with line-items + payment summary
c.setFont('Helvetica-Bold', 8.2)
c.drawString(4.22*inch, 4.79*inch, f"Invoice #: {int(cid):06d}")
c.setFont('Helvetica', 8.0)
c.drawString(4.22*inch, 4.61*inch, f"Date: {datetime.now().strftime('%m/%d/%Y')}")

dy = 4.42*inch
for d,a,t in charges[:3]:
    line = (str(d)[:26] if d else (str(t)[:26] if t else 'Charge'))
    c.drawString(4.22*inch, dy, line)
    c.drawRightString(7.43*inch, dy, f"${float(a or 0):,.2f}")
    dy -= 0.15*inch

c.setFont('Helvetica-Bold', 8.2)
c.drawString(4.22*inch, 3.86*inch, 'TOTAL PAYMENT')
c.drawRightString(7.43*inch, 3.86*inch, f"${paid_total:,.2f}")
c.drawString(4.22*inch, 3.62*inch, 'AMOUNT DUE')
c.drawRightString(7.43*inch, 3.62*inch, f"${abs(amount_due):,.2f}")

# COMMENTS body (client + phone + pax)
c.setFont('Helvetica', 7.6)
c.drawString(1.02*inch, 2.69*inch, f"Client: {str(customer)[:34]}")
c.drawString(3.00*inch, 2.69*inch, f"Phone: {str(phone)[:18]}")
c.drawString(1.02*inch, 2.53*inch, f"Reserve: {str(reserve)[:10]}   Pax: {int(passengers or 0)}   Stops: {int(route_count)}")

# PAYMENTS table body (Date/Method/Ref/Amount)
c.setFont('Helvetica', 7.0)
py = 1.25*inch
for amt, method, pdate, pkey in payments[:5]:
    dstr = pdate.strftime('%m-%d') if hasattr(pdate, 'strftime') else ''
    c.drawString(1.03*inch, py, dstr)
    c.drawString(1.45*inch, py, str(method or '')[:10])
    c.drawString(2.20*inch, py, str(pkey or '')[:8])
    c.drawRightString(3.86*inch, py, f"${float(amt or 0):,.2f}")
    py -= 0.13*inch

# ROUTING table body
c.setFont('Helvetica', 6.9)
ry = 1.25*inch
for seq, pick, drop, ptime, stime in routes[:5]:
    t = ptime.strftime('%H:%M') if hasattr(ptime, 'strftime') else (stime.strftime('%H:%M') if hasattr(stime, 'strftime') else '')
    line = f"{int(seq)} {str(pick or '')[:10]}->{str(drop or '')[:12]}"
    c.drawString(4.06*inch, ry, t[:5])
    c.drawString(4.45*inch, ry, line[:38])
    ry -= 0.13*inch

c.save()
buf.seek(0)

over = PdfReader(buf)
writer = PdfWriter()
page = base_page
page.merge_page(over.pages[0])
writer.add_page(page)

os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
with open(out_pdf, 'wb') as f:
    writer.write(f)

print('OUTPUT', out_pdf)
print('CHARTER', cid, 'RESERVE', reserve, 'ROUTES', route_count, 'CHARGES', charge_count, 'CHARGE_SUM', round(total_charges,2))
print('PAID', round(paid_total,2), 'DUE', round(amount_due,2))
print('SIZE', os.path.getsize(out_pdf))
os.startfile(out_pdf)
