"""Shared domain enums used across multiple modules.

Contains ``TokenType`` and other
cross-cutting enumerations that don't belong to a single module.
"""

from enum import StrEnum


class PaymentProcessor(StrEnum):
    stripe = "stripe"


class AccountType(StrEnum):
    stripe = "stripe"
    manual = "manual"

    def get_display_name(self) -> str:
        return {
            AccountType.stripe: "Stripe Connect Express",
            AccountType.manual: "Manual",
        }[self]


class TokenType(StrEnum):
    client_secret = "rapidly_client_secret"
    client_registration_token = "rapidly_client_registration_token"
    authorization_code = "rapidly_authorization_code"
    access_token = "rapidly_access_token"
    refresh_token = "rapidly_refresh_token"
    personal_access_token = (
        "rapidly_personal_access_token"  # Deprecated: kept for secret scanning compat
    )
    workspace_access_token = "rapidly_workspace_access_token"
    customer_session_token = "rapidly_customer_session_token"
    user_session_token = "rapidly_user_session_token"


class RateLimitGroup(StrEnum):
    web = "web"
    restricted = "restricted"
    default = "default"
    elevated = "elevated"
