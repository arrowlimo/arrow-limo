from modern_backend.app.main import app


def test_charters_routes_registered():
    paths = set(app.routes[i].path for i in range(len(app.routes)))
    assert "/api/charters" in paths
    assert "/api/charters/{charter_id}" in paths
