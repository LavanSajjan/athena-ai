from fastapi import FastAPI

from apps.api.lifespan import lifespan
from apps.api.routes.v1.system import router as system_router

from packages.config.settings import get_settings
from packages.observability.logging import configure_logging


def create_application() -> FastAPI:
    settings = get_settings()

    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.include_router(system_router)

    return app