import asyncio
import random
from typing import NotRequired, TypedDict

import dramatiq
import typer

import rapidly.workers  # noqa: F401
from rapidly.core.db.postgres import create_async_sessionmaker
from rapidly.core.utils import now_utc
from rapidly.customers.customer import actions as customer_service
from rapidly.customers.customer.types.customer import CustomerCreate
from rapidly.enums import AccountType
from rapidly.identity.auth.models import AuthPrincipal
from rapidly.models.account import Account
from rapidly.models.user import IdentityVerificationStatus
from rapidly.models.workspace import WorkspaceDetails, WorkspaceStatus
from rapidly.models.workspace_review import WorkspaceReview
from rapidly.platform.user import actions as user_service
from rapidly.platform.user.queries import UserRepository
from rapidly.platform.workspace import actions as workspace_service
from rapidly.platform.workspace.types import WorkspaceCreate
from rapidly.postgres import AsyncSession, create_async_engine
from rapidly.redis import Redis, create_redis
from rapidly.worker import JobQueueManager

cli = typer.Typer()


class WorkspaceDict(TypedDict):
    name: str
    slug: str
    email: str
    website: str
    bio: str
    status: NotRequired[WorkspaceStatus]
    details: NotRequired[WorkspaceDetails]
    is_admin: NotRequired[bool]
    feature_settings: NotRequired[dict[str, bool]]


async def create_seed_data(session: AsyncSession, redis: Redis) -> None:
    """Create sample data for development and testing."""

    # Workspaces data
    orgs_data: list[WorkspaceDict] = [
        {
            "name": "Acme Corporation",
            "slug": "acme-corp",
            "email": "contact@acme-corp.com",
            "website": "https://acme-corp.com",
            "bio": "Leading provider of innovative solutions for modern businesses.",
            "status": WorkspaceStatus.ACTIVE,
            "details": {
                "about": "We provide business intelligence dashboard",
                "intended_use": "We use Rapidly for encrypted file sharing.",
                "switching": False,
                "switching_from": None,
                "product_description": "Our business intelligence dashboards and data reports are shared securely via Rapidly.",
                "customer_acquisition": ["website"],
                "future_annual_revenue": 2000000,
                "previous_annual_revenue": 0,
            },
        },
        {
            "name": "Widget Industries",
            "slug": "widget-industries",
            "email": "info@widget-industries.com",
            "website": "https://widget-industries.com",
            "bio": "Manufacturing high-quality widgets since 1985.",
        },
        {
            "name": "MeltedSQL",
            "slug": "melted-sql",
            "email": "support@meltedsql.com",
            "website": "https://meltedsql.com",
            "bio": "Your go-to solution for SQL database management and optimization.",
            "status": WorkspaceStatus.ACTIVE,
            "details": {
                "about": "We make beautiful SQL management products for macOS.",
                "intended_use": "We share database exports and reports via encrypted file sharing.",
                "switching": False,
                "switching_from": None,
                "product_description": "Desktop apps for connecting to SQL databases and performing queries.",
                "customer_acquisition": ["website"],
                "future_annual_revenue": 2000000,
                "previous_annual_revenue": 0,
            },
        },
        {
            "name": "ColdMail Inc.",
            "slug": "coldmail",
            "email": "hello@coldmail.com",
            "website": "https://coldmail.com",
            "bio": "Online mail services like it's 1999!",
            "status": WorkspaceStatus.ACTIVE,
            "details": {
                "about": "We're a hottest cloud provider since sliced bread",
                "intended_use": "We use Rapidly for secure document sharing with clients.",
                "switching": False,
                "switching_from": None,
                "product_description": "We sell ColdMail which provides an email inbox plus file storage.",
                "customer_acquisition": ["website"],
                "future_annual_revenue": 2000000,
                "previous_annual_revenue": 0,
            },
        },
        {
            "name": "Example News Inc.",
            "slug": "example-news-inc",
            "email": "hello@examplenewsinc.com",
            "website": "https://examplenewsinc.com",
            "bio": "Your source of news",
            "status": WorkspaceStatus.ACTIVE,
            "details": {
                "about": "We provide news in various formats",
                "intended_use": "We share press releases and media kits via encrypted file sharing.",
                "switching": False,
                "switching_from": None,
                "product_description": "We send out our news products as emails daily and weekly",
                "customer_acquisition": ["website"],
                "future_annual_revenue": 2000000,
                "previous_annual_revenue": 0,
            },
        },
        {
            "name": "Admin Org",
            "slug": "admin-org",
            "email": "admin@rapidly.tech",
            "website": "https://rapidly.tech",
            "bio": "The admin workspace of Rapidly",
            "status": WorkspaceStatus.ACTIVE,
            "is_admin": True,
            "details": {
                "about": "Rapidly is an encrypted file sharing platform",
                "intended_use": "We provide P2P encrypted file sharing with optional paid sharing.",
                "switching": False,
                "switching_from": None,
                "product_description": "SaaS platform for secure file sharing",
                "customer_acquisition": ["website"],
                "future_annual_revenue": 1000000,
                "previous_annual_revenue": 0,
            },
        },
    ]

    # Create workspaces with users and sample data
    for org_data in orgs_data:
        # Get or create user (allows multiple orgs to share the same user)
        user, _created = await user_service.get_by_email_or_create(
            session=session,
            email=org_data["email"],
        )
        user_repository = UserRepository.from_session(session)
        await user_repository.update(
            user,
            update_dict={
                # Start with the user being admin, so that we can create daily and weekly products
                "is_admin": True,
                "identity_verification_status": IdentityVerificationStatus.verified,
                "identity_verification_id": f"vs_{org_data['slug']}_test",
            },
        )

        auth_subject = AuthPrincipal(subject=user, scopes=set(), session=None)

        # Create workspace
        workspace = await workspace_service.create(
            session=session,
            create_schema=WorkspaceCreate(
                name=org_data["name"],
                slug=org_data["slug"],
            ),
            auth_subject=auth_subject,
        )

        # Update workspace with additional details
        workspace.email = org_data["email"]
        workspace.website = org_data["website"]
        workspace.bio = org_data["bio"]
        workspace.details = org_data.get("details", {})  # type: ignore
        workspace.details_submitted_at = now_utc()
        workspace.status = org_data.get("status", WorkspaceStatus.CREATED)
        workspace.feature_settings = org_data.get("feature_settings", {})
        session.add(workspace)

        # Create WorkspaceReview with PASS verdict for ACTIVE workspaces
        if workspace.status == WorkspaceStatus.ACTIVE:
            workspace.initially_reviewed_at = now_utc()
            workspace_review = WorkspaceReview(
                workspace_id=workspace.id,
                verdict=WorkspaceReview.Verdict.PASS,
                risk_score=0.0,
                violated_sections=[],
                reason="Seed data - automatically approved",
                timed_out=False,
                model_used="seed",
                validated_at=now_utc(),
                workspace_details_snapshot=org_data.get("details", {}),
            )
            session.add(workspace_review)

        # Create an Account for all workspaces except Widget Industries
        if org_data["slug"] != "widget-industries":
            account = Account(
                account_type=AccountType.stripe,
                admin_id=user.id,
                stripe_id=f"acct_{workspace.slug}_test",  # Test Stripe account ID
                country="US",
                currency="USD",
                is_details_submitted=True,
                is_charges_enabled=True,
                is_payouts_enabled=True,
                status=Account.Status.ACTIVE,
                email=org_data["email"],
                processor_fees_applicable=True,
            )
            session.add(account)
            await session.flush()

            # Link the account to the workspace
            workspace.account_id = account.id
            session.add(workspace)

        # Create customers for workspace
        num_customers = random.randint(0, 5)
        for i in range(num_customers):
            customer_email = f"customer_{org_data['slug']}_{i + 1}@rapidly.tech"
            await customer_service.create(
                session=session,
                customer_create=CustomerCreate(
                    email=customer_email,
                    name=f"Customer {i + 1}",
                    workspace_id=workspace.id,
                ),
                auth_subject=auth_subject,
            )

        # Downgrade user from admin (for non-admin users)
        # Preserve admin status if already granted by a previous workspace
        await user_repository.update(
            user,
            update_dict={"is_admin": user.is_admin or org_data.get("is_admin", False)},
        )

    await session.commit()
    print("Sample data created successfully!")
    print("Created workspaces with users and customers")


@cli.command()
def seeds_load() -> None:
    """Load sample/test data into the database."""

    async def run() -> None:
        redis = create_redis("app")
        async with JobQueueManager.open(dramatiq.get_broker(), redis):
            engine = create_async_engine("script")
            sessionmaker = create_async_sessionmaker(engine)
            async with sessionmaker() as session:
                await create_seed_data(session, redis)

    asyncio.run(run())


if __name__ == "__main__":
    cli()
