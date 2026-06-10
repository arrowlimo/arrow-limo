import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def _load_env_file() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _authenticate(client: TestClient) -> dict:
    """Get Authorization header for API smoke checks."""
    os.environ["AUTO_LOGIN"] = "true"

    auto = client.get("/auth/auto-login-check")
    if auto.status_code == 200:
        payload = auto.json()
        token = payload.get("token") if isinstance(payload, dict) else None
        if token:
            return {"Authorization": f"Bearer {token}"}

    username = (
        os.getenv("AUTH_SMOKE_USER") or os.getenv("AUTO_LOGIN_USER") or os.getenv("WEB_LOGIN_USER")
    )
    password = os.getenv("AUTH_SMOKE_PASSWORD") or os.getenv("WEB_LOGIN_PASSWORD")
    if not username or not password:
        return {}

    login = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    if login.status_code != 200:
        return {}
    token = (login.json() or {}).get("access_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    _load_env_file()
    client = TestClient(app)
    headers = _authenticate(client)

    endpoints = [
        ("GET", "/api/reports/accounting/views", None),
        ("GET", "/api/reports/accounting/rules", None),
        (
            "POST",
            "/api/reports/accounting/rules",
            {"name": "Test", "pattern": "T", "gl_code": "4100"},
        ),
        (
            "POST",
            "/api/reports/accounting/reclassify/receipts",
            {"receipt_ids": [1], "gl_code": "4100"},
        ),
        (
            "POST",
            "/api/reports/accounting/reclassify/ledger",
            {"ledger_ids": [1], "gl_code": "4100"},
        ),
    ]

    failures = 0
    for method, path, body in endpoints:
        try:
            if method == "GET":
                resp = client.get(path, headers=headers)
            else:
                resp = client.post(path, json=body, headers=headers)
            ok = 200 <= resp.status_code < 500 and resp.status_code != 401
            if not ok:
                failures += 1
            print(f"{method} {path} -> {resp.status_code} | {resp.text[:120]}")
        except Exception as exc:
            failures += 1
            print(f"{method} {path} -> EXCEPTION: {exc}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
