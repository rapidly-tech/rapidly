"""OAuth account linking actions for customer portal.

Handles token exchange, profile retrieval, and associating third-party
OAuth accounts (Microsoft, Discord) with customers or members.
"""

from typing import Any

import logfire
from httpx_oauth.exceptions import GetProfileError
from httpx_oauth.oauth2 import BaseOAuth2, GetAccessTokenError

from rapidly.customers.customer.queries import CustomerRepository
from rapidly.identity.member.queries import MemberRepository
from rapidly.models import Customer, Member
from rapidly.models.customer import CustomerOAuthAccount, CustomerOAuthPlatform
from rapidly.postgres import AsyncSession


async def exchange_and_link_oauth_account(
    session: AsyncSession,
    oauth_client: BaseOAuth2[Any],
    platform: CustomerOAuthPlatform,
    code: str,
    redirect_uri: str,
    customer: Customer,
    member: Member | None,
) -> tuple[str | None, dict[str, str]]:
    """Exchange an OAuth code, fetch the profile, and link the account.

    Returns ``(None, {})`` on success, or ``(error_message, error_params)`` on failure.
    """
    # Exchange code for access token
    try:
        token_data = await oauth_client.get_access_token(code, redirect_uri)
    except GetAccessTokenError as exc:
        err_params: dict[str, str] = {
            "error": "Failed to get access token. Please try again later.",
            "error_platform": platform.value,
        }
        if exc.response is not None and exc.response.status_code == 429:
            err_params["error"] = f"Rate limited by {platform.value.capitalize()}."
            retry_after = exc.response.headers.get("X-RateLimit-Reset-After")
            if not retry_after and platform == CustomerOAuthPlatform.discord:
                retry_after_ms = exc.response.headers.get("Retry-After")
                if retry_after_ms:
                    retry_after = str(int(retry_after_ms) // 1000)
            if retry_after:
                err_params["error_retry_after"] = retry_after
        with logfire.span(
            "Failed to get access token",
            platform=platform,
            customer_id=str(customer.id),
        ) as span:
            from rapidly.customers.customer_portal.api.oauth_accounts import (
                _extract_response_attrs,
            )

            for k, v in _extract_response_attrs(exc.response).items():
                span.set_attribute(k, v)
        return err_params.get("error"), err_params

    # Fetch profile
    try:
        profile = await oauth_client.get_profile(token_data["access_token"])
    except GetProfileError as exc:
        err_params = {
            "error": "Failed to get profile information. Please try again later.",
            "error_platform": platform.value,
        }
        with logfire.span(
            "Failed to get profile",
            platform=platform,
            customer_id=str(customer.id),
        ) as span:
            from rapidly.customers.customer_portal.api.oauth_accounts import (
                _extract_response_attrs,
            )

            for k, v in _extract_response_attrs(exc.response).items():
                span.set_attribute(k, v)
        return err_params.get("error"), err_params

    # Link OAuth account
    oauth_acct = CustomerOAuthAccount(
        access_token=token_data["access_token"],
        expires_at=token_data["expires_at"],
        refresh_token=token_data["refresh_token"],
        account_id=platform.get_account_id(profile),
        account_username=platform.get_account_username(profile),
    )

    if member is not None:
        member.set_oauth_account(oauth_acct, platform)
        member_repo = MemberRepository.from_session(session)
        await member_repo.update(member)
    else:
        customer.set_oauth_account(oauth_acct, platform)
        customer_repo = CustomerRepository.from_session(session)
        await customer_repo.update(customer)

    return None, {}
