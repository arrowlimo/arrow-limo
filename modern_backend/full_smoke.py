from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)

endpoints = [
    ('GET', '/api/reports/accounting/views'),
    ('GET', '/api/reports/accounting/rules'),
    ('POST', '/api/reports/accounting/rules', {'name': 'Test', 'pattern': 'T', 'gl_code': '4100'}),
    ('POST', '/api/reports/accounting/reclassify/receipts', {'receipt_ids': [1], 'gl_code': '4100'}),
    ('POST', '/api/reports/accounting/reclassify/ledger', {'ledger_ids': [1], 'gl_code': '4100'})
]

for method, path, *data in endpoints:
    try:
        if method == 'GET':
            r = client.get(path)
        else:
            r = client.post(path, json=data[0])
        print(f'{method} {path} -> {r.status_code} | {r.text[:100]}')
    except Exception as e:
        print(f'{method} {path} -> EXCEPTION: {e}')
