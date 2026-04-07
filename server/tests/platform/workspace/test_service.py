"""Tests for workspace service."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture

from rapidly.config import Environment, settings
from rapidly.enums import AccountType
from rapidly.errors import RequestValidationError
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models import Share, User, Workspace
from rapidly.models.account import Account
from rapidly.models.user import IdentityVerificationStatus
from rapidly.models.workspace import (
    WorkspaceNotificationSettings,
    WorkspaceStatus,
)
from rapidly.models.workspace_review import WorkspaceReview
from rapidly.platform.workspace import actions as workspace_service
from rapidly.platform.workspace.types import (
    WorkspaceCreate,
    WorkspaceFeatureSettings,
    WorkspaceUpdate,
)
from rapidly.platform.workspace_membership import (
    actions as workspace_membership_service,
)
from rapidly.postgres import AsyncSession
from tests.fixtures.database import SaveFixture

# ── create_workspace ──


@pytest.mark.asyncio
class TestCreate:
    @pytest.mark.auth
    @pytest.mark.parametrize(
        "slug",
        [
            "",
            "a",
            "ab",
            "Rapidly Software Inc 🌀",
            "slug/with/slashes",
            *settings.WORKSPACE_SLUG_RESERVED_KEYWORDS,
        ],
    )
    async def test_slug_validation(
        self, slug: str, auth_subject: AuthPrincipal[User], session: AsyncSession
    ) -> None:
        with pytest.raises(ValidationError):
            await workspace_service.create(
                session,
                WorkspaceCreate(name="My New Workspace", slug=slug),
                auth_subject,
            )

    @pytest.mark.auth
    async def test_existing_slug(
        self,
        auth_subject: AuthPrincipal[User],
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        with pytest.raises(RequestValidationError):
            await workspace_service.create(
                session,
                WorkspaceCreate(name=workspace.name, slug=workspace.slug),
                auth_subject,
            )

    @pytest.mark.auth
    @pytest.mark.parametrize("slug", ["rapidly-software-inc", "slug-with-dashes"])
    async def test_valid(
        self,
        slug: str,
        mocker: MockerFixture,
        auth_subject: AuthPrincipal[User],
        session: AsyncSession,
    ) -> None:
        enqueue_job_mock = mocker.patch(
            "rapidly.platform.workspace.actions.dispatch_task"
        )

        workspace = await workspace_service.create(
            session,
            WorkspaceCreate(name="My New Workspace", slug=slug),
            auth_subject,
        )

        assert workspace.name == "My New Workspace"
        assert workspace.slug == slug
        assert workspace.feature_settings == {"member_model_enabled": True}

        workspace_membership = await workspace_membership_service.get_by_user_and_org(
            session, auth_subject.subject.id, workspace.id
        )
        assert workspace_membership is not None

        enqueue_job_mock.assert_called_once_with(
            "workspace.created", workspace_id=workspace.id
        )

    @pytest.mark.auth
    async def test_valid_with_feature_settings(
        self, auth_subject: AuthPrincipal[User], session: AsyncSession
    ) -> None:
        workspace = await workspace_service.create(
            session,
            WorkspaceCreate(
                name="My New Workspace",
                slug="my-new-workspace",
                feature_settings=WorkspaceFeatureSettings(member_model_enabled=True),
            ),
            auth_subject,
        )

        assert workspace.name == "My New Workspace"

        assert workspace.feature_settings["member_model_enabled"] is True

    @pytest.mark.auth
    async def test_valid_with_notification_settings(
        self, auth_subject: AuthPrincipal[User], session: AsyncSession
    ) -> None:
        workspace = await workspace_service.create(
            session,
            WorkspaceCreate(
                name="My New Workspace",
                slug="my-new-workspace",
                notification_settings=WorkspaceNotificationSettings(
                    new_payment=False,
                ),
            ),
            auth_subject,
        )

        assert workspace.notification_settings == {
            "new_payment": False,
        }

    @pytest.mark.auth
    async def test_valid_with_defaults(
        self, auth_subject: AuthPrincipal[User], session: AsyncSession
    ) -> None:
        workspace = await workspace_service.create(
            session,
            WorkspaceCreate(
                name="My New Workspace",
                slug="my-new-workspace",
            ),
            auth_subject,
        )

        assert workspace is not None
        assert workspace.name == "My New Workspace"


# ── confirm_workspace_reviewed ──


@pytest.mark.asyncio
class TestConfirmWorkspaceReviewed:
    async def test_initial_review(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Given workspace under review
        workspace.status = WorkspaceStatus.INITIAL_REVIEW

        enqueue_job_mock = mocker.patch(
            "rapidly.platform.workspace.actions.dispatch_task"
        )

        # When
        result = await workspace_service.confirm_workspace_reviewed(
            session, workspace, 15000
        )

        # Then
        assert result.status == WorkspaceStatus.ACTIVE
        assert result.initially_reviewed_at is not None
        assert result.next_review_threshold == 15000
        enqueue_job_mock.assert_called_once_with(
            "workspace.reviewed",
            workspace_id=workspace.id,
            initial_review=True,
        )

    async def test_ongoing_review(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Given workspace under review
        workspace.status = WorkspaceStatus.ONGOING_REVIEW
        initially_reviewed_at = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
        workspace.initially_reviewed_at = initially_reviewed_at

        enqueue_job_mock = mocker.patch(
            "rapidly.platform.workspace.actions.dispatch_task"
        )

        # When
        result = await workspace_service.confirm_workspace_reviewed(
            session, workspace, 15000
        )

        # Then
        assert result.status == WorkspaceStatus.ACTIVE
        assert result.initially_reviewed_at == initially_reviewed_at
        assert result.next_review_threshold == 15000
        enqueue_job_mock.assert_called_once_with(
            "workspace.reviewed",
            workspace_id=workspace.id,
            initial_review=False,
        )


# ── deny_workspace ──


@pytest.mark.asyncio
class TestDenyWorkspace:
    async def test_deny_workspace(
        self,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Given workspace active
        workspace.status = WorkspaceStatus.ACTIVE

        # When
        result = await workspace_service.deny_workspace(session, workspace)

        # Then
        assert result.status == WorkspaceStatus.DENIED


# ── set_workspace_under_review ──


@pytest.mark.asyncio
class TestSetWorkspaceUnderReview:
    async def test_set_workspace_under_review(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        workspace: Workspace,
    ) -> None:
        # Given workspace active
        workspace.status = WorkspaceStatus.ACTIVE

        enqueue_job_mock = mocker.patch(
            "rapidly.platform.workspace.actions.dispatch_task"
        )

        # When
        result = await workspace_service.set_workspace_under_review(session, workspace)

        # Then
        assert result.status == WorkspaceStatus.ONGOING_REVIEW
        enqueue_job_mock.assert_called_once_with(
            "workspace.under_review", workspace_id=workspace.id
        )


# ── get_payment_status ──


@pytest.mark.asyncio
class TestGetPaymentStatus:
    async def test_all_steps_incomplete(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        # Make this a new workspace (not grandfathered)
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        await save_fixture(workspace)

        # Workspace with no account setup
        payment_status = await workspace_service.get_payment_status(session, workspace)

        assert payment_status.payment_ready is False
        assert len(payment_status.steps) == 3

        setup_account_step = next(
            s for s in payment_status.steps if s.id == "setup_account"
        )
        assert setup_account_step.completed is False

    async def test_with_product_created_but_no_account(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        share: Share,
    ) -> None:
        # Make this a new workspace (not grandfathered)
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        await save_fixture(workspace)

        # Workspace with a share but no account setup
        payment_status = await workspace_service.get_payment_status(session, workspace)

        assert payment_status.payment_ready is False

        setup_account_step = next(
            s for s in payment_status.steps if s.id == "setup_account"
        )
        assert setup_account_step.completed is False

    async def test_without_account_setup(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        # Make this a new workspace (not grandfathered)
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        await save_fixture(workspace)

        # Workspace without account setup
        payment_status = await workspace_service.get_payment_status(session, workspace)

        assert payment_status.payment_ready is False

        setup_account_step = next(
            s for s in payment_status.steps if s.id == "setup_account"
        )
        assert setup_account_step.completed is False

    async def test_with_account_setup_complete(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
    ) -> None:
        # Make this a new workspace (not grandfathered)
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)

        user.identity_verification_status = IdentityVerificationStatus.verified
        await save_fixture(user)

        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="STRIPE_ACCOUNT_ID",
        )
        await save_fixture(account)

        workspace.account = account
        workspace.account_id = account.id
        workspace.details_submitted_at = datetime.now(UTC)
        workspace.details = {"about": "Test"}  # type: ignore
        await save_fixture(workspace)

        # Ensure relationships are loaded
        await session.refresh(workspace, attribute_names=["account"])
        await session.refresh(workspace.account, attribute_names=["admin"])

        payment_status = await workspace_service.get_payment_status(session, workspace)

        # Account setup step should be complete but payment_ready requires all steps
        setup_account_step = next(
            s for s in payment_status.steps if s.id == "setup_account"
        )
        assert setup_account_step.completed is True

        # Without shares or API keys, not all steps are complete
        assert payment_status.payment_ready is False

    async def test_all_steps_complete_grandfathered(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        share: Share,
        user: User,
    ) -> None:
        # Set up a complete account so payment is ready
        user.identity_verification_status = IdentityVerificationStatus.verified
        await save_fixture(user)

        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="STRIPE_ACCOUNT_ID",
        )
        await save_fixture(account)

        workspace.account = account
        workspace.account_id = account.id
        workspace.details_submitted_at = datetime.now(UTC)
        workspace.details = {"about": "Test"}  # type: ignore
        await save_fixture(workspace)

        await session.refresh(workspace, attribute_names=["account"])
        await session.refresh(workspace.account, attribute_names=["admin"])

        payment_status = await workspace_service.get_payment_status(session, workspace)

        # Should be payment ready with account setup complete
        assert payment_status.payment_ready is True

    async def test_all_steps_complete_new_org(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        share: Share,
        user: User,
        mocker: MockerFixture,
    ) -> None:
        # Set up as new workspace
        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        workspace.status = WorkspaceStatus.ACTIVE
        workspace.details_submitted_at = datetime.now(UTC)
        workspace.details = {"about": "Test"}  # type: ignore

        # Set up user verification
        user.identity_verification_status = IdentityVerificationStatus.verified
        await save_fixture(user)

        # Set up account
        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="STRIPE_ACCOUNT_ID",
        )
        await save_fixture(account)

        workspace.account = account
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Ensure relationships are loaded
        await session.refresh(workspace, attribute_names=["account"])
        await session.refresh(workspace.account, attribute_names=["admin"])

        # Mock API key count so integrate_api step is complete
        mocker.patch(
            "rapidly.platform.workspace_access_token.queries.WorkspaceAccessTokenRepository.count_by_workspace_id",
            return_value=1,
        )

        payment_status = await workspace_service.get_payment_status(session, workspace)

        # Should be payment ready with all steps complete
        assert payment_status.payment_ready is True
        assert all(step.completed for step in payment_status.steps)

    async def test_sandbox_environment_allows_payments(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
        mocker: MockerFixture,
    ) -> None:
        # In sandbox, payment_ready is True when account_id is set,
        # even if account setup is not fully complete
        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=False,
            is_charges_enabled=False,
            is_payouts_enabled=False,
            stripe_id="STRIPE_SANDBOX_ID",
        )
        await save_fixture(account)

        workspace.created_at = datetime(2025, 8, 4, 12, 0, tzinfo=UTC)
        workspace.status = WorkspaceStatus.CREATED
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Ensure relationships are loaded
        await session.refresh(workspace, attribute_names=["account"])
        await session.refresh(workspace.account, attribute_names=["admin"])

        # Mock environment to be sandbox
        mocker.patch(
            "rapidly.platform.workspace.actions.settings.ENV", Environment.sandbox
        )

        payment_status = await workspace_service.get_payment_status(session, workspace)

        # Should be payment ready in sandbox if account_id is set
        assert payment_status.payment_ready is True


# ── set_account ──


@pytest.mark.asyncio
class TestSetAccount:
    @pytest.mark.auth
    async def test_first_account_setup_by_any_member(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
        auth_subject: AuthPrincipal[User],
    ) -> None:
        """Test that any member can set up the first account."""
        # Ensure workspace has no account initially
        workspace.account_id = None
        await save_fixture(workspace)

        # Create an account
        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="STRIPE_ACCOUNT_ID",
        )
        await save_fixture(account)

        # First account setup should succeed
        updated_workspace = await workspace_service.set_account(
            session, auth_subject, workspace, account.id
        )

        assert updated_workspace.account_id == account.id

    @pytest.mark.auth
    async def test_account_switch_disconnects_old(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        auth_subject: AuthPrincipal[User],
        save_fixture: SaveFixture,
        workspace: Workspace,
        user: User,
    ) -> None:
        initial_account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="INITIAL_ACCOUNT_ID",
        )
        await save_fixture(initial_account)

        workspace.account_id = initial_account.id
        await save_fixture(workspace)

        # Create a new account
        new_account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="NEW_ACCOUNT_ID",
        )
        await save_fixture(new_account)

        # Mock disconnect_stripe to avoid Stripe API calls
        mocker.patch(
            "rapidly.billing.account.actions.disconnect_stripe",
            return_value=initial_account,
        )

        updated = await workspace_service.set_account(
            session, auth_subject, workspace, new_account.id
        )

        assert updated.account_id == new_account.id


# ── submit_appeal ──


@pytest.mark.asyncio
class TestSubmitAppeal:
    async def test_submit_appeal_success(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.FAIL,
            risk_score=85.0,
            violated_sections=["human_resources"],
            reason="Policy violation detected",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
        )
        await save_fixture(review)

        appeal_reason = "We selling templates and not consultancy services"
        result = await workspace_service.submit_appeal(
            session, workspace, appeal_reason
        )

        assert result.appeal_submitted_at is not None
        assert result.appeal_reason == appeal_reason

    async def test_submit_appeal_no_review_exists(
        self, session: AsyncSession, workspace: Workspace
    ) -> None:
        with pytest.raises(ValueError, match="Workspace must have a review"):
            await workspace_service.submit_appeal(session, workspace, "Appeal reason")

    async def test_submit_appeal_passed_review(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.PASS,
            risk_score=25.0,
            violated_sections=[],
            reason="No issues found",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
        )
        await save_fixture(review)

        with pytest.raises(
            ValueError, match="Cannot submit appeal for a passed review"
        ):
            await workspace_service.submit_appeal(session, workspace, "Appeal reason")

    async def test_submit_appeal_already_submitted(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.FAIL,
            risk_score=85.0,
            violated_sections=["terms_of_service"],
            reason="Policy violation detected",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
            appeal_submitted_at=datetime.now(UTC),
            appeal_reason="Previous appeal",
        )
        await save_fixture(review)

        with pytest.raises(
            ValueError, match="Appeal has already been submitted for this workspace"
        ):
            await workspace_service.submit_appeal(
                session, workspace, "New appeal reason"
            )

    async def test_submit_appeal_uncertain_verdict(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.UNCERTAIN,
            risk_score=50.0,
            violated_sections=[],
            reason="Manual review required",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
        )
        await save_fixture(review)

        result = await workspace_service.submit_appeal(
            session, workspace, "Please review again"
        )

        assert result.appeal_submitted_at is not None
        assert result.appeal_reason == "Please review again"


# ── approve_appeal ──


@pytest.mark.asyncio
class TestApproveAppeal:
    async def test_approve_appeal_success(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        workspace.status = WorkspaceStatus.INITIAL_REVIEW
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.FAIL,
            risk_score=85.0,
            violated_sections=["terms_of_service"],
            reason="Policy violation detected",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
            appeal_submitted_at=datetime.now(UTC),
            appeal_reason="We have fixed the issues",
        )
        await save_fixture(review)

        result = await workspace_service.approve_appeal(session, workspace)

        assert workspace.status == WorkspaceStatus.ACTIVE
        assert result.appeal_decision == WorkspaceReview.AppealDecision.APPROVED
        assert result.appeal_reviewed_at is not None

    async def test_approve_appeal_no_review_exists(
        self, session: AsyncSession, workspace: Workspace
    ) -> None:
        with pytest.raises(ValueError, match="Workspace must have a review"):
            await workspace_service.approve_appeal(session, workspace)

    async def test_approve_appeal_no_appeal_submitted(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.FAIL,
            risk_score=85.0,
            violated_sections=["terms_of_service"],
            reason="Policy violation detected",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
        )
        await save_fixture(review)

        with pytest.raises(
            ValueError, match="No appeal has been submitted for this workspace"
        ):
            await workspace_service.approve_appeal(session, workspace)

    async def test_approve_appeal_already_reviewed(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.FAIL,
            risk_score=85.0,
            violated_sections=["terms_of_service"],
            reason="Policy violation detected",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
            appeal_submitted_at=datetime.now(UTC),
            appeal_reason="We have fixed the issues",
            appeal_decision=WorkspaceReview.AppealDecision.REJECTED,
            appeal_reviewed_at=datetime.now(UTC),
        )
        await save_fixture(review)

        with pytest.raises(ValueError, match="Appeal has already been reviewed"):
            await workspace_service.approve_appeal(session, workspace)


# ── deny_appeal ──


@pytest.mark.asyncio
class TestDenyAppeal:
    async def test_deny_appeal_success(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.FAIL,
            risk_score=85.0,
            violated_sections=["terms_of_service"],
            reason="Policy violation detected",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
            appeal_submitted_at=datetime.now(UTC),
            appeal_reason="We have fixed the issues",
        )
        await save_fixture(review)

        result = await workspace_service.deny_appeal(session, workspace)

        assert result.appeal_decision == WorkspaceReview.AppealDecision.REJECTED
        assert result.appeal_reviewed_at is not None

    async def test_deny_appeal_no_review_exists(
        self, session: AsyncSession, workspace: Workspace
    ) -> None:
        with pytest.raises(ValueError, match="Workspace must have a review"):
            await workspace_service.deny_appeal(session, workspace)

    async def test_deny_appeal_no_appeal_submitted(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.FAIL,
            risk_score=85.0,
            violated_sections=["terms_of_service"],
            reason="Policy violation detected",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
        )
        await save_fixture(review)

        with pytest.raises(
            ValueError, match="No appeal has been submitted for this workspace"
        ):
            await workspace_service.deny_appeal(session, workspace)

    async def test_deny_appeal_already_reviewed(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        review = WorkspaceReview(
            workspace_id=workspace.id,
            verdict=WorkspaceReview.Verdict.FAIL,
            risk_score=85.0,
            violated_sections=["terms_of_service"],
            reason="Policy violation detected",
            model_used="test-model",
            workspace_details_snapshot={"name": workspace.name},
            appeal_submitted_at=datetime.now(UTC),
            appeal_reason="We have fixed the issues",
            appeal_decision=WorkspaceReview.AppealDecision.APPROVED,
            appeal_reviewed_at=datetime.now(UTC),
        )
        await save_fixture(review)

        with pytest.raises(ValueError, match="Appeal has already been reviewed"):
            await workspace_service.deny_appeal(session, workspace)


# ── request_deletion ──


@pytest.mark.asyncio
class TestRequestDeletion:
    @pytest.mark.auth
    async def test_immediate_deletion_no_activity(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        auth_subject: AuthPrincipal[User],
        workspace: Workspace,
    ) -> None:
        """Workspace with no activity is immediately deleted."""
        enqueue_job_mock = mocker.patch(
            "rapidly.platform.workspace.actions.dispatch_task"
        )

        result = await workspace_service.request_deletion(
            session, auth_subject, workspace
        )

        assert result.can_delete_immediately is True
        assert workspace.deleted_at is not None
        # No job should be enqueued for immediate deletion
        enqueue_job_mock.assert_not_called()

    @pytest.mark.auth
    async def test_with_account_deletes_stripe_account(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        save_fixture: SaveFixture,
        auth_subject: AuthPrincipal[User],
        workspace: Workspace,
        user: User,
    ) -> None:
        """Workspace with account deletes Stripe account first."""
        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="STRIPE_ACCOUNT_ID",
        )
        await save_fixture(account)

        workspace.account = account
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Mock Stripe account deletion
        mock_delete_stripe = mocker.patch(
            "rapidly.platform.workspace.actions.account_service.delete_stripe_account"
        )
        mock_delete_account = mocker.patch(
            "rapidly.platform.workspace.actions.account_service.delete"
        )

        result = await workspace_service.request_deletion(
            session, auth_subject, workspace
        )

        assert result.can_delete_immediately is True
        assert workspace.deleted_at is not None
        mock_delete_stripe.assert_called_once()
        mock_delete_account.assert_called_once()

    @pytest.mark.auth
    async def test_stripe_deletion_failure_creates_ticket(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        save_fixture: SaveFixture,
        auth_subject: AuthPrincipal[User],
        workspace: Workspace,
        user: User,
    ) -> None:
        """Stripe account deletion failure creates support ticket."""
        account = Account(
            account_type=AccountType.stripe,
            admin_id=user.id,
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="STRIPE_ACCOUNT_ID",
        )
        await save_fixture(account)

        workspace.account = account
        workspace.account_id = account.id
        await save_fixture(workspace)

        # Mock Stripe account deletion to fail
        mocker.patch(
            "rapidly.platform.workspace.actions.account_service.delete_stripe_account",
            side_effect=Exception("Stripe deletion failed"),
        )
        enqueue_job_mock = mocker.patch(
            "rapidly.platform.workspace.actions.dispatch_task"
        )

        result = await workspace_service.request_deletion(
            session, auth_subject, workspace
        )

        assert result.can_delete_immediately is False
        assert "stripe_account_deletion_failed" in [
            r.value for r in result.blocked_reasons
        ]
        assert workspace.deleted_at is None
        enqueue_job_mock.assert_called_once()

    @pytest.mark.auth
    async def test_non_admin_with_account_raises_not_permitted(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        auth_subject: AuthPrincipal[User],
        workspace: Workspace,
    ) -> None:
        """Non-admin cannot delete workspace with an account."""
        from rapidly.errors import NotPermitted

        # Create a different user who is the admin
        other_user = User(email="admin@example.com")
        await save_fixture(other_user)

        account = Account(
            account_type=AccountType.stripe,
            admin_id=other_user.id,  # Different admin than auth_subject
            country="US",
            currency="USD",
            is_details_submitted=True,
            is_charges_enabled=True,
            is_payouts_enabled=True,
            stripe_id="STRIPE_ACCOUNT_ID",
        )
        await save_fixture(account)

        workspace.account = account
        workspace.account_id = account.id
        await save_fixture(workspace)

        with pytest.raises(NotPermitted) as exc_info:
            await workspace_service.request_deletion(session, auth_subject, workspace)

        assert "account admin" in str(exc_info.value).lower()

    @pytest.mark.auth
    async def test_any_member_can_delete_without_account(
        self,
        mocker: MockerFixture,
        session: AsyncSession,
        auth_subject: AuthPrincipal[User],
        workspace: Workspace,
    ) -> None:
        """Any workspace member can delete when there's no account."""
        # Ensure no account is set
        assert workspace.account_id is None

        mocker.patch("rapidly.platform.workspace.actions.dispatch_task")

        result = await workspace_service.request_deletion(
            session, auth_subject, workspace
        )

        assert result.can_delete_immediately is True


# ── soft_delete_workspace ──


@pytest.mark.asyncio
class TestSoftDeleteWorkspace:
    async def test_anonymizes_pii_preserves_slug(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Soft delete anonymizes PII but preserves slug."""
        original_slug = workspace.slug
        workspace.name = "Test Workspace"
        workspace.email = "test@example.com"
        workspace.website = "https://test.com"
        workspace.bio = "Test bio"
        workspace.avatar_url = "https://example.com/avatar.png"
        await save_fixture(workspace)

        result = await workspace_service.soft_delete_workspace(session, workspace)

        # Slug should be preserved
        assert result.slug == original_slug

        # PII should be anonymized
        assert result.name != "Test Workspace"
        assert result.email != "test@example.com"
        assert result.website != "https://test.com"
        assert result.bio != "Test bio"

        # Avatar should be set to Rapidly logo
        assert result.avatar_url is not None
        assert "avatars.githubusercontent.com" in result.avatar_url

        # Should be soft deleted
        assert result.deleted_at is not None

    async def test_clears_details_and_socials(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        """Soft delete clears details and socials."""
        workspace.details = {"about": "Test company"}  # type: ignore[assignment]
        workspace.socials = [{"platform": "twitter", "url": "https://twitter.com/test"}]
        await save_fixture(workspace)

        result = await workspace_service.soft_delete_workspace(session, workspace)

        assert result.details == {}  # type: ignore[comparison-overlap]
        assert result.socials == []


# ── update (seat-based pricing) ──


@pytest.mark.asyncio
class TestUpdateFeatureSettings:
    async def test_enable_member_model(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        workspace.feature_settings = {
            "member_model_enabled": False,
        }
        await save_fixture(workspace)

        result = await workspace_service.update(
            session,
            workspace,
            WorkspaceUpdate(
                feature_settings=WorkspaceFeatureSettings(
                    member_model_enabled=True,
                ),
            ),
        )

        assert result.feature_settings["member_model_enabled"] is True

    async def test_keep_member_model_enabled(
        self,
        session: AsyncSession,
        save_fixture: SaveFixture,
        workspace: Workspace,
    ) -> None:
        workspace.feature_settings = {
            "member_model_enabled": True,
        }
        await save_fixture(workspace)

        result = await workspace_service.update(
            session,
            workspace,
            WorkspaceUpdate(
                feature_settings=WorkspaceFeatureSettings(
                    member_model_enabled=True,
                ),
            ),
        )

        assert result.feature_settings["member_model_enabled"] is True
