"""Registry of all background job modules for the Dramatiq worker."""

from rapidly.agents.execution import workers as agents_execution
from rapidly.agents.rag import workers as agents_rag
from rapidly.analytics.event import workers as event
from rapidly.analytics.eventstream import workers as eventstream
from rapidly.analytics.external_event import workers as external_event
from rapidly.customers.customer import workers as customer
from rapidly.customers.customer_session import workers as customer_session
from rapidly.identity.auth import workers as auth
from rapidly.integrations.stripe import workers as stripe
from rapidly.messaging.email import workers as email
from rapidly.messaging.email_update import workers as email_update
from rapidly.messaging.notifications import workers as notifications
from rapidly.messaging.webhook import workers as webhook
from rapidly.platform.user import workers as user
from rapidly.platform.workspace import workers as workspace
from rapidly.platform.workspace_access_token import workers as workspace_access_token
from rapidly.sharing.file_sharing import workers as file_sharing
from rapidly.viewer.federated_model import workers as viewer_federated_model

__all__ = [
    "agents_execution",
    "agents_rag",
    "auth",
    "customer",
    "customer_session",
    "email",
    "email_update",
    "event",
    "eventstream",
    "external_event",
    "file_sharing",
    "notifications",
    "stripe",
    "user",
    "viewer_federated_model",
    "webhook",
    "workspace",
    "workspace_access_token",
]
