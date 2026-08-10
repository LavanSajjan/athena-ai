from fastapi import FastAPI

from apps.api.lifespan import lifespan
from apps.api.routes.v1.datasets import router as datasets_router
from apps.api.routes.v1.system import router as system_router
from packages.config.settings import get_settings
from packages.domains.dataset.service import DatasetService
from packages.observability.logging import configure_logging
from packages.storage.blob.local import LocalStorageProvider


def create_application() -> FastAPI:
    settings = get_settings()

    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.state.dataset_service = DatasetService(
        storage_provider=LocalStorageProvider(settings.storage_root)
    )

    app.include_router(system_router)
    app.include_router(datasets_router)

    return app
