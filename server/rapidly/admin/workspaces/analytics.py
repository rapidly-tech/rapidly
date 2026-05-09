"""Analytics service for workspace account review functionality."""

from pydantic import UUID4
from sqlalchemy import func, select

from rapidly.billing.payment.queries import PaymentRepository
from rapidly.models import (
    Payment,
    Share,
    User,
    WebhookEndpoint,
    Workspace,
    WorkspaceAccessToken,
    WorkspaceMembership,
)
from rapidly.models.payment import PaymentStatus
from rapidly.models.user import IdentityVerificationStatus
from rapidly.postgres import AsyncReadSession, AsyncSession

# ── Query Builders ──


class PaymentAnalyticsService:
    """Service for computing payment statistics and analytics."""

    def __init__(self, session: AsyncSession | AsyncReadSession):
        self.session = session
        self.payment_repo = PaymentRepository.from_session(session)

    async def get_workspace_account_id(self, workspace_id: UUID4) -> UUID4 | None:
        """Get account ID for workspace."""
        result = await self.session.execute(
            select(Workspace.account_id).where(Workspace.id == workspace_id)
        )
        row = result.first()
        return row[0] if row else None

    async def get_succeeded_payments_stats(
        self, workspace_id: UUID4
    ) -> tuple[int, int, list[float]]:
        """Get succeeded payments count, total amount, and risk scores."""
        statement = self.payment_repo.get_base_statement().where(
            Payment.workspace_id == workspace_id,
            Payment.status == PaymentStatus.succeeded,
        )

        # Get risk scores
        risk_scores_result = await self.session.execute(
            statement.where(Payment.risk_score.isnot(None)).with_only_columns(
                Payment.risk_score
            )
        )
        risk_scores = [row[0] for row in risk_scores_result if row[0] is not None]

        # Get count and total amount
        stats_result = await self.session.execute(
            statement.with_only_columns(
                func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0)
            )
        )
        count, total_amount = stats_result.first() or (0, 0)

        return count, total_amount, risk_scores

    @staticmethod
    def calculate_risk_percentiles(risk_scores: list[float]) -> tuple[float, float]:
        """Calculate P50 and P90 risk percentiles."""
        if not risk_scores:
            return 0.0, 0.0

        # Create a copy to avoid mutating the original list
        sorted_scores: list[float] = sorted(risk_scores)
        n = len(sorted_scores)

        # Calculate P50 (median)
        if n % 2 == 0:
            p50_risk = (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
        else:
            p50_risk = sorted_scores[n // 2]

        # Calculate P90
        p90_index = int(0.9 * n)
        if p90_index >= n:
            p90_index = n - 1
        p90_risk = sorted_scores[p90_index]

        return p50_risk, p90_risk

    @staticmethod
    def determine_risk_level(p90_risk: float) -> str:
        """Determine risk level based on P90 risk score."""
        if p90_risk < 65:
            return "green"
        elif p90_risk < 75:
            return "yellow"
        else:
            return "red"


# ── Aggregation ──


class WorkspaceSetupAnalyticsService:
    """Service for computing workspace setup statistics and analytics."""

    def __init__(self, session: AsyncSession | AsyncReadSession):
        self.session = session

    async def get_webhooks_count(self, workspace_id: UUID4) -> int:
        """Get count of webhook endpoints for workspace."""
        result = await self.session.execute(
            select(func.count(WebhookEndpoint.id)).where(
                WebhookEndpoint.workspace_id == workspace_id,
                WebhookEndpoint.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    async def get_workspace_tokens_count(self, workspace_id: UUID4) -> int:
        """Get count of workspace access tokens."""
        result = await self.session.execute(
            select(func.count(WorkspaceAccessToken.id)).where(
                WorkspaceAccessToken.workspace_id == workspace_id,
                WorkspaceAccessToken.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    async def get_products_count(self, workspace_id: UUID4) -> int:
        """Get count of products for workspace."""
        result = await self.session.execute(
            select(func.count(Share.id)).where(
                Share.workspace_id == workspace_id,
                Share.deleted_at.is_(None),
            )
        )
        return result.scalar() or 0

    async def is_owner_identity_verified(self, workspace_id: UUID4) -> bool:
        """Check if the workspace owner has a verified identity."""
        result = await self.session.execute(
            select(User.identity_verification_status)
            .join(WorkspaceMembership, User.id == WorkspaceMembership.user_id)
            .where(WorkspaceMembership.workspace_id == workspace_id)
            .limit(1)
        )
        row = result.first()
        if row is None:
            return False
        return row[0] == IdentityVerificationStatus.verified

    async def check_user_verified_in_stripe(self, workspace: Workspace) -> bool:
        """Check if workspace owner is verified in Stripe."""
        if not workspace.account or not workspace.account.stripe_id:
            return False

        return (
            hasattr(workspace.account, "charges_enabled")
            and workspace.account.charges_enabled
        )

    async def check_account_enabled(self, workspace: Workspace) -> tuple[bool, bool]:
        """Check if account charges and payouts are enabled."""
        if not workspace.account:
            return False, False

        charges_enabled = getattr(workspace.account, "charges_enabled", False)
        payouts_enabled = getattr(workspace.account, "payouts_enabled", False)

        return charges_enabled, payouts_enabled

    @staticmethod
    def calculate_setup_score(
        webhooks_count: int,
        org_tokens_count: int,
        products_count: int,
        user_verified: bool,
        account_charges_enabled: bool,
        account_payouts_enabled: bool,
    ) -> int:
        """Calculate setup score based on various metrics."""
        return sum(
            [
                1 if webhooks_count > 0 else 0,
                1 if org_tokens_count > 0 else 0,
                1 if products_count > 0 else 0,
                1 if user_verified else 0,
                1 if account_charges_enabled else 0,
                1 if account_payouts_enabled else 0,
            ]
        )
