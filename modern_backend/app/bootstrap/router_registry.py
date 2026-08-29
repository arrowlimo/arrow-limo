from fastapi import Depends, FastAPI

from ..auth import require_roles
from ..routers import chauffeur_self_service as chauffeur_self_service_router
from ..routers import driver_auth as driver_auth_router


def register_routers(app: FastAPI) -> None:
    """Register only the authentication and driver self-service API."""
    driver_access = Depends(require_roles("driver", "operator"))
    app.include_router(driver_auth_router.router)
    app.include_router(
        chauffeur_self_service_router.router,
        dependencies=[driver_access],
    )  # Record received payments
