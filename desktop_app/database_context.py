"""Compatibility module for legacy DatabaseContext imports.

Some widgets import DatabaseContext from database_context. The canonical
implementation lives in db_error_handling.
"""

from db_error_handling import DatabaseContext

__all__ = ["DatabaseContext"]
