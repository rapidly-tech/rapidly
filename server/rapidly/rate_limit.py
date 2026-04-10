"""ASGI rate-limiting middleware configuration.

Builds the ``RateLimitMiddleware`` with per-route rules extracted from
each endpoint's rate-limit annotations, using the authenticated
principal (or client IP as fallback) as the throttle key.
"""

from collections.abc import Sequence

from ratelimit import RateLimitMiddleware, Rule
from ratelimit.auths import EmptyInformation
from ratelimit.auths.ip import client_ip
from ratelimit.backends.redis import RedisBackend
from ratelimit.types import ASGIApp, Scope

from rapidly.config import Environment, settings
from rapidly.enums import RateLimitGroup
from rapidly.identity.auth.models import AuthPrincipal, Subject, is_anonymous_principal
from rapidly.redis import create_redis

# ── Helpers ──


async def _authenticate(scope: Scope) -> tuple[str, RateLimitGroup]:
    auth_subject: AuthPrincipal[Subject] = scope["state"]["auth_subject"]

    if is_anonymous_principal(auth_subject):
        try:
            ip, _ = await client_ip(scope)
            return ip, RateLimitGroup.default
        except EmptyInformation:
            return auth_subject.rate_limit_key

    return auth_subject.rate_limit_key


# ── Configuration ──

_BASE_RULES: dict[str, Sequence[Rule]] = {
    "^/v1/login-code": [Rule(minute=6, hour=12, block_time=900, zone="login-code")],
    "^/v1/customer-portal/customer-session/(request|authenticate)": [
        Rule(minute=6, hour=12, block_time=900, zone="customer-session-login")
    ],
    # File sharing channel creation - prevent spam
    "^/v1/file-sharing/channels$": [
        Rule(minute=10, hour=50, block_time=300, zone="file-sharing-create")
    ],
    # File sharing channel fetch - prevent enumeration/scanning
    # Uses .+ to match both short slugs (abc123) and long slugs (bacon/cheese/tomato)
    "^/v1/file-sharing/channels/.+/renew$": [
        Rule(minute=30, block_time=60, zone="file-sharing-renew")
    ],
    # File sharing reader-token registration - normal operational endpoint
    "^/v1/file-sharing/channels/.+/reader-token$": [
        Rule(minute=30, block_time=60, zone="file-sharing-reader-token")
    ],
    # File sharing password attempt - rate limit to prevent brute-force
    "^/v1/file-sharing/channels/.+/password-attempt$": [
        Rule(minute=15, block_time=120, zone="file-sharing-password-attempt")
    ],
    # File sharing download-complete - normal operational endpoint
    "^/v1/file-sharing/channels/.+/download-complete$": [
        Rule(minute=30, block_time=60, zone="file-sharing-download-complete")
    ],
    # File sharing channel destruction - prevent abuse
    "^/v1/file-sharing/channels/.+/destroy$": [
        Rule(minute=5, block_time=120, zone="file-sharing-delete")
    ],
    # File sharing channel report - destructive action, keep strict
    "^/v1/file-sharing/channels/.+/report$": [
        Rule(minute=5, block_time=120, zone="file-sharing-report")
    ],
    # File sharing channel fetch (catch-all for slug paths without sub-actions)
    "^/v1/file-sharing/channels/.+$": [
        Rule(minute=60, block_time=60, zone="file-sharing-channel-fetch")
    ],
    # File sharing text secret creation - prevent spam
    "^/v1/file-sharing/secret$": [
        Rule(minute=20, hour=100, block_time=300, zone="file-sharing-secret-create")
    ],
    # File sharing text secret fetch - prevent enumeration attacks
    "^/v1/file-sharing/secret/.+$": [
        Rule(minute=30, block_time=60, zone="file-sharing-secret-fetch")
    ],
    # File sharing file secret creation - prevent spam (stricter due to larger payloads)
    "^/v1/file-sharing/file$": [
        Rule(minute=10, hour=50, block_time=300, zone="file-sharing-file-create")
    ],
    # File sharing file secret fetch - prevent enumeration attacks
    "^/v1/file-sharing/file/.+$": [
        Rule(minute=30, block_time=60, zone="file-sharing-file-fetch")
    ],
    # File sharing ICE config - prevent abuse of TURN credential generation
    "^/v1/file-sharing/ice/.+$": [
        Rule(minute=20, block_time=60, zone="file-sharing-ice")
    ],
}

_SANDBOX_RULES: dict[str, Sequence[Rule]] = {
    **_BASE_RULES,
    "^/v1": [
        Rule(group=RateLimitGroup.restricted, minute=10, zone="api"),
        Rule(group=RateLimitGroup.default, minute=100, zone="api"),
        Rule(group=RateLimitGroup.web, second=50, zone="api"),
        Rule(group=RateLimitGroup.elevated, second=50, zone="api"),
    ],
}

_PRODUCTION_RULES: dict[str, Sequence[Rule]] = {
    **_BASE_RULES,
    "^/v1": [
        Rule(group=RateLimitGroup.restricted, minute=60, zone="api"),
        Rule(group=RateLimitGroup.default, minute=500, zone="api"),
        Rule(group=RateLimitGroup.web, second=100, zone="api"),
        Rule(group=RateLimitGroup.elevated, second=100, zone="api"),
    ],
}


# ── Middleware ──


def get_middleware(app: ASGIApp) -> RateLimitMiddleware:
    match settings.ENV:
        case Environment.production:
            rules = _PRODUCTION_RULES
        case Environment.sandbox | Environment.test:
            rules = _SANDBOX_RULES
        case _:
            rules = {}
    return RateLimitMiddleware(
        app, _authenticate, RedisBackend(create_redis("rate-limit")), rules
    )


__all__ = ["get_middleware"]
