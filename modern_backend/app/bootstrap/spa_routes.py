import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

NOT_FOUND_DETAIL = {"detail": "Not Found"}


def get_frontend_dist_dir() -> str | None:
    base_dir = os.path.dirname(__file__)
    candidates = [
        os.path.abspath(os.path.join(base_dir, "..", "..", "..", "frontend", "dist")),
        os.path.abspath(os.path.join(base_dir, "..", "..", "frontend", "dist")),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return None


def get_frontend_index_path() -> str | None:
    dist_dir = get_frontend_dist_dir()
    if not dist_dir:
        return None
    index_path = os.path.join(dist_dir, "index.html")
    if os.path.isfile(index_path):
        return index_path
    return None


def get_frontend_file_path(request_path: str) -> str | None:
    dist_dir = get_frontend_dist_dir()
    if not dist_dir:
        return None

    normalized_path = request_path.lstrip("/")
    candidate = os.path.abspath(os.path.join(dist_dir, normalized_path))
    dist_root = os.path.abspath(dist_dir)
    if candidate != dist_root and not candidate.startswith(dist_root + os.sep):
        return None
    if os.path.isfile(candidate):
        return candidate
    return None


def register_spa_routes(app: FastAPI) -> None:
    @app.get("/")
    async def spa_root():
        index_path = get_frontend_index_path()
        if index_path:
            return FileResponse(index_path)
        return JSONResponse(status_code=404, content=NOT_FOUND_DETAIL)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        frontend_file = get_frontend_file_path(full_path)
        if frontend_file:
            return FileResponse(frontend_file)

        index_path = get_frontend_index_path()
        if index_path:
            return FileResponse(index_path)
        return JSONResponse(status_code=404, content=NOT_FOUND_DETAIL)
