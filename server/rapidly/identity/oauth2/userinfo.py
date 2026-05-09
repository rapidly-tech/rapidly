"""OpenID Connect UserInfo claim builder.

Translates an authenticated subject (user or workspace) and its approved
scopes into the standard OIDC ``UserInfo`` claim set returned by the
``/oauth2/userinfo`` endpoint.
"""

import typing

from authlib.oidc.core import UserInfo

from rapidly.identity.auth.scope import Scope, scope_to_list

from .sub_type import SubTypeValue, is_sub_user, is_sub_workspace


def _build_user_claims(user: typing.Any, scopes: list[Scope]) -> dict[str, typing.Any]:
    """Extract claims for a ``User`` subject based on the granted scopes."""
    claims: dict[str, typing.Any] = {}
    if Scope.email in scopes:
        claims["email"] = user.email
        claims["email_verified"] = user.email_verified
    return claims


def _build_workspace_claims(
    workspace: typing.Any, scopes: list[Scope]
) -> dict[str, typing.Any]:
    """Extract claims for a ``Workspace`` subject based on the granted scopes."""
    claims: dict[str, typing.Any] = {}
    if Scope.openid in scopes:
        claims["name"] = workspace.slug
    return claims


def generate_user_info(sub: SubTypeValue, scope: str) -> UserInfo:
    """Assemble OIDC UserInfo claims for the given subject and scope string."""
    _, subject = sub
    base_claims: dict[str, typing.Any] = {"sub": str(subject.id)}
    granted_scopes = scope_to_list(scope)

    if not granted_scopes:
        return UserInfo(**base_claims)

    if is_sub_user(sub):
        base_claims.update(_build_user_claims(subject, granted_scopes))
    elif is_sub_workspace(sub):
        base_claims.update(_build_workspace_claims(subject, granted_scopes))
    else:
        raise NotImplementedError(f"Unknown subject type: {type(subject)}")

    return UserInfo(**base_claims)


__all__ = ["UserInfo", "generate_user_info"]
