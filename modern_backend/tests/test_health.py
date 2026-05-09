from fastapi import status
from httpx import ASGITransport, AsyncClient

from modern_backend.app.main import app


async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json().get("status") == "ok"

# Allow running via pytest-asyncio auto mode
pytest_plugins = ("pytest_asyncio",)
