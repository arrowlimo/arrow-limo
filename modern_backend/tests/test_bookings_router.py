from modern_backend.app.main import app


def test_bookings_routes_registered():
    paths = set(r.path for r in app.routes)
    assert "/api/bookings" in paths
    assert "/api/bookings/{charter_id}" in paths
    assert "/api/bookings/search" in paths
