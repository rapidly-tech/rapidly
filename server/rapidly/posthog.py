"""PostHog analytics integration for Rapidly.

Wraps the PostHog SDK in a singleton ``Service`` that degrades gracefully
when no API key is configured.  Events are enriched with standard user
and workspace properties automatically.
"""

from __future__ import annotations

from typing import Any, Literal

from posthog import Posthog

from rapidly.config import settings
from rapidly.core.geolocation import GeoInfo
from rapidly.identity.auth.models import (
    AuthPrincipal,
    Subject,
    is_user_principal,
    is_workspace_principal,
)
from rapidly.models import User, Workspace

# Group-analytics sentinel used when capturing workspace-scoped events
# without an individual user.  See PostHog docs on group events.
WORKSPACE_EVENT_DISTINCT_ID = "workspace_event"

EventCategory = Literal[
    "user",
    "workspaces",
    "file_sharing",
]
EventNoun = str
EventVerb = Literal[
    "click",
    "submit",
    "create",
    "view",
    "add",
    "invite",
    "update",
    "delete",
    "remove",
    "start",
    "end",
    "cancel",
    "fail",
    "generate",
    "send",
    "archive",
    "done",
    "open",
    "close",
]


def _format_event_name(
    category: EventCategory, noun: EventNoun, verb: EventVerb
) -> str:
    """Build the structured event key sent to PostHog.

    All backend events use ``backend`` as the surface identifier so they
    can be distinguished from client-side analytics.
    """
    return f"backend:{category}:{noun}:{verb}"


def _extract_signup_attrs(user: User) -> dict[str, Any]:
    """Pull signup-attribution fields from the user record, if present."""
    attribution = user.signup_attribution
    if not attribution:
        return {}
    return {f"signup_{k}": v for k, v in attribution.items()}


class Service:
    """Thin PostHog wrapper with environment-aware initialisation."""

    client: Posthog | None = None

    # -- Lifecycle ------------------------------------------------------------

    def configure(self) -> None:
        api_key = settings.POSTHOG_PROJECT_API_KEY
        if not api_key:
            self.client = None
            return
        self.client = Posthog(api_key)
        self.client.disabled = settings.is_testing()
        self.client.debug = settings.POSTHOG_DEBUG

    # -- Low-level capture ----------------------------------------------------

    def capture(
        self,
        distinct_id: str,
        event: str,
        *,
        properties: dict[str, Any] | None = None,
        groups: dict[str, Any] | None = None,
    ) -> None:
        if self.client is None:
            return
        merged_props = {**self._env_properties(), **(properties or {})}
        self.client.capture(
            event,
            distinct_id=distinct_id,
            groups=groups,
            properties=merged_props,
        )

    # -- High-level event helpers --------------------------------------------

    def auth_subject_event(
        self,
        auth_subject: AuthPrincipal[Subject],
        category: EventCategory,
        noun: EventNoun,
        verb: EventVerb,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if is_user_principal(auth_subject):
            self.user_event(auth_subject.subject, category, noun, verb, properties)
        elif is_workspace_principal(auth_subject):
            self.workspace_event(auth_subject.subject, category, noun, verb, properties)
        else:
            self.anonymous_event(category, noun, verb, properties)

    def anonymous_event(
        self,
        category: EventCategory,
        noun: EventNoun,
        verb: EventVerb,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Record an event with no associated user or workspace."""
        self.capture(
            distinct_id="rapidly_anonymous",
            event=_format_event_name(category, noun, verb),
            properties={**self._env_properties(), **(properties or {})},
        )

    def user_event(
        self,
        user: User,
        category: EventCategory,
        noun: EventNoun,
        verb: EventVerb,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self.capture(
            user.posthog_distinct_id,
            event=_format_event_name(category, noun, verb),
            properties={
                **self._env_properties(),
                "$set": self._user_traits(user),
                **(properties or {}),
            },
        )

    def workspace_event(
        self,
        workspace: Workspace,
        category: EventCategory,
        noun: EventNoun,
        verb: EventVerb,
        properties: dict[str, Any] | None = None,
    ) -> None:
        self.capture(
            WORKSPACE_EVENT_DISTINCT_ID,
            event=_format_event_name(category, noun, verb),
            groups={"workspace": str(workspace.id)},
            properties={**self._env_properties(), **(properties or {})},
        )

    # -- Identity management --------------------------------------------------

    def identify(self, user: User) -> None:
        if self.client is None:
            return
        self.client.set(
            distinct_id=user.posthog_distinct_id,
            properties={**self._env_properties(), **self._user_traits(user)},
        )

    def user_login(
        self,
        user: User,
        method: Literal["microsoft", "google", "apple", "ml", "code"],
        geo: GeoInfo | None = None,
    ) -> None:
        self.identify(user)
        props: dict[str, Any] = {"method": method}
        if geo and geo.country:
            props.update(
                {
                    "$geoip_country_code": geo.country,
                    "$geoip_continent_code": geo.continent,
                }
            )
        self.user_event(user, "user", "login", "done", props)

    def user_signup(
        self,
        user: User,
        method: Literal["microsoft", "google", "apple", "ml", "code"],
        geo: GeoInfo | None = None,
    ) -> None:
        self.identify(user)
        props: dict[str, Any] = {"method": method}
        if geo and geo.country:
            props.update(
                {
                    "$geoip_country_code": geo.country,
                    "$geoip_continent_code": geo.continent,
                }
            )
        self.user_event(user, "user", "signup", "done", props)

    # -- Internal helpers -----------------------------------------------------

    @staticmethod
    def _env_properties() -> dict[str, Any]:
        return {"_environment": settings.ENV}

    @staticmethod
    def _user_traits(user: User) -> dict[str, Any]:
        base = {"email": user.email, "verified": user.email_verified}
        base.update(_extract_signup_attrs(user))
        return base


# Module-level singleton and convenience initialiser.
posthog = Service()


def configure_posthog() -> None:
    """Bootstrap the PostHog singleton from application settings."""
    posthog.configure()
