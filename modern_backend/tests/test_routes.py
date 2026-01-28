from modern_backend.app.main import app


def collect_paths():
    return {f"{r.methods} {r.path}" for r in app.routes}


def test_api_route_registration():
    paths = {r.path for r in app.routes}
    # health
    assert "/health" in paths
    # reports
    assert "/api/reports/export" in paths
    # charges
    assert "/api/charters/{charter_id}/charges" in paths
    assert "/api/charges/{charge_id}" in paths
    # payments
    assert "/api/charters/{charter_id}/payments" in paths
    assert "/api/payments/{payment_id}" in paths
