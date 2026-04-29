"""
File Storage Router - Role-based file upload/download/list for employees,
vehicles, business documents
"""

import os
import shutil
from pathlib import Path
from typing import Annotated

from anyio import open_file
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..auth import get_current_user, require_roles
from ..settings import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/files", tags=["files"])

# File storage root from environment
FILE_STORAGE_ROOT = Path(os.environ.get("FILE_STORAGE_ROOT", "Z:/limo_files"))
ACCESS_DENIED_DETAIL = "Access denied"

# Role-based access control
ROLE_PERMISSIONS = {
    "admin": [
        "employees",
        "vehicles",
        "business_documents",
        "banking_records",
        "reports",
        "backups",
    ],
    "dispatcher": ["employees", "vehicles", "business_documents", "reports"],
    # Drivers can only access their own employee folder
    "driver": ["employees"],
    "accountant": ["business_documents", "banking_records", "reports"],
}


class FileInfo(BaseModel):
    filename: str
    path: str
    size: int
    modified: str


def check_access(
    category: str,
    user_role: str,
    employee_id: int | None = None,
    target_employee_id: int | None = None,
) -> bool:
    """Check if user has access to category/folder."""
    if user_role == "admin":
        return True

    allowed_categories = ROLE_PERMISSIONS.get(user_role, [])
    if category not in allowed_categories:
        return False

    # Drivers can only access their own employee folder
    if user_role == "driver" and category == "employees":
        return employee_id == target_employee_id

    return True


def create_employee_folder(employee_id: int) -> Path:
    """Create employee folder structure from template."""
    emp_folder = FILE_STORAGE_ROOT / "employees" / str(employee_id)
    if emp_folder.exists():
        return emp_folder

    template = FILE_STORAGE_ROOT / "employees" / "_TEMPLATE"
    shutil.copytree(template, emp_folder)
    return emp_folder


def create_vehicle_folder(vehicle_number: str) -> Path:
    """Create vehicle folder structure from template."""
    vehicle_folder = FILE_STORAGE_ROOT / "vehicles" / vehicle_number
    if vehicle_folder.exists():
        return vehicle_folder

    template = FILE_STORAGE_ROOT / "vehicles" / "_TEMPLATE"
    shutil.copytree(template, vehicle_folder)
    return vehicle_folder


@router.post(
    "/upload/{category}/{entity_id}/{subfolder}",
    responses={403: {"description": ACCESS_DENIED_DETAIL}},
)
async def upload_file(
    category: str,
    entity_id: str,
    subfolder: str,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Upload file to category/entity/subfolder.

    Examples:
    - /api/files/upload/employees/123/licenses
    - /api/files/upload/vehicles/L-1/maintenance
    - /api/files/upload/business_documents/accounting/2025
    """
    user_role = current_user.get("role", "user")
    employee_id = current_user.get("employee_id")

    # Check access
    target_employee_id = int(entity_id) if category == "employees" else None
    if not check_access(category, user_role, employee_id, target_employee_id):
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_DETAIL)

    # Construct target path
    target_dir = FILE_STORAGE_ROOT / category / entity_id / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / file.filename

    # Save file
    async with await open_file(target_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    return {
        "filename": file.filename,
        "path": str(target_path.relative_to(FILE_STORAGE_ROOT)),
        "size": len(content),
    }


@router.get(
    "/list/{category}/{entity_id}/{subfolder}",
    responses={403: {"description": ACCESS_DENIED_DETAIL}},
)
async def list_files(
    category: str,
    entity_id: str,
    subfolder: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[FileInfo]:
    """List files in category/entity/subfolder."""
    user_role = current_user.get("role", "user")
    employee_id = current_user.get("employee_id")

    target_employee_id = int(entity_id) if category == "employees" else None
    if not check_access(category, user_role, employee_id, target_employee_id):
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_DETAIL)

    target_dir = FILE_STORAGE_ROOT / category / entity_id / subfolder
    if not target_dir.exists():
        return []

    files = []
    for item in target_dir.iterdir():
        if item.is_file() and item.name != ".gitkeep":
            stat = item.stat()
            files.append(
                FileInfo(
                    filename=item.name,
                    path=str(item.relative_to(FILE_STORAGE_ROOT)),
                    size=stat.st_size,
                    modified=str(stat.st_mtime),
                )
            )

    return files


@router.get(
    "/download/{category}/{entity_id}/{subfolder}/{filename}",
    responses={
        403: {"description": ACCESS_DENIED_DETAIL},
        404: {"description": "File not found"},
    },
)
async def download_file(
    category: str,
    entity_id: str,
    subfolder: str,
    filename: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Download file from category/entity/subfolder."""
    user_role = current_user.get("role", "user")
    employee_id = current_user.get("employee_id")

    target_employee_id = int(entity_id) if category == "employees" else None
    if not check_access(category, user_role, employee_id, target_employee_id):
        raise HTTPException(status_code=403, detail=ACCESS_DENIED_DETAIL)

    target_path = (
        FILE_STORAGE_ROOT / category / entity_id / subfolder / filename
    )
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(target_path, filename=filename)


@router.delete(
    "/delete/{category}/{entity_id}/{subfolder}/{filename}",
    responses={
        403: {"description": "Only admins can delete files"},
        404: {"description": "File not found"},
    },
)
async def delete_file(
    category: str,
    entity_id: str,
    subfolder: str,
    filename: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Delete file from category/entity/subfolder."""
    user_role = current_user.get("role", "user")

    # Only admin can delete files
    if user_role != "admin":
        raise HTTPException(
            status_code=403, detail="Only admins can delete files"
        )

    target_path = (
        FILE_STORAGE_ROOT / category / entity_id / subfolder / filename
    )
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    target_path.unlink()
    return {"status": "deleted", "filename": filename}


@router.post("/employees/{employee_id}/create-folder")
async def create_employee_folder_endpoint(
    employee_id: int,
    current_user: Annotated[
        dict, Depends(require_roles("admin", "manager", "super_user"))
    ],
):
    """Create employee folder structure (called when new employee is added)."""
    folder = create_employee_folder(employee_id)
    return {"employee_id": employee_id, "folder": str(folder)}


@router.post("/vehicles/{vehicle_number}/create-folder")
async def create_vehicle_folder_endpoint(
    vehicle_number: str,
    current_user: Annotated[
        dict, Depends(require_roles("admin", "manager", "super_user"))
    ],
):
    """Create vehicle folder structure (called when new vehicle is added)."""
    folder = create_vehicle_folder(vehicle_number)
    return {"vehicle_number": vehicle_number, "folder": str(folder)}
