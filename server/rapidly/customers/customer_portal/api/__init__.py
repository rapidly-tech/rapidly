"""Customer portal route aggregation: mounts all customer-facing sub-routers."""

from rapidly.routing import APIRouter

from .customer import router as customer_router
from .customer_session import router as customer_session_router
from .file_sharing import router as file_sharing_router
from .member import router as member_router
from .oauth_accounts import router as oauth_accounts_router
from .payment_methods import router as payment_methods_router
from .workspace import router as workspace_router

router = APIRouter(prefix="/customer-portal", tags=["customer_portal"])

router.include_router(customer_router)
router.include_router(customer_session_router)
router.include_router(file_sharing_router)
router.include_router(member_router)
router.include_router(oauth_accounts_router)
router.include_router(payment_methods_router)
router.include_router(workspace_router)
