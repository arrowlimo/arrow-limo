from pathlib import Path
import json

from desktop_app.t4_official_form_filler import T4OfficialFormFiller

try:
    import psycopg2
except Exception:
    psycopg2 = None

employee_data = {
    'full_name': 'PAUL RICHARD',
    'first_name': 'PAUL',
    'last_name': 'RICHARD',
    'sin': '637 660 614',
    'address': '',
    'city': 'RED DEER',
    'province': 'AB',
    'postal_code': 'T4P 2Z1',
}

t4_data = {
    'box14': 0.0,
    'box16': 0.0,
    'box18': 0.0,
    'box22': 0.0,
    'box24': 0.0,
    'box26': 0.0,
    'box44': 0.0,
    'box52': 0.0,
    'box29': 1,
}

if psycopg2 is not None:
    try:
        conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine', port=5432)
        cur = conn.cursor()
        cur.execute("""
            SELECT employee_id, full_name, first_name, last_name, t4_sin, street_address, city, province, postal_code
            FROM employees
            WHERE employee_id = 10
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            _, full_name, first_name, last_name, t4_sin, street, city, prov, postal = row
            employee_data.update({
                'full_name': full_name or employee_data['full_name'],
                'first_name': first_name or employee_data['first_name'],
                'last_name': last_name or employee_data['last_name'],
                'sin': (t4_sin or employee_data['sin']),
                'address': street or employee_data['address'],
                'city': city or employee_data['city'],
                'province': prov or employee_data['province'],
                'postal_code': postal or employee_data['postal_code'],
            })

        cur.execute("""
            SELECT box_14_employment_income, box_16_cpp_contributions, box_18_ei_premiums,
                   box_22_income_tax, box_24_ei_insurable_earnings, box_26_cpp_pensionable_earnings,
                   box_44_union_dues, box_29_exempt_ei_ei_insurable
            FROM employee_t4_records
            WHERE employee_id = 10 AND tax_year = 2012
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            box14, box16, box18, box22, box24, box26, box44, box29 = row
            t4_data.update({
                'box14': float(box14 or 0),
                'box16': float(box16 or 0),
                'box18': float(box18 or 0),
                'box22': float(box22 or 0),
                'box24': float(box24 or 0),
                'box26': float(box26 or 0),
                'box44': float(box44 or 0),
                'box29': int(box29 or 0),
            })

        cur.close()
        conn.close()
    except Exception:
        pass

out_path = Path('tmp') / 'T4_2012_Paul_test_OFFICIAL.pdf'
out_path.parent.mkdir(parents=True, exist_ok=True)

filler = T4OfficialFormFiller()
result = filler.fill_t4_form(employee_data=employee_data, t4_data=t4_data, tax_year=2012, output_path=str(out_path), format_type='employee')

print(f'TEST_FILE={Path(result).resolve() if result else out_path.resolve()}')

# Read resulting fields using pypdf
try:
    from pypdf import PdfReader
except Exception:
    from PyPDF2 import PdfReader

reader = PdfReader(str(out_path))
fields = reader.get_fields() or {}
needles = ['Box55', 'Box29', 'EI_CheckBox', 'EmployersName', 'EmployersAccount']

for name in sorted(fields):
    if any(n in name for n in needles):
        obj = fields[name]
        value = obj.get('/V', '') if hasattr(obj, 'get') else ''
        print(f'{name} => {value}')
