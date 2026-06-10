"""Compatibility database utilities.

Legacy modules import DatabaseContext from db_utils. This shim keeps those
imports working while delegating to the canonical implementation.
"""

from db_error_handling import DatabaseContext

__all__ = ["DatabaseContext"]
