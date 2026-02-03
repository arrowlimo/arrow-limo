"""Locked charter enforcement utilities."""

from fastapi import HTTPException, status
from psycopg2.extras import RealDictCursor


def check_charter_locked(charter_id: int, db_cursor) -> bool:
    """Check if a charter is locked."""
    try:
        db_cursor.execute("SELECT locked FROM charters WHERE charter_id = %s", (charter_id,))
        result = db_cursor.fetchone()
        return result[0] if result else False
    except Exception:
        return False


def enforce_charter_not_locked(charter_id: int, db_cursor, operation: str = "update") -> None:
    """Raise exception if charter is locked."""
    if check_charter_locked(charter_id, db_cursor):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Charter {charter_id} is locked and cannot be {operation}d. "
            "Contact administrator to unlock if changes are needed.",
        )


def lock_charter(charter_id: int, db_cursor) -> None:
    """Lock a charter to prevent further modifications."""
    try:
        db_cursor.execute(
            "UPDATE charters SET locked = TRUE WHERE charter_id = %s",
            (charter_id,),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to lock charter: {str(e)}",
        )


def unlock_charter(charter_id: int, db_cursor) -> None:
    """Unlock a charter to allow modifications (admin only)."""
    try:
        db_cursor.execute(
            "UPDATE charters SET locked = FALSE WHERE charter_id = %s",
            (charter_id,),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unlock charter: {str(e)}",
        )
