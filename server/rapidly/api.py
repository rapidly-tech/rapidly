"""Top-level API router that mounts all module routers.

Assembles the ``/api`` prefix tree by including every module's router
(accounts, auth, customers, events, files, metrics, etc.) into a
single ``APIRouter`` instance consumed by the application factory.
"""

from fastapi import APIRouter

# Importing the signaling validators module registers
# ("screen", "host") and ("screen", "guest") at import time — before any
# WebSocket can dispatch to the registry. The import is a side-effect
# (registration via decorator); the name itself is unused here.
import rapidly.sharing.call.signaling_validators
import rapidly.sharing.screen.signaling_validators
import rapidly.sharing.watch.signaling_validators  # noqa: F401
from rapidly.analytics.event.api import router as event_router
from rapidly.analytics.event_type.api import router as event_type_router
from rapidly.analytics.eventstream.api import router as stream_router
from rapidly.analytics.metrics.api import router as metrics_router
from rapidly.billing.account.api import router as accounts_router
from rapidly.billing.payment.api import router as payment_router
from rapidly.billing.stripe_connect.api import router as stripe_connect_router

# ── File operations ──
from rapidly.catalog.file.api import router as files_router

# ── Share catalog ──
from rapidly.catalog.share.api import router as product_router

# ── Customer lifecycle ──
from rapidly.customers.customer.api import router as customer_router
from rapidly.customers.customer_portal.api import router as customer_portal_router
from rapidly.customers.customer_session.api import router as customer_session_router
from rapidly.identity.auth.api import router as auth_router
from rapidly.identity.login_code.api import router as login_code_router
from rapidly.identity.member.api import router as member_router
from rapidly.identity.member_session.api import router as member_session_router
from rapidly.identity.oauth2.api.oauth2 import router as oauth2_router
from rapidly.integrations.apple.api import router as apple_router
from rapidly.integrations.discord.api import router as discord_router

# ── Integrations ──
from rapidly.integrations.github.api import router as github_router
from rapidly.integrations.google.api import router as google_router
from rapidly.integrations.microsoft.api import router as microsoft_router
from rapidly.integrations.stripe.api import router as stripe_router
from rapidly.messaging.email_update.api import router as email_update_router
from rapidly.messaging.notifications.api import router as notifications_router

# ── Observability & messaging ──
from rapidly.messaging.webhook.api import router as webhook_router

# ── Identity & authentication ──
from rapidly.platform.user.api import router as user_router

# ── Workspace management ──
from rapidly.platform.workspace.api import router as workspace_router
from rapidly.platform.workspace_access_token.api import (
    router as workspace_access_token_router,
)
from rapidly.sharing.call.api import router as call_router
from rapidly.sharing.file_sharing.api import router as file_sharing_router
from rapidly.sharing.screen.api import router as screen_router
from rapidly.sharing.storefront.api import router as storefront_router
from rapidly.sharing.watch.api import router as watch_router

router = APIRouter(prefix="/api")

# ── Identity & authentication ──

# user profile and settings
router.include_router(user_router)
# authentication flows
router.include_router(auth_router)
# OAuth 2.0 authorization endpoints
router.include_router(oauth2_router)
# passwordless login codes
router.include_router(login_code_router)

# ── Workspace management ──

# workspace CRUD
router.include_router(workspace_router)
# org-scoped access tokens
router.include_router(workspace_access_token_router)
# team member management
router.include_router(member_router)
# member session tracking
router.include_router(member_session_router)
# payout accounts (Stripe Connect)
router.include_router(accounts_router)

# ── Share catalog ──

# share listings (shares)
router.include_router(product_router)
# storefront configuration
router.include_router(storefront_router)
# analytics and usage metrics
router.include_router(metrics_router)

# ── File operations ──

# file upload and retrieval
router.include_router(files_router)
# shared file access links
router.include_router(file_sharing_router)
# screen sharing sessions (gated by FILE_SHARING_SCREEN_ENABLED)
router.include_router(screen_router)
# watch-together sessions (gated by FILE_SHARING_WATCH_ENABLED)
router.include_router(watch_router)
# call sessions (gated by FILE_SHARING_CALL_ENABLED)
router.include_router(call_router)

# ── Customer lifecycle ──

# customer records
router.include_router(customer_router)
# customer auth sessions
router.include_router(customer_session_router)
# self-service customer portal
router.include_router(customer_portal_router)
# email address changes
router.include_router(email_update_router)
# payment processing
router.include_router(payment_router)
# Stripe Connect onboarding
router.include_router(stripe_connect_router)

# ── Integrations ──

# Microsoft OAuth integration
router.include_router(microsoft_router)
# GitHub secret scanning partnership
router.include_router(github_router)
# Stripe webhook and config endpoints
router.include_router(stripe_router)
# Discord bot integration
router.include_router(discord_router)
# Apple Sign-In integration
router.include_router(apple_router)
# Google Sign-In integration
router.include_router(google_router)

# ── Observability & messaging ──

# outbound webhook dispatch
router.include_router(webhook_router)
# in-app notification feed
router.include_router(notifications_router)
# server-sent event stream
router.include_router(stream_router)
# event ingestion, listing and statistics
router.include_router(event_router)
# event type management
router.include_router(event_type_router)
