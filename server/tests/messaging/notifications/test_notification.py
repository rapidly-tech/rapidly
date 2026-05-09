"""Tests for ``rapidly/messaging/notifications/notification.py``.

Notification type registry + payload contract. Four load-bearing
surfaces:

- ``NotificationType.workspace_create_account`` keeps the historical
  wire value ``MaintainerCreateAccountNotification`` for DB-row
  compatibility (the column was renamed from ``maintainer`` to
  ``workspace`` in the API but the DB enum kept the old string).
  Drift would require a data migration on every existing row.
- Each ``*NotificationPayload``'s ``subject()`` interpolates the
  payload fields into a customer-facing email subject. Drift would
  blank out the subject (showing "(no subject)") or leak field names.
- ``template_name()`` returns the React-email template stem (no
  extension). Drift in the stem name would 404 the renderer
  subprocess and silently send blank emails.
- Discriminated union — each ``*Notification`` model carries a
  ``Literal[NotificationType.<x>]`` so Pydantic dispatches correctly
  on the wire ``type`` field. Drift would let an attacker forge
  one notification class as another.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from rapidly.messaging.notifications.notification import (
    FileShareDownloadCompletedNotification,
    FileShareDownloadCompletedNotificationPayload,
    FileSharePaymentReceivedNotification,
    FileSharePaymentReceivedNotificationPayload,
    FileShareSessionExpiredNotification,
    FileShareSessionExpiredNotificationPayload,
    Notification,
    NotificationPayloadBase,
    NotificationType,
    WorkspaceCreateAccountNotification,
    WorkspaceCreateAccountNotificationPayload,
)


class TestNotificationType:
    def test_is_str_enum(self) -> None:
        # StrEnum so wire-format value round-trips through Pydantic
        # / Postgres without an explicit serialiser.
        assert issubclass(NotificationType, StrEnum)

    def test_workspace_create_account_keeps_legacy_db_value(self) -> None:
        # Pin the legacy wire value. Drift would break every
        # existing row in the notifications table; renaming
        # requires a data migration, not a code change.
        assert (
            NotificationType.workspace_create_account.value
            == "MaintainerCreateAccountNotification"
        )

    def test_member_set_pinned(self) -> None:
        # Pin the exact set so adding a new type without a
        # corresponding handler isn't silent.
        assert {t.value for t in NotificationType} == {
            "MaintainerCreateAccountNotification",
            "FileShareDownloadCompletedNotification",
            "FileShareSessionExpiredNotification",
            "FileSharePaymentReceivedNotification",
        }


class TestWorkspaceCreateAccountPayload:
    def test_subject_includes_workspace_name(self) -> None:
        # Pin: workspace name is interpolated into the subject so
        # multi-workspace customers can distinguish notifications.
        p = WorkspaceCreateAccountNotificationPayload(
            workspace_name="Acme", url="https://x"
        )
        assert "Acme" in p.subject()
        # Pin the exact subject — copy is approved messaging.
        assert p.subject() == "Create a payout account for Acme now to receive funds"

    def test_template_name(self) -> None:
        # Pin: template stem matches the React-email source. Drift
        # would 404 the renderer subprocess.
        assert (
            WorkspaceCreateAccountNotificationPayload.template_name()
            == "notification_create_account"
        )


class TestFileShareDownloadCompletedPayload:
    def test_subject_includes_file_name(self) -> None:
        p = FileShareDownloadCompletedNotificationPayload(file_name="report.pdf")
        assert "report.pdf" in p.subject()
        assert p.subject() == "Someone downloaded your file: report.pdf"

    def test_template_name(self) -> None:
        assert (
            FileShareDownloadCompletedNotificationPayload.template_name()
            == "notification_file_share_download_completed"
        )


class TestFileShareSessionExpiredPayload:
    def test_subject_includes_file_name(self) -> None:
        p = FileShareSessionExpiredNotificationPayload(file_name="report.pdf")
        assert p.subject() == "Your share link has expired: report.pdf"

    def test_template_name(self) -> None:
        assert (
            FileShareSessionExpiredNotificationPayload.template_name()
            == "notification_file_share_session_expired"
        )


class TestFileSharePaymentReceivedPayload:
    def test_subject_includes_file_name_and_amount(self) -> None:
        # Pin: BOTH file_name and formatted_amount appear so the
        # creator sees the financial detail in the subject (mobile
        # push shows only subject, not body).
        p = FileSharePaymentReceivedNotificationPayload(
            file_name="report.pdf", formatted_amount="$10.00"
        )
        assert p.subject() == "Payment received for report.pdf: $10.00"

    def test_template_name(self) -> None:
        assert (
            FileSharePaymentReceivedNotificationPayload.template_name()
            == "notification_file_share_payment_received"
        )


class TestNotificationPayloadBaseAbstract:
    def test_subject_is_abstract(self) -> None:
        # Pin: NotificationPayloadBase requires subject() and
        # template_name() — a regression that gave them defaults
        # would let a new subclass ship with no subject (sends
        # "(no subject)" emails).
        assert getattr(NotificationPayloadBase.subject, "__isabstractmethod__", False)

    def test_template_name_is_abstract(self) -> None:
        assert getattr(
            NotificationPayloadBase.template_name, "__isabstractmethod__", False
        )


class TestNotificationDiscriminatedUnion:
    def _base(self, type_: NotificationType, payload: object) -> dict[str, object]:
        return {
            "id": uuid4(),
            "created_at": datetime(2026, 1, 1),
            "type": type_,
            "payload": payload,
        }

    def test_workspace_create_dispatches_correctly(self) -> None:
        # Pin: Pydantic discriminator on the ``type`` Literal selects
        # the right model. Drift in the Literal would let an
        # attacker submit one type with another's payload schema.
        adapter: TypeAdapter[Notification] = TypeAdapter(Notification)
        notif = adapter.validate_python(
            self._base(
                NotificationType.workspace_create_account,
                {"workspace_name": "Acme", "url": "https://x"},
            )
        )
        assert isinstance(notif, WorkspaceCreateAccountNotification)

    def test_download_completed_dispatches_correctly(self) -> None:
        adapter: TypeAdapter[Notification] = TypeAdapter(Notification)
        notif = adapter.validate_python(
            self._base(
                NotificationType.file_share_download_completed,
                {"file_name": "x.pdf"},
            )
        )
        assert isinstance(notif, FileShareDownloadCompletedNotification)

    def test_session_expired_dispatches_correctly(self) -> None:
        adapter: TypeAdapter[Notification] = TypeAdapter(Notification)
        notif = adapter.validate_python(
            self._base(
                NotificationType.file_share_session_expired,
                {"file_name": "x.pdf"},
            )
        )
        assert isinstance(notif, FileShareSessionExpiredNotification)

    def test_payment_received_dispatches_correctly(self) -> None:
        adapter: TypeAdapter[Notification] = TypeAdapter(Notification)
        notif = adapter.validate_python(
            self._base(
                NotificationType.file_share_payment_received,
                {"file_name": "x.pdf", "formatted_amount": "$1"},
            )
        )
        assert isinstance(notif, FileSharePaymentReceivedNotification)

    def test_mismatched_type_and_payload_rejected(self) -> None:
        # Pin: a mismatch between ``type`` and ``payload`` shape is
        # rejected (NOT silently accepted). This is the security
        # invariant the discriminated union provides — without it,
        # an attacker could submit a payment-received-shaped
        # payload under a download-completed type and bypass
        # validation.
        adapter: TypeAdapter[Notification] = TypeAdapter(Notification)
        with pytest.raises(ValidationError):
            adapter.validate_python(
                self._base(
                    NotificationType.file_share_payment_received,
                    # Missing formatted_amount — payload doesn't
                    # match the discriminator's schema.
                    {"file_name": "x.pdf"},
                )
            )
