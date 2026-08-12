from fastapi import FastAPI

from apps.api.lifespan import lifespan
from apps.api.routes.v1.datasets import router as datasets_router
from apps.api.routes.v1.system import router as system_router
from packages.config.settings import get_settings
from packages.domains.dataset.service import DatasetService
from packages.observability.logging import configure_logging
from packages.persistence.sqlite_dataset_repository import SQLiteDatasetRepository
from packages.query.duckdb import DuckDBQueryEngine
from packages.services.dataset_profiling_service import DatasetProfilingService
from packages.services.dataset_query_service import DatasetQueryService
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

    storage_provider = LocalStorageProvider(settings.storage_root)
    dataset_repository = SQLiteDatasetRepository(settings.dataset_catalog_path)
    dataset_service = DatasetService(
        storage_provider=storage_provider,
        repository=dataset_repository,
        provider_id="local",
    )
    app.state.dataset_repository = dataset_repository
    app.state.dataset_service = dataset_service
    app.state.dataset_profiling_service = DatasetProfilingService(
        dataset_service=dataset_service,
        storage_provider=storage_provider,
    )
    app.state.dataset_query_service = DatasetQueryService(
        dataset_service=dataset_service,
        storage_provider=storage_provider,
        query_engine=DuckDBQueryEngine(
            memory_limit=settings.dataset_query_memory_limit,
            timeout_seconds=settings.dataset_query_timeout_seconds,
        ),
        max_rows=settings.dataset_query_max_rows,
    )

    app.include_router(system_router)
    app.include_router(datasets_router)

    return app
