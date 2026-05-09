"""Admin panel webhooks section: re-exports the webhooks router."""

from .api import router

__all__ = ["router"]
