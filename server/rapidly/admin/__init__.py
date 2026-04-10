"""Admin panel sub-application: HTMX + DaisyUI admin interface.

Mounts all admin panel routes, static assets, and middleware into a
separate FastAPI application served under ``/admin panel``.
"""

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from tagflow import tag, text

from rapidly.observability.http_metrics import exclude_app_from_metrics

from .accounts.api import router as accounts_router
from .customers.api import router as customers_router
from .dependencies import get_admin
from .external_events.api import router as external_events_router
from .file_sharing.api import router as file_sharing_router
from .impersonation.api import router as impersonation_router
from .layout import layout
from .middlewares import CSRFMiddleware, SecurityHeadersMiddleware, TagflowMiddleware
from .responses import TagResponse
from .shares.api import router as shares_router
from .users.api import router as users_router
from .versioned_static import VersionedStaticFiles
from .webhooks.api import router as webhooks_router
from .workers.api import router as tasks_router
from .workspaces.api import router as workspaces_router
from .workspaces_v2.api import router as workspaces_v2_router

app = FastAPI(
    default_response_class=TagResponse,
    dependencies=[Depends(get_admin)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Exclude admin panel from HTTP metrics (not sent to Grafana Cloud)
exclude_app_from_metrics(app)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(TagflowMiddleware)


app.mount(
    "/static",
    VersionedStaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)
app.include_router(users_router, prefix="/users")
app.include_router(workspaces_router, prefix="/workspaces")
app.include_router(workspaces_v2_router)  # New redesigned interface
app.include_router(customers_router, prefix="/customers")
app.include_router(shares_router, prefix="/products")
app.include_router(accounts_router, prefix="/accounts")
app.include_router(external_events_router, prefix="/external-events")
app.include_router(file_sharing_router, prefix="/file-sharing")
app.include_router(tasks_router, prefix="/tasks")
app.include_router(impersonation_router, prefix="/impersonation")
app.include_router(webhooks_router, prefix="/webhooks")


@app.get("/", name="index")
async def index(request: Request) -> None:
    with layout(request, [], "index"):
        with tag.h1():
            text("Dashboard")


__all__ = ["app"]
