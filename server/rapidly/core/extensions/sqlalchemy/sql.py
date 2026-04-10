"""Convenience re-exports of SQLAlchemy SQL constructs.

Centralises imports so that domain modules can write
``from rapidly.core.extensions.sqlalchemy import sql`` and get both
standard SQL operations and PostgreSQL-specific upsert support in one
namespace.
"""

from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.sql import Delete, Select, Update, delete, func, select, update
from sqlalchemy.sql.base import ExecutableOption

__all__ = [
    "Delete",
    "ExecutableOption",
    "Insert",
    "Select",
    "Update",
    "delete",
    "func",
    "insert",
    "select",
    "update",
]
