"""Health-check and readiness probe endpoints."""

from typing import Any

from fastapi import Depends, HTTPException
from redis import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from rapidly.integrations.clamav import actions as clamav_service
from rapidly.postgres import AsyncReadSession, get_db_read_session
from rapidly.redis import Redis, get_redis
from rapidly.routing import APIRouter

router = APIRouter(tags=["health"], include_in_schema=False)


@router.get("/healthz")
async def healthz(
    session: AsyncReadSession = Depends(get_db_read_session),
    redis: Redis = Depends(get_redis),
) -> dict[str, str]:
    try:
        await session.execute(select(1))
    except SQLAlchemyError as e:
        raise HTTPException(status_code=503, detail="Database is not available") from e

    try:
        await redis.ping()
    except RedisError as e:
        raise HTTPException(status_code=503, detail="Redis is not available") from e

    return {"status": "ok"}


@router.get("/healthz/security")
async def healthz_security() -> dict[str, Any]:
    """Get security services health status.

    Returns availability of security-related services without exposing
    version or signature details (which could aid evasion).
    """
    clamav_status = await clamav_service.get_status()

    return {
        "status": "ok" if clamav_status.get("available", False) else "degraded",
        "services": {
            "clamav": {
                "enabled": clamav_status.get("enabled", False),
                "available": clamav_status.get("available", False),
            },
        },
    }
