"""Rapidly ORM foundation layer.

Re-exports the base classes that every domain model builds on.  The
typical import for a new table definition is::

    from rapidly.core.db.models import BaseEntity

Use ``Model`` or ``UUIDModel`` directly only for association tables or
other lightweight mappings that don't need audit timestamps.
"""

from .base import AuditableModel, BaseEntity, Model, RateLimitMixin, UUIDModel

__all__ = ["AuditableModel", "BaseEntity", "Model", "RateLimitMixin", "UUIDModel"]
