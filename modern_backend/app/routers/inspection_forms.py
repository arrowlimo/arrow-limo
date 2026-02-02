"""
Secure inspection form access with JWT auth, signed URLs, and audit logging
eHOS compliance: Inspection forms with digital signatures and timestamps
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta
from pathlib import Path

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..db import get_connection

router = APIRouter(prefix="/api/inspection-forms", tags=["inspection-forms"])
security = HTTPBearer()

# Use SECRET_KEY from environment (required for auth)
SECRET_KEY = os.environ.get("SECRET_KEY")


def verify_jwt_token(credentials: HTTPAuthorizationCredentials) -> dict:
    """Verify JWT token and return payload"""
    if not SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SECRET_KEY environment variable is required for inspection form authentication",
        )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


def verify_signature(reserve_number: str, expires: int, signature: str) -> None:
    """Verify HMAC signature (prevents URL tampering)"""
    if not SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SECRET_KEY environment variable is required for inspection form authentication",
        )
    current_time = int(datetime.now().timestamp())

    # Check expiration (30 minutes default)
    if current_time > expires:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Link expired")

    # Verify HMAC signature
    expected_sig = hmac.new(
        SECRET_KEY.encode(),
        f"{reserve_number}{expires}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature"
        )


def check_authorization(user_id: int, user_role: str, charter_id: int) -> None:
    """Verify user has permission to access this charter's inspection form"""
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Allow: charter driver, dispatch staff, admins
        if user_role not in ["admin", "dispatch", "dispatcher"]:
            # Regular users can only access their own charters
            cur.execute(
                """
                SELECT employee_id FROM charters
                WHERE charter_id = %s
            """,
                (charter_id,),
            )

            result = cur.fetchone()
            if not result or result[0] != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this inspection form",
                )

        cur.close()
        conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authorization check failed",
        )


def audit_log_access(
    user_id: int, charter_id: int, action: str, ip_address: str
) -> None:
    """Log file access for compliance audit trail"""
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO audit_logs (user_id, action, charter_id, ip_address, timestamp)
            VALUES (%s, %s, %s, %s, NOW())
        """,
            (user_id, action, charter_id, ip_address),
        )

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        # Non-critical: log but don't fail
        print(f"Audit log error: {e}")


@router.post("/signed-url/{reserve_number}")
async def get_signed_url(
    reserve_number: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    expires_in_minutes: int = 30,
) -> dict:
    """
    Generate a signed, time-limited URL for inspection form download

    Usage: POST /api/inspection-forms/signed-url/019123?expires_in_minutes=60
    Returns: {"url": "http://...api/inspection-forms/019123?signature=...&expires=..."}
    """
    try:
        # 1. Verify JWT token
        payload = verify_jwt_token(credentials)
        user_id = payload.get("user_id")
        user_role = payload.get("role", "user")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id",
            )

        # 2. Get charter ID from reserve_number
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT charter_id FROM charters WHERE reserve_number = %s
        """,
            (reserve_number,),
        )

        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Charter not found",
            )

        charter_id = result[0]

        # 3. Verify authorization
        check_authorization(user_id, user_role, charter_id)

        # 4. Generate signature
        expires = int(
            (datetime.now() + timedelta(minutes=expires_in_minutes)).timestamp()
        )
        signature = hmac.new(
            SECRET_KEY.encode(),
            f"{reserve_number}{expires}".encode(),
            hashlib.sha256,
        ).hexdigest()

        # 5. Build signed URL
        base_url = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
        signed_url = f"{base_url}/api/inspection-forms/{reserve_number}?signature={signature}&expires={expires}"

        return {
            "url": signed_url,
            "expires_at": datetime.fromtimestamp(expires).isoformat(),
            "reserve_number": reserve_number,
            "charter_id": charter_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate signed URL",
        )


@router.get("/{reserve_number}")
async def download_inspection_form(
    reserve_number: str,
    signature: str = None,
    expires: int = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None,
) -> FileResponse:
    """
    Download inspection form with security checks

    Usage: GET /api/inspection-forms/019123?signature=...&expires=...

    Security checks:
    - JWT token validation
    - Signature verification (HMAC-SHA256)
    - URL expiration check (30 min default)
    - Authorization check (user/role)
    - Audit logging
    """
    try:
        # 1. Verify JWT token
        payload = verify_jwt_token(credentials)
        user_id = payload.get("user_id")
        user_role = payload.get("role", "user")
        ip_address = request.client.host if request else "unknown"

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user_id",
            )

        # 2. Verify signed URL
        if not signature or not expires:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing signature or expires parameter",
            )

        verify_signature(reserve_number, int(expires), signature)

        # 3. Get charter ID
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT charter_id FROM charters WHERE reserve_number = %s
        """,
            (reserve_number,),
        )

        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Charter not found",
            )

        charter_id = result[0]

        # 4. Verify authorization
        check_authorization(user_id, user_role, charter_id)

        # 5. Audit log the access
        audit_log_access(user_id, charter_id, "download_inspection_form", ip_address)

        # 6. Find and return the file
        inspections_dir = Path("L:/limo/data/inspections") / f"charter_{reserve_number}"

        if not inspections_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No inspection forms found for this charter",
            )

        # Get latest form (PDF preferred, then images)
        forms = sorted(
            list(inspections_dir.glob("inspection_*.pdf"))
            + list(inspections_dir.glob("inspection_*.png"))
            + list(inspections_dir.glob("inspection_*.jpg")),
            reverse=True,
        )

        if not forms:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No inspection form file found",
            )

        form_path = forms[0]

        # Determine media type
        media_type = (
            "application/pd" if form_path.suffix.lower() == ".pd" else "image/jpeg"
        )

        # Return file with security headers
        return FileResponse(
            form_path,
            media_type=media_type,
            filename=form_path.name,
            headers={
                "X-Content-Type-Options": "nosniff",  # Prevent MIME sniffing
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",  # Prevent caching
                "Content-Disposition": f"attachment; filename={form_path.name}",
                "X-Charter-ID": str(charter_id),
                "X-Reserve-Number": reserve_number,
                "X-Downloaded-At": datetime.now().isoformat(),
                "X-Downloaded-By": f"user_{user_id}",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download inspection form",
        )


@router.get("/{reserve_number}/metadata")
async def get_form_metadata(
    reserve_number: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Get metadata about inspection forms (without exposing file)
    Useful for checking if form exists before generating signed URL
    """
    try:
        # 1. Verify JWT token
        payload = verify_jwt_token(credentials)
        user_id = payload.get("user_id")
        user_role = payload.get("role", "user")

        # 2. Get charter ID
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT charter_id FROM charters WHERE reserve_number = %s
        """,
            (reserve_number,),
        )

        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Charter not found",
            )

        charter_id = result[0]

        # 3. Verify authorization
        check_authorization(user_id, user_role, charter_id)

        # 4. Get form metadata
        inspections_dir = Path("L:/limo/data/inspections") / f"charter_{reserve_number}"

        forms = []
        if inspections_dir.exists():
            for form_file in sorted(inspections_dir.glob("inspection_*"), reverse=True):
                stat = form_file.stat()
                forms.append(
                    {
                        "filename": form_file.name,
                        "size_bytes": stat.st_size,
                        "uploaded_at": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                        "type": form_file.suffix.lower(),
                    }
                )

        return {
            "reserve_number": reserve_number,
            "charter_id": charter_id,
            "forms_count": len(forms),
            "forms": forms,
            "latest_form": forms[0] if forms else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get form metadata",
        )
