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
import rapidly.sharing.markup.signaling_validators  # noqa: F401
from rapidly.agents.dataset.api import router as datasets_router
from rapidly.agents.eval_run.api import router as eval_runs_router
from rapidly.agents.integration_credential.api import (
    router as integration_credentials_router,
)
from rapidly.agents.llm_usage.api import router as llm_usage_router

# ── Agents (workflow runtime) ──
from rapidly.agents.node_run.api import router as node_runs_router
from rapidly.agents.run.api import router as runs_router
from rapidly.agents.run.api import trigger_router as runs_trigger_router
from rapidly.agents.vector_collection.api import router as vector_collections_router
from rapidly.agents.workflow.api import router as workflows_router
from rapidly.agents.workflow_version.api import router as workflow_versions_router
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

# ── Project management ──
from rapidly.projects.activity.api import router as work_item_activity_router
from rapidly.projects.comment.api import router as work_item_comment_router
from rapidly.projects.label.api import router as project_label_router
from rapidly.projects.project.api import router as project_router
from rapidly.projects.state.api import router as project_state_router
from rapidly.projects.work_item.api import router as work_item_router
from rapidly.sharing.file_sharing.api import router as file_sharing_router
from rapidly.sharing.markup.api import router as collab_router

# ── Viewer (3D models) ──
from rapidly.viewer.federated_model.api import router as federated_models_router

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
# analytics and usage metrics
router.include_router(metrics_router)

# ── File operations ──

# file upload and retrieval
router.include_router(files_router)
# shared file access links
router.include_router(file_sharing_router)
# collab sessions (gated by FILE_SHARING_COLLAB_ENABLED)
router.include_router(collab_router)

# ── Viewer (3D models) ──

# federated 3D models (IFC ingestion + XKT for the viewer)
router.include_router(federated_models_router)

# ── Agents (workflow runtime) ──

# workflow CRUD (runs / node_runs land in follow-ups)
router.include_router(workflows_router)
# workflow_versions (immutable graph_json snapshots)
router.include_router(workflow_versions_router)
# runs — list + get + cancel (trigger is 501 until M4.2 engine)
router.include_router(runs_router)
router.include_router(runs_trigger_router)
# node_runs — per-step records under a run (read-only surface)
router.include_router(node_runs_router)
# vector_collections — RAG corpus root + indexing-trigger endpoint
router.include_router(vector_collections_router)
# integration_credentials — per-workspace LLM/embedding API keys
router.include_router(integration_credentials_router)
# llm_usage — per-call token tracking + grouped rollups
router.include_router(llm_usage_router)
# datasets — eval fixtures (CRUD; runner lands in M4.8b)
router.include_router(datasets_router)
# eval_runs — drives a workflow over every case in a dataset
router.include_router(eval_runs_router)

# ── Customer lifecycle ──

# customer records
router.include_router(customer_router)
# customer auth sessions
router.include_router(customer_session_router)
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

# ── Project management ──

# projects CRUD
router.include_router(project_router)
# project workflow states
router.include_router(project_state_router)
# project labels
router.include_router(project_label_router)
# work items
router.include_router(work_item_router)
# work item comments
router.include_router(work_item_comment_router)
# work-item activity log
router.include_router(work_item_activity_router)
