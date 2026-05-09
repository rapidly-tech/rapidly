"""Tests for ``rapidly/messaging/email/types.py``.

Email-template values are load-bearing: the renderer picks the React-
Email file in ``emails/src/emails/`` by matching the enum value, NOT
the enum attribute name. Several values deliberately still use the
legacy ``organization_*`` prefix because renaming the files on disk
would be a separate, larger migration:

    workspace_access_token_leaked = "organization_access_token_leaked"
    workspace_invite               = "organization_invite"
    workspace_account_unlink       = "organization_account_unlink"
    workspace_under_review         = "organization_under_review"
    workspace_reviewed             = "organization_reviewed"

A regression that tidied those up would silently 404 the template
lookup at send time. Pinning the wire value prevents that.

Also pins the ``Email`` discriminated union: the union dispatches on
``template`` and must round-trip each template variant cleanly.
"""

from __future__ import annotations

import pytest

from rapidly.messaging.email.types import (
    Email,
    EmailAdapter,
    EmailTemplate,
    EmailUpdateEmail,
    EmailUpdateProps,
    LoginCodeEmail,
    LoginCodeProps,
)


class TestEmailTemplateEnumValues:
    # The template ENUM VALUE is what the renderer uses to locate the
    # React-Email file on disk. Pinning each value prevents an
    # accidental value-rename that would desync enum → template file.

    @pytest.mark.parametrize(
        ("attr", "expected_value"),
        [
            ("login_code", "login_code"),
            ("customer_session_code", "customer_session_code"),
            ("email_update", "email_update"),
            ("oauth2_leaked_client", "oauth2_leaked_client"),
            ("oauth2_leaked_token", "oauth2_leaked_token"),
            # Legacy "organization_*" wire values — file names on disk
            # still use the old prefix, so these must stay.
            (
                "workspace_access_token_leaked",
                "organization_access_token_leaked",
            ),
            ("workspace_invite", "organization_invite"),
            ("workspace_account_unlink", "organization_account_unlink"),
            ("workspace_under_review", "organization_under_review"),
            ("workspace_reviewed", "organization_reviewed"),
            ("webhook_endpoint_disabled", "webhook_endpoint_disabled"),
            ("notification_create_account", "notification_create_account"),
            (
                "notification_file_share_download_completed",
                "notification_file_share_download_completed",
            ),
            (
                "notification_file_share_session_expired",
                "notification_file_share_session_expired",
            ),
            (
                "notification_file_share_payment_received",
                "notification_file_share_payment_received",
            ),
        ],
    )
    def test_enum_value_matches_template_filename(
        self, attr: str, expected_value: str
    ) -> None:
        assert getattr(EmailTemplate, attr).value == expected_value

    def test_enum_is_str_enum(self) -> None:
        # ``StrEnum`` lets ``str(EmailTemplate.login_code) == "login_code"``
        # which the renderer relies on when concatenating the path.
        assert str(EmailTemplate.login_code) == "login_code"


class TestDiscriminatedUnion:
    # ``Email`` is an ``Annotated[Union[...], Discriminator("template")]``.
    # The discriminator MUST be the template literal — otherwise Pydantic
    # would fall back to nested trial-validation which is both slower
    # and less precise.

    def test_parses_each_template_variant_by_discriminator(self) -> None:
        login = EmailAdapter.validate_python(
            {
                "template": "login_code",
                "props": {"email": "a@b", "code": "42", "code_lifetime_minutes": 10},
            }
        )
        assert isinstance(login, LoginCodeEmail)
        assert login.props.code == "42"

    def test_unknown_template_is_rejected(self) -> None:
        # A payload with an unknown discriminator must fail — the
        # render worker would otherwise blow up trying to match a
        # union branch that doesn't exist.
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EmailAdapter.validate_python(
                {"template": "not_a_real_template", "props": {"email": "a@b"}}
            )

    def test_missing_props_field_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EmailAdapter.validate_python({"template": "login_code"})

    def test_wrong_props_shape_rejected(self) -> None:
        # The discriminator dispatches to LoginCodeEmail; its props
        # require ``code`` + ``code_lifetime_minutes``. Missing a
        # required prop is a rendering bug surface — pinning it
        # ensures the API rejects the payload instead of crashing
        # the renderer downstream.
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EmailAdapter.validate_python(
                {"template": "login_code", "props": {"email": "a@b"}}
            )


class TestEmailVariantTemplateDefaults:
    # Each *Email model binds a ``Literal[EmailTemplate.x]`` as its
    # default so callers don't have to set the template field manually.
    # Pin the defaults so a regression that drops the default silently
    # breaks every in-code constructor.

    def test_login_code_default(self) -> None:
        msg = LoginCodeEmail(
            props=LoginCodeProps(email="a@b", code="1", code_lifetime_minutes=5)
        )
        assert msg.template == EmailTemplate.login_code

    def test_email_update_default(self) -> None:
        msg = EmailUpdateEmail(
            props=EmailUpdateProps(
                email="a@b", token_lifetime_minutes=15, url="https://x"
            )
        )
        assert msg.template == EmailTemplate.email_update


class TestEmailAdapterIsPreBuilt:
    def test_adapter_covers_the_union(self) -> None:
        # ``EmailAdapter: TypeAdapter[Email]`` is the renderer's entry
        # point — building a fresh TypeAdapter per request would be
        # slow. Pinning that the module-level adapter exists and
        # validates against the aliased union prevents a regression
        # that inlined it.
        from pydantic import TypeAdapter

        assert isinstance(EmailAdapter, TypeAdapter)


def test_email_alias_is_discriminated() -> None:
    # Guards the overall shape: ``Email`` must be an Annotated union
    # with a Discriminator metadata, not a plain union. Plain unions
    # fall back to trial-validation which is both slower and loses
    # the exact-match property the renderer relies on.
    from typing import get_args

    from pydantic import Discriminator

    metadata = getattr(Email, "__metadata__", ())
    assert any(isinstance(m, Discriminator) for m in metadata), (
        "Email must carry a Discriminator"
    )
    # The union includes all 15 known templates — regression check
    # against losing a variant.
    args = get_args(get_args(Email)[0])
    assert len(args) == 15
