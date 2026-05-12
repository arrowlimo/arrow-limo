from fastapi.testclient import TestClient
from app.main import app
from app.routers.driver_auth import create_session

c = TestClient(app)
token = create_session(
    999985,
    'restart-auth-smoke',
    role='admin',
    permissions={'all': True},
    username='restart-auth-smoke'
)
headers = {'Authorization': f'Bearer {token}'}
endpoints = [
 '/api/vehicles/',
 '/api/cash-box/transactions',
 '/api/beverage/reconciliations',
 '/api/payroll/entries?year=2026',
 '/api/payroll-compliance/pd7a',
 '/api/files/list/business_documents/general/general',
 '/api/t2/returns/2026',
 '/api/t4/1/2026',
 '/api/t4/1/2026/pdf'
]
for ep in endpoints:
    r = c.get(ep, headers=headers)
    print(f'{ep} -> {r.status_code}')
